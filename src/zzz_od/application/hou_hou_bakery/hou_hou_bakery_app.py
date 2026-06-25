import time

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_notify import NotifyTiming, node_notify
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.application.hou_hou_bakery import hou_hou_bakery_const
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.transport import Transport


class HouHouBakeryApp(ZApplication):
    """吼吼饼铺 每日签到

    流程: 传送到布亚斯特城区-吼吼饼铺 -> 与吼吼先生交互 -> 领取每日「零食盲盒」奖励 -> 返回大世界。
    与刮刮卡/卦象集录同类, 每日刷新后最多领取一次。
    """

    def __init__(self, ctx: ZContext):
        """初始化吼吼饼铺签到应用。

        Args:
            ctx: 运行上下文。
        """
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=hou_hou_bakery_const.APP_ID,
            op_name=hou_hou_bakery_const.APP_NAME,
        )
        self.claimed: bool = False  # 本次运行是否已点击领取卡片

    @operation_node(name='传送', is_start_node=True)
    def transport(self) -> OperationRoundResult:
        """传送到吼吼饼铺, 由 Transport 等待大世界加载完成。"""
        op = Transport(self.ctx, '布亚斯特城区', '吼吼饼铺', wait_at_last=True)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='传送')
    @operation_node(name='移动交互')
    def move_and_interact(self) -> OperationRoundResult:
        """传送之后与吼吼先生交互, 打开领奖界面。传送点已足够近, 无需前移。"""
        # self.ctx.controller.move_w(press=True, press_time=1, release=True)
        # time.sleep(1)

        self.ctx.controller.interact(press=True, press_time=0.2, release=True)
        time.sleep(3)

        return self.round_success()

    @node_from(from_name='移动交互')
    @node_notify(when=NotifyTiming.CURRENT_DONE)
    @operation_node(name='领取奖励', node_max_retry_times=20)
    def collect(self) -> OperationRoundResult:
        """领取每日奖励 单节点自循环。

        各画面按 OCR 文字分发
        - 「确定/确认」: 卡片揭示界面, 点击确认领取并标记 claimed。
        - 「查看今天」: 盲盒已居中(点击盲盒, 查看今天的「卡片」吧), 点屏幕中心开盒。
        - 「每日可领取一次」: 集卡机界面可领取, 点击格子里的盲盒。
        - 「同类型奖励」: 今日已领取同类型奖励, 两条路径的终点, 结束。
        其余(黑屏过渡/加载) -> 重试。
        """
        # 卡片揭示 -> 点击确定
        for confirm_word in ['确定', '确认']:
            result = self.round_by_ocr_and_click(self.last_screenshot, confirm_word)
            if result.is_success:
                self.claimed = True
                return self.round_wait(status=confirm_word, wait=1)

        # 盲盒已居中 -> 点击屏幕中心开盒
        result = self.round_by_ocr(self.last_screenshot, '查看今天')
        if result.is_success:
            center = Point(self.ctx.controller.standard_width // 2,
                           self.ctx.controller.standard_height // 2)
            self.ctx.controller.click(center)
            return self.round_wait(status='点击盲盒', wait=1)

        # 集卡机可领取 -> 点击盲盒格子
        result = self.round_by_ocr(self.last_screenshot, '每日可领取一次')
        if result.is_success:
            click_result = self.round_by_click_area('吼吼饼铺', '盲盒')
            if click_result.is_success:
                return self.round_wait(status='选择盲盒', wait=1)
            return self.round_retry(status='盲盒区域点击失败', wait=1)

        # 今日已领取同类型奖励(两条路径终点) -> 结束
        result = self.round_by_ocr(self.last_screenshot, '同类型奖励')
        if result.is_success:
            status = '领取成功' if self.claimed else '今日已领取'
            return self.round_success(status=status)

        return self.round_retry(status='未识别目标文本', wait=1)

    @node_from(from_name='领取奖励')
    @operation_node(name='返回大世界')
    def back_to_world(self) -> OperationRoundResult:
        """领取完成后返回大世界。"""
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug() -> None:
    """本地调试入口: 初始化上下文并直接运行一次吼吼饼铺签到。"""
    ctx = ZContext()
    ctx.init_by_config()
    app = HouHouBakeryApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()
