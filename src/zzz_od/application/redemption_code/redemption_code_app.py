import time
from typing import List, Optional

from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.application.redemption_code import redemption_code_const
from zzz_od.application.redemption_code.redemption_code_run_record import (
    RedemptionCodeRunRecord,
)
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld


class RedemptionCodeApp(ZApplication):

    def __init__(self, ctx: ZContext):
        """
        每天自动接收邮件奖励
        """
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=redemption_code_const.APP_ID,
            op_name=redemption_code_const.APP_NAME,
            need_notify=True,
        )
        self.run_record: Optional[RedemptionCodeRunRecord] = self.ctx.run_context.get_run_record(
            app_id=redemption_code_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
        )

        self.unused_code_list: List[str] = []
        self.code_idx: int = 0  # 当前输入兑换码的下标

    def handle_init(self) -> None:
        """
        执行前的初始化 由子类实现
        注意初始化要全面 方便一个指令重复使用
        """
        pass

    @operation_node(name='检测新兑换码', is_start_node=True)
    def check_new_code(self) -> OperationRoundResult:
        self.unused_code_list = self.run_record.get_unused_code_list(self.run_record.get_current_dt())
        if len(self.unused_code_list) == 0:
            return self.round_success('无新的兑换码')
        else:
            return self.round_success('有新的兑换码')

    @node_from(from_name='检测新兑换码', status='有新的兑换码')
    @operation_node(name='打开菜单')
    def open_menu(self) -> OperationRoundResult:
        return self.round_by_goto_screen(screen_name='菜单')

    @node_from(from_name='打开菜单')
    @operation_node(name='点击更多')
    def click_more(self) -> OperationRoundResult:
        area = self.ctx.screen_loader.get_area('菜单', '底部列表')
        return self.round_by_ocr_and_click(self.last_screenshot, '更多', area=area,
                                           success_wait=1, retry_wait=1)

    @node_from(from_name='点击更多')
    @operation_node(name='点击兑换码')
    def click_code(self) -> OperationRoundResult:
        area = self.ctx.screen_loader.get_area('菜单', '更多功能区域')
        self.code_idx = 0
        return self.round_by_ocr_and_click(self.last_screenshot, '兑换码', area=area,
                                           success_wait=1, retry_wait=1)

    @node_from(from_name='点击兑换码')  # 第一次兑换
    @node_from(from_name='兑换后确认')  # 继续兑换
    @operation_node(name='输入兑换码')
    def input_code(self) -> OperationRoundResult:
        if self.code_idx >= len(self.unused_code_list):
            return self.round_success('全部兑换完毕')

        self.round_by_click_area('菜单', '兑换码输入框')
        time.sleep(1)

        self.ctx.controller.keyboard_controller.keyboard.type(self.unused_code_list[self.code_idx])
        time.sleep(6)

        return self.round_by_find_and_click_area(self.last_screenshot, '菜单', '兑换码兑换',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='输入兑换码', status='兑换码兑换')
    @operation_node(name='兑换后确认')
    def confirm_code(self) -> OperationRoundResult:
        result = self.round_by_find_and_click_area(self.last_screenshot, '菜单', '兑换码兑换')
        if result.is_success:
            self.run_record.add_used_code(self.unused_code_list[self.code_idx])
            self.code_idx += 1
            return self.round_success(result.status, wait=1)

        return self.round_retry(result.status, wait=1)

    @node_from(from_name='输入兑换码', status='全部兑换完毕')
    @operation_node(name='返回大世界')
    def back(self) -> OperationRoundResult:
        self.notify_screenshot = self.save_screenshot_bytes()  # 结束后通知的截图
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.run_context.run_application(
        app_id=redemption_code_const.APP_ID,
        instance_idx=ctx.current_instance_idx,
        group_id=application_const.DEFAULT_GROUP_ID,
    )


if __name__ == '__main__':
    __debug()