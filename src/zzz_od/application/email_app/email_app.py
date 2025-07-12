from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext


class EmailApp(ZApplication):

    def __init__(self, ctx: ZContext):
        """
        每天自动接收邮件奖励
        """
        ZApplication.__init__(
            self,
            ctx=ctx, app_id='email',
            op_name=gt('邮件'),
            run_record=ctx.email_run_record,
            need_notify=True,
        )

    def handle_init(self) -> None:
        """
        执行前的初始化 由子类实现
        注意初始化要全面 方便一个指令重复使用
        """
        pass

    @operation_node(name='打开邮件', is_start_node=True)
    def goto_email(self) -> OperationRoundResult:
        return self.round_by_goto_screen(screen_name='邮件')

    @node_from(from_name='打开邮件')
    @operation_node(name='全部领取')
    def click_get_all(self) -> OperationRoundResult:
        """
        邮件画面 点击全部领取
        就算时灰色的也能识别到
        :return:
        """
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '邮件', '全部领取', success_wait=1, retry_wait=1)

    @node_from(from_name='全部领取')
    @operation_node(name='确认')
    def click_confirm(self) -> OperationRoundResult:
        """
        邮件画面 领取后点击确认
        :return:
        """
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '邮件', '确认', success_wait=1, retry_wait=1)

    @node_from(from_name='确认')  # 确认之后返回
    @node_from(from_name='确认', success=False)  # 没有确认 其实就是没有东西能领取 也返回
    @node_from(from_name='全部领取', success=False)  # 没找到全部领取的话 也返回
    @operation_node(name='返回菜单')
    def back_to_menu(self) -> OperationRoundResult:
        """
        返回菜单
        领取后的确认按钮可以不按 直接点击外层也可以返回
        :return:
        """
        self.notify_screenshot = self.save_screenshot_bytes()  # 结束后通知的截图
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '菜单', '返回', success_wait=1, retry_wait=1)
