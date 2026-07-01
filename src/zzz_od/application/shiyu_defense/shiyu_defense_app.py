import re
from typing import ClassVar

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_notify import NotifyTiming, node_notify
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.log_utils import log
from zzz_od.application.shiyu_defense import (
    shiyu_defense_const,
    shiyu_defense_team_utils,
)
from zzz_od.application.shiyu_defense.shiyu_defense_battle import ShiyuDefenseBattle
from zzz_od.application.shiyu_defense.shiyu_defense_config import (
    ShiyuDefenseConfig,
)
from zzz_od.application.shiyu_defense.shiyu_defense_run_record import (
    ShiyuDefenseRunRecord,
)
from zzz_od.application.shiyu_defense.shiyu_defense_team_utils import (
    DefensePhaseTeamInfo,
)
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.choose_predefined_team import ChoosePredefinedTeam
from zzz_od.operation.compendium.tp_by_compendium import TransportByCompendium
from zzz_od.operation.deploy import Deploy

# 多间模式房间名称
ROOM_NAMES = ['第一间', '第二间', '第三间']
MULTI_ROOM_NODES = [5]


class ShiyuDefenseApp(ZApplication):

    STATUS_ALL_FINISHED: ClassVar[str] = '所有节点都完成挑战'
    STATUS_NEXT_NODE: ClassVar[str] = '下一节点'
    STATUS_ROOM_COMPLETE: ClassVar[str] = '房间挑战完成'
    STATUS_ALL_ROOMS_COMPLETE: ClassVar[str] = '所有房间完成'

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx, app_id=shiyu_defense_const.APP_ID,
            op_name=shiyu_defense_const.APP_NAME,
        )

        self.config: ShiyuDefenseConfig = self.ctx.run_context.get_config(
            app_id=shiyu_defense_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )
        self.run_record: ShiyuDefenseRunRecord = self.ctx.run_context.get_run_record(
            instance_idx=self.ctx.current_instance_idx,
            app_id=shiyu_defense_const.APP_ID,
        )

        self.current_node_idx: int = 0  # 当前挑战的节点下标 跟着游戏的1开始
        self.phase_team_list: list[DefensePhaseTeamInfo] = []  # 每个阶段使用的配队
        self.phase_idx: int = 0  # 当前阶段

        # 多间模式相关
        self.current_room_idx: int = 0
        self.room_teams: list[DefensePhaseTeamInfo] = []

    @operation_node(name='传送', is_start_node=True)
    def tp(self) -> OperationRoundResult:
        op = TransportByCompendium(self.ctx, '作战', '式舆防卫战', '剧变节点')
        return self.round_by_op_result(op.execute())

    @node_from(from_name='传送')
    @operation_node(name='等待画面加载', node_max_retry_times=60)
    def wait_loading(self) -> OperationRoundResult:
        result = self.round_by_find_area(self.last_screenshot, '式舆防卫战', '前次行动最佳记录')
        if result.is_success:
            self.round_by_click_area('式舆防卫战', '前次-关闭')
            return self.round_wait(result.status, wait=2)

        # 判断是否已进入到主界面(“前哨档案”文本出现)
        return self.round_by_find_area(self.last_screenshot, '式舆防卫战', '前哨档案', retry_wait=1)

    @node_from(from_name='等待画面加载')
    @operation_node(name='选择节点')
    def choose_node_idx(self) -> OperationRoundResult:
        # OCR 读取剧变节点进度 X/Y，确定下一个要挑战的节点
        area = self.ctx.screen_loader.get_area('式舆防卫战', '剧变节点进度')
        ocr_results = self.ctx.ocr.crop_and_run_ocr(self.last_screenshot, area.rect)
        if len(ocr_results) > 0:
            # crop_and_run_ocr 返回 dict，key 为文本；过滤出包含数字的条目
            progress_text = ''
            for key in ocr_results:
                if re.search(r'\d', key):
                    progress_text = key
                    break
            if not progress_text:
                progress_text = list(ocr_results.keys())[0]
            match = re.search(r'(\d+)\s*/\s*(\d+)', progress_text)
            if match:
                total = int(match.group(2))
                current = int(match.group(1))
                log.info('剧变节点进度 %d/%d', current, total)
                self.config.critical_max_node_idx = total
                next_idx = current + 1
                if next_idx > total:
                    return self.round_success(ShiyuDefenseApp.STATUS_ALL_FINISHED)
            else:
                # 解析失败，回退到单数字（全部完成时可能只显示总节点数）
                digits = re.findall(r'\d+', progress_text)
                if len(digits) >= 2:
                    current = int(digits[0])
                    total = int(digits[1])
                    log.info('剧变节点进度 %d/%d', current, total)
                    self.config.critical_max_node_idx = total
                    next_idx = current + 1
                    if next_idx > total:
                        return self.round_success(ShiyuDefenseApp.STATUS_ALL_FINISHED)
                elif len(digits) == 1:
                    # 只有一个数字，可能是 "5"，说明已完成
                    total = int(digits[0])
                    log.info('剧变节点进度 已完成 %d', total)
                    self.config.critical_max_node_idx = total
                    return self.round_success(ShiyuDefenseApp.STATUS_ALL_FINISHED)
                else:
                    log.info('OCR 进度解析失败: %s', progress_text)
                    next_idx = 1
        else:
            log.info('未读到剧变节点进度，尝试从 run_record 获取')
            next_idx = self.run_record.next_node_idx()
            if next_idx is None:
                return self.round_success(ShiyuDefenseApp.STATUS_ALL_FINISHED)

        self.current_node_idx = next_idx

        # 多间模式节点
        if self.current_node_idx in MULTI_ROOM_NODES:
            self.current_room_idx = 0
            self.room_teams = []
            result1 = self.round_by_find_and_click_area(
                self.last_screenshot, '式舆防卫战', '节点-05'
            )
            if result1.is_success:
                return self.round_success(result1.status, wait=1)
            return self.round_retry(result1.status, wait=1)

        # 普通节点
        result1 = self.round_by_find_and_click_area(
            self.last_screenshot, '式舆防卫战',
            ('节点-%02d' % next_idx)
        )

        if result1.is_success:
            return self.round_wait(result1.status, wait=1)

        # 点击直到下一步出现
        result = self.round_by_find_area(self.last_screenshot, '式舆防卫战', '下一步')
        if result.is_success:
            log.info('当前节点 %d', self.current_node_idx)
            return self.round_success(result.status, wait=1)

        # 模板匹配失败，尝试滑动节点区域找目标节点
        area = self.ctx.screen_loader.get_area('式舆防卫战', '节点区域')
        start_point = area.rect.center
        end_point = start_point + Point(-300, 0)
        self.ctx.controller.drag_to(start=start_point, end=end_point)

        return self.round_retry(result1.status, wait=1)

    @node_from(from_name='选择节点')
    @node_from(from_name='下一节点')
    @operation_node(name='识别弱点并计算配队', node_max_retry_times=10)
    def check_weakness(self) -> OperationRoundResult:
        if self.current_node_idx in MULTI_ROOM_NODES:
            # 等待多间模式画面加载
            result = self.round_by_find_area(self.last_screenshot, '式舆防卫战-三间选择', '本期最佳总分')
            if not result.is_success:
                return self.round_retry('等待多间模式画面', wait=1)

            # 检查是否有房间已打过（得分不为 0/空）
            need_reset = False
            for room_name in ROOM_NAMES:
                area = self.ctx.screen_loader.get_area('式舆防卫战-三间选择', room_name)
                ocr_result = self.ctx.ocr.crop_and_run_ocr(self.last_screenshot, area.rect)
                all_text = ' '.join(ocr_result.keys()).strip()
                if all_text != '0' and all_text != '':
                    need_reset = True
                    break

            if need_reset:
                self.round_by_click_area('式舆防卫战-三间选择', '重置全部', success_wait=0.3)
                self.round_by_click_area('式舆防卫战-三间选择', '确认', success_wait=1)
                return self.round_retry('已重置', wait=1)

            # 多间模式
            self.room_teams = shiyu_defense_team_utils.calc_teams_for_multi_room(
                self.ctx, self.last_screenshot, '式舆防卫战-三间选择', len(ROOM_NAMES)
            )
            for idx, team in enumerate(self.room_teams):
                predefined_team = self.ctx.team_config.get_team_by_idx(team.team_idx)
                log.info('%s 弱点:%s 抗性:%s 配队:%s',
                         ROOM_NAMES[idx], [i.value for i in team.phase_weakness],
                         [i.value for i in team.phase_resistance],
                         predefined_team.name if predefined_team else '无')

            if len(self.room_teams) < len(ROOM_NAMES):
                return self.round_retry('配队计算失败 请检查配置', wait=1)
            for idx, team in enumerate(self.room_teams):
                if team.team_idx < 0:
                    continue
                if self.ctx.team_config.get_team_by_idx(team.team_idx) is None:
                    return self.round_retry(f'{ROOM_NAMES[idx]}未找到编队', wait=1)
            return self.round_success('多间模式')

        # 普通节点
        self.phase_team_list = shiyu_defense_team_utils.calc_teams(self.ctx, self.last_screenshot)

        for idx, team in enumerate(self.phase_team_list):
            predefined_team = self.ctx.team_config.get_team_by_idx(team.team_idx)
            log.info('阶段 %d', idx)
            log.info('弱点: %s', [i.value for i in team.phase_weakness])
            log.info('抗性: %s', [i.value for i in team.phase_resistance])
            log.info('配队: %s', predefined_team.name)
            log.info('自动战斗: %s', predefined_team.auto_battle)

        if len(self.phase_team_list) < 2:
            return self.round_retry('当前配置计算配队未足够多阶段 请检查配置', wait=1)

        return self.round_by_click_area('式舆防卫战', '角色头像',
                                        success_wait=1, retry_wait=1)

    @node_from(from_name='识别弱点并计算配队', status='角色头像')
    @operation_node(name='选择配队')
    def choose_team(self) -> OperationRoundResult:
        target_team_idx_list = [i.team_idx for i in self.phase_team_list]
        op = ChoosePredefinedTeam(self.ctx, target_team_idx_list)
        return self.round_by_op_result(op.execute())

    # ==================== 多间模式 ====================

    @node_from(from_name='识别弱点并计算配队', status='多间模式')
    @node_from(from_name='多间-战斗结束', status=STATUS_ROOM_COMPLETE)
    @operation_node(name='多间-选择房间', node_max_retry_times=30)
    def multi_room_select(self) -> OperationRoundResult:
        # 从 room_teams 中找第一个 team_idx >= 0 的房间
        idx = -1
        for i, team in enumerate(self.room_teams):
            if team.team_idx >= 0:
                idx = i
                break
        if idx < 0:
            self.run_record.add_node_finished(self.current_node_idx)
            return self.round_success(ShiyuDefenseApp.STATUS_ALL_ROOMS_COMPLETE)
        self.current_room_idx = idx
        log.info('选择房间: %s', ROOM_NAMES[self.current_room_idx])
        return self.round_by_find_and_click_area(self.last_screenshot, '式舆防卫战-三间选择', f'前往{ROOM_NAMES[self.current_room_idx]}', success_wait=1, retry_wait=1)

    @node_from(from_name='多间-选择房间')
    @operation_node(name='多间-等待预备编队')
    def multi_room_wait_prepare(self) -> OperationRoundResult:
        result = self.round_by_find_area(self.last_screenshot, '实战模拟室', '预备编队')
        if result.is_success:
            op = ChoosePredefinedTeam(self.ctx, [self.room_teams[self.current_room_idx].team_idx])
            op.execute()
            return self.round_success('预备编队完成')
        # 没有预备编队，点下一步后继续等
        self.round_by_click_area(
            '实战模拟室', '下一步',
            success_wait=0.5, retry_wait=1
        )
        return self.round_retry('未找到预备编队', wait=1)

    @node_from(from_name='多间-等待预备编队', status='预备编队完成')
    @operation_node(name='多间-出战')
    def multi_room_deploy(self) -> OperationRoundResult:
        result = self.round_by_find_and_click_area(
            self.last_screenshot, '实战模拟室', '出战',
            success_wait=1, retry_wait=1
        )
        if result.is_success:
            # 已出战，标记当前房间为已完成
            self.room_teams[self.current_room_idx].team_idx = -1
        return result

    @node_from(from_name='多间-出战')
    @operation_node(name='多间-战斗')
    def multi_room_battle(self) -> OperationRoundResult:
        op = ShiyuDefenseBattle(self.ctx, self.room_teams[self.current_room_idx].team_idx)
        return self.round_success() if op.execute().success else self.round_success('战斗失败')

    @node_from(from_name='多间-战斗')
    @operation_node(name='多间-战斗结束', node_max_retry_times=30)
    def multi_room_exit(self) -> OperationRoundResult:
        result = self.round_by_find_and_click_area(self.last_screenshot, '式舆防卫战', '战斗结束-退出', success_wait=5)
        if result.is_success:
            return self.round_success(ShiyuDefenseApp.STATUS_ROOM_COMPLETE)
        return self.round_retry(result.status, wait=1)

    @node_from(from_name='多间-战斗结束', status=STATUS_ALL_ROOMS_COMPLETE)
    @node_from(from_name='多间-选择房间', status=STATUS_ALL_ROOMS_COMPLETE)
    @operation_node(name='多间-返回主界面')
    def multi_room_back(self) -> OperationRoundResult:
        return self.round_by_goto_screen(screen_name='式舆防卫战')

    @node_from(from_name='多间-战斗', status='战斗失败')
    @operation_node(name='多间-战斗失败', node_max_retry_times=30)
    def multi_room_failed(self) -> OperationRoundResult:
        result = self.round_by_find_area(self.last_screenshot, '式舆防卫战', '前哨档案')
        if result.is_success:
            return self.round_success(result.status)
        return self.round_by_click_area('菜单', '返回', success_wait=1, retry_wait=1)

    # ==================== 普通节点 ====================

    @node_from(from_name='选择配队')
    @operation_node(name='出战')
    def deploy(self) -> OperationRoundResult:
        op = Deploy(self.ctx)
        self.phase_idx = 0
        return self.round_by_op_result(op.execute())

    @node_from(from_name='出战')
    @operation_node(name='自动战斗')
    def shiyu_battle(self) -> OperationRoundResult:
        op = ShiyuDefenseBattle(self.ctx, self.phase_team_list[self.phase_idx].team_idx)

        op_result = op.execute()
        if op_result.success:
            self.phase_idx += 1
            if self.phase_idx >= len(self.phase_team_list):
                self.run_record.add_node_finished(self.current_node_idx)
                return self.round_success(ShiyuDefenseApp.STATUS_NEXT_NODE)
            else:
                return self.round_wait()
        else:
            return self.round_success()

    @node_from(from_name='自动战斗', status=STATUS_NEXT_NODE)
    @node_notify(when=NotifyTiming.PREVIOUS_DONE, detail=True)
    @operation_node(name='下一节点')
    def to_next_node(self) -> OperationRoundResult:
        # 点击直到下一步出现
        result = self.round_by_find_area(self.last_screenshot, '式舆防卫战', '下一步')
        if result.is_success:
            self.current_node_idx += 1
            return self.round_success(result.status, wait=1)

        if self.current_node_idx == self.config.critical_max_node_idx:
            # 已经是最后一层了
            return self.round_by_find_and_click_area(self.last_screenshot, '式舆防卫战', '战斗结束-退出',
                                                     success_wait=5, retry_wait=1)
        else:
            result = self.round_by_find_and_click_area(self.last_screenshot, '式舆防卫战', '战斗结束-下一防线')
            if result.is_success:
                return self.round_wait(result.status, wait=1)

            # 没有下一防线，说明前四关打完了，退出后进第五关
            self.round_by_find_and_click_area(self.last_screenshot, '式舆防卫战', '战斗结束-退出',
                                              success_wait=10)

            result2 = self.round_by_find_and_click_area(self.last_screenshot, '式舆防卫战', '节点-05')
            if result2.is_success:
                self.current_node_idx = 5
                return self.round_success(wait=1)
            return self.round_retry(result2.status, wait=3)

    @node_from(from_name='下一节点', success=False)
    @node_from(from_name='下一节点', status='战斗结束-退出')
    @operation_node(name='所有节点完成', node_max_retry_times=60)
    def all_node_finished(self) -> OperationRoundResult:
        # 点击直到“前哨档案”出现
        result = self.round_by_find_area(self.last_screenshot, '式舆防卫战', '前哨档案')
        if result.is_success:
            return self.round_success(result.status, wait=1)

        result = self.round_by_find_and_click_area(self.last_screenshot, '式舆防卫战', '战斗结束-退出')
        if result.is_success:
            return self.round_wait(result.status, wait=5)
        else:
            return self.round_retry(result.status, wait=1)

    @node_from(from_name='所有节点完成')
    @node_from(from_name='选择节点', status=STATUS_ALL_FINISHED)
    @node_from(from_name='多间-返回主界面')
    @node_notify(when=NotifyTiming.CURRENT_DONE, detail=True)
    @operation_node(name='领取奖励')
    def claim_reward(self) -> OperationRoundResult:
        # 检测是否在奖励界面（通过模板匹配）
        result = self.round_by_find_area(self.last_screenshot, '式舆防卫战', '领取奖励-界面')
        if result.is_success:
            # 已在奖励界面，直接点击全部领取区域（无论是否能识别到）
            self.round_by_click_area('式舆防卫战', '全部领取')
            return self.round_success('全部领取', wait=1)

        # 不在奖励界面，点击奖励入口
        result = self.round_by_click_area('式舆防卫战', '奖励入口')
        if result.is_success:
            return self.round_wait(result.status, wait=0.5)

        return self.round_retry(result.status, wait=1)

    @node_from(from_name='领取奖励')
    @operation_node(name='关闭奖励')
    def close_reward(self) -> OperationRoundResult:
        # 判断是否已回到主界面(“前哨档案”出现)
        result = self.round_by_find_area(self.last_screenshot, '式舆防卫战', '前哨档案')
        if result.is_success:
            return self.round_success(result.status)

        result = self.round_by_find_and_click_area(self.last_screenshot, '式舆防卫战', '领取奖励-确认')
        if result.is_success:
            return self.round_wait(result.status, wait=0.5)

        result = self.round_by_click_area('式舆防卫战', '领取奖励-关闭')
        if result.is_success:
            return self.round_wait(result.status, wait=0.5)

        return self.round_retry(result.status, wait=1)

    @node_from(from_name='自动战斗')  # 战斗失败的情况
    @node_from(from_name='关闭奖励')
    @node_from(from_name='多间-战斗失败')
    @operation_node(name='结束后返回')
    def back_after_all(self) -> OperationRoundResult:
        log.info('新一期刷新后 可到「式舆防卫战」重置运行记录')
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()

    from one_dragon.utils import debug_utils
    screen = debug_utils.get_debug_image('_1728799789929')

    app = ShiyuDefenseApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()
