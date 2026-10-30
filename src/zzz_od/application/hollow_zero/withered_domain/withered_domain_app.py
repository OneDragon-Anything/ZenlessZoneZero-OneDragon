import difflib
import time
from typing import ClassVar

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_notify import NotifyTiming, node_notify
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.utils import str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.hollow_zero.withered_domain import withered_domain_const
from zzz_od.application.hollow_zero.withered_domain.withered_domain_config import (
    WitheredDomainConfig,
)
from zzz_od.application.hollow_zero.withered_domain.withered_domain_run_record import (
    WitheredDomainRunRecord,
)
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.hollow_zero.event import hollow_event_utils
from zzz_od.hollow_zero.game_data.hollow_zero_event import HollowZeroSpecialEvent
from zzz_od.hollow_zero.hollow_runner import HollowRunner
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.compendium.tp_by_compendium import TransportByCompendium
from zzz_od.operation.deploy import Deploy
from zzz_od.screen_area.screen_normal_world import ScreenNormalWorldEnum


class WitheredDomainApp(ZApplication):

    """枯萎之都:零号空洞-枯萎之都副本,周限 rogue 玩法(与迷失之地共享每周奖励次数)。消耗周次数、进入战斗、耗时较长。"""

    STATUS_IN_HOLLOW: ClassVar[str] = '在空洞内'
    STATUS_NO_REWARD: ClassVar[str] = '无奖励可领取'
    STATUS_TIMES_FINISHED: ClassVar[str] = '已完成基本次数'
    STATUS_NO_EVAL_POINT: ClassVar[str] = '已完成刷取业绩'

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=withered_domain_const.APP_ID,
            op_name=withered_domain_const.APP_NAME,
        )
        self.config: WitheredDomainConfig = self.ctx.run_context.get_config(
            app_id=withered_domain_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )
        self.run_record: WitheredDomainRunRecord = self.ctx.run_context.get_run_record(
            instance_idx=self.ctx.current_instance_idx,
            app_id=withered_domain_const.APP_ID,
        )

        self.mission_name: str = '枯败花圃-核心'
        self.mission_type_name: str = '枯败花圃'
        self.level: int = 1
        self.phase: int = 1

    def handle_init(self):
        """运行前初始化 从配置解析副本名称与副本类型 未配置时使用 枯败花圃-核心"""
        self.ctx.withered_domain.init_before_run()
        mission_name = self.config.mission_name if self.config is not None else None
        if not mission_name:
            mission_name = '枯败花圃-核心'
        idx = mission_name.find('-')
        if idx != -1:
            self.mission_name = mission_name
            self.mission_type_name = mission_name[:idx]
        else:
            self.mission_name = mission_name
            self.mission_type_name = mission_name

    @operation_node(name='初始画面识别', is_start_node=True)
    def check_first_screen(self) -> OperationRoundResult:
        event_name = hollow_event_utils.check_screen(self.ctx, self.last_screenshot, set())
        # 特殊兼容：已在副本内，接力运行（层信息忽略）
        if (event_name is not None
                and event_name not in [
                    HollowZeroSpecialEvent.OLD_CAPITAL.value.event_name,  # 旧都失物是左上角的返回符合 有较多地方存在 不适合这里判断
                ]):
            self.level = -1
            self.phase = -1
            return self.round_success(WitheredDomainApp.STATUS_IN_HOLLOW)

        screen_name, _ = self.check_screen_with_can_go(self.last_screenshot, '零号空洞-入口')
        # 特殊兼容：在入口区域开始，接力运行
        if screen_name == '零号空洞-入口':
            return self.round_success('零号空洞-入口')

        # 未识别到画面；走快捷手册传送流程
        can_go = self.check_current_can_go('快捷手册-作战')
        if can_go:
            return self.round_success('可前往快捷手册')

        return self.round_success('未识别初始画面', wait=1)

    @node_from(from_name='初始画面识别', status='可前往快捷手册')
    @node_from(from_name='初始画面识别', status='未识别初始画面')
    @operation_node(name='前往零号空洞-入口')
    def tp(self) -> OperationRoundResult:
        op = TransportByCompendium(self.ctx,
                                   '作战',
                                   '周期征讨',
                                   '迷失之地')
        return self.round_by_op_result(op.execute())

    @node_from(from_name='前往零号空洞-入口')
    @node_from(from_name='初始画面识别', status='零号空洞-入口')
    @node_from(from_name='自动运行')
    @operation_node(name='前往枯萎之都-入口', node_max_retry_times=20)
    def choose_withered_domain_entry(self) -> OperationRoundResult:
        """前往枯萎之都入口"""
        entry_result = self.round_by_find_area(self.last_screenshot, '零号空洞-入口', '街区')
        if entry_result.is_success:
            return self.round_success('已进入枯萎之都-入口')

        result = self.round_by_ocr_and_click_by_priority(['枯败花圃', '枯萎之都', '零号空洞'])
        if result.is_success:
            return self.round_retry('尝试进入枯萎之都-入口', wait=1)

        return self.round_retry(result.status, wait=1)

    @node_from(from_name='前往枯萎之都-入口')
    @operation_node(name='选择副本类型')
    def choose_mission_type(self) -> OperationRoundResult:
        """选择副本类型 已完成本周或本日次数时直接结束 出现 下一步 时进入下一步节点"""
        if (self.run_record.is_finished_by_week()
            or self.run_record.is_finished_by_day()):
            return self.round_success(WitheredDomainApp.STATUS_TIMES_FINISHED)

        result = self.round_by_find_and_click_area(self.last_screenshot, '零号空洞-入口', '下一步')
        if result.is_success:
            return self.round_success(result.status)

        target_list = [self.mission_type_name]
        if self.mission_type_name in ['枯萎之都', '枯败花圃']:
            target_list = ['枯败花圃', '枯萎之都', '花圃']
        return self.round_by_ocr_and_click_by_priority(target_list, success_wait=1, retry_wait=1)

    @node_from(from_name='选择副本类型')
    @operation_node(name='选择副本')
    def choose_mission(self) -> OperationRoundResult:
        """按配置的副本名称及其备选名称选择副本"""
        area = self.ctx.screen_loader.get_area('零号空洞-入口', '副本列表')
        target_list = [self.mission_name]
        if '-' in self.mission_name:
            target_list.append(self.mission_name.split('-')[-1])
        if '核心' in self.mission_name:
            target_list.extend(['核心', 'Core', '枯败花圃-核心', '枯萎之都-核心'])
        # 去重并保持顺序
        target_list = list(dict.fromkeys(target_list))
        return self._click_mission_by_priority(target_list, area)

    def _click_mission_by_priority(self, target_list: list[str], area: ScreenArea) -> OperationRoundResult:
        """
        按优先级在副本列表中点击副本
        同一个候选名称可能模糊匹配到多个副本（如 枯萎之都-核心 / 枯萎之都-外围 都能匹配 枯萎之都-核心）
        此时优先点击文本最相似的结果 相似度相同再比较 OCR 置信度
        :param target_list: 按优先级排序的候选名称
        :param area: 副本列表区域
        :return:
        """
        ocr_result_map = self.ctx.ocr_service.get_ocr_result_map(
            image=self.last_screenshot,
            rect=area.rect,
            color_range=area.color_range,
        )
        to_match_list: list[str] = [gt(i, 'game') for i in target_list]
        for word_idx, word in enumerate(target_list):
            candidate_list: list[tuple[float, float, Point]] = []
            for ocr_text, mrl in ocr_result_map.items():
                if mrl.max is None:
                    continue
                # 与 match_word_list_by_priority 相同的分组方式：OCR 文本归到最相近的候选名称
                if str_utils.find_best_match_by_difflib(ocr_text, to_match_list) != word_idx:
                    continue
                ratio = difflib.SequenceMatcher(None, ocr_text, to_match_list[word_idx]).ratio()
                candidate_list.append((ratio, mrl.max.confidence, mrl.max.center))
            if len(candidate_list) == 0:
                continue

            _, _, to_click = max(candidate_list, key=lambda c: (c[0], c[1]))
            time.sleep(0.3)
            if self.ctx.controller.click(to_click):
                return self.round_success(status=word, wait=1)
            return self.round_retry(f'点击 {word} 失败', wait=1)

        return self.round_retry(status='未匹配到目标文本', wait=1)

    @node_from(from_name='选择副本类型', status='下一步')
    @node_from(from_name='选择副本')
    @operation_node(name='下一步')
    def click_next(self) -> OperationRoundResult:
        result = self.round_by_find_and_click_area(self.last_screenshot, '零号空洞-入口', '下一步')
        if result.is_success:
            time.sleep(0.5)
            self.ctx.controller.mouse_move(ScreenNormalWorldEnum.UID.value.center)  # 点击后 移开鼠标 防止识别不到出战
            return self.round_wait(result.status, wait=0.5)

        result = self.round_by_find_and_click_area(self.last_screenshot, '零号空洞-入口', '行动中-确认')
        if result.is_success:
            return self.round_wait(wait=1)

        result = self.round_by_find_area(self.last_screenshot, '零号空洞-入口', '出战')
        if result.is_success:
            return self.round_success(result.status, wait=1)

        result = self.round_by_find_and_click_area(self.last_screenshot, '零号空洞-入口', '继续-确认')
        if result.is_success:
            self.level = -1
            self.phase = -1
            return self.round_success(result.status, wait=1)

        return self.round_retry(wait=1)

    @node_from(from_name='下一步', status='出战')
    @operation_node(name='出战')
    def deploy(self) -> OperationRoundResult:
        op = Deploy(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='初始画面识别', status=STATUS_IN_HOLLOW)  # 最开始就在
    @node_from(from_name='下一步', status='继续-确认')
    @node_from(from_name='出战')
    @operation_node(name='自动运行')
    def auto_run(self) -> OperationRoundResult:
        try:
            self.ctx.withered_domain.init_before_hollow_start(self.mission_type_name, self.mission_name, self.level, self.phase)
        except Exception:
            log.error('模型加载失败', exc_info=True)
            return self.round_fail('模型加载失败 请重新下载模型')
        op = HollowRunner(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='选择副本类型', status=STATUS_TIMES_FINISHED)
    @operation_node(name='完成后等待加载', node_max_retry_times=20)
    def wait_back_loading(self) -> OperationRoundResult:
        return self.round_by_find_area(self.last_screenshot, '零号空洞-入口', '街区', retry_wait=1)

    @node_from(from_name='完成后等待加载')
    @node_notify(when=NotifyTiming.PREVIOUS_DONE)
    @operation_node(name='完成')
    def finish(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init()
    op = WitheredDomainApp(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()
