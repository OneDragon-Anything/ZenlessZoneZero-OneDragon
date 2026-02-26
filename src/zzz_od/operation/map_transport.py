from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import str_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.map_area import MapArea
from zzz_od.operation.zzz_operation import ZOperation


class MapTransport(ZOperation):
    """在地图界面执行传送（选区域->选传送点->点击传送）"""

    def __init__(self, ctx: ZContext, area_name: str, tp_name: str) -> None:
        ZOperation.__init__(self, ctx,
                            op_name=f"{gt('地图传送')} {gt(area_name, 'game')} {gt(tp_name, 'game')}")

        self.area_name: str = area_name
        self.tp_name: str = tp_name

    @operation_node(name='选择区域', is_start_node=True)
    def choose_area(self) -> OperationRoundResult:
        area_name_list: list[str] = []
        for area in self.ctx.map_service.area_list:
            area_name_list.append(gt(area.area_name, 'game'))

        target_area: MapArea = self.ctx.map_service.area_name_map[self.area_name]
        target_area_idx: int = str_utils.find_best_match_by_difflib(gt(target_area.area_name, 'game'), area_name_list)

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

        start_point = Point(self.ctx.controller.standard_width // 2, self.ctx.controller.standard_height // 2)
        if max_current_area_idx > target_area_idx:
            end_point = start_point + Point(500, 0)
        else:
            end_point = start_point - Point(500, 0)
        self.ctx.controller.drag_to(start=start_point, end=end_point)
        return self.round_retry(wait=0.5)

    @node_from(from_name='选择区域')
    @operation_node(name='选择传送点', node_max_retry_times=10)
    def choose_tp(self) -> OperationRoundResult:
        area = self.ctx.screen_loader.get_area('地图', '传送点名称')
        ocr_map = self.ctx.ocr.run_ocr(self.last_screenshot)
        if len(ocr_map) == 0:
            return self.round_retry('未识别到传送点', wait_round_time=1)

        target_ocr_str = None
        display_tp_list: list[str] = []
        for ocr_str in ocr_map:
            ocr_tp_name = self.ctx.map_service.get_best_match_tp(self.area_name, ocr_str)
            display_tp_list.append(ocr_tp_name)
            if self.tp_name == ocr_tp_name:
                target_ocr_str = ocr_str

        if target_ocr_str is not None:
            mrl = ocr_map[target_ocr_str]
            self.ctx.controller.click(mrl.max.center)
            return self.round_success(wait=1)

        area_tp_list: list[str] = self.ctx.map_service.area_name_map[self.area_name].tp_list
        left_cnt: int = 0
        for area_tp in area_tp_list:
            if area_tp == self.tp_name:
                break
            if area_tp in display_tp_list:
                left_cnt += 1

        if left_cnt > 0:
            from_point = area.center + Point(-20, -20)
            end_point = from_point + Point(-800, 0)
            self.ctx.controller.drag_to(start=from_point, end=end_point)
        else:
            from_point = area.center + Point(-20, -20)
            end_point = from_point + Point(750, 0)
            self.ctx.controller.drag_to(start=from_point, end=end_point)
        return self.round_retry(wait=1, data=left_cnt)

    @node_from(from_name='选择传送点')
    @operation_node(name='点击传送')
    def click_tp(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(self.last_screenshot, '地图', '确认', success_wait=1, retry_wait=1)
