from pathlib import Path

import yaml

from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.base.screen.screen_info import ScreenInfo
from one_dragon.utils import os_utils, yaml_utils
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

        self.last_screen_name: str | None = None  # 上一个画面名字
        self.current_screen_name: str | None = None  # 当前的画面名字

        # Screen scope management
        self._global_screen_names: set[str] = set()
        self._local_screen_names: set[str] = set()
        self._scoped: bool = False

    @property
    def yml_file_dir(self) -> Path:
        return Path(os_utils.get_path_under_work_dir('assets', 'game_data', 'screen_info'))

    @property
    def merge_yml_file_path(self) -> Path:
        return self.yml_file_dir / '_od_merged.yml'

    def get_yml_file_path(self, screen_id: str) -> Path:
        return self.yml_file_dir / f'{screen_id}.yml'

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
            for file_path in self.yml_file_dir.iterdir():
                if file_path.suffix != '.yml':
                    continue
                if file_path.name == '_od_merged.yml':
                    continue
                with file_path.open(encoding='utf-8') as file:
                    log.debug(f"加载yaml: {file_path}")
                    data = yaml_utils.safe_load(file)
                if not isinstance(data, dict):
                    log.warning(f"画面配置格式错误，已跳过: {file_path}")
                    continue

                screen_info = ScreenInfo(data)
                self.screen_info_list.append(screen_info)
                self.screen_info_map[screen_info.screen_name] = screen_info
                self._id_2_screen[screen_info.screen_id] = screen_info

                for screen_area in screen_info.area_list:
                    self._screen_area_map[f'{screen_info.screen_name}.{screen_area.area_name}'] = screen_area
        else:
            self._id_2_screen.clear()
            file_path = self.merge_yml_file_path
            with file_path.open(encoding='utf-8') as file:
                log.debug(f"加载yaml: {file_path}")
                yaml_data = yaml_utils.safe_load(file)
            if not isinstance(yaml_data, list):
                if yaml_data is not None:
                    log.warning(f"合并画面配置格式错误，已忽略: {file_path}")
                yaml_data = []
            for data in yaml_data:
                if not isinstance(data, dict):
                    log.warning(f"合并画面配置中存在非字典条目，已跳过: {file_path}")
                    continue
                screen_info = ScreenInfo(data)
                self.screen_info_list.append(screen_info)
                self.screen_info_map[screen_info.screen_name] = screen_info
                self._id_2_screen[screen_info.screen_id] = screen_info

                for screen_area in screen_info.area_list:
                    self._screen_area_map[f'{screen_info.screen_name}.{screen_area.area_name}'] = screen_area

        self.init_screen_route()

        # 自动计算全局 screen：没有 app_id 的 screen 为全局
        self._global_screen_names = {
            s.screen_name for s in self.screen_info_list if not s.app_id
        }

    def load_extra_screen_dir(self, dir_path: str, default_app_id: str = '') -> None:
        """从额外目录加载 screen YAML 并注册（用于插件 screen 注入）

        加载后会重新计算路由和全局 screen 集合。

        Args:
            dir_path: 包含 screen YAML 文件的目录路径
            default_app_id: 如果 YAML 中未设置 app_id，使用此默认值
        """
        screen_dir = Path(dir_path)
        if not screen_dir.is_dir():
            return

        added = False
        for file_path in screen_dir.iterdir():
            if file_path.suffix != '.yml':
                continue
            with file_path.open(encoding='utf-8') as file:
                log.debug(f"加载插件画面: {file_path}")
                data = yaml_utils.safe_load(file)
            if not isinstance(data, dict):
                log.warning(f"插件画面配置格式错误，已跳过: {file_path}")
                continue

            if default_app_id and not data.get('app_id'):
                data['app_id'] = default_app_id

            screen_info = ScreenInfo(data)
            if screen_info.screen_name in self.screen_info_map:
                log.warning(f"插件画面名称冲突，已跳过: {screen_info.screen_name}")
                continue

            self.screen_info_list.append(screen_info)
            self.screen_info_map[screen_info.screen_name] = screen_info
            self._id_2_screen[screen_info.screen_id] = screen_info

            for screen_area in screen_info.area_list:
                self._screen_area_map[f'{screen_info.screen_name}.{screen_area.area_name}'] = screen_area
            added = True

        if added:
            self.init_screen_route()
            self._global_screen_names = {
                s.screen_name for s in self.screen_info_list if not s.app_id
            }

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
            if file_path.exists():
                file_path.unlink()

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
                with self.get_yml_file_path(screen_id).open('w', encoding='utf-8') as file:
                    yaml.safe_dump(data, file, allow_unicode=True, default_flow_style=False, sort_keys=False)

        # 保存到合并文件
        with self.merge_yml_file_path.open('w', encoding='utf-8') as file:
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

    def get_screen_route(self, from_screen: str, to_screen: str) -> ScreenRoute | None:
        """
        获取两个画面之间的路径
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

    # ---- Screen Scope 管理 ----
    # 通过 ScreenInfo.app_id 自动区分全局/局部 screen：
    #   - app_id 为空 → 全局 screen，始终参与匹配
    #   - app_id 非空 → 局部 screen，仅在对应应用 scope 内参与匹配
    # reload() 后自动计算全局集合，Application 启动/停止时自动 enter/exit scope

    def enter_scope(self, app_id: str) -> None:
        """进入应用 scope，活跃范围 = 全局 screen + 该 app_id 的局部 screen

        仅当 YAML 中存在 app_id 匹配的 screen 时才真正启用 scope，否则保持全量匹配。

        Args:
            app_id: 当前应用的唯一标识符（与 ScreenInfo.app_id 对应）
        """
        if not self._global_screen_names:
            return  # 所有 screen 都没有 app_id，不启用 scope

        local_names = {s.screen_name for s in self.screen_info_list if s.app_id == app_id}
        if not local_names:
            return  # 该应用没有专属 screen，不启用 scope

        self._local_screen_names = local_names
        self._scoped = True

    def exit_scope(self) -> None:
        """退出应用 scope，恢复全量 screen 匹配"""
        self._local_screen_names.clear()
        self._scoped = False

    @property
    def active_screen_names(self) -> set[str] | None:
        """当前活跃的 screen 名称集合。None 表示全部活跃（未启用 scope）。"""
        if not self._scoped:
            return None
        return self._global_screen_names | self._local_screen_names

    @property
    def active_screen_info_list(self) -> list[ScreenInfo]:
        """当前活跃的 ScreenInfo 列表"""
        names = self.active_screen_names
        if names is None:
            return self.screen_info_list
        return [s for s in self.screen_info_list if s.screen_name in names]

    def is_screen_active(self, screen_name: str) -> bool:
        """判断某个 screen 是否在当前活跃范围内"""
        names = self.active_screen_names
        if names is None:
            return True
        return screen_name in names
