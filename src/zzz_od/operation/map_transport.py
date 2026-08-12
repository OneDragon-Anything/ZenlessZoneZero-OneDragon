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
        # 首次识别到主区域时确定滑动方向，后续保持不变，避免搜索方向来回切换。
        self._area_search_drag_x: int | None = None
        # 保存上一轮识别到的主区域集合，用于判断滑动后列表是否仍在变化。
        self._last_area_idx_set: set[int] | None = None
        self._same_area_times: int = 0
        # 当前方向连续三轮没有变化后只反向一次，反向后仍无变化才结束查找。
        self._area_search_reversed: bool = False

    @node_from(from_name='选择传送点', success=False)
    @operation_node(name='选择区域', is_start_node=True)
    def choose_area(self) -> OperationRoundResult:
        area_name_list: list[str] = []
        for area in self.ctx.map_service.area_list:
            area_name_list.append(gt(area.area_name, 'game'))

        target_area: MapArea = self.ctx.map_service.area_name_map[self.area_name]
        target_area_idx: int = str_utils.find_best_match_by_difflib(gt(target_area.area_name, 'game'), area_name_list)

        # 先做整屏 OCR，再用区域框过滤结果，避免底部传送点名称误匹配成主区域。
        area = self.ctx.screen_loader.get_area('地图', '主区域名称')
        ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
            self.last_screenshot,
            rect=area.rect,
            crop_first=False,
        )
        # 收藏数量和排列不固定，使用 OCR 结果中最后一个主区域判断初始翻页方向。
        last_current_area_idx: int = -1
        current_area_idx_set: set[int] = set()
        for ocr_result in ocr_result_list:
            current_idx = str_utils.find_best_match_by_difflib(ocr_result.data, area_name_list)
            if current_idx is None or current_idx < 0:
                continue
            if current_idx == target_area_idx:
                self.ctx.controller.click(ocr_result.center)
                return self.round_success(wait=1)
            last_current_area_idx = current_idx
            current_area_idx_set.add(current_idx)

        if last_current_area_idx < 0:
            # 地图转场期间只等待，不改变翻页判断状态。
            return self.round_wait('未识别到地图区域', wait=0.5)

        if self._area_search_drag_x is None:
            if last_current_area_idx > target_area_idx:
                self._area_search_drag_x = 500
            else:
                self._area_search_drag_x = -500

        # 连续三轮识别到相同的主区域集合，视为当前方向没有再翻出新区域。
        if current_area_idx_set == self._last_area_idx_set:
            self._same_area_times += 1
        else:
            self._last_area_idx_set = current_area_idx_set
            self._same_area_times = 0

        search_reversed = False
        if self._same_area_times >= 3:
            if self._area_search_reversed:
                return self.round_fail('未找到目标地图区域')
            self._area_search_reversed = True
            self._area_search_drag_x = -self._area_search_drag_x
            self._same_area_times = 0
            search_reversed = True

        start_point = Point(self.ctx.controller.standard_width // 2, self.ctx.controller.standard_height // 2)
        end_point = start_point + Point(self._area_search_drag_x, 0)
        self.ctx.controller.drag_to(start=start_point, end=end_point)
        if search_reversed:
            return self.round_wait('切换相反方向查找地图区域', wait=0.5)
        return self.round_wait(wait=0.5)

    @node_from(from_name='选择区域')
    @operation_node(name='选择传送点', node_max_retry_times=10)
    def choose_tp(self) -> OperationRoundResult:
        area = self.ctx.screen_loader.get_area('地图', '传送点名称')
        ocr_map = self.ctx.ocr_service.get_ocr_result_map(
            self.last_screenshot,
            rect=area.rect,
            crop_first=False,
        )
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
