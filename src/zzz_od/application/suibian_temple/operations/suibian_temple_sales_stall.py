from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class SuibianTempleSalesStall(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        随便观 - 售卖铺

        需要在随便观主界面时候调用，完成后返回随便观主界面

        操作步骤
        0. 前往售卖铺画面
        1. 点击库存不足，取消售卖
        2. 点击开始售卖，没有 -> 最后一步
        3. 库存不足 -> 选择新的商品
        4. 库存充足 -> 开始售卖 返回了售卖铺画面
        5. 没有新的商品 -> 最后一步
        6. 返回随便观

        Args:
            ctx: 上下文
        """
        ZOperation.__init__(
            self, ctx,
            op_name=f'{gt("随便观", "game")} {gt("售卖铺", "game")}'
        )

    @operation_node(name='前往售卖铺', is_start_node=True)
    def goto_sales_stall(self) -> OperationRoundResult:
        current_screen_name = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=['随便观-售卖铺'])
        if current_screen_name is not None:
            return self.round_success(status=current_screen_name)

        target_cn_list: list[str] = [
            '经营',
            '售卖',
        ]
        ignore_cn_list: list[str] = [
        ]
        result = self.round_by_ocr_and_click_by_priority(target_cn_list, ignore_cn_list=ignore_cn_list)
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)

        return self.round_retry(status='未识别当前画面', wait=1)

    @node_from(from_name='前往售卖铺')
    @operation_node(name='更换邦布')
    def choose_another_bangboo(self) -> OperationRoundResult:
        # 偷懒 直接点击
        self.round_by_click_area(
            '随便观-售卖铺', '区域-选择邦布',
            success_wait=1, retry_wait=1
        )

        self.round_by_click_area(
            "随便观-售卖铺", "区域-第二只邦布",
            success_wait=1, retry_wait=1
        )

        self.round_by_click_area(
            "随便观-售卖铺", "按钮-确认派驻",
            success_wait=1, retry_wait=1
        )

        return self.round_success()

    @node_from(from_name='更换邦布')
    @node_from(from_name='取消售卖后返回售卖铺')
    @operation_node(name='选择库存不足货架', node_max_retry_times=2)
    def choose_shelf_with_not_enough(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            '库存不足',
        ]
        ignore_cn_list: list[str] = [
        ]
        return self.round_by_ocr_and_click_by_priority(
            target_cn_list=target_cn_list,
            ignore_cn_list=ignore_cn_list,
            success_wait=1,
            retry_wait=0.3,
        )

    @node_from(from_name='选择库存不足货架')
    @operation_node(name='点击取消售卖')
    def cancel_selling(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            '取消售卖',
        ]
        ignore_cn_list: list[str] = [
        ]
        return self.round_by_ocr_and_click_by_priority(
            target_cn_list=target_cn_list,
            ignore_cn_list=ignore_cn_list,
            success_wait=1,
            retry_wait=0.5,
        )

    @node_from(from_name='点击取消售卖')
    @operation_node(name='取消售卖后返回售卖铺')
    def back_from_cancel_selling(self) -> OperationRoundResult:
        current_screen_name = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=['随便观-售卖铺'])
        if current_screen_name is not None:
            return self.round_success(status=current_screen_name)

        result = self.round_by_click_area("随便观-售卖铺", "按钮-返回")
        return self.round_retry(status=result.status, wait=1)

    @node_from(from_name='选择库存不足货架', success=False)
    @node_from(from_name='点击开始售卖')
    @operation_node(name='选择货架开始售卖', node_max_retry_times=2)
    def click_choose_shelf_sell(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            '开始售卖',
            '售卖铺',
        ]
        ignore_cn_list: list[str] = [
            '售卖铺',
        ]
        return self.round_by_ocr_and_click_by_priority(
            target_cn_list=target_cn_list,
            ignore_cn_list=ignore_cn_list,
            success_wait=1,
            retry_wait=0.3,
        )

    @node_from(from_name="选择货架开始售卖")
    @operation_node(name="选择商品")
    def choose_item(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            "库存不足",
        ]
        result = self.round_by_ocr_and_click_by_priority(target_cn_list)
        if result.is_success:
            # 这个画面应该有排序 只要出现库存不足 那下方都是库存不足的
            return self.round_success(status=result.status)
        else:
            return self.round_success(status="库存充足")

    @node_from(from_name='选择商品')
    @operation_node(name='点击开始售卖')
    def click_start_selling(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            '开始售卖',
        ]
        return self.round_by_ocr_and_click_by_priority(target_cn_list, success_wait=1, retry_wait=1)

    @node_from(from_name='选择货架开始售卖', success=False)
    @node_from(from_name='选择商品', status='库存不足')
    @node_from(from_name='选择商品', success=False)
    @operation_node(name='返回随便观')
    def back_to_entry(self) -> OperationRoundResult:
        current_screen_name = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=['随便观-入口'])
        if current_screen_name is not None:
            return self.round_success()

        result = self.round_by_find_and_click_area(self.last_screenshot, '菜单', '返回')
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)
        else:
            return self.round_retry(status=result.status, wait=1)


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.run_context.start_running()
    ctx.run_context.current_instance_idx = ctx.current_instance_idx
    ctx.run_context.current_app_id = 'suibian_temple'
    ctx.run_context.current_group_id = 'one_dragon'
    op = SuibianTempleSalesStall(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()
