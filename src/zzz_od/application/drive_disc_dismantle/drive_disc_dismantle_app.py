from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld


class DriveDiscDismantleApp(ZApplication):

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx, app_id='drive_disc_dismantle',
            op_name=gt('驱动盘分解'),
            run_record=ctx.drive_disc_dismantle_record,
            need_notify=True,
        )

    @operation_node(name='开始前返回', is_start_node=True)
    def back_at_first(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='开始前返回')
    @operation_node(name='前往分解画面')
    def goto_salvage(self) -> OperationRoundResult:
        return self.round_by_goto_screen(screen_name='仓库-驱动仓库-驱动盘拆解')

    @node_from(from_name='前往分解画面')
    @operation_node(name='快速选择')
    def click_filter(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '仓库-驱动仓库-驱动盘拆解', '按钮-快速选择',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='快速选择')
    @operation_node(name='选择等级')
    def choose_level(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(
            screen, '仓库-驱动仓库-驱动盘拆解', f'按钮-{self.ctx.drive_disc_dismantle_config.dismantle_level}',
            success_wait=1, retry_wait=1
        )

    @node_from(from_name='选择等级')
    @operation_node(name='选择弃置')
    def choose_abandon(self) -> OperationRoundResult:
        if self.ctx.drive_disc_dismantle_config.dismantle_abandon:
            screen = self.screenshot()
            return self.round_by_find_and_click_area(screen, '仓库-驱动仓库-驱动盘拆解', '按钮-全选已弃置',
                                                     success_wait=1, retry_wait=1)
        else:
            return self.round_success('无需选择')

    @node_from(from_name='选择等级', success=False)
    @node_from(from_name='选择弃置')
    @node_from(from_name='选择弃置', success=False)
    @operation_node(name='快速选择确认')
    def click_filter_confirm(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '仓库-驱动仓库-驱动盘拆解', '按钮-快速选择-确认',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='快速选择确认')
    @operation_node(name='点击拆解')
    def click_salvage(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '仓库-驱动仓库-驱动盘拆解', '按钮-拆解',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='点击拆解')
    @operation_node(name='点击拆解确认')
    def click_salvage_confirm(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '仓库-驱动仓库-驱动盘拆解', '按钮-拆解-确认',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='点击拆解确认')
    @node_from(from_name='点击拆解确认', success=False)  # 可能没有需要拆解的
    @operation_node(name='完成后返回')
    def back_at_last(self) -> OperationRoundResult:
        self.notify_screenshot = self.save_screenshot_bytes()  # 结束后通知的截图
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    app = DriveDiscDismantleApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()