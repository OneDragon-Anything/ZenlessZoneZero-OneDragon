import os
from typing import Optional

import yaml

from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.base.screen.screen_info import ScreenInfo
from one_dragon.utils import os_utils
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
        self._id_2_screen: dict[str, ScreenInfo] = {}
        self.screen_route_map: dict[str, dict[str, ScreenRoute]] = {}

        self.last_screen_name: Optional[str] = None  # 上一个画面名字
        self.current_screen_name: Optional[str] = None  # 当前的画面名字

    @property
    def yml_file_dir(self) -> str:
        return os_utils.get_path_under_work_dir('assets', 'game_data', 'screen_info')

    @property
    def merge_yml_file_path(self) -> str:
        return os.path.join(self.yml_file_dir, '_od_merged.yml')

    def get_yml_file_path(self, screen_id: str) -> str:
        return os.path.join(self.yml_file_dir, f'{screen_id}.yml')

    def reload(self, from_memory: bool = False, from_separated_files: bool = False) -> None:
        """
        重新加载配置文件

        Args:
            from_memory: 是否从内存中加载 管理画面修改的是 self._id_2_screen 修改后从这里更新其它内存值
            from_separated_files: 是否从单独文件加载
        """
        self.screen_info_list.clear()
        self.screen_info_map.clear()
        self._screen_area_map.clear()

        if from_memory:
            for screen_info in self._id_2_screen.values():
                self.screen_info_list.append(screen_info)
                self.screen_info_map[screen_info.screen_name] = screen_info

                for screen_area in screen_info.area_list:
                    self._screen_area_map[f'{screen_info.screen_name}.{screen_area.area_name}'] = screen_area
        elif from_separated_files:
            self._id_2_screen.clear()
            for file_name in os.listdir(self.yml_file_dir):
                if not file_name.endswith('.yml'):
                    continue
                if file_name == '_od_merged.yml':
                    continue
                file_path = os.path.join(self.yml_file_dir, file_name)
                with open(file_path, 'r', encoding='utf-8') as file:
                    log.debug(f"加载yaml: {file_path}")
                    data = yaml.safe_load(file)

                screen_info = ScreenInfo(data)
                self.screen_info_list.append(screen_info)
                self.screen_info_map[screen_info.screen_name] = screen_info
                self._id_2_screen[screen_info.screen_id] = screen_info

                for screen_area in screen_info.area_list:
                    self._screen_area_map[f'{screen_info.screen_name}.{screen_area.area_name}'] = screen_area
        else:
            self._id_2_screen.clear()
            file_path = self.merge_yml_file_path
            with open(file_path, 'r', encoding='utf-8') as file:
                log.debug(f"加载yaml: {file_path}")
                yaml_data = yaml.safe_load(file)
            for data in yaml_data:
                screen_info = ScreenInfo(data)
                self.screen_info_list.append(screen_info)
                self.screen_info_map[screen_info.screen_name] = screen_info
                self._id_2_screen[screen_info.screen_id] = screen_info

                for screen_area in screen_info.area_list:
                    self._screen_area_map[f'{screen_info.screen_name}.{screen_area.area_name}'] = screen_area

        self.init_screen_route()

    def get_screen(self, screen_name: str, copy: bool = False) -> ScreenInfo:
        """
        获取某个画面

        Args:
            screen_name: 画面名称
            copy: 是否复制 用于管理界面临时修改使用

        Returns:
            ScreenInfo 画面信息
        """
        key = screen_name
        screen = self.screen_info_map.get(key, None)
        if screen is None:
            raise Exception(f"未找到画面: {screen_name}")
        if copy:
            return ScreenInfo(screen.to_dict())
        else:
            return screen

    def get_area(self, screen_name: str, area_name: str) -> ScreenArea:
        """
        获取某个区域的信息
        :return:
        """
        key = f'{screen_name}.{area_name}'
        return self._screen_area_map.get(key, None)

    def save_screen(self, screen_info: ScreenInfo) -> None:
        """
        保存画面

        Args:
            screen_info: 画面信息
        """
        if screen_info.old_screen_id != screen_info.screen_id:
            self.delete_screen(screen_info.old_screen_id, save=False)
        self._id_2_screen[screen_info.screen_id] = screen_info
        self.save(screen_id=screen_info.screen_id)

    def delete_screen(self, screen_id: str, save: bool = True) -> None:
        """
        删除一个画面
        Args:
            screen_id: 画面ID
            save: 是否触发保存
        """
        if screen_id in self._id_2_screen:
            del self._id_2_screen[screen_id]

            file_path = self.get_yml_file_path(screen_id)
            if os.path.exists(file_path):
                os.remove(file_path)

        if save:
            self.save(screen_id=screen_id)
        else:
            self.reload(from_memory=True)

    def save(self, screen_id: str | None = None, reload_after_save: bool = True) -> None:
        """
        保存到文件

        Args:
            screen_id: 画面ID
            reload_after_save: 保存后是否重新加载
        """
        all_data = []

        # 保存到单个文件
        for screen_info in self._id_2_screen.values():
            data = screen_info.to_dict()
            all_data.append(data)

            if screen_id is not None and screen_id == screen_info.screen_id:
                with open(self.get_yml_file_path(screen_id), 'w', encoding='utf-8') as file:
                    yaml.safe_dump(data, file, allow_unicode=True, default_flow_style=False, sort_keys=False)

        # 保存到合并文件
        with open(self.merge_yml_file_path, 'w', encoding='utf-8') as file:
            yaml.safe_dump(all_data, file, allow_unicode=True, default_flow_style=False, sort_keys=False)

        if reload_after_save:
            self.reload(from_memory=True)

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
