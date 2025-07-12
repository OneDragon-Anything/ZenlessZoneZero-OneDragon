import time

from typing import ClassVar

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.hollow_zero.event import hollow_event_utils
from zzz_od.hollow_zero.game_data.hollow_zero_event import HollowZeroSpecialEvent
from zzz_od.hollow_zero.hollow_runner import HollowRunner
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.compendium.tp_by_compendium import TransportByCompendium
from zzz_od.operation.deploy import Deploy
from zzz_od.screen_area.screen_normal_world import ScreenNormalWorldEnum


class HollowZeroApp(ZApplication):

    STATUS_IN_HOLLOW: ClassVar[str] = '在空洞内'
    STATUS_NO_REWARD: ClassVar[str] = '无奖励可领取'
    STATUS_TIMES_FINISHED: ClassVar[str] = '已完成基本次数'
    STATUS_NO_EVAL_POINT: ClassVar[str] = '已完成刷取业绩'

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx, app_id='hollow_zero',
            op_name=gt('枯萎之都'),
            run_record=ctx.hollow_zero_record,
            need_notify=True,
        )

        self.mission_name: str = '内部'
        self.mission_type_name: str = '旧都列车'
        self.level: int = 1
        self.phase: int = 1

    def handle_init(self):
        self.ctx.init_hollow_config()
        mission_name = self.ctx.hollow_zero_config.mission_name
        idx = mission_name.find('-')
        if idx != -1:
            self.mission_name = mission_name
            self.mission_type_name = mission_name[:idx]
        else:
            self.mission_name = mission_name
            self.mission_type_name = mission_name

    @operation_node(name='初始画面识别', is_start_node=True)
    def check_first_screen(self) -> OperationRoundResult:
        screen = self.screenshot()
        event_name = hollow_event_utils.check_screen(self.ctx, screen, set())

        if (event_name is not None
                and event_name not in [
                    HollowZeroSpecialEvent.OLD_CAPITAL.value.event_name,  # 旧都失物是左上角的返回符合 有较多地方存在 不适合这里判断
                ]):
            self.level = -1
            self.phase = -1
            return self.round_success(HollowZeroApp.STATUS_IN_HOLLOW)

        result = self.round_by_find_area(screen, '大世界', '信息')

        if result.is_success:
            return self.round_success(result.status)
        else:
            return self.round_retry(result.status, wait=1)

    @node_from(from_name='初始画面识别', success=False)
    @node_from(from_name='初始画面识别', status='信息')
    @operation_node(name='传送')
    def tp(self) -> OperationRoundResult:
        op = TransportByCompendium(self.ctx,
                                   '作战',
                                   '零号空洞',
                                   '枯萎之都')
        return self.round_by_op_result(op.execute())

    @node_from(from_name='传送')
    @node_from(from_name='自动运行')
    @operation_node(name='等待入口加载', node_max_retry_times=20)
    def wait_entry_loading(self) -> OperationRoundResult:
        screen = self.screenshot()

        return self.round_by_find_area(screen, '零号空洞-入口', '街区', retry_wait=1)

    @node_from(from_name='等待入口加载')
    @operation_node(name='选择副本类型')
    def choose_mission_type(self) -> OperationRoundResult:
        if (self.ctx.hollow_zero_record.is_finished_by_week()
            or self.ctx.hollow_zero_record.is_finished_by_day()):
            return self.round_success(HollowZeroApp.STATUS_TIMES_FINISHED)

        screen = self.screenshot()
        result = self.round_by_find_and_click_area(screen, '零号空洞-入口', '下一步')
        if result.is_success:
            return self.round_success(result.status)

        return self.round_by_ocr_and_click(screen, self.mission_type_name,
                                           success_wait=1, retry_wait=1)

    @node_from(from_name='选择副本类型')
    @operation_node(name='选择副本')
    def choose_mission(self) -> OperationRoundResult:
        screen = self.screenshot()
        area = self.ctx.screen_loader.get_area('零号空洞-入口', '副本列表')
        return self.round_by_ocr_and_click(screen, self.mission_name, area=area,
                                           success_wait=1, retry_wait=1)

    @node_from(from_name='选择副本类型', status='下一步')
    @node_from(from_name='选择副本')
    @operation_node(name='下一步')
    def click_next(self) -> OperationRoundResult:
        screen = self.screenshot()

        result = self.round_by_find_and_click_area(screen, '零号空洞-入口', '下一步')
        if result.is_success:
            time.sleep(0.5)
            self.ctx.controller.mouse_move(ScreenNormalWorldEnum.UID.value.center)  # 点击后 移开鼠标 防止识别不到出战
            return self.round_wait(result.status, wait=0.5)

        result = self.round_by_find_and_click_area(screen, '零号空洞-入口', '行动中-确认')
        if result.is_success:
            return self.round_wait(wait=1)

        result = self.round_by_find_area(screen, '零号空洞-入口', '出战')
        if result.is_success:
            return self.round_success(result.status, wait=1)

        result = self.round_by_find_and_click_area(screen, '零号空洞-入口', '继续-确认')
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
            self.ctx.hollow.init_before_hollow_start(self.mission_type_name, self.mission_name, self.level, self.phase)
        except Exception:
            log.error('模型加载失败', exc_info=True)
            return self.round_fail('模型加载失败 请重新下载模型')
        op = HollowRunner(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='选择副本类型', status=STATUS_TIMES_FINISHED)
    @operation_node(name='完成后等待加载', node_max_retry_times=20)
    def wait_back_loading(self) -> OperationRoundResult:
        screen = self.screenshot()

        return self.round_by_find_area(screen, '零号空洞-入口', '街区', retry_wait=1)

    @node_from(from_name='完成后等待加载')
    @operation_node(name='完成')
    def finish(self) -> OperationRoundResult:
        self.notify_screenshot = self.save_screenshot_bytes()  # 结束后通知的截图
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    op = HollowZeroApp(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()
