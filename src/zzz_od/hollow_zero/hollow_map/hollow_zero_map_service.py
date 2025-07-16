import time

from cv2.typing import MatLike
from typing import List, Optional

from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext
from zzz_od.hollow_zero.hollow_map import hollow_map_utils
from zzz_od.hollow_zero.hollow_map.hollow_zero_map import HollowZeroMap
from zzz_od.hollow_zero.hollow_zero_data_service import HallowZeroDataService
from zzz_od.yolo.hollow_event_detector import HollowEventDetector


class HollowZeroMapService:

    def __init__(self, ctx: ZContext):
        self.ctx: ZContext = ctx

        self.data_service: HallowZeroDataService = HallowZeroDataService()
        self.event_model: Optional[HollowEventDetector] = None
        self.map_list: List[HollowZeroMap] = []

    def init_event_yolo(self) -> None:
        use_gpu = self.ctx.model_config.hollow_zero_event_gpu
        if self.event_model is None or self.event_model.gpu != use_gpu:
            self.event_model = HollowEventDetector(
                model_name=self.ctx.model_config.hollow_zero_event,
                backup_model_name=self.ctx.model_config.hollow_zero_event_backup,
                gh_proxy=self.ctx.env_config.is_gh_proxy,
                gh_proxy_url=self.ctx.env_config.gh_proxy_url if self.ctx.env_config.is_gh_proxy else None,
                personal_proxy=self.ctx.env_config.personal_proxy if self.ctx.env_config.is_personal_proxy else None,
                gpu=use_gpu
            )

    def cal_current_map_by_screen(self, screen: MatLike, screenshot_time: float) -> Optional[HollowZeroMap]:
        """
        根据当前的游戏画面 计算对应的空洞地图
        :param screen: 游戏画面
        :param screenshot_time: 截图时间
        :return:
        """
        if self.event_model is None:
            return None
        result = self.event_model.run(screen, run_time=screenshot_time)
        # from zzz_od.yolo import detect_utils
        # cv2_utils.show_image(detect_utils.draw_detections(result), wait=0)
        if result is None:
            return None

        return hollow_map_utils.construct_map_from_yolo_result(self.ctx, result, self.data_service.name_2_entry)

    def cal_map_by_screen(self, screen: MatLike, screenshot_time: float) -> Optional[HollowZeroMap]:
        """
        根据游戏画面 计算空洞地图
        会与过去一段时间识别到的地图进行合并
        :param screen: 游戏画面
        :param screenshot_time: 截图时间
        :return:
        """
        start_time = time.time()
        # 当前帧的地图
        current_map = self.cal_current_map_by_screen(screen, screenshot_time)
        if current_map is None:
            return None

        # 尝试与过去识别的结果合并
        merge_idx: int = -1
        merge_map: HollowZeroMap = current_map
        for i in range(len(self.map_list)):
            old_map = self.map_list[i]
            # 判断是一样的地图 才有可能进行合并
            if not hollow_map_utils.is_same_map(current_map, old_map):
                continue

            merge_map = hollow_map_utils.merge_map(self.ctx, [current_map, old_map])
            if merge_map.is_valid_map:
                merge_idx = i
                break

        for old_map in self.map_list:
            old_map.not_current_map_times += 1

        if merge_idx != -1:
            merge_map.not_current_map_times = 0
            self.map_list[merge_idx] = merge_map
        else:
            self.map_list.append(current_map)

        self.map_list = [x for x in self.map_list if x.not_current_map_times <= 10]

        log.debug('空洞地图识别 耗时 %.2f 秒', time.time() - start_time)
        return merge_map

    def clear_map_result(self) -> None:
        """
        清除所有识别结果
        :return:
        """
        self.map_list.clear()

def __debug_cal_current_map_by_screen():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    service = HollowZeroMapService(ctx)
    service.init_event_yolo()

    from one_dragon.utils import debug_utils
    screen = debug_utils.get_debug_image('_1733016932243')
    import time
    ctx.hollow.init_before_hollow_start('旧都列车', '旧都列车-核心')
    current_map = service.cal_current_map_by_screen(screen, time.time())
    ctx.hollow.check_info_before_move(screen, current_map)
    from zzz_od.hollow_zero.hollow_map import hollow_pathfinding
    hollow_pathfinding.search_map(current_map, ctx.hollow._get_avoid(), [])
    target = ctx.hollow.get_next_to_move(current_map)
    next_node_to_move = target.next_node_to_move
    from zzz_od.hollow_zero.hollow_runner import HollowRunner
    runner = HollowRunner(ctx)
    to_click = runner.get_map_node_pos_to_click(screen, next_node_to_move)
    result_img = hollow_pathfinding.draw_map(screen, current_map,
                                             next_node=next_node_to_move, to_click=to_click)
    from one_dragon.utils import cv2_utils
    cv2_utils.show_image(result_img, wait=0)
    import cv2
    cv2.destroyAllWindows()
    # print(current_map.contains_entry('业绩考察点'))
    print(next_node_to_move.pos)
    print(to_click)


if __name__ == '__main__':
    __debug_cal_current_map_by_screen()