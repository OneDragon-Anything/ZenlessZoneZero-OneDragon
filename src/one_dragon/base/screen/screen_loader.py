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
        self._extra_screen_dirs: dict[Path, str] = {}
        """插件画面来源：目录 → 未声明 app_id 时的默认应用 ID。由 load_extra_screen_dir / set_extra_screen_dirs 写。"""
        self._extra_screen_ids: set[str] = set()
        """派生：当前内存里确实来自插件目录的画面 ID（save 过滤用）。每次 _load_extras 重建。"""
        self._extra_screen_paths: dict[str, Path] = {}
        """派生：插件画面 ID → 所在 yml 路径（devtools 编辑插件画面用）。每次 _load_extras 重建。"""
        self.screen_route_map: dict[str, dict[str, ScreenRoute]] = {}

        self.last_screen_name: str | None = None  # 上一个画面名字
        self.current_screen_name: str | None = None  # 当前的画面名字

        # 屏幕作用域管理
        self._global_screen_names: set[str] = set()
        self._local_screen_names: set[str] = set()
        self._scoped: bool = False
        self._scope_app_id: str = ''
        """当前 scope 对应的应用 ID；画面集合变化后按它重算局部集合。"""

    @property
    def yml_file_dir(self) -> Path:
        return Path(os_utils.get_path_under_work_dir('assets', 'game_data', 'screen_info'))

    @property
    def merge_yml_file_path(self) -> Path:
        return self.yml_file_dir / '_od_merged.yml'

    def get_yml_file_path(self, screen_id: str) -> Path:
        return self.yml_file_dir / f'{screen_id}.yml'

    def reload(self, from_memory: bool = False, from_separated_files: bool = False) -> None:
        """重建主配置与插件画面。

        插件安装/卸载不要调这里（用 OneDragonContext.refresh_application_registration）；
        需要显式重读磁盘时用 OneDragonContext.reload_screens()。

        Args:
            from_memory: 是否从内存中加载 管理画面修改的是 self._id_2_screen 修改后从这里更新其它内存值
            from_separated_files: 是否从单独文件加载
        """
        prev_extra = set(self._extra_screen_ids)
        # 先摘掉上一轮插件画面，再加载 base：反过来会让新出现的同名 base 画面
        # 先进入内存、随后被「上一轮插件 id」当成插件摘掉，save() 就丢了 base。
        for screen_id in prev_extra:
            self._remove_screen(screen_id)
        self._extra_screen_ids.clear()
        self._extra_screen_paths.clear()
        self._load_base(from_memory, from_separated_files)
        self._load_extras()

    def _load_base(self, from_memory: bool, from_separated_files: bool) -> None:
        """只加载主配置（内存/分离文件/合并文件），不碰插件画面。"""
        self.screen_info_list.clear()
        self.screen_info_map.clear()
        self._screen_area_map.clear()

        if from_memory:
            for screen_info in self._id_2_screen.values():
                self._append_screen(screen_info)
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
                if screen_info.screen_name in self.screen_info_map:
                    log.warning(f"画面名称冲突，已跳过: {screen_info.screen_name}")
                    continue
                if screen_info.screen_id in self._id_2_screen:
                    log.warning(f"画面ID冲突，已跳过: {screen_info.screen_id}")
                    continue
                self._append_screen(screen_info)
        else:
            self._id_2_screen.clear()
            file_path = self.merge_yml_file_path
            if file_path.exists():
                with file_path.open(encoding='utf-8') as file:
                    log.debug(f"加载yaml: {file_path}")
                    yaml_data = yaml_utils.safe_load(file)
            else:
                log.info(f"合并画面配置文件不存在，按空配置加载: {file_path}")
                yaml_data = []
            if not isinstance(yaml_data, list):
                if yaml_data is not None:
                    log.warning(f"合并画面配置格式错误，已忽略: {file_path}")
                yaml_data = []
            for data in yaml_data:
                if not isinstance(data, dict):
                    log.warning(f"合并画面配置中存在非字典条目，已跳过: {file_path}")
                    continue
                screen_info = ScreenInfo(data)
                if screen_info.screen_name in self.screen_info_map:
                    log.warning(f"画面名称冲突，已跳过: {screen_info.screen_name}")
                    continue
                if screen_info.screen_id in self._id_2_screen:
                    log.warning(f"画面ID冲突，已跳过: {screen_info.screen_id}")
                    continue
                self._append_screen(screen_info)

    def _append_screen(self, screen_info: ScreenInfo) -> None:
        """把画面登记进四张内存表。"""
        self.screen_info_list.append(screen_info)
        self.screen_info_map[screen_info.screen_name] = screen_info
        self._id_2_screen[screen_info.screen_id] = screen_info
        for screen_area in screen_info.area_list:
            self._screen_area_map[f'{screen_info.screen_name}.{screen_area.area_name}'] = screen_area

    def _remove_screen(self, screen_id: str) -> None:
        """从内存各表里摘掉一个画面；不在内存里时什么也不做。"""
        screen_info = self._id_2_screen.pop(screen_id, None)
        if screen_info is None:
            return
        self.screen_info_map.pop(screen_info.screen_name, None)
        for index, item in enumerate(self.screen_info_list):
            if item is screen_info:
                self.screen_info_list.pop(index)
                break
        for screen_area in screen_info.area_list:
            self._screen_area_map.pop(f'{screen_info.screen_name}.{screen_area.area_name}', None)

    def _refresh_derived_state(self) -> None:
        """重建路由、全局画面集合与当前 scope。"""
        self.init_screen_route()
        self._global_screen_names = {
            s.screen_name for s in self.screen_info_list if not s.app_id
        }
        self._refresh_scope()

    def _load_extras(self) -> None:
        """按来源目录全量重建插件画面；派生表只在这里产生。"""
        for screen_id in list(self._extra_screen_ids):
            self._remove_screen(screen_id)
        self._extra_screen_ids.clear()
        self._extra_screen_paths.clear()

        for screen_dir, default_app_id in self._extra_screen_dirs.items():
            if not screen_dir.is_dir():
                continue
            for file_path in screen_dir.iterdir():
                if file_path.suffix != '.yml':
                    continue
                try:
                    with file_path.open(encoding='utf-8') as file:
                        log.debug(f"加载插件画面: {file_path}")
                        data = yaml_utils.safe_load(file)
                except (OSError, yaml.YAMLError):
                    log.warning(f"插件画面配置读取失败，已跳过: {file_path}")
                    continue
                if not isinstance(data, dict):
                    log.warning(f"插件画面配置格式错误，已跳过: {file_path}")
                    continue
                if default_app_id and not data.get('app_id'):
                    data['app_id'] = default_app_id
                try:
                    screen_info = ScreenInfo(data)
                except Exception:
                    log.warning(f"插件画面配置无效，已跳过: {file_path}")
                    continue
                if screen_info.screen_name in self.screen_info_map:
                    log.warning(
                        f"插件画面名称冲突，已跳过: {screen_info.screen_name}（{file_path}）"
                    )
                    continue
                if screen_info.screen_id in self._id_2_screen:
                    log.warning(
                        f"插件画面 ID 冲突，已跳过: {screen_info.screen_id}（{file_path}）"
                    )
                    continue
                self._append_screen(screen_info)
                self._extra_screen_ids.add(screen_info.screen_id)
                self._extra_screen_paths[screen_info.screen_id] = file_path
        self._refresh_derived_state()

    def set_extra_screen_dirs(self, screen_dirs: dict[Path, str]) -> None:
        """替换插件画面来源表并重建插件层（刷新注册用；不重载主配置）。"""
        self._extra_screen_dirs.clear()
        self._extra_screen_dirs.update(screen_dirs)
        self._load_extras()

    def unload_extra_screens(self) -> None:
        """清空插件画面来源并重建插件层；主配置不动。"""
        self._extra_screen_dirs.clear()
        self._load_extras()

    def load_extra_screen_dir(self, dir_path: str, default_app_id: str = '') -> None:
        """登记插件画面来源目录并立刻重建插件层（登记即生效）。

        Args:
            dir_path: 包含 screen YAML 的目录路径
            default_app_id: 插件 screen 未声明 app_id 时使用的默认值
        """
        self._extra_screen_dirs[Path(dir_path)] = default_app_id
        self._load_extras()

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
        old_screen_id = screen_info.old_screen_id
        if old_screen_id in self._extra_screen_ids:
            self._save_extra_screen(screen_info)
            return
        if screen_info.screen_id in self._extra_screen_ids:
            # 基础画面改成插件已占用的 id：直接写会覆盖内存里的插件画面并让 base 丢写。
            log.warning(
                f"基础画面不能改成插件画面 ID，已跳过保存: {old_screen_id} → {screen_info.screen_id}"
            )
            return

        if old_screen_id and old_screen_id != screen_info.screen_id:
            self.delete_screen(old_screen_id, save=False)
        self._id_2_screen[screen_info.screen_id] = screen_info
        self.save(screen_id=screen_info.screen_id)
        screen_info.old_screen_id = screen_info.screen_id

    def delete_screen(self, screen_id: str, save: bool = True) -> None:
        """
        删除一个画面
        Args:
            screen_id: 画面ID
            save: 是否触发保存
        """
        if screen_id in self._extra_screen_ids:
            # 插件画面：删文件后只重建插件层，主配置不动。
            self._remove_screen(screen_id)
            extra_file_path = self._extra_screen_paths.get(screen_id)
            if extra_file_path is not None and extra_file_path.exists():
                extra_file_path.unlink()
            self._load_extras()
            return

        if screen_id in self._id_2_screen:
            del self._id_2_screen[screen_id]
            file_path = self.get_yml_file_path(screen_id)
            if file_path.exists():
                file_path.unlink()

        if save:
            self.save(screen_id=screen_id)
        else:
            self.reload(from_memory=True)

    def _save_extra_screen(self, screen_info: ScreenInfo) -> None:
        """保存插件 screen 到原插件目录的独立 YAML。"""
        old_screen_id = screen_info.old_screen_id
        if old_screen_id not in self._extra_screen_ids:
            return
        old_file_path = self._extra_screen_paths.get(old_screen_id)
        if old_file_path is None:
            return
        file_path = old_file_path

        if old_screen_id != screen_info.screen_id:
            if old_file_path.exists():
                old_file_path.unlink()
            file_path = old_file_path.with_name(f'{screen_info.screen_id}.yml')

        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open('w', encoding='utf-8') as file:
            yaml.safe_dump(screen_info.to_dict(), file, allow_unicode=True, default_flow_style=False, sort_keys=False)

        screen_info.old_screen_id = screen_info.screen_id
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
        target_screen_id = screen_id
        for current_screen_id, screen_info in self._id_2_screen.items():
            if current_screen_id in self._extra_screen_ids:
                continue

            data = screen_info.to_dict()
            all_data.append(data)

            if target_screen_id is not None and target_screen_id == screen_info.screen_id:
                with self.get_yml_file_path(target_screen_id).open('w', encoding='utf-8') as file:
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
        self.screen_route_map.clear()

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
        self.exit_scope()
        self._scope_app_id = app_id

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
        self._scope_app_id = ''

    def _refresh_scope(self) -> None:
        """画面集合变化后按 scope 应用 ID 重算局部集合。

        集合为空时只清空局部集合、保留 scope 本身：插件画面是随后才注入的，
        这时退出 scope 会丢掉 _scope_app_id，等画面加回来也恢复不了。
        """
        if not self._scoped:
            return
        self._local_screen_names = {
            s.screen_name for s in self.screen_info_list if s.app_id == self._scope_app_id
        }

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
