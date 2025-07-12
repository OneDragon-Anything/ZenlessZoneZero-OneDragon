from typing import Optional

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class CompendiumChooseTab(ZOperation):

    def __init__(self, ctx: ZContext, tab_name: str):
        """
        已经打开了快捷手册了 选择一个 Tab
        :param ctx:
        """
        ZOperation.__init__(
            self, ctx,
            op_name='%s %s %s' % (
                gt('快捷手册', 'game'),
                gt('选择Tab'),
                gt(tab_name, 'game')
            )
        )

        self.tab_name: str = tab_name

    @operation_node(name='选择TAB', is_start_node=True)
    def choose_tab(self) -> OperationRoundResult:
        screen = self.screenshot()
        area = self.ctx.screen_loader.get_area('快捷手册', 'TAB列表')
        part = cv2_utils.crop_image_only(screen, area.rect)

        target_point: Optional[Point] = None
        ocr_results = self.ctx.ocr.run_ocr(part)
        for ocr_result, mrl in ocr_results.items():
            if mrl.max is None:
                continue
            if str_utils.find_by_lcs(gt(self.tab_name, 'game'), ocr_result, percent=0.5):
                target_point = area.left_top + mrl.max
                break

        if target_point is None:
            return self.round_retry(status='找不到 %s' % self.tab_name, wait=1)

        click = self.ctx.controller.click(target_point)
        return self.round_success(wait=1)


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.start_running()
    op = CompendiumChooseTab(ctx, tab_name='训练')
    op.execute()


if __name__ == '__main__':
    __debug()