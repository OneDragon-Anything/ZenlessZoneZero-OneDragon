import time

from typing import List, Optional

from one_dragon.base.geometry.rectangle import Rect
from zzz_od.hollow_zero.game_data.hollow_zero_event import HollowZeroEntry
from one_dragon.utils.log_utils import log


class HollowZeroMapNode:

    def __init__(self, pos: Rect, entry: HollowZeroEntry,
                 check_time: Optional[float] = None,
                 confidence: float = 0):
        self.pos: Rect = pos
        self.entry: HollowZeroEntry = entry
        self.check_time: float = time.time() if check_time is None else check_time  # 识别时间
        self.confidence: float = confidence
        self.visited_times: int = 0  # 尝试前往的次数 在寻路时候使用

        # 寻路相关的信息 前往这个节点的信息
        self.path_first_node: Optional[HollowZeroMapNode] = None  # 路径上的第一个节点 就是当前节点的相邻节点
        self.path_first_need_step_node: Optional[HollowZeroMapNode] = None  # 路径上的第一个需要步数的节点 就是鼠标需要点击的节点
        self.path_last_node: Optional[HollowZeroMapNode] = None  # 路径上的倒数第2个节点 就是前往这个节点的上一个节点
        self.path_step_cnt: int = -1  # 前往目标节点需要的步数 即路上需要点击多少次鼠标
        self.path_node_cnt: int = -1  # 前往目标节点需要经过的格子数量 会影响最终的移动耗时
        self.path_go_way: int = 1  # 0=往相邻节点移动 1=往需要步数的节点移动

    @property
    def gt_max_visited_times(self) -> bool:
        return self.visited_times >= self.entry.can_visited_times

    @property
    def next_node_to_move(self):
        return self.path_first_need_step_node if self.path_go_way == 1 else self.path_first_node


class HollowZeroMap:

    def __init__(self, nodes: List[HollowZeroMapNode],
                 current_idx: int,
                 edges: dict[int, List[int]],
                 check_time: Optional[float] = None):
        self.nodes: List[HollowZeroMapNode] = nodes
        self.current_idx: int = current_idx
        self.edges: dict[int, List[int]] = edges
        self.check_time: float = time.time() if check_time is None else check_time  # 识别时间

        # 不是当前识别到的地图的次数 过多之后 就认为该地图已经失效
        self.not_current_map_times: int = 0

    @property
    def is_valid_map(self) -> bool:
        """
        判断一个地图是否合法
        判断 [当前] 节点是否存在
        :return:
        """
        return self.current_idx is not None

    def contains_entry(self, entry_name: str) -> bool:
        """
        是否保护某个类型的格子
        :param entry_name:
        :return:
        """
        for node in self.nodes:
            if node.entry.entry_name == entry_name:
                return True

        return False

    def search_entry(self, entry_name: str) -> bool:
        for node in self.nodes:
            if node.entry.entry_name == entry_name:
                log.info(f"发现节点 [{entry_name}]")
                return True
        return False

    def init_path_related(self) -> None:
        """
        初始化寻路相关信息
        :return:
        """
        for node in self.nodes:
            node.path_first_node = None  # 路径上的第一个节点 就是当前节点的相邻节点
            node.path_first_need_step_node = None  # 路径上的第一个需要步数的节点 就是鼠标需要点击的节点
            node.path_last_node = None
            node.path_step_cnt = -1  # 前往目标节点需要的步数 即路上需要点击多少次鼠标
            node.path_node_cnt = -1

            node.path_go_way = 1  # 0=往相邻节点移动 1=往需要步数的节点移动

        if self.is_valid_map:
            current_node = self.nodes[self.current_idx]
            current_node.path_step_cnt = 0
            current_node.path_node_cnt = 0
