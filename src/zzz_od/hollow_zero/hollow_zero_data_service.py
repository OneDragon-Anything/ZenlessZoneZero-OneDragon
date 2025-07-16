import difflib
import os
import yaml
from typing import List, Optional, Tuple

from one_dragon.utils import os_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.hollow_zero.game_data.hollow_zero_event import HallowZeroEvent, HollowZeroEntry
from zzz_od.hollow_zero.game_data.hollow_zero_resonium import Resonium


class HallowZeroDataService:

    def __init__(self):
        # 事件
        self.normal_events: List[HallowZeroEvent] = []
        self.entry_list: List[HollowZeroEntry] = []
        self.name_2_entry: dict[str, HollowZeroEntry] = {}

        # 鸣徽
        self.resonium_list: List[Resonium] = []
        self.resonium_cate_list: List[str] = []
        self.cate_2_resonium: dict[str, List[Resonium]] = {}

        self.reload()

    def reload(self):
        self._load_normal_events()
        self._load_entry_list()
        self._load_resonium()

    def _load_normal_events(self):
        dir_path = os_utils.get_path_under_work_dir('assets', 'game_data', 'hollow_zero', 'normal_event')
        file_name_list = os.listdir(dir_path)

        self.normal_events: List[HallowZeroEvent] = []
        for file_name in file_name_list:
            if not file_name.endswith('.yml'):
                continue
            file_path = os.path.join(dir_path, file_name)
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    event_list: List[dict] = yaml.safe_load(file)
                    events = [HallowZeroEvent(**i) for i in event_list]
                    for e in events:
                        e.on_the_right = True
                    self.normal_events = self.normal_events + events
            except Exception:
                log.error(f'文件读取失败 {file_path}', exc_info=True)

    def get_normal_event_by_name(self, event_name: str) -> Optional[HallowZeroEvent]:
        """
        通过事件名称获取事件
        """
        for event in self.normal_events:
            if event.event_name == event_name:
                return event

    def _load_entry_list(self):
        self.entry_list = []
        self.name_2_entry = {}

        file_path = os_utils.get_path_under_work_dir('assets', 'game_data', 'hollow_zero', 'entry_list.yml')
        if not os.path.exists(file_path):
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                entry_list: List[dict] = yaml.safe_load(file)
                for i in entry_list:
                    entry = HollowZeroEntry(**i)
                    self.entry_list.append(entry)
                    self.name_2_entry[entry.entry_name] = entry
        except Exception:
            log.error(f'文件读取失败 {file_path}', exc_info=True)

    def get_entry_by_name(self, entry_name: str) -> Optional[HollowZeroEntry]:
        return self.name_2_entry.get(entry_name, None)

    def _load_resonium(self) -> None:
        self.resonium_list = []
        self.resonium_cate_list = []
        self.cate_2_resonium = {}

        file_path = os_utils.get_path_under_work_dir('assets', 'game_data', 'hollow_zero', 'resonium.yml')
        if not os.path.exists(file_path):
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                entry_list: List[dict] = yaml.safe_load(file)
                for i in entry_list:
                    item = Resonium(**i)
                    self.resonium_list.append(item)
                    if item.category not in self.cate_2_resonium:
                        self.resonium_cate_list.append(item.category)
                        self.cate_2_resonium[item.category] = [item]
                    else:
                        self.cate_2_resonium[item.category].append(item)
        except Exception:
            log.error(f'文件读取失败 {file_path}', exc_info=True)

    def match_resonium_by_ocr(self, cate_ocr: str, name_ocr: str) -> Optional[Resonium]:
        log.info('当前识别 %s %s', cate_ocr, name_ocr)
        category_list = [gt(i, 'game') for i in self.resonium_cate_list]
        results = difflib.get_close_matches(cate_ocr, category_list, n=2, cutoff=0.5)

        if results is None or len(results) == 0:
            log.info('匹配结果 无')
            return None

        # 强x会同时匹配到强袭和顽强 这里用字符顺序顺序额外判断一下
        if len(results) == 2:
            if len(cate_ocr) > 1 and cate_ocr[1] == '_':
                if results[0].startswith(cate_ocr[0]):
                    category_idx = category_list.index(results[0])
                else:
                    category_idx = category_list.index(results[1])
            elif cate_ocr[0] == '_':
                if results[0].endswith(cate_ocr[1]):
                    category_idx = category_list.index(results[0])
                else:
                    category_idx = category_list.index(results[1])
            else:
                category_idx = category_list.index(results[0])
        else:
            category_idx = category_list.index(results[0])

        resonium_list = self.cate_2_resonium[self.resonium_cate_list[category_idx]]

        resonium_name_list = [gt(i.name, 'game') for i in resonium_list]
        results = difflib.get_close_matches(name_ocr, resonium_name_list, n=1)

        if results is None or len(results) == 0:
            log.info('匹配结果 无')
            return None

        resonium_idx = resonium_name_list.index(results[0])
        r = resonium_list[resonium_idx]
        log.info('匹配结果 %s %s', r.category, r.name)
        return r

    def match_resonium_by_ocr_full(self, name_full_str: str) -> Optional[Resonium]:
        """
        使用 [类型]名称 的文本匹配鸣徽
        :param name_full_str: 识别的文本 [类型]名称
        :return 鸣徽
        """
        name_full_str = name_full_str.strip()
        name_full_str = name_full_str.replace('[', '')
        name_full_str = name_full_str.replace(']', '')

        idx = name_full_str.find('】')
        if idx == -1:
            idx = name_full_str.find(']')
        if idx == -1:
            idx = name_full_str.find(' ')

        if idx == -1:
            if len(name_full_str) < 2:
                return None

            # 没有分隔符的情况 大概率是第二个字识别失败
            cate_str = name_full_str[:1] + '_'
            name_str = name_full_str[1:]
            result = self.match_resonium_by_ocr(cate_str, name_str)
            if result is not None:
                return result

            # 尝试看看是不是第一个字识别失败
            cate_str = '_' + name_full_str[:1]
            name_str = name_full_str[1:]

            result = self.match_resonium_by_ocr(cate_str, name_str)
            if result is not None:
                return result

            if len(name_full_str) == 2:  # 已经没法匹配到了
                return None

            # 尝试看前两个字
            cate_str = name_full_str[:2]
            name_str = name_full_str[2:]

            return self.match_resonium_by_ocr(cate_str, name_str)
        else:
            cate_str = name_full_str[:idx]
            name_str = name_full_str[idx+1:]

        cate_str = cate_str.strip()
        name_str = name_str.strip()

        if len(cate_str) > 1:
            return self.match_resonium_by_ocr(cate_str, name_str)
        else:
            result = self.match_resonium_by_ocr(cate_str + '_', name_str)
            if result is not None:
                return result
            else:
                return self.match_resonium_by_ocr('_' + cate_str, name_str)

    def check_resonium_priority(self, input_str: str) -> Tuple[List[str], str]:
        """
        校验优先级的文本输入
        错误的输入会被过滤掉
        :param input_str:
        :return: 匹配的鸣徽和错误信息
        """
        if input_str is None or len(input_str) == 0:
            return [], ''

        input_arr = [i.strip() for i in input_str.split('\n')]
        resonium_list = []
        error_msg = ''
        for i in input_arr:
            if len(i) == 0:
                continue
            split_idx = i.find(' ')
            if split_idx != -1:
                cate_name = i[:split_idx]
                item_name = i[split_idx+1:]
            else:
                cate_name = i
                item_name = ''

            is_valid: bool = False

            for cate in self.resonium_cate_list:
                if item_name != '':  # 不可能是分类
                    break
                if cate_name == cate:
                    resonium_list.append(i)
                    is_valid = True
                    break
            for r in self.resonium_list:
                if cate_name == r.category and item_name == r.name:
                    resonium_list.append(i)
                    is_valid = True
                    break

            if not is_valid:
                error_msg += f'输入非法 {i}'

        return resonium_list, error_msg

    def check_entry_list_input(self, input_str: str) -> Tuple[List[str], str]:
        if input_str is None or len(input_str) == 0:
            return [], ''

        input_arr = [i.strip() for i in input_str.split('\n')]
        entry_list = []
        error_msg = ''
        for i in input_arr:
            if len(i) == 0:
                continue

        for i in input_arr:
            if len(i) == 0:
                continue
            if i not in self.name_2_entry:
                error_msg += f'输入非法 {i}; '
            else:
                entry_list.append(i)

        return entry_list, error_msg

    def get_default_go_in_1_step_entry_list(self) -> List[str]:
        """
        默认的一步可达前往的格子类型
        :return:
        """
        return [entry.entry_name for entry in self.entry_list if entry.is_benefit]

    def get_only_boss_go_in_1_step_entry_list(self) -> List[str]:
        """
        速通模式的一步可达前往的格子类型
        :return:
        """
        return []

    def get_default_waypoint_entry_list(self) -> List[str]:
        """
        默认的途径点类型
        :return:
        """
        return [
            '呼叫增援',
            '业绩考察点',
            '零号银行',
            '邦布商人',
            '诡雾',
        ]

    def get_only_boss_waypoint_entry_list(self) -> List[str]:
        """
        速通模式的途径点类型
        :return:
        """
        return [
            '呼叫增援',
            '业绩考察点',
            '诡雾',
        ]

    def get_default_avoid_entry_list(self) -> List[str]:
        """
        默认的避免途经点类型
        :return:
        """
        return ['危机', '双重危机', '限时战斗']

    def get_no_battle_list(self) -> List[str]:
        """
        不包含战斗的类型
        @return:
        """
        return [
            i.entry_name
            for i in self.entry_list
            if i.entry_name not in ['危机', '双重危机', '限时战斗'] and i.can_go
        ]


if __name__ == '__main__':
    _data = HallowZeroDataService()
    _data.match_resonium_by_ocr_full('[强聚合徽标')