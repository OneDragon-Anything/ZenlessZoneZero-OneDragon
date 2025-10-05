import re
from typing import Optional

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.matcher.ocr.ocr_match_result import OcrMatchResult
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import str_utils, cal_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.suibian_temple.suibian_temple_config import SuibianTempleConfig
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class SuibianTempleCraftDispatch(ZOperation):

    def __init__(
        self,
        ctx: ZContext,
        from_craft: bool,
        chosen_item_list: list[str],
    ):
        """
        随便观 - 制造 - 派驻

        需要在随便观制造坊选择商品和邦布的页面调用，完成后退出这个页面。
        返回结果的 data=done_craft

        操作步骤
        1. 先处理邦布电量不足 or 未选择邦布，选择一个邦布。无法选择则退出。
        2. 选择一个有材料可制造的商品。无法选择则退出。
        3. 点击开始制造，处理后续的弹窗确认。
        """
        ZOperation.__init__(
            self, ctx, op_name=f"{gt('随便观', 'game')} {gt('制造派驻', 'game')}"
        )
        self.config: Optional[SuibianTempleConfig] = self.ctx.run_context.get_config(
            app_id="suibian_temple"
        )

        self.from_craft: bool = from_craft  # 是否来源制造坊，不是的话就是饮茶仙来的

        self.current_bangboo_idx: int = 1  # 当前选择的邦布下标
        self.bangboo_dispatch_clicked: bool = False  # 是否已经点击了邦布派驻
        self.last_item_list: list[str] = []  # 上一次的商品列表
        self.chosen_item_list: list[str] = chosen_item_list  # 已经选择过的商品列表
        self.scroll_after_choose: bool = False  # 选择后是否已经滑动了
        self.drag_times: int = 0  # 下拉次数

        self.done_craft: bool = False  # 是否点击了开始制造

    @operation_node(name='检查邦布', node_max_retry_times=1, is_start_node=True)
    def check_bangboo(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            '邦布电量不足',
            '未选择邦布',
            '请先选择邦布',
        ]
        return self.round_by_ocr_and_click_by_priority(
            target_cn_list,
            success_wait=1,
            retry_wait=0.5,
        )

    @node_from(from_name='检查邦布')
    @operation_node(name='打开选择邦布')
    def open_choose_bangboo(self) -> OperationRoundResult:
        self.current_bangboo_idx = 1
        return self.round_by_click_area('随便观-制造坊', '区域-选择邦布',
                                        success_wait=1, retry_wait=1)

    @node_from(from_name='打开选择邦布')
    @node_from(from_name='点击派驻', status='无法派驻')
    @operation_node(name='选择邦布')
    def choose_bangboo(self) -> OperationRoundResult:
        while True:
            if self.current_bangboo_idx > 8:
                return self.round_success(status='没有合适邦布')
            area = self.ctx.screen_loader.get_area('随便观-制造坊', f'区域-邦布-{self.current_bangboo_idx}')

            is_working: bool = False
            ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(self.last_screenshot)
            for ocr_result in ocr_result_list:
                if not (
                    ocr_result.data == gt('制造中')
                    or ocr_result.data == gt('游历中')
                    or ocr_result.data == gt('售卖中')
                ):
                    continue
                if cal_utils.cal_overlap_percent(ocr_result.rect, area.rect, base=ocr_result.rect) > 0.7:
                    is_working = True
                    break

            if is_working:
                self.current_bangboo_idx += 1
            else:
                break

        self.ctx.controller.click(area.center)
        return self.round_success(status='已选择邦布')

    @node_from(from_name='选择邦布', status='已选择邦布')
    @operation_node(name='点击派驻')
    def click_bangboo_dispatch(self) -> OperationRoundResult:
        if self.bangboo_dispatch_clicked:
            result = self.round_by_find_area(
                screen=self.last_screenshot,
                screen_name='随便观-制造坊',
                area_name='按钮-街区'
            )
            if result.is_success:
                self.current_bangboo_idx += 1
                return self.round_success(status='无法派驻')
            else:
                return self.round_success(status='派驻完成')

        target_cn_list: list[str] = [
            '确认派驻',
        ]
        result = self.round_by_ocr_and_click_by_priority(target_cn_list)
        if result.is_success:
            self.bangboo_dispatch_clicked = True
            return self.round_wait(status=result.status, wait=1)
        else:
            return self.round_retry(status=result.status, wait=1)

    @node_from(from_name='检查邦布', success=False)
    @node_from(from_name='选择邦布', status='没有合适邦布')
    @node_from(from_name='点击派驻', status='派驻完成')
    @operation_node(name='选择商品')
    def choose_item(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            '所需材料不足',
            '邦布电量不足',
            '未选择邦布',
            '请先选择邦布',  # 有上一个就肯定有这个 加入防止点错
        ]
        result = self.round_by_ocr_and_click_by_priority(target_cn_list)
        if not result.is_success:
            return self.round_success(status='材料充足')
        if result.status in ['邦布电量不足', '未选择邦布']:
            return self.round_success(status=result.status)

        if not self.from_craft:  # 只有制造坊来的才能选商品
            return self.round_success(status=result.status)

        # 不能制造的 换一个商品
        area = self.ctx.screen_loader.get_area('随便观-制造坊', '区域-商品列表')
        ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
            self.last_screenshot,
            rect=area.rect,
            color_range=[[230, 230, 230], [255, 255, 255]],
        )
        goods_ocr_result_list: list[OcrMatchResult] = []  # 商品列表

        for ocr_result in ocr_result_list:
            # 移除字符串中的所有数字
            ocr_word: str = re.sub(r'\d+', '', ocr_result.data)
            if len(ocr_word) == 0:  # 全是数字的
                continue

            goods_ocr_result_list.append(ocr_result)

        ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
            self.last_screenshot,
            rect=area.rect,
        )
        can_make_pos_list: list[Rect] = []  # 可制造的位置

        for ocr_result in ocr_result_list:
            # 移除字符串中的所有数字
            ocr_word: str = re.sub(r'\d+', '', ocr_result.data)
            if len(ocr_word) == 0:  # 全是数字的
                continue

            can_make_idx = str_utils.find_best_match_by_difflib(ocr_word, ['可制造'])
            if can_make_idx is not None and can_make_idx >= 0:
                can_make_pos_list.append(ocr_result.rect)

        # 右方有可制造的商品
        can_make_goods_list: list[OcrMatchResult] = []
        for ocr_result in goods_ocr_result_list:
            can_make: bool = False
            for can_make_pos in can_make_pos_list:
                # 可制造需要在商品名称的右侧
                if not can_make_pos.center.x > ocr_result.rect.center.x:
                    continue
                # 可制造和商品名称在同一行
                if not abs(can_make_pos.center.y - ocr_result.rect.center.y) < 20:
                    continue
                can_make = True
                break
            if can_make:
                can_make_goods_list.append(ocr_result)

        # 找到还没有选择过的一个进行选择
        for ocr_result in can_make_goods_list:
            if ocr_result.data in self.chosen_item_list:
                continue
            self.scroll_after_choose = False
            self.chosen_item_list.append(ocr_result.data)
            self.ctx.controller.click(ocr_result.right_bottom + Point(50, 0))  # 往右方点击 防止遮挡到商品名称
            return self.round_wait(status='选择下一个商品', wait=1)

        # 判断当前列表是否有变化
        new_item_list: list[str] = [i.data for i in goods_ocr_result_list]
        with_new_item: bool = False  # 是否出现了新商品
        for new_item in new_item_list:
            old_idx = str_utils.find_best_match_by_difflib(new_item, self.last_item_list)
            if old_idx is not None and old_idx >= 0:
                continue
            with_new_item = True
            break
        self.last_item_list = new_item_list
        log.info('当前识别商品 %s', new_item_list)

        if self.drag_times >= self.config.craft_drag_times:
            return self.round_success(status='已滑动次数达到上限', wait=1)
        if not with_new_item and self.scroll_after_choose:
            return self.round_success(status='未发现新商品', wait=1)
        else:
            self.drag_times += 1
            self.scroll_after_choose = True
            start = area.center
            end = start + Point(0, -300)
            self.ctx.controller.drag_to(start=start, end=end)
            return self.round_wait(status='滑动找未选择过的商品', wait=1)

    @node_from(from_name='选择商品', status='材料充足')
    @operation_node(name='点击开始制造')
    def click_start_crafting(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            '开始制造',
            '调整计划',
        ]
        result = self.round_by_ocr_and_click_by_priority(target_cn_list, success_wait=1, retry_wait=1)
        self.done_craft = result.is_success
        return result

    @node_from(from_name='选择商品', success=False)
    @node_from(from_name='选择商品', status='未发现新商品')
    @node_from(from_name='选择商品', status='已滑动次数达到上限')
    @node_from(from_name='选择商品', status='所需材料不足')
    @node_from(from_name='选择商品', status='邦布电量不足')
    @node_from(from_name='选择商品', status='未选择邦布')
    @node_from(from_name='点击开始制造')
    @node_from(from_name='点击开始制造', success=False)
    @operation_node(name='完成后返回')
    def back_at_last(self) -> OperationRoundResult:
        if self.from_craft:
            current_screen_name = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=['随便观-制造坊'])
            if current_screen_name is not None:
                return self.round_success(status=current_screen_name, data=self.done_craft)
        else:
            result = self.round_by_find_area(self.last_screenshot, screen_name='随便观-饮茶仙', area_name='按钮-制造')
            if result.is_success:
                return self.round_success(status=result.status, data=self.done_craft)

        # 点击开始制造后 可能需要确认 (调整计划、返回材料)
        target_cn_list: list[str] = [
            '确认',
        ]
        result = self.round_by_ocr_and_click_by_priority(target_cn_list)
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)

        result = self.round_by_find_and_click_area(self.last_screenshot, '菜单', '返回')
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)
        else:
            return self.round_retry(status=result.status, wait=1, data=False)


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.run_context.start_running()
    ctx.run_context.current_instance_idx = ctx.current_instance_idx
    ctx.run_context.current_app_id = 'suibian_temple'
    ctx.run_context.current_group_id = 'one_dragon'
    op = SuibianTempleCraftDispatch(ctx, from_craft=False, chosen_item_list=[],)
    op.execute()


if __name__ == '__main__':
    __debug()
