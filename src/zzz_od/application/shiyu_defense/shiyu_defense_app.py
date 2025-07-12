from typing import ClassVar, List

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.shiyu_defense import shiyu_defense_team_utils
from zzz_od.application.shiyu_defense.shiyu_defense_battle import ShiyuDefenseBattle
from zzz_od.application.shiyu_defense.shiyu_defense_team_utils import DefensePhaseTeamInfo
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.choose_predefined_team import ChoosePredefinedTeam
from zzz_od.operation.compendium.tp_by_compendium import TransportByCompendium
from zzz_od.operation.deploy import Deploy


class ShiyuDefenseApp(ZApplication):

    STATUS_ALL_FINISHED: ClassVar[str] = '所有节点都完成挑战'
    STATUS_NEXT_NODE: ClassVar[str] = '下一节点'

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx, app_id='shiyu_defense',
            op_name=gt('式舆防卫战'),
            run_record=ctx.shiyu_defense_record,
            need_notify=True,
        )

        self.current_node_idx: int = 0  # 当前挑战的节点下标 跟着游戏的1开始
        self.phase_team_list: List[DefensePhaseTeamInfo] = []  # 每个阶段使用的配队
        self.phase_idx: int = 0  # 当前阶段

    @operation_node(name='传送', is_start_node=True)
    def tp(self) -> OperationRoundResult:
        op = TransportByCompendium(self.ctx, '作战', '式舆防卫战', '剧变节点')
        return self.round_by_op_result(op.execute())

    @node_from(from_name='传送')
    @operation_node(name='等待画面加载', node_max_retry_times=60)
    def wait_loading(self) -> OperationRoundResult:
        screen = self.screenshot()

        result = self.round_by_find_area(screen, '式舆防卫战', '前次行动最佳记录')
        if result.is_success:
            self.round_by_click_area('式舆防卫战', '前次-关闭')
            return self.round_wait(result.status, wait=2)

        return self.round_by_find_area(screen, '式舆防卫战', '街区', retry_wait=1)

    @node_from(from_name='等待画面加载')
    @operation_node(name='选择节点')
    def choose_node_idx(self) -> OperationRoundResult:
        idx = self.ctx.shiyu_defense_record.next_node_idx()

        if idx is None:
            return self.round_success(ShiyuDefenseApp.STATUS_ALL_FINISHED)

        self.current_node_idx = idx
        screen = self.screenshot()

        result1 = self.round_by_find_and_click_area(screen, '式舆防卫战', ('节点-%02d' % idx))
        if result1.is_success:
            return self.round_wait(result1.status, wait=1)

        # 点击直到下一步出现 出现后 再等一会等属性出现
        result = self.round_by_find_area(screen, '式舆防卫战', '下一步')
        if result.is_success:
            log.info('当前节点 %d', self.current_node_idx)
            return self.round_success(result.status, wait=1)

        # 可能之前人工挑战了 这里重新判断看哪个节点可以挑战
        idx_to_check = (
            [i for i in range(idx, self.ctx.shiyu_defense_config.critical_max_node_idx + 1)]  # 优先检测后续的关卡
            + [i for i in range(1, idx)]
        )
        for i in idx_to_check:
            result2 = self.round_by_find_area(screen, '式舆防卫战', ('节点-%02d' % i))
            if not result2.is_success:
                continue

            if i > idx:
                for j in range(1, i):
                    self.ctx.shiyu_defense_record.add_node_finished(j)
                return self.round_wait(result2.status, wait=1)
            break

        area = self.ctx.screen_loader.get_area('式舆防卫战', '节点区域')
        start_point = area.rect.center
        end_point = start_point + Point(-300, 0)
        self.ctx.controller.drag_to(start=start_point, end=end_point)

        return self.round_retry(result1.status, wait=1)

    @node_from(from_name='选择节点')
    @node_from(from_name='下一节点')
    @operation_node(name='识别弱点并计算配队', node_max_retry_times=10)
    def check_weakness(self) -> OperationRoundResult:
        screen = self.screenshot()

        self.phase_team_list = shiyu_defense_team_utils.calc_teams(self.ctx, screen)

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

    @node_from(from_name='识别弱点并计算配队')
    @operation_node(name='选择配队')
    def choose_team(self) -> OperationRoundResult:
        target_team_idx_list = [i.team_idx for i in self.phase_team_list]
        op = ChoosePredefinedTeam(self.ctx, target_team_idx_list)
        return self.round_by_op_result(op.execute())

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
                self.ctx.shiyu_defense_record.add_node_finished(self.current_node_idx)
                return self.round_success(ShiyuDefenseApp.STATUS_NEXT_NODE)
            else:
                return self.round_wait()
        else:
            return self.round_success()

    @node_from(from_name='自动战斗', status=STATUS_NEXT_NODE)
    @operation_node(name='下一节点')
    def to_next_node(self) -> OperationRoundResult:
        screen = self.screenshot()

        # 点击直到下一步出现 出现后 再等一会等属性出现
        result = self.round_by_find_area(screen, '式舆防卫战', '下一步')
        if result.is_success:
            self.current_node_idx += 1
            return self.round_success(result.status, wait=1)

        if self.current_node_idx == self.ctx.shiyu_defense_config.critical_max_node_idx:
            # 已经是最后一层了
            return self.round_by_find_and_click_area(screen, '式舆防卫战', '战斗结束-退出',
                                                     success_wait=5, retry_wait=1)
        else:
            result = self.round_by_find_and_click_area(screen, '式舆防卫战', '战斗结束-下一防线')
            if result.is_success:
                return self.round_wait(result.status, wait=1)

        return self.round_retry(result.status, wait=1)

    @node_from(from_name='下一节点', success=False)
    @node_from(from_name='下一节点', status='战斗结束-退出')
    @operation_node(name='所有节点完成', node_max_retry_times=60)
    def all_node_finished(self) -> OperationRoundResult:
        screen = self.screenshot()

        # 点击直到街区出现
        result = self.round_by_find_area(screen, '式舆防卫战', '街区')
        if result.is_success:
            return self.round_success(result.status, wait=1)

        result = self.round_by_find_and_click_area(screen, '式舆防卫战', '战斗结束-退出')
        if result.is_success:
            return self.round_wait(result.status, wait=5)
        else:
            return self.round_retry(result.status, wait=1)

    @node_from(from_name='所有节点完成')
    @node_from(from_name='选择节点', status=STATUS_ALL_FINISHED)
    @operation_node(name='领取奖励')
    def claim_reward(self) -> OperationRoundResult:
        screen = self.screenshot()

        result = self.round_by_find_and_click_area(screen, '式舆防卫战', '全部领取')
        if result.is_success:
            return self.round_success(result.status, wait=1)

        self.round_by_click_area('式舆防卫战', '奖励入口')

        return self.round_retry(result.status, wait=1)

    @node_from(from_name='领取奖励')
    @operation_node(name='关闭奖励')
    def close_reward(self) -> OperationRoundResult:
        screen = self.screenshot()

        result = self.round_by_find_area(screen, '式舆防卫战', '街区')
        if result.is_success:
            return self.round_success(result.status)

        result = self.round_by_find_and_click_area(screen, '式舆防卫战', '领取奖励-确认')
        if result.is_success:
            return self.round_wait(result.status, wait=1)

        self.round_by_click_area('式舆防卫战', '领取奖励-关闭')
        return self.round_retry(result.status, wait=1)

    @node_from(from_name='自动战斗')  # 战斗失败的情况
    @node_from(from_name='关闭奖励')
    @operation_node(name='结束后返回')
    def back_after_all(self) -> OperationRoundResult:
        log.info('新一期刷新后 可到「式舆防卫战」重置运行记录')
        self.notify_screenshot = self.save_screenshot_bytes()  # 结束后通知的截图
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