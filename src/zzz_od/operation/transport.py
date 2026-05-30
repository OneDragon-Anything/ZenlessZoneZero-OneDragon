from typing import ClassVar

from cv2.typing import MatLike

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import str_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.map_transport import MapTransport
from zzz_od.operation.zzz_operation import ZOperation


class Transport(ZOperation):

    STATUS_NOT_IN_MAP: ClassVar[str] = '未在地图页面'

    def __init__(self, ctx: ZContext, area_name: str, tp_name: str, wait_at_last: bool = True):
        """
        传送到某个区域
        由于使用了返回大世界 应可保证在任何情况下使用
        :param ctx:
        :param area_name:
        :param tp_name:
        :param wait_at_last: 最后等待大世界加载
        """
        ZOperation.__init__(self, ctx,
                            op_name='%s %s %s' % (
                                gt('传送'),
                                gt(area_name, 'game'),
                                gt(tp_name, 'game')
                            ))

        self.area_name: str = area_name
        self.tp_name: str = tp_name
        self.wait_at_last: bool = wait_at_last

    @operation_node(name='画面识别', is_start_node=True)
    def check_screen(self) -> OperationRoundResult:
        """
        画面识别
        :return:
        """
        if self.is_map_screen(self.last_screenshot):
            return self.round_success()
        else:
            return self.round_success(status=Transport.STATUS_NOT_IN_MAP)

    @node_from(from_name='画面识别', status=STATUS_NOT_IN_MAP)
    @operation_node(name='返回大世界')
    def back_to_world(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='返回大世界')
    @operation_node(name='打开地图')
    def open_map(self) -> OperationRoundResult:
        """
        在大世界画面 点击
        :return:
        """
        if self.is_map_screen(self.last_screenshot):
            return self.round_success()

        result = self.round_by_find_and_click_area(self.last_screenshot, '大世界', '地图')
        if result.is_success:
            return self.round_wait(status=result.status, wait=2)
        else:
            return self.round_retry(status=result.status, wait=1)

    @node_from(from_name='打开地图')
    @node_from(from_name='画面识别')
    @operation_node(name='执行传送')
    def do_transport(self) -> OperationRoundResult:
        """
        已在地图画面，调用 MapTransport 执行传送
        :return:
        """
        op = MapTransport(self.ctx, self.area_name, self.tp_name)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='执行传送')
    @operation_node(name='等待大世界加载')
    def wait_in_world(self) -> OperationRoundResult:
        if not self.wait_at_last:
            return self.round_success('不等待大世界加载')
        op = BackToNormalWorld(self.ctx)  # 传送落地可能触发好感度事件 使用BackToNormalWorld可以处理
        return self.round_by_op_result(op.execute())

    def is_map_screen(self, screen: MatLike) -> bool:
        """
        当前画面是否在地图选择画面
        要同时出现多个地区名称和传送点名称
        :param screen: 游戏画面
        :return:
        """
        area_name_list: list[str] = []
        tp_name_list: list[str] = []

        for area in self.ctx.map_service.area_list:
            area_name_list.append(gt(area.area_name, 'game'))
            for tp in area.tp_list:
                tp_name_list.append(gt(tp, 'game'))

        area_name_cnt: int = 0
        tp_name_cnt: int = 0
        ocr_result_map = self.ctx.ocr.run_ocr(screen)
        for ocr_result, mrl in ocr_result_map.items():
            area_idx: int = str_utils.find_best_match_by_difflib(ocr_result, area_name_list)
            if area_idx is not None and area_idx >= 0:
                area_name_cnt += 1
            tp_idx: int = str_utils.find_best_match_by_difflib(ocr_result, tp_name_list)
            if tp_idx is not None and tp_idx >= 0:
                tp_name_cnt += 1

        # 增加判断条件，左上角返回
        result = self.round_by_find_area(screen, '地图', '左上角返回')

        return area_name_cnt >= 3 and tp_name_cnt >= 1 and result.is_success


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.run_context.start_running()
    op = Transport(ctx, '澄辉坪', '阿朔')
    op.execute()


if __name__ == '__main__':
    __debug()
