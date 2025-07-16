import difflib

import os
import yaml
from typing import List, Optional

from one_dragon.utils import os_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log


class MapArea:

    def __init__(self, area_name: str, tp_list: List[str]):
        """
        一个地图区域
        :param area_name: 区域名称
        :param tp_list: 传送点名称 有序
        """
        self.area_name: str = area_name
        self.tp_list: List[str] = tp_list


class MapAreaService:

    def __init__(self):
        """
        地图区域
        """
        self.area_list: List[MapArea] = []
        self.area_name_map: dict[str, MapArea] = {}
        self.reload()

    def reload(self) -> None:
        """
        重新加载数据
        :return:
        """
        file_path = os.path.join(
            os_utils.get_path_under_work_dir('assets', 'game_data'),
            'map_area.yml'
        )
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                area_list: List[dict] = yaml.safe_load(file)
                self.area_list = []
                self.area_name_map = {}
                for area_data in area_list:
                    area = MapArea(area_data.get('area_name', ''), area_data.get('tp_list', []))
                    self.area_list.append(area)
                    self.area_name_map[area.area_name] = area
        except Exception:
            log.error(f'文件读取失败 {file_path}', exc_info=True)

    def get_best_match_area(self, ocr_result: str) -> Optional[MapArea]:
        """
        根据OCR结果 匹配最接近的区域
        :param ocr_result: OCR结果
        :return:
        """
        target_list = [gt(area.area_name, 'game') for area in self.area_list]
        results = difflib.get_close_matches(ocr_result, target_list, n=1)

        if results is not None and len(results) > 0:
            idx = target_list.index(results[0])
            return self.area_list[idx]
        else:
            return None

    def get_direction_to_target_area(self, current_area: MapArea, target_area: MapArea) -> int:
        """
        获取 从当前区域 到 目标区域 需要往哪个方向点击多少次可到达
        :param current_area: 当前区域
        :param target_area: 目标区域
        :return: 正数向右 负数向左
        """
        current_idx = self.area_list.index(current_area)
        target_idx = self.area_list.index(target_area)

        result = target_idx - current_idx
        length = len(self.area_list)
        if result > 0 and length - result < result:  # 右边走太远了 走左边
            result = -(length - result)
        elif result < 0 and length - (-result) < (-result):  # 左边走太远了 走右边
            result = length - (-result)

        return result

    def get_best_match_tp(self, area_name: str, ocr_result: str) -> Optional[str]:
        """
        根据OCR结果 匹配最接近的区域
        :param area_name: 所在区域名称
        :param ocr_result: OCR结果
        :return:
        """
        area = self.area_name_map[area_name]
        target_list = [gt(tp, 'game') for tp in area.tp_list]
        results = difflib.get_close_matches(ocr_result, target_list, n=1)

        if results is not None and len(results) > 0:
            idx = target_list.index(results[0])
            return area.tp_list[idx]
        else:
            return None
