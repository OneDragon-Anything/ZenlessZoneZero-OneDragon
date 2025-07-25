import cv2

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class SuibianTempleCraft(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        随便观 - 制造

        需要在制造台画面(可看见开工)时候调用，完成后返回随便观主界面

        操作步骤
        1. 点击开工，没有 -> 最后一步
        2. 所需材料不足 -> 选择新的商品
        3. 没有新的商品 -> 最后一步
        4. 制造
        5. 返回随便观
        Args:
            ctx: 上下文
        """
        ZOperation.__init__(self, ctx,
                            op_name=f'{gt("随便观", "game")} {gt("制造", "game")}')

        self.last_item_list: list[str] = []  # 上一次的商品列表
        self.chosen_item_list: list[str] = []  # 已经选择过的货品列表
        self.scroll_after_choose: bool = False  # 选择后是否已经滑动了

    @node_from(from_name='点击开始制造')
    @operation_node(name='点击开工', is_start_node=True)
    def click_lets_go(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            '开工',
            '开物',
        ]
        ignore_cn_list: list[str] = [
            '开物',
        ]
        return self.round_by_ocr_and_click_by_priority(target_cn_list, ignore_cn_list=ignore_cn_list,
                                                       success_wait=1, retry_wait=1)

    @node_from(from_name='点击开工')
    @operation_node(name='选择物品')
    def choose_item(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            '所需材料不足',
        ]
        result = self.round_by_ocr_and_click_by_priority(target_cn_list)
        if not result.is_success:
            return self.round_success(status='材料充足')

        # 不能制造的 换一个货品
        area = self.ctx.screen_loader.get_area('随便观-制造坊', '区域-商品列表')
        part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)
        mask = cv2_utils.color_in_range(part, [230, 230, 230], [255, 255, 255])
        to_ocr_part = cv2.bitwise_and(part, part, mask=mask)
        ocr_result_map = self.ctx.ocr.run_ocr(to_ocr_part)
        for ocr_result, mrl in ocr_result_map.items():
            if mrl.max is None:
                continue
            if ocr_result in self.chosen_item_list:
                continue
            self.scroll_after_choose = False
            self.chosen_item_list.append(ocr_result)
            self.ctx.controller.click(area.left_top + mrl.max.right_bottom + Point(50, 0))  # 往右方点击 防止遮挡到货品名称
            return self.round_wait(status='选择下一个货品', wait=1)

        # 判断当前列表是否有变化
        new_item_list: list[str] = list(ocr_result_map.keys())
        with_new_item: bool = False  # 是否出现了新商品
        for new_item in new_item_list:
            old_idx = str_utils.find_best_match_by_difflib(new_item, self.last_item_list)
            if old_idx is None or old_idx < 0:
                continue
            with_new_item = True
            break
        self.last_item_list = new_item_list

        if not with_new_item and self.scroll_after_choose:
            return self.round_success(status='未发现新商品', wait=1)
        else:
            self.scroll_after_choose = True
            start = area.center
            end = start + Point(0, -300)
            self.ctx.controller.drag_to(start=start, end=end)
            return self.round_retry(status='滑动找未选择过的货品', wait=1)

    @node_from(from_name='选择物品')
    @operation_node(name='点击开始制造')
    def click_start_crafting(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            '开始制造',
        ]
        return self.round_by_ocr_and_click_by_priority(target_cn_list)

    @node_from(from_name='点击开工', success=False)
    @node_from(from_name='选择物品', success=False)
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
    ctx.start_running()
    op = SuibianTempleCraft(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()
