from enum import StrEnum

from cv2.typing import MatLike

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cal_utils, str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.logistics_shop.logistics_shop_config import (
    LogisticsShopConfig,
    LogisticsShopGoods,
)
from zzz_od.application.logistics_shop.logistics_shop_run_record import (
    LogisticsShopRunRecord,
)
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation

POWER_CARD_COST = 120  # 储值电卡(限购)单价 零号业绩


class GoodsPos:

    def __init__(self, name: str, pos: Rect):
        self.name: str = name
        self.pos: Rect = pos
        self.sold_out: bool = False
        self.unlimited: bool = False


class LogisticsShopBuy(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        快捷手册 - 哨站后勤

        需要在普通大世界时调用，完成后返回大世界

        操作步骤
        0. 通过快捷手册作战页进入哨站后勤商店
        1. 找到未售罄且限购的 储值电卡 按限额逐张购买
        2. 开启开关时 用深度清扫服务卡购买不限购的 储值电卡(每轮1张)
        3. 返回快捷手册

        Args:
            ctx: 上下文
        """
        ZOperation.__init__(
            self, ctx,
            op_name=f'{gt("快捷手册", "game")} {gt("哨站后勤", "game")}'
        )

        self.config: LogisticsShopConfig = self.ctx.run_context.get_config(
            app_id='logistics_shop',
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )
        self.run_record: LogisticsShopRunRecord = self.ctx.run_context.get_run_record(
            app_id='logistics_shop',
            instance_idx=self.ctx.current_instance_idx,
        )

        self.run_buy_times: int = 0  # 本轮已购买的目标储值电卡数量
        self.confirm_clicked: bool = False  # 本次购买流程是否点击过确认

    @operation_node(name='前往哨站后勤', is_start_node=True, timeout_seconds=120)
    def goto_shop(self) -> OperationRoundResult:
        return self.round_by_goto_screen(
            self.last_screenshot,
            '哨站后勤-商店',
            success_wait=1,
            retry_wait=1,
        )

    @node_from(from_name='前往哨站后勤')
    @node_from(from_name='购买目标商品后处理', status='继续购买')
    @operation_node(name='选择目标商品', node_max_retry_times=2)
    def choose_target_goods(self) -> OperationRoundResult:
        # 月度限额
        if self.run_record.monthly_bought >= self.config.monthly_limit:
            return self.round_success(status='已达月度限额')

        # 单轮购买上限
        if self.run_buy_times >= self.config.single_run_limit:
            return self.round_success(status='已达单轮上限')

        # 保底零号业绩
        balance = self.get_performance_balance()
        if balance is not None and balance - POWER_CARD_COST < self.config.min_performance_reserve:
            return self.round_success(status='零号业绩不足')

        self.confirm_clicked = False
        goods_pos_list = self.get_goods_pos_list(self.last_screenshot, LogisticsShopGoods)

        # 目标条目: 限购的储值电卡(不限购条目走深度清扫服务卡阶段)
        for goods in goods_pos_list:
            if goods.name != str(LogisticsShopGoods.PREPAID_POWER_CARD):
                continue
            if goods.unlimited:
                continue

            self.ctx.controller.click(goods.pos.center)
            return self.round_success(status=goods.name, wait=1)

        return self.round_retry(status='未找到可购买商品', wait=0.5)

    @node_from(from_name='选择目标商品')
    @operation_node(name='购买目标商品', node_max_retry_times=2)
    def buy_target_goods(self) -> OperationRoundResult:
        return self.buy_goods()

    @node_from(from_name='购买目标商品')
    @node_from(from_name='购买目标商品', success=False)
    @operation_node(name='购买目标商品后处理', node_max_retry_times=5)
    def after_buy_target_goods(self) -> OperationRoundResult:
        return self.after_buy_target()

    @node_from(from_name='选择目标商品', status='已达月度限额')
    @node_from(from_name='选择目标商品', status='已达单轮上限')
    @node_from(from_name='选择目标商品', status='零号业绩不足')
    @node_from(from_name='选择目标商品', success=False)
    @node_from(from_name='购买目标商品后处理', status='目标购买完成')
    @node_from(from_name='购买目标商品后处理', success=False)
    @operation_node(name='选择不限购商品', node_max_retry_times=2)
    def choose_cleaning_card_goods(self) -> OperationRoundResult:
        if not self.config.cleaning_card_enabled:
            return self.round_success(status='未开启')

        self.confirm_clicked = False
        goods_pos_list = self.get_goods_pos_list(self.last_screenshot, LogisticsShopGoods)

        # 不限购条目: 储值电卡 @10 深度清扫服务卡
        for goods in goods_pos_list:
            if goods.name != str(LogisticsShopGoods.PREPAID_POWER_CARD):
                continue
            if not goods.unlimited:
                continue

            self.ctx.controller.click(goods.pos.center)
            return self.round_success(status=goods.name, wait=1)

        return self.round_success(status='未找到可购买商品')

    @node_from(from_name='选择不限购商品')
    @operation_node(name='购买不限购商品', node_max_retry_times=2)
    def buy_cleaning_card_goods(self) -> OperationRoundResult:
        return self.buy_goods()

    @node_from(from_name='购买不限购商品')
    @node_from(from_name='购买不限购商品', success=False)
    @operation_node(name='购买不限购商品后处理', node_max_retry_times=5)
    def after_buy_cleaning_card_goods(self) -> OperationRoundResult:
        return self.after_buy_cleaning_card()

    @node_from(from_name='选择不限购商品', status='未开启')
    @node_from(from_name='选择不限购商品', status='未找到可购买商品')
    @node_from(from_name='选择不限购商品', success=False)
    @node_from(from_name='购买不限购商品后处理')
    @node_from(from_name='购买不限购商品后处理', success=False)
    @operation_node(name='返回快捷手册', node_max_retry_times=10)
    def back_to_compendium(self) -> OperationRoundResult:
        current_screen_name = self.check_and_update_current_screen(
            self.last_screenshot, screen_name_list=['哨站后勤-商店']
        )
        if current_screen_name is None:
            return self.round_success()

        result = self.round_by_click_area('哨站后勤-商店', '按钮-返回')
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)
        else:
            return self.round_retry(status=result.status, wait=1)

    def get_goods_pos_list(self, screen: MatLike, goods: type[StrEnum]) -> list[GoodsPos]:
        list_area = self.ctx.screen_loader.get_area('哨站后勤-商店', '区域-商品列表')
        ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
            screen,
            rect=list_area.rect,
        )

        goods_list: list[GoodsPos] = []
        target_word_list: list[str] = [str(i) for i in goods]
        for ocr_result in ocr_result_list:
            idx = str_utils.find_best_match_by_difflib(
                ocr_result.data, target_word_list
            )
            if idx is None:
                continue

            goods_list.append(GoodsPos(name=target_word_list[idx], pos=ocr_result.rect))

        log.info('识别商品列表: %s', [goods.name for goods in goods_list])

        # 过滤已售罄的商品
        for ocr_result in ocr_result_list:
            idx = str_utils.find_best_match_by_difflib(
                ocr_result.data, ['已售罄', '不限购', '限购x']
            )
            if idx is None:
                continue

            target_goods: GoodsPos | None = None
            for goods in goods_list:
                # 限购说明在商品名称下方
                if not ocr_result.rect.center.y > goods.pos.center.y:
                    continue
                # 找距离最近的
                if target_goods is None:
                    old_dis = 9999
                else:
                    old_dis = cal_utils.distance_between(target_goods.pos.center, ocr_result.center)

                new_dis = cal_utils.distance_between(goods.pos.center, ocr_result.center)
                if new_dis < old_dis:
                    target_goods = goods

            if idx == 0:  # 已售罄
                target_goods.sold_out = True
            elif idx == 1:  # 不限购
                target_goods.unlimited = True

        filter_goods_list = [goods for goods in goods_list if not goods.sold_out]
        log.info('可购买商品列表: %s', [goods.name for goods in filter_goods_list])

        return filter_goods_list

    def get_performance_balance(self) -> int | None:
        """识别零号业绩余额"""
        area = self.ctx.screen_loader.get_area('哨站后勤-商店', '区域-零号业绩余额')
        ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
            self.last_screenshot,
            rect=area.rect,
        )

        balance: int | None = None
        for ocr_result in ocr_result_list:
            digit = str_utils.get_positive_digits(ocr_result.data, None)
            if digit is not None:
                # 余额是区域内唯一的数字 取最大值 避免前导0被拆分识别
                if balance is None or digit > balance:
                    balance = digit

        return balance

    def buy_goods(self) -> OperationRoundResult:
        # 数量不足等提示 只识别不点击
        # 注意不能放「已售罄」 背景商品卡上可能带该文字 会误判
        for word in ['零号业绩不足', '深度清扫服务卡不足', '已达购买上限']:
            result = self.round_by_ocr(self.last_screenshot, word)
            if result.is_success:
                return self.round_success(status=result.status, wait=1)

        # 点击购买确认弹窗
        result = self.round_by_find_and_click_area(
            self.last_screenshot,
            '哨站后勤-商店',
            '按钮-购买-确认',
            success_wait=1,
            retry_wait=0.5,
        )
        if result.is_success:
            self.confirm_clicked = True
            return self.round_success(status=result.status)

        return self.round_retry(status='未找到购买确认按钮', wait=0.5)

    def after_buy_target(self) -> OperationRoundResult:
        # 优先关闭可能残留的弹窗(购买确认/获得奖励)
        result = self.round_by_find_and_click_area(
            self.last_screenshot,
            '哨站后勤-商店',
            '按钮-购买-确认',
            success_wait=1,
            retry_wait=0.5,
        )
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)

        screen_name = self.check_and_update_current_screen(
            self.last_screenshot, screen_name_list=['哨站后勤-商店']
        )
        if screen_name is None:
            # 其他弹窗 尝试点击确认
            result = self.round_by_ocr_and_click_by_priority(target_cn_list=['确认'])
            if result.is_success:
                return self.round_wait(status=result.status, wait=1)

            return self.round_retry(status='未识别当前画面', wait=1)

        # 没有确认过购买(数量不足提示等) 结束目标阶段
        if not self.confirm_clicked:
            return self.round_success(status='目标购买完成')

        # 确认过购买 计入月度限额
        self.run_buy_times += 1
        self.run_record.add_monthly_bought(1)

        if (self.run_buy_times >= self.config.single_run_limit
                or self.run_record.monthly_bought >= self.config.monthly_limit):
            return self.round_success(status='目标购买完成')

        return self.round_success(status='继续购买')

    def after_buy_cleaning_card(self) -> OperationRoundResult:
        # 优先关闭可能残留的弹窗(购买确认/获得奖励)
        result = self.round_by_find_and_click_area(
            self.last_screenshot,
            '哨站后勤-商店',
            '按钮-购买-确认',
            success_wait=1,
            retry_wait=0.5,
        )
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)

        screen_name = self.check_and_update_current_screen(
            self.last_screenshot, screen_name_list=['哨站后勤-商店']
        )
        if screen_name is None:
            # 其他弹窗 尝试点击确认
            result = self.round_by_ocr_and_click_by_priority(target_cn_list=['确认'])
            if result.is_success:
                return self.round_wait(status=result.status, wait=1)

            return self.round_retry(status='未识别当前画面', wait=1)

        return self.round_success(status='不限购购买完成')


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.run_context.start_running()
    ctx.run_context.current_instance_idx = ctx.current_instance_idx
    ctx.run_context.current_app_id = 'logistics_shop'
    ctx.run_context.current_group_id = 'one_dragon'

    op = LogisticsShopBuy(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()
