import os
from cv2.typing import MatLike
from typing import Optional

from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.base.screen.screen_info import ScreenInfo
from one_dragon.utils.log_utils import log


class ScreenRouteNode:

    def __init__(self, from_screen: str, from_area: str, to_screen: str):
        """
        记录一个画面跳转的节点
        :param from_screen: 从某个画面出发
        :param from_area: 点击某个区域
        :param to_screen: 可以前往某个目标画面
        """
        self.from_screen: str = from_screen
        self.from_area: str = from_area
        self.to_screen: str = to_screen


class ScreenRoute:

    def __init__(self, from_screen: str, to_screen: str):
        """
        记录两个画面质检跳转的路径
        :param from_screen:
        :param to_screen:
        """
        self.from_screen: str = from_screen
        self.to_screen: str = to_screen
        self.node_list: list[ScreenRouteNode] = []

    @property
    def can_go(self) -> bool:
        """
        :return: 可到达
        """
        return self.node_list is not None and len(self.node_list) > 0


class ScreenContext:

    def __init__(self):
        self.screen_info_list: list[ScreenInfo] = []
        self.screen_info_map: dict[str, ScreenInfo] = {}
        self._screen_area_map: dict[str, ScreenArea] = {}
        self.screen_route_map: dict[str, dict[str, ScreenRoute]] = {}

        self.last_screen_name: Optional[str] = None  # 上一个画面名字
        self.current_screen_name: Optional[str] = None  # 当前的画面名字

    def load_all(self) -> None:
        """
        加载当前全部的画面
        :return:
        """
        self.screen_info_list.clear()
        self.screen_info_map.clear()
        self._screen_area_map.clear()

        dir_path = ScreenInfo.get_dir_path()
        for file_name in os.listdir(dir_path):
            file_path = os.path.join(dir_path, file_name)
            if file_name.endswith('.yml') and os.path.isfile(file_path):
                screen_info = ScreenInfo(screen_id=file_name[:-4])
                self.screen_info_list.append(screen_info)
                self.screen_info_map[screen_info.screen_name] = screen_info

                for screen_area in screen_info.area_list:
                    self._screen_area_map[f'{screen_info.screen_name}.{screen_area.area_name}'] = screen_area

        self.init_screen_route()

    def get_screen(self, screen_name: str) -> ScreenInfo:
        """
        获取某个画面
        :param screen_name:
        :return:
        """
        key = screen_name
        return self.screen_info_map.get(key, None)

    def get_area(self, screen_name: str, area_name: str) -> ScreenArea:
        """
        获取某个区域的信息
        :return:
        """
        key = f'{screen_name}.{area_name}'
        return self._screen_area_map.get(key, None)

    def init_screen_route(self) -> None:
        """
        初始化画面间的跳转路径
        :return:
        """
        # 先对任意两个画面之间做初始化
        for screen_1 in self.screen_info_list:
            self.screen_route_map[screen_1.screen_name] = {}
            for screen_2 in self.screen_info_list:
                self.screen_route_map[screen_1.screen_name][screen_2.screen_name] = ScreenRoute(
                    from_screen=screen_1.screen_name,
                    to_screen=screen_2.screen_name
                )

        # 根据画面的goto_list来初始化边
        for screen_info in self.screen_info_list:
            for area in screen_info.area_list:
                if area.goto_list is None or len(area.goto_list) == 0:
                    continue
                from_screen_route = self.screen_route_map[screen_info.screen_name]
                if from_screen_route is None:
                    log.error('画面路径没有初始化 %s', screen_info.screen_name)
                    continue
                for goto_screen_name in area.goto_list:
                    if goto_screen_name not in from_screen_route:
                        log.error('画面路径 %s -> %s 无法找到目标画面', screen_info.screen_name, goto_screen_name)
                        continue
                    from_screen_route[goto_screen_name].node_list.append(
                        ScreenRouteNode(
                            from_screen=screen_info.screen_name,
                            from_area=area.area_name,
                            to_screen=goto_screen_name
                        )
                    )

        # Floyd算出任意两个画面之间的路径
        screen_len = len(self.screen_info_list)
        for k in range(screen_len):
            screen_k = self.screen_info_list[k]
            for i in range(screen_len):
                if i == k:
                    continue
                screen_i = self.screen_info_list[i]

                route_ik: ScreenRoute = self.screen_route_map[screen_i.screen_name][screen_k.screen_name]
                if not route_ik.can_go:  # 无法从 i 到 k
                    continue

                for j in range(screen_len):
                    if k == j or i == j:
                        continue
                    screen_j = self.screen_info_list[j]

                    route_kj: ScreenRoute = self.screen_route_map[screen_k.screen_name][screen_j.screen_name]
                    if not route_kj.can_go:  # 无法从 k 到 j
                        continue

                    route_ij: ScreenRoute = self.screen_route_map[screen_i.screen_name][screen_j.screen_name]

                    if (not route_ij.can_go  # 当前无法从 i 到 j
                        or len(route_ik.node_list) + len(route_kj.node_list) < len(route_ij.node_list)  # 新的更短
                    ):
                        route_ij.node_list = []
                        for node_ik in route_ik.node_list:
                            route_ij.node_list.append(node_ik)
                        for node_kj in route_kj.node_list:
                            route_ij.node_list.append(node_kj)

    def get_screen_route(self, from_screen: str, to_screen: str) -> Optional[ScreenRoute]:
        """
        获取两个画面之间的
        :param from_screen:
        :param to_screen:
        :return:
        """
        from_route = self.screen_route_map.get(from_screen, None)
        if from_route is None:
            return None
        return from_route.get(to_screen, None)

    def update_current_screen_name(self, screen_name: str) -> None:
        """
        更新当前的画面名字
        """
        self.last_screen_name = self.current_screen_name
        self.current_screen_name = screen_name