import cv2
from cv2.typing import MatLike
from typing import ClassVar

from one_dragon.base.matcher.match_result import MatchResultList, MatchResult
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext
from zzz_od.hollow_zero.event import hollow_event_utils, resonium_utils
from zzz_od.operation.zzz_operation import ZOperation


class BambooMerchant(ZOperation):

    STATUS_LEVEL_1: ClassVar[str] = '外层选择'
    STATUS_LEVEL_2_BUY: ClassVar[str] = '二级标题-鸣徽交易'
    STATUS_LEVEL_2_UPGRADE: ClassVar[str] = '二级标题-鸣徽催化'
    NOT_TO_BUY: ClassVar[str] = '不购买'

    def __init__(self, ctx: ZContext):
        """
        在邦布商人的画面了 尽量购买
        :param ctx:
        """
        ZOperation.__init__(
            self, ctx,
            op_name=gt('邦布商人', 'game')
        )

    @node_from(from_name='购买后确定')
    @operation_node(name='画面识别', is_start_node=True)
    def check_screen(self) -> OperationRoundResult:
        screen = self.screenshot()

        area = self.ctx.screen_loader.get_area('零号空洞-商店', '二级标题')
        result = self.round_by_ocr(screen, '交易', area=area, lcs_percent=1)
        if result.is_success:
            return self.round_success(status=BambooMerchant.STATUS_LEVEL_2_BUY)

        result = self.round_by_ocr(screen, '特价折扣', area=area, lcs_percent=1)
        if result.is_success:
            return self.round_success(status=BambooMerchant.STATUS_LEVEL_2_BUY)

        result = self.round_by_ocr(screen, '催化', area=area, lcs_percent=1)
        if result.is_success:
            return self.round_success(status=BambooMerchant.STATUS_LEVEL_2_UPGRADE)

        result = self.round_by_ocr(screen, '血汗交易', area=area, lcs_percent=0.6)
        if result.is_success:
            return self.round_success(status=BambooMerchant.NOT_TO_BUY)

        area = self.ctx.screen_loader.get_area('零号空洞-事件', '底部-选择列表')
        result = self.round_by_ocr_and_click(screen, '确定', area=area)
        if result.is_success:
            return self.round_wait(wait=1)

        area = hollow_event_utils.get_event_text_area(self.ctx)
        result = self.round_by_ocr_and_click(screen, '进入商店', area=area, lcs_percent=0.6)
        if result.is_success:
            return self.round_wait(wait=1)

        result = self.round_by_ocr(screen, '血汗交易', area=area, lcs_percent=0.6)
        if result.is_success:
            return self.round_success(BambooMerchant.NOT_TO_BUY)

        result = self.round_by_ocr(screen, '鸣徽交易', area=area, lcs_percent=0.6)
        if result.is_success:
            return self.round_success(BambooMerchant.STATUS_LEVEL_1)

        result = self.round_by_ocr(screen, '特价折扣', area=area)
        if result.is_success:
            return self.round_success(BambooMerchant.STATUS_LEVEL_1)

        return self.round_retry('未知画面', wait=1)

    @node_from(from_name='画面识别', status=STATUS_LEVEL_1)
    @operation_node(name='鸣徽交易')
    def choose_buy(self) -> OperationRoundResult:
        screen = self.screenshot()
        area = hollow_event_utils.get_event_text_area(self.ctx)

        result = self.round_by_ocr_and_click(screen, '鸣徽交易', area=area)
        if result.is_success:
            return self.round_success(BambooMerchant.STATUS_LEVEL_2_BUY, wait=1)

        result = self.round_by_ocr_and_click(screen, '特价折扣', area=area)
        if result.is_success:
            return self.round_success(BambooMerchant.STATUS_LEVEL_2_BUY, wait=1)

        return self.round_retry(status=result.status, wait=1)

    @node_from(from_name='画面识别', status=STATUS_LEVEL_2_BUY)
    @node_from(from_name='鸣徽交易')
    @operation_node(name='选择鸣徽')
    def choose_item(self) -> OperationRoundResult:
        screen = self.screenshot()

        price_ocr_result_map = self._ocr_price_area(screen)
        price_pos_list = [i.center for mrl in price_ocr_result_map.values() for i in mrl]

        desc_ocr_result_map = self._ocr_desc_area(screen)
        item_list = []
        pos_list = []
        # 只保留有价格的
        for ocr_result, mrl in desc_ocr_result_map.items():
            item = self.ctx.hollow.data_service.match_resonium_by_ocr_full(ocr_result)
            log.info('%s 匹配鸣徽 %s' % (ocr_result, item.name if item is not None else 'none'))
            if item is None:
                continue
            with_price: bool = False
            for price in price_pos_list:
                if price.y > mrl.max.center.y and price.y - mrl.max.center.y < 150:
                    with_price = True
                    break

            if not with_price:
                continue
            item_list.append(item)
            pos_list.append(mrl.max.center)

        if len(item_list) > 0:
            idx_list = resonium_utils.choose_resonium_by_priority(item_list, self.ctx.hollow_zero_challenge_config.resonium_priority,
                                                                  only_priority=self.ctx.hollow_zero_challenge_config.buy_only_priority)
            if len(idx_list) > 0:
                to_choose = pos_list[idx_list[0]]
            else:
                to_choose = None
        else:
            to_choose = None
            for price in price_pos_list:
                if to_choose is None or price.y > to_choose.y:
                    to_choose = price

        if to_choose is None:
            return self.round_success(BambooMerchant.NOT_TO_BUY, wait=1)
        else:
            self.ctx.controller.click(to_choose)
            return self.round_success(wait=1)

    def _ocr_price_area(self, screen: MatLike) -> dict[str, MatchResultList]:
        area = self.ctx.screen_loader.get_area('零号空洞-商店', '商品价格区域')
        part = cv2_utils.crop_image_only(screen, area.rect)
        mask = cv2.inRange(part, (240, 140, 0), (255, 255, 50))
        mask = cv2_utils.dilate(mask, 5)

        to_ocr = cv2.bitwise_and(part, part, mask=mask)
        # cv2_utils.show_image(to_ocr, wait=0)

        result_result_map = {}
        ocr_result_map = self.ctx.ocr.run_ocr(to_ocr)
        for ocr_result, mrl in ocr_result_map.items():
            digit = str_utils.get_positive_digits(ocr_result, None)
            if digit is None:  # 忽略没有数字的
                continue
            mrl.add_offset(area.left_top)
            result_result_map[ocr_result] = mrl

        if len(result_result_map) == 0:
            # 没有识别的情况 可能是价格为0识别不到 额外再每个价格格子识别一次
            for i in range(2, 4):
                for j in range(1, i+1):
                    area = self.ctx.screen_loader.get_area('零号空洞-商店', f'商品价格-{i}-{j}')
                    part = cv2_utils.crop_image_only(screen, area.rect)
                    mask = cv2.inRange(part, (240, 140, 0), (255, 255, 50))
                    mask = cv2_utils.dilate(mask, 5)
                    to_ocr = cv2.bitwise_and(part, part, mask=mask)
                    # 底层onnx的ocr 使用 run_ocr 会对只有一个0的情况识别不到 只能用这个方法
                    ocr_result = self.ctx.ocr.run_ocr_single_line(to_ocr)
                    for special_char in ['.', '。', 'o', 'O']:  # 0 有可能被识别成其它字符 特殊处理
                        ocr_result = ocr_result.replace(special_char, '0')
                    digit = str_utils.get_positive_digits(ocr_result, None)
                    if digit is None:
                        continue
                    # 构造返回结果
                    digit_str = str(digit)
                    if digit_str not in result_result_map:
                        result_result_map[digit_str] = MatchResultList(only_best=False)
                    result_result_map[digit_str].append(
                        MatchResult(1, area.left_top.x, area.left_top.y, area.width, area.height,
                                    data=digit_str)
                    )

        return ocr_result_map

    def _ocr_desc_area(self, screen: MatLike) -> dict[str, MatchResultList]:
        area = self.ctx.screen_loader.get_area('零号空洞-商店', '商品描述区域')
        part = cv2_utils.crop_image_only(screen, area.rect)
        ocr_result_map = self.ctx.ocr.run_ocr(part)
        for mrl in ocr_result_map.values():
            mrl.add_offset(area.left_top)

        return ocr_result_map

    @node_from(from_name='选择鸣徽')
    @operation_node(name='购买')
    def buy(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '零号空洞-商店', '商品购买区域')

    @node_from(from_name='购买')
    @operation_node(name='购买后确定')
    def confirm(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '零号空洞-商店', '购买后确定',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='画面识别', status=STATUS_LEVEL_2_UPGRADE)
    @operation_node(name='鸣徽催化')
    def upgrade_resonium(self) -> OperationRoundResult:
        return self.round_success()

    @node_from(from_name='画面识别', status=NOT_TO_BUY)
    @node_from(from_name='选择鸣徽', status=NOT_TO_BUY)
    @node_from(from_name='鸣徽催化')
    @node_from(from_name='鸣徽交易', success=False)  # 在第一层找到选项 就退出
    @operation_node(name='返回')
    def back(self) -> OperationRoundResult:
        screen = self.screenshot()
        result1 = self.round_by_find_and_click_area(screen, '零号空洞-商店', '右上角-返回',
                                                    success_wait=1.5, retry_wait=1)

        if not result1.is_success:
            return self.round_retry(status=result1.status)

        return self.round_by_find_and_click_area(screen, '零号空洞-商店', '右上角-返回',
                                                 success_wait=1, retry_wait=1)


def __debug_check_screen():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    op = BambooMerchant(ctx)
    from one_dragon.utils import os_utils
    import os
    screen = cv2_utils.read_image(os.path.join(
        os_utils.get_path_under_work_dir('.debug', 'devtools', 'screen', 'hollow_zero_merchant'),
        '_1725071431457.png'
    ))
    from one_dragon.utils import debug_utils
    screen = debug_utils.get_debug_image('1')
    print(op._ocr_price_area(screen))
    area = hollow_event_utils.get_event_text_area(op.ctx)
    print(op.round_by_ocr(screen, '鸣徽交易', area=area, lcs_percent=0.6).status)


if __name__ == '__main__':
    __debug_check_screen()