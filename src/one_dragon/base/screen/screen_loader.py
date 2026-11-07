import inspect
import os
from collections.abc import Callable
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
        self._extra_screen_source: Callable[[], list[tuple[Path, str]]] | None = None
        """插件画面来源回调：返回 [(画面目录, 默认 app_id)]；每次重建现取，None 表示不注入。"""
        self._manual_extra_screen_dirs: dict[Path, str] = {}
        """手工登记的插件画面目录（load_extra_screen_dir 写入，bagel ensure_screens 用）。"""
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

    def set_extra_screen_source(self, source: Callable[[], list[tuple[Path, str]]] | None) -> None:
        """设置插件画面来源回调，之后每次非 from_memory 重建都会现取。

        Args:
            source: 返回 [(画面目录, 默认 app_id)] 的函数；None 表示不注入插件画面。
        """
        self._extra_screen_source = source

    def _collect_extra_sources(self) -> dict[Path, str]:
        """汇总回调与手工登记的插件画面目录，按 resolve 后路径去重。

        同一目录同时来自回调与手工登记时只保留一份；app_id 不一致时 warning，
        并以回调为准（回调代表插件当前声明）。
        """
        sources: dict[Path, str] = {}
        if self._extra_screen_source is not None:
            for dir_path, default_app_id in self._extra_screen_source():
                key = Path(dir_path).resolve()
                if key in sources and sources[key] != default_app_id:
                    log.warning(
                        f"插件画面来源 app_id 不一致，使用回调值: {key} "
                        f"{sources[key]} -> {default_app_id}"
                    )
                sources[key] = default_app_id
        for dir_path, default_app_id in self._manual_extra_screen_dirs.items():
            key = Path(dir_path).resolve()
            if key in sources:
                if sources[key] != default_app_id:
                    log.warning(
                        f"插件画面来源 app_id 不一致，保留回调值: {key} "
                        f"{sources[key]} vs {default_app_id}"
                    )
                continue
            sources[key] = default_app_id
        return sources

    def reload(self, from_memory: bool = False, from_separated_files: bool = False) -> bool:
        """重建主配置与插件画面，返回是否成功。

        插件安装/卸载不要调这里（用 OneDragonContext.refresh_application_registration）；
        需要显式重读磁盘时直接调用本方法（devtools 的「更新」、init 都是直调）。

        先构建完整新状态、成功后一次性替换；构建中任何异常都保留原状态并返回 False，
        避免插件画面已清空、主配置却加载失败这种半更新状态。

        ``from_memory=True`` 只用内存重建 base 与派生状态，不读取、不重建插件目录；
        插件画面保持内存里的对象，供 devtools 保存后回读。

        Args:
            from_memory: 是否从内存中加载 管理画面修改的是 self._id_2_screen 修改后从这里更新其它内存值
            from_separated_files: 是否从单独文件加载

        Returns:
            是否重载成功；失败时内存保持重载前的状态。
        """
        self._log_reload_caller(from_memory)
        if from_memory:
            base = self._build_base(True, False)
            extras = {
                screen_id: self._id_2_screen[screen_id]
                for screen_id in self._extra_screen_ids
                if screen_id in self._id_2_screen
            }
            extra_paths = dict(self._extra_screen_paths)
            return self._apply_state(base, extras, extra_paths)

        try:
            base = self._build_base(from_memory, from_separated_files)
            extras, extra_paths = self._build_extras(base, self._collect_extra_sources())
        except Exception:
            log.error('画面重载失败，保留原状态', exc_info=True)
            return False
        return self._apply_state(base, extras, extra_paths)

    def _log_reload_caller(self, from_memory: bool) -> None:
        """记录触发重载的调用方模块/行号（只定位，不拦截）。"""
        frame = inspect.currentframe()
        try:
            caller = frame.f_back if frame is not None else None
            if caller is not None and caller.f_code.co_filename == __file__:
                # 跳过 reload 自身帧，取真实调用方
                caller = caller.f_back
            if caller is not None and caller.f_code.co_filename == __file__:
                # save/_save_extra_screen/delete_screen 内部的 from_memory 重载不刷 info
                log.debug(
                    '画面重载 caller=screen_loader.%s from_memory=%s',
                    caller.f_code.co_name, from_memory,
                )
                return
            if caller is None:
                log.debug('画面重载 caller=未知 from_memory=%s', from_memory)
                return
            log.info(
                '画面重载 caller=%s:%s from_memory=%s',
                caller.f_globals.get('__name__'), caller.f_lineno, from_memory,
            )
        finally:
            del frame

    def _build_base(
        self, from_memory: bool, from_separated_files: bool,
    ) -> dict[str, ScreenInfo]:
        """构建主配置（内存/分离文件/合并文件），不修改现有内存表。

        base 文件解析/构造异常向上抛，由 reload 统一兜底保留旧状态。
        """
        base: dict[str, ScreenInfo] = {}
        names: set[str] = set()

        def add(screen_info: ScreenInfo) -> None:
            if screen_info.screen_name in names:
                log.warning(f"画面名称冲突，已跳过: {screen_info.screen_name}")
                return
            if screen_info.screen_id in base:
                log.warning(f"画面ID冲突，已跳过: {screen_info.screen_id}")
                return
            base[screen_info.screen_id] = screen_info
            names.add(screen_info.screen_name)

        if from_memory:
            for screen_id, screen_info in self._id_2_screen.items():
                if screen_id in self._extra_screen_ids:
                    continue
                add(screen_info)
        elif from_separated_files:
            for file_path in sorted(
                self.yml_file_dir.iterdir(), key=lambda path: path.name.casefold(),
            ):
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
                add(ScreenInfo(data))
        else:
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
                add(ScreenInfo(data))
        return base

    def _build_extras(
        self, base: dict[str, ScreenInfo], extra_sources: dict[Path, str],
    ) -> tuple[dict[str, ScreenInfo], dict[str, Path]]:
        """按来源目录构建插件画面，不修改现有内存表。

        同名/同 id 冲突时先遍历到的优先：来源目录按 str(path).casefold() 排序、
        目录内文件按文件名 casefold 排序，遍历顺序显式且稳定。
        """
        base_names = {screen_info.screen_name for screen_info in base.values()}
        extras: dict[str, ScreenInfo] = {}
        extra_paths: dict[str, Path] = {}
        extra_names: set[str] = set()

        for screen_dir in sorted(extra_sources, key=lambda path: str(path).casefold()):
            default_app_id = extra_sources[screen_dir]
            if not screen_dir.is_dir():
                continue
            try:
                file_paths = sorted(screen_dir.iterdir(), key=lambda path: path.name.casefold())
            except OSError:
                log.warning(f"插件画面目录读取失败，已跳过: {screen_dir}")
                continue
            for file_path in file_paths:
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
                if screen_info.screen_name in base_names or screen_info.screen_name in extra_names:
                    log.warning(
                        f"插件画面名称冲突，已跳过: {screen_info.screen_name}（{file_path}）"
                    )
                    continue
                if screen_info.screen_id in base or screen_info.screen_id in extras:
                    log.warning(
                        f"插件画面 ID 冲突，已跳过: {screen_info.screen_id}（{file_path}）"
                    )
                    continue
                extras[screen_info.screen_id] = screen_info
                extra_paths[screen_info.screen_id] = file_path
                extra_names.add(screen_info.screen_name)
        return extras, extra_paths

    def _apply_state(
        self,
        base: dict[str, ScreenInfo],
        extras: dict[str, ScreenInfo],
        extra_paths: dict[str, Path],
    ) -> bool:
        """一次性替换四张内存表与两张派生表，并重建路由/global/scope。

        重建派生状态若抛错，恢复替换前的状态并返回 False。
        """
        snapshot = self._snapshot_state()
        try:
            self.screen_info_list = list(base.values()) + list(extras.values())
            self.screen_info_map = {
                screen_info.screen_name: screen_info for screen_info in self.screen_info_list
            }
            self._id_2_screen = {
                screen_info.screen_id: screen_info for screen_info in self.screen_info_list
            }
            self._screen_area_map = {}
            for screen_info in self.screen_info_list:
                for screen_area in screen_info.area_list:
                    self._screen_area_map[f'{screen_info.screen_name}.{screen_area.area_name}'] = screen_area
            self._extra_screen_ids = set(extras)
            self._extra_screen_paths = dict(extra_paths)
            self._refresh_derived_state()
        except Exception:
            log.error('画面状态应用失败，恢复旧状态', exc_info=True)
            self._restore_state(snapshot)
            return False
        return True

    def _snapshot_state(self) -> tuple:
        """保存当前画面状态引用，供 _apply_state 失败时回滚。"""
        return (
            self.screen_info_list,
            self.screen_info_map,
            self._id_2_screen,
            self._screen_area_map,
            self._extra_screen_ids,
            self._extra_screen_paths,
            dict(self._manual_extra_screen_dirs),
            {name: dict(routes) for name, routes in self.screen_route_map.items()},
            self._global_screen_names,
            self._local_screen_names,
            self._scoped,
            self._scope_app_id,
        )

    def _restore_state(self, snapshot: tuple) -> None:
        """恢复 _snapshot_state 保存的画面状态。"""
        (
            self.screen_info_list,
            self.screen_info_map,
            self._id_2_screen,
            self._screen_area_map,
            self._extra_screen_ids,
            self._extra_screen_paths,
            self._manual_extra_screen_dirs,
            self.screen_route_map,
            self._global_screen_names,
            self._local_screen_names,
            self._scoped,
            self._scope_app_id,
        ) = snapshot

    def _drop_screen(self, screen_id: str) -> None:
        """把画面从四张内存表摘掉并更新派生表（删插件画面文件成功后用）。"""
        screen_info = self._id_2_screen.pop(screen_id, None)
        if screen_info is not None:
            self.screen_info_map.pop(screen_info.screen_name, None)
            for index, item in enumerate(self.screen_info_list):
                if item is screen_info:
                    self.screen_info_list.pop(index)
                    break
            for screen_area in screen_info.area_list:
                self._screen_area_map.pop(f'{screen_info.screen_name}.{screen_area.area_name}', None)
        self._extra_screen_ids.discard(screen_id)
        self._extra_screen_paths.pop(screen_id, None)
        self._refresh_derived_state()

    def _refresh_derived_state(self) -> None:
        """重建路由、全局画面集合与当前 scope。"""
        self.init_screen_route()
        self._global_screen_names = {
            s.screen_name for s in self.screen_info_list if not s.app_id
        }
        self._refresh_scope()

    def _load_extras(self) -> bool:
        """按当前来源重建插件画面，返回是否成功。

        来源每次现取：回调（插件当前 plugin_infos）+ 手工登记目录。单独调用也一次性
        替换，失败保留原状态。同名/同 id 冲突时先遍历到的优先：来源目录按
        str(path).casefold() 排序、目录内文件按文件名 casefold 排序，遍历顺序显式且稳定。
        """
        base = {
            screen_id: screen_info
            for screen_id, screen_info in self._id_2_screen.items()
            if screen_id not in self._extra_screen_ids
        }
        try:
            extras, extra_paths = self._build_extras(base, self._collect_extra_sources())
        except Exception:
            log.error('插件画面重建失败，保留原状态', exc_info=True)
            return False
        return self._apply_state(base, extras, extra_paths)

    def reload_extra_screens(self) -> bool:
        """只重建插件画面层（refresh 的唯一入口；不重载主配置），返回是否成功。"""
        return self._load_extras()

    def unload_extra_screens(self) -> bool:
        """清空手工登记的插件画面来源并重建插件层，返回是否成功。

        来源回调仍会提供插件目录，因此卸载只对 load_extra_screen_dir 手工注入的画面
        生效；回调目录会在下一次重建时回来。
        """
        self._manual_extra_screen_dirs.clear()
        return self._load_extras()

    def load_extra_screen_dir(self, dir_path: str, default_app_id: str = '') -> bool:
        """手工登记插件画面来源目录并立刻重建插件层（登记即生效），返回是否成功。

        Args:
            dir_path: 包含 screen YAML 的目录路径
            default_app_id: 插件 screen 未声明 app_id 时使用的默认值
        """
        self._manual_extra_screen_dirs[Path(dir_path)] = default_app_id
        return self._load_extras()

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

    def save_screen(self, screen_info: ScreenInfo) -> bool:
        """保存画面。

        改名时先写新文件/新状态，成功后再删旧文件，避免写失败丢旧画面。

        Returns:
            True 成功；False 已知冲突或写盘失败（旧文件与内存保持原样）。
        """
        old_screen_id = screen_info.old_screen_id
        if old_screen_id in self._extra_screen_ids:
            return self._save_extra_screen(screen_info)
        if screen_info.screen_id in self._extra_screen_ids:
            # 基础画面改成插件已占用的 id：直接写会覆盖内存里的插件画面并让 base 丢写。
            log.warning(
                f"基础画面不能改成插件画面 ID，已跳过保存: {old_screen_id} → {screen_info.screen_id}"
            )
            return False
        plugin_names = {
            self._id_2_screen[screen_id].screen_name
            for screen_id in self._extra_screen_ids
            if screen_id in self._id_2_screen
        }
        if screen_info.screen_name in plugin_names:
            # 名称也是冲突源：否则保存后重建会把插件画面挤掉、base 变成同名画面。
            log.warning(
                f"基础画面不能改成插件画面名称，已跳过保存: {old_screen_id} → {screen_info.screen_name}"
            )
            return False

        renamed = bool(old_screen_id) and old_screen_id != screen_info.screen_id
        old_info = self._id_2_screen.get(old_screen_id) if old_screen_id else None
        if renamed:
            self._id_2_screen.pop(old_screen_id, None)
        self._id_2_screen[screen_info.screen_id] = screen_info
        try:
            self.save(screen_id=screen_info.screen_id)
        except OSError:
            log.error(f"保存画面失败，已回滚内存: {screen_info.screen_id}", exc_info=True)
            self._id_2_screen.pop(screen_info.screen_id, None)
            if old_screen_id and old_info is not None:
                self._id_2_screen[old_screen_id] = old_info
            return False

        if renamed:
            old_file_path = self.get_yml_file_path(old_screen_id)
            if old_file_path.exists():
                try:
                    old_file_path.unlink()
                except OSError:
                    log.error(f"新配置已保存，旧文件删除失败: {old_file_path}", exc_info=True)
                    screen_info.old_screen_id = screen_info.screen_id
                    return False
        screen_info.old_screen_id = screen_info.screen_id
        return True

    def delete_screen(self, screen_id: str, save: bool = True) -> bool:
        """
        删除一个画面
        Args:
            screen_id: 画面ID
            save: 是否触发保存

        Returns:
            True 成功；False 删除文件失败（内存保持原样）。
        """
        if screen_id in self._extra_screen_ids:
            # 插件画面：先删文件，失败则保留内存状态；成功后直接摘内存，不重读磁盘。
            extra_file_path = self._extra_screen_paths.get(screen_id)
            if extra_file_path is None:
                log.error(f"插件画面缺少文件路径登记，已跳过删除: {screen_id}")
                return False
            if extra_file_path.exists():
                try:
                    extra_file_path.unlink()
                except OSError:
                    log.error(f"删除插件画面文件失败，保留内存状态: {extra_file_path}", exc_info=True)
                    return False
            self._drop_screen(screen_id)
            return True

        # 基础画面：同样先删文件，失败则不碰内存；成功后再摘除并重建派生状态。
        file_path = self.get_yml_file_path(screen_id)
        if file_path.exists():
            try:
                file_path.unlink()
            except OSError:
                log.error(f"删除画面文件失败，保留内存状态: {file_path}", exc_info=True)
                return False
        if screen_id in self._id_2_screen:
            del self._id_2_screen[screen_id]
            self._refresh_derived_state()

        if save:
            try:
                self.save(screen_id=screen_id)
            except OSError:
                log.error(f"删除画面后保存失败: {screen_id}", exc_info=True)
                return False
            return True
        return self.reload(from_memory=True)

    def _save_extra_screen(self, screen_info: ScreenInfo) -> bool:
        """保存插件 screen 到原插件目录的独立 YAML。

        先写新文件成功后再删旧文件、更新内存；写盘失败回滚内存、旧文件保留。

        Returns:
            True 成功；False 冲突、写盘失败或回读失败。
        """
        old_screen_id = screen_info.old_screen_id
        if old_screen_id not in self._extra_screen_ids:
            return False
        old_file_path = self._extra_screen_paths.get(old_screen_id)
        if old_file_path is None:
            return False

        # from_memory 不重读插件目录；改成别的画面的 id/name 会覆盖 base 或其它插件且无法自愈。
        base_ids = set(self._id_2_screen) - self._extra_screen_ids
        base_names = {
            self._id_2_screen[screen_id].screen_name
            for screen_id in base_ids
            if screen_id in self._id_2_screen
        }
        other_ids = self._extra_screen_ids - {old_screen_id}
        other_names = {
            self._id_2_screen[screen_id].screen_name
            for screen_id in other_ids
            if screen_id in self._id_2_screen
        }
        if (
            screen_info.screen_id in base_ids
            or screen_info.screen_name in base_names
            or screen_info.screen_id in other_ids
            or screen_info.screen_name in other_names
        ):
            log.warning(
                f"插件画面不能改成其它画面的 ID/名称，已跳过保存: "
                f"{old_screen_id} → {screen_info.screen_id}/{screen_info.screen_name}"
            )
            return False

        renamed = old_screen_id != screen_info.screen_id
        if renamed:
            try:
                file_path = old_file_path.with_name(f'{screen_info.screen_id}.yml')
            except (OSError, ValueError):
                log.error(f"插件画面 ID 无法生成合法文件名: {screen_info.screen_id}", exc_info=True)
                return False
        else:
            file_path = old_file_path

        temp_path = file_path.with_name(f'.{file_path.name}.tmp')
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with temp_path.open('w', encoding='utf-8') as file:
                yaml.safe_dump(screen_info.to_dict(), file, allow_unicode=True, default_flow_style=False, sort_keys=False)
            os.replace(temp_path, file_path)
        except (OSError, ValueError):
            log.error(f"插件画面写入失败，保留旧文件: {file_path}", exc_info=True)
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass
            return False

        delete_old_failed = False
        if renamed and old_file_path.exists():
            try:
                old_file_path.unlink()
            except OSError:
                log.error(f"新配置已保存，旧文件删除失败: {old_file_path}", exc_info=True)
                delete_old_failed = True

        screen_info.old_screen_id = screen_info.screen_id
        # 显式维护内存：from_memory 重载不读插件目录，这里先把对象/派生表改成新值。
        if renamed:
            self._id_2_screen.pop(old_screen_id, None)
            self._extra_screen_ids.discard(old_screen_id)
            self._extra_screen_paths.pop(old_screen_id, None)
        self._id_2_screen[screen_info.screen_id] = screen_info
        self._extra_screen_ids.add(screen_info.screen_id)
        self._extra_screen_paths[screen_info.screen_id] = file_path
        if not self.reload(from_memory=True):
            log.error(f"插件画面已写入文件，但内存回读失败: {file_path}")
            return False
        return not delete_old_failed

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
                goto_list = area.goto_list
                if not isinstance(goto_list, (list, tuple)) or len(goto_list) == 0:
                    continue
                from_screen_route = self.screen_route_map[screen_info.screen_name]
                if from_screen_route is None:
                    log.error('画面路径没有初始化 %s', screen_info.screen_name)
                    continue
                for goto_screen_name in goto_list:
                    if not isinstance(goto_screen_name, str):
                        continue
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
