import time
from typing import ClassVar, List

from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.map_area import MapArea
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
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
    @operation_node(name='选择区域')
    def choose_area(self) -> OperationRoundResult:
        """
        在地图画面 选择上方的区域
        :return:
        """
        # 地图信息是按从上往下 从左往右存放的
        area_name_list: list[str] = []
        for area in self.ctx.map_service.area_list:
            area_name_list.append(gt(area.area_name, 'game'))

        # 目标区域的下标
        target_area: MapArea = self.ctx.map_service.area_name_map[self.area_name]
        target_area_idx: int = str_utils.find_best_match_by_difflib(gt(target_area.area_name, 'game'), area_name_list)

        # 判断当前显示区域是否有目标区域 有则点击
        # 没有则找出最大的区域下标
        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
        max_current_area_idx: int = -1
        for ocr_result, mrl in ocr_result_map.items():
            current_idx = str_utils.find_best_match_by_difflib(ocr_result, area_name_list)
            if current_idx is None or current_idx < 0:
                continue

            if current_idx == target_area_idx:
                self.ctx.controller.click(mrl.max.center)
                return self.round_success(wait=1)
            elif current_idx > max_current_area_idx:
                max_current_area_idx = current_idx

        # 如果当前显示没有目标区域 则判断滑动方向
        start_point = Point(self.ctx.controller.standard_width // 2, self.ctx.controller.standard_height // 2)
        if max_current_area_idx > target_area_idx:  # 有目标区域右边的 往左滑动
            end_point = start_point + Point(500, 0)
        else:
            end_point = start_point - Point(500, 0)
        self.ctx.controller.drag_to(start=start_point, end=end_point)

        return self.round_retry(wait=0.5)

    @node_from(from_name='选择区域')
    @operation_node(name='选择传送点')
    def choose_tp(self) -> OperationRoundResult:
        """
        在地图画面 已经选择好区域了 选择传送点
        :return:
        """
        area = self.ctx.screen_loader.get_area('地图', '传送点名称')

        ocr_map = self.ctx.ocr.run_ocr(self.last_screenshot)

        if len(ocr_map) == 0:
            return self.round_retry('未识别到传送点', wait_round_time=1)

        target_ocr_str = None
        display_tp_list: List[str] = []  # 当前显示的传送点名称
        for ocr_str in ocr_map.keys():
            ocr_tp_name = self.ctx.map_service.get_best_match_tp(self.area_name, ocr_str)
            display_tp_list.append(ocr_tp_name)
            if self.tp_name == ocr_tp_name:
                target_ocr_str = ocr_str

        if target_ocr_str is not None:
            mrl = ocr_map[target_ocr_str]
            # self.ctx.controller.click(mrl.max.center + area.left_top)
            self.ctx.controller.click(mrl.max.center)
            return self.round_success(wait=1)

        area_tp_list: List[str] = self.ctx.map_service.area_name_map[self.area_name].tp_list  # 当前区域的传送点名称
        left_cnt: int = 0  # 当前出现在画面上的 在目标传送点左方的传送点数量
        for area_tp in area_tp_list:
            if area_tp == self.tp_name:
                break
            if area_tp in display_tp_list:
                left_cnt += 1

        if left_cnt > 0:  # 往右滑
            from_point = area.center + Point(-20, -20)  # 如果在两个地点卡片中间 会滑动不了 这里选择了一个特殊点
            end_point = from_point + Point(-800, 0)
            self.ctx.controller.drag_to(start=from_point, end=end_point)
        else:  # 往左滑
            from_point = area.center + Point(-20, -20)
            end_point = from_point + Point(750, 0)  # 跟上面滑动距离稍微不一样 防止一直重复左右都找不到
            self.ctx.controller.drag_to(start=from_point, end=end_point)

        # 返回数量只是为了测试 实际不会用到
        return self.round_retry(wait=1, data=left_cnt)

    @node_from(from_name='选择传送点')
    @operation_node(name='点击传送')
    def click_tp(self) -> OperationRoundResult:
        """
        在地图画面 已经选好传送点了 点击传送
        :return:
        """
        return self.round_by_find_and_click_area(self.last_screenshot, '地图', '确认', success_wait=1, retry_wait=1)

    @node_from(from_name='点击传送')
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