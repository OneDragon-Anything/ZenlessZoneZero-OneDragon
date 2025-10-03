from enum import StrEnum
from typing import Optional

from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cal_utils, str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.suibian_temple.suibian_temple_config import (
    PawnshopCrestGoods,
    PawnshopOmnicoinGoods,
    SuibianTempleConfig,
)
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class GoodsPos:

    def __init__(self, name: str, pos: Rect):
        self.name: str = name
        self.pos: Rect = pos
        self.sold_out: bool = False
        self.unlimited: bool = False


class SuibianTemplePawnshop(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        随便观 - 德丰大押

        需要在随便观主界面时候调用，完成后返回随便观主界面

        操作步骤
        0. 进入德丰大押画面
        1. 切换到 百通宝-周期
        2. 找到未售罄商品 按优先级兑换
        3. 切换到 云纹徽-周期
        4. 找到未售罄且限购的商品 按优先级兑换
        5. 找到不限购商品

        Args:
            ctx: 上下文
        """
        ZOperation.__init__(
            self, ctx,
            op_name=f'{gt("随便观", "game")} {gt("德丰大押", "game")}'
        )

        self.config: Optional[SuibianTempleConfig] = self.ctx.run_context.get_config(app_id='suibian_temple')

        self.chosen_goods_list: list[str] = []  # 已经选择过的商品
        self.chosen_unlimited_goods_list: list[str] = []  # 已经选择过的不限购商品

    @operation_node(name='前往德丰大押', is_start_node=True)
    def goto_pawnshop(self) -> OperationRoundResult:
        current_screen_name = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=['随便观-德丰大押'])
        if current_screen_name is not None:
            return self.round_success(status=current_screen_name)

        target_cn_list: list[str] = [
            '邻里街坊',
            '德丰大押',
        ]
        ignore_cn_list: list[str] = [
        ]
        result = self.round_by_ocr_and_click_by_priority(target_cn_list, ignore_cn_list=ignore_cn_list)
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)

        return self.round_retry(status='未识别当前画面', wait=1)

    @node_from(from_name='前往德丰大押')
    @operation_node(name='切换到百通宝-周期')
    def goto_omnicoin(self) -> OperationRoundResult:
        if not self.config.pawnshop_omnicoin_enabled:
            return self.round_success(status='未开启')

        return self.round_by_find_and_click_area(
            self.last_screenshot,
            '随便观-德丰大押',
            '按钮-百通宝-周期',
            success_wait=1,
            retry_wait=1,
        )

    @node_from(from_name='切换到百通宝-周期')
    @node_from(from_name='购买百通宝商品后处理')
    @operation_node(name='选择百通宝商品', node_max_retry_times=2)
    def choose_omnicoin_goods(self) -> OperationRoundResult:
        goods_pos = self.get_goods_pos_list(self.last_screenshot, PawnshopOmnicoinGoods)

        for target in self.config.pawnshop_omnicoin_priority:
            target_goods = PawnshopOmnicoinGoods[target]
            for goods in goods_pos:
                if goods.name != str(target_goods):
                    continue
                if goods.name in self.chosen_goods_list:
                    continue

                self.chosen_goods_list.append(goods.name)
                self.ctx.controller.click(goods.pos.center)
                return self.round_success(status=goods.name, wait=1)

        return self.round_retry(status='未找到可购买商品', wait=0.3)

    @node_from(from_name='选择百通宝商品')
    @operation_node(name='购买百通宝商品')
    def buy_omnicoin_goods(self) -> OperationRoundResult:
        return self.buy_goods()

    @node_from(from_name='购买百通宝商品')
    @operation_node(name='购买百通宝商品后处理')
    def after_buy_omnicoin_goods(self) -> OperationRoundResult:
        return self.after_buy()

    @node_from(from_name='切换到百通宝-周期', status='未开启')
    @node_from(from_name='选择百通宝商品', success=False)
    @operation_node(name='切换到云纹徽-周期')
    def goto_crest(self) -> OperationRoundResult:
        if not self.config.pawnshop_crest_enabled:
            return self.round_success(status='未开启')

        return self.round_by_find_and_click_area(
            self.last_screenshot,
            '随便观-德丰大押',
            '按钮-云纹徽-周期',
            success_wait=1,
            retry_wait=1,
        )

    @node_from(from_name='切换到云纹徽-周期')
    @node_from(from_name='购买云纹徽商品后处理')
    @operation_node(name='选择云纹徽商品', node_max_retry_times=2)
    def choose_crest_goods(self) -> OperationRoundResult:
        goods_pos = self.get_goods_pos_list(self.last_screenshot, PawnshopCrestGoods)

        for target in self.config.pawnshop_crest_priority:
            target_goods = PawnshopCrestGoods[target]
            for goods in goods_pos:
                if goods.name != str(target_goods):
                    continue
                if goods.name in self.chosen_goods_list:
                    continue
                if goods.unlimited:
                    continue

                self.chosen_goods_list.append(goods.name)

                self.ctx.controller.click(goods.pos.center)
                return self.round_success(status=goods.name, wait=1)

        if self.config.pawnshop_crest_unlimited_denny_enabled:
            for goods in goods_pos:
                if not goods.unlimited:
                    continue
                if goods.name in self.chosen_unlimited_goods_list:
                    continue

                self.chosen_unlimited_goods_list.append(goods.name)
                self.ctx.controller.click(goods.pos.center)
                return self.round_success(status=goods.name, wait=1)

        return self.round_retry(status='未找到可购买商品', wait=0.3)

    @node_from(from_name='选择云纹徽商品')
    @operation_node(name='购买云纹徽商品')
    def buy_crest_goods(self) -> OperationRoundResult:
        return self.buy_goods()

    @node_from(from_name='购买云纹徽商品')
    @operation_node(name='购买云纹徽商品后处理')
    def after_buy_crest_goods(self) -> OperationRoundResult:
        return self.after_buy()

    def get_goods_pos_list(self, screen: MatLike, goods: type[StrEnum]) -> list[GoodsPos]:
        ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
            screen,
            rect=self.ctx.screen_loader.get_area('随便观-德丰大押', '区域-商品列表').rect,
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

            target_goods: Optional[GoodsPos] = None
            for goods in goods_list:
                # 已售罄在商品名称下方
                if not ocr_result.rect.center.y > goods.pos.center.y:
                    continue
                # 找距离最近的
                if target_goods is None:
                    old_dis = 9999
                else:
                    old_dis = cal_utils.distance_between(target_goods.pos.center, ocr_result.center)

                new_ids = cal_utils.distance_between(goods.pos.center, ocr_result.center)
                if new_ids < old_dis:
                    target_goods = goods

            if idx == 0:  # 已售罄
                target_goods.sold_out = True
            elif idx == 1:  # 不限购
                target_goods.unlimited = True

        filter_goods_list = [goods for goods in goods_list if not goods.sold_out]
        log.info('可购买商品列表: %s', [goods.name for goods in filter_goods_list])

        return filter_goods_list

    def buy_goods(self) -> OperationRoundResult:
        result = self.round_by_ocr_and_click_by_priority(
            target_cn_list=[
                '[百通宝]数量不足',
                '[云纹徽]数量不足',
                '已达背包容量上限',  # issue #1449
            ],
        )
        if result.is_success:
            return self.round_success(status=result.status)

        start_point = self.ctx.screen_loader.get_area('随便观-德丰大押', '按钮-购买件数-最小').rect.center
        end_point = self.ctx.screen_loader.get_area('随便观-德丰大押', '按钮-购买件数-最大').rect.center

        self.ctx.controller.drag_to(
            start=start_point,
            end=end_point + Point(50, 0),
            duration=2,
        )

        return self.round_by_find_and_click_area(
            self.last_screenshot,
            '随便观-德丰大押',
            '按钮-确认',
            success_wait=1,
            retry_wait=1,
        )

    def after_buy(self) -> OperationRoundResult:
        screen_name = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=['随便观-德丰大押'])
        if screen_name is not None:
            return self.round_success(status=screen_name)

        # 判断是否有货币不足的情况
        ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
            self.last_screenshot,
            rect=self.ctx.screen_loader.get_area(
                "随便观-德丰大押", "区域-购买货币"
            ).rect,
            color_range=[[170, 50, 40], [200, 65, 50]],
        )
        for ocr_result in ocr_result_list:
            digit = str_utils.get_positive_digits(ocr_result.data, err=None)
            if digit is not None:
                result = self.round_by_click_area('随便观-德丰大押', '按钮-兑换关闭')
                return self.round_wait(status=result.status, wait=1)

        result = self.round_by_ocr_and_click_by_priority(
            target_cn_list=[
                '[百通宝]数量不足',
                '[云纹徽]数量不足',
                '已达背包容量上限',
                '确认'
            ],
        )
        if result.is_success and result.status == '确认':
            return self.round_wait(status=result.status, wait=1)

        self.round_by_click_area('随便观-德丰大押', '按钮-兑换关闭')

        return self.round_retry(status='未识别当前画面', wait=1)

    @node_from(from_name='切换到云纹徽-周期', status='未开启')
    @node_from(from_name='购买百通宝商品', success=False)
    @node_from(from_name='购买百通宝商品后处理', success=False)
    @node_from(from_name='选择云纹徽商品', success=False)
    @node_from(from_name='购买云纹徽商品', success=False)
    @node_from(from_name='购买云纹徽商品后处理', success=False)
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

    op = SuibianTemplePawnshop(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()