"""插件导入服务

处理第三方插件的导入、解压和验证。

支持的导入方式：
- ZIP 文件：自动解压到 plugins 目录
- 目录：复制到 plugins 目录

主要功能：
- 验证插件结构（factory 文件所在目录必须包含 const 文件）
- 预览插件信息（从 *_const.py 读取）
- 覆盖安装（可选）
- 删除插件
"""

from __future__ import annotations

import inspect
import os
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import TYPE_CHECKING
from uuid import uuid4

from one_dragon.utils.log_utils import log

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_context import OneDragonContext

_MAX_EXTRACT_SIZE: int = 512 * 1024 * 1024


@dataclass
class ImportResult:
    """导入操作结果

    Attributes:
        success: 是否成功
        plugin_name: 插件名称
        message: 结果消息
        plugin_dir: 插件目录路径（如果插件已存在，返回已有目录路径）
        new_version: 新版本号（用于覆盖安装时的版本比较）
    """

    success: bool
    plugin_name: str
    message: str
    plugin_dir: Path | None = None
    new_version: str | None = None


@dataclass
class PluginPreviewInfo:
    """插件预览信息

    用于导入前显示插件的基本信息。

    Attributes:
        plugin_name: 插件名称（目录名）
        version: 版本号
        author: 作者名称
    """

    plugin_name: str
    version: str | None = None
    author: str | None = None


@dataclass(frozen=True)
class _ZipLayout:
    """ZIP 中一个已校验插件根的布局。"""

    plugin_dir_name: str
    members: list[tuple[zipfile.ZipInfo, PurePosixPath]]
    preview_const_info: zipfile.ZipInfo


@dataclass(frozen=True)
class _DirectoryLayout:
    """松散目录中一个已校验插件根的布局。"""

    plugin_dir_name: str
    source_dir: Path
    preview_const_path: Path


class PluginImportService:
    """插件导入服务

    处理第三方插件的导入、解压、验证和删除。
    """

    def __init__(self, ctx: OneDragonContext) -> None:
        self.ctx: OneDragonContext = ctx

    @property
    def plugins_dir(self) -> Path:
        """获取插件目录

        返回项目根目录下的 plugins 目录。
        """
        cls_file = inspect.getfile(self.ctx.__class__)
        parts = Path(cls_file).parts
        try:
            src_index = parts.index("src")
            project_root = Path(*parts[:src_index])
            return project_root / "plugins"
        except ValueError:
            return Path(cls_file).parent.parent / "plugins"

    def import_plugins(self, zip_paths: list[str | Path], overwrite: bool = False) -> list[ImportResult]:
        """按旧单插件语义导入多个 ZIP 文件。"""
        results: list[ImportResult] = []
        for zip_path in zip_paths:
            results.append(self.import_plugin(zip_path, overwrite=overwrite))
        return results

    def import_plugin(self, zip_path: str | Path, overwrite: bool = False) -> ImportResult:
        """按旧单插件语义导入一个 ZIP 文件。"""
        results = self._import_zip_source(
            Path(zip_path),
            overwrite=overwrite,
            selected_plugin_names=None,
            require_single=True,
        )
        return results[0]

    def import_plugins_from_zip(
        self,
        zip_path: str | Path,
        overwrite: bool = False,
        selected_plugin_names: set[str] | None = None,
    ) -> list[ImportResult]:
        """导入一个 ZIP 来源中的全部或指定插件。"""
        return self._import_zip_source(
            Path(zip_path),
            overwrite=overwrite,
            selected_plugin_names=selected_plugin_names,
            require_single=False,
        )

    def _import_zip_source(
        self,
        zip_path: Path,
        overwrite: bool,
        selected_plugin_names: set[str] | None,
        require_single: bool,
    ) -> list[ImportResult]:
        """分析一个 ZIP 来源，并按插件根分别导入。"""
        source_name = zip_path.stem
        if not zip_path.exists():
            return [
                ImportResult(
                    success=False,
                    plugin_name=source_name,
                    message=f"文件不存在: {zip_path}",
                )
            ]

        if zip_path.suffix.lower() != ".zip":
            return [
                ImportResult(
                    success=False,
                    plugin_name=source_name,
                    message="只支持 .zip 格式的文件",
                )
            ]

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                layouts = self._analyze_zip(zf)
                if require_single and len(layouts) != 1:
                    return [
                        ImportResult(
                            success=False,
                            plugin_name=source_name,
                            message="无效的插件结构: ZIP 包含多个互不隶属的插件",
                        )
                    ]

                if selected_plugin_names is not None:
                    requested_names = {name.casefold() for name in selected_plugin_names}
                    available_names = {layout.plugin_dir_name.casefold() for layout in layouts}
                    missing_names = sorted(requested_names - available_names)
                    if missing_names:
                        return [
                            ImportResult(
                                success=False,
                                plugin_name=source_name,
                                message=f"ZIP 中不存在指定插件: {', '.join(missing_names)}",
                            )
                        ]
                    layouts = [
                        layout
                        for layout in layouts
                        if layout.plugin_dir_name.casefold() in requested_names
                    ]

                total_size = sum(
                    info.file_size
                    for layout in layouts
                    for info, _ in layout.members
                    if not info.is_dir()
                )
                if total_size > _MAX_EXTRACT_SIZE:
                    return [
                        ImportResult(
                            success=False,
                            plugin_name=source_name,
                            message=(
                                f"插件解压后体积过大: 总计 {total_size} 字节"
                                f"（上限 {_MAX_EXTRACT_SIZE} 字节）"
                            ),
                        )
                    ]

                return [
                    self._import_zip_layout(zf, layout, overwrite)
                    for layout in layouts
                ]
        except ValueError as e:
            return [
                ImportResult(
                    success=False,
                    plugin_name=source_name,
                    message=str(e),
                )
            ]
        except zipfile.BadZipFile:
            return [
                ImportResult(
                    success=False,
                    plugin_name=source_name,
                    message="无效的 zip 文件",
                )
            ]
        except Exception as e:
            log.error(f"导入 ZIP 来源失败: {e}", exc_info=True)
            return [
                ImportResult(
                    success=False,
                    plugin_name=source_name,
                    message=f"导入失败: {e}",
                )
            ]

    def _import_zip_layout(
        self,
        zf: zipfile.ZipFile,
        layout: _ZipLayout,
        overwrite: bool,
    ) -> ImportResult:
        """独立导入 ZIP 中的一个插件根。"""
        plugin_name = layout.plugin_dir_name
        staging_dir: Path | None = None
        try:
            target_dir = self._get_target_dir(plugin_name)
            if self._path_exists(target_dir) and not overwrite:
                return ImportResult(
                    success=False,
                    plugin_name=plugin_name,
                    message=f"插件目录已存在: {plugin_name}",
                    plugin_dir=target_dir,
                )

            staging_dir = self._new_staging_dir(plugin_name)
            self._extract_plugin(zf, staging_dir, layout)
            self._find_primary_const_file(staging_dir)
            self._replace_plugin_dir(staging_dir, target_dir, overwrite)

            log.info(f"插件导入成功: {plugin_name}")
            return ImportResult(
                success=True,
                plugin_name=plugin_name,
                message="导入成功",
                plugin_dir=target_dir,
            )
        except Exception as e:
            log.error(f"导入插件失败: {plugin_name}, {e}", exc_info=True)
            return ImportResult(
                success=False,
                plugin_name=plugin_name,
                message=f"导入失败: {e}",
            )
        finally:
            if staging_dir is not None and self._path_exists(staging_dir):
                try:
                    self._remove_path(staging_dir)
                except Exception as e:
                    log.warning(f"清理插件临时目录失败: {staging_dir}, {e}")

    def preview_plugin(self, zip_path: str | Path) -> PluginPreviewInfo | None:
        """按旧单插件语义预览一个 ZIP 文件。"""
        previews = self.preview_plugins_from_zip(zip_path)
        return previews[0] if len(previews) == 1 else None

    def preview_plugins_from_zip(self, zip_path: str | Path) -> list[PluginPreviewInfo]:
        """预览一个 ZIP 来源中的全部插件。"""
        zip_path = Path(zip_path)
        if not zip_path.exists() or zip_path.suffix.lower() != ".zip":
            return []

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                layouts = self._analyze_zip(zf)
                return [self._preview_zip_layout(zf, layout) for layout in layouts]
        except Exception:
            return []

    def _preview_zip_layout(
        self,
        zf: zipfile.ZipFile,
        layout: _ZipLayout,
    ) -> PluginPreviewInfo:
        """读取 ZIP 中一个插件根的预览信息。"""
        content = zf.read(layout.preview_const_info).decode("utf-8")
        return PluginPreviewInfo(
            plugin_name=layout.plugin_dir_name,
            version=self._extract_const_value(content, "PLUGIN_VERSION"),
            author=self._extract_const_value(content, "PLUGIN_AUTHOR"),
        )

    def _extract_const_value(self, content: str, const_name: str) -> str | None:
        """从代码内容中提取字符串常量值。"""
        pattern = rf"{const_name}\s*=\s*['\"](.+?)['\"]"
        match = re.search(pattern, content)
        return match.group(1) if match else None

    def _analyze_zip(self, zf: zipfile.ZipFile) -> list[_ZipLayout]:
        """校验 ZIP 成员，并识别全部最外层合法插件根。"""
        archive_members: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
        file_paths: list[PurePosixPath] = []
        path_types: dict[str, bool] = {}

        for info in zf.infolist():
            path = self._normalize_zip_member_path(info.filename)
            if not path.parts or self._is_metadata_path(path):
                continue

            path_key = path.as_posix().casefold()
            if path_key in path_types:
                raise ValueError(f"ZIP 包含重复路径: {info.filename}")
            path_types[path_key] = info.is_dir()
            archive_members.append((info, path))
            if not info.is_dir():
                file_paths.append(path)

        file_path_keys = {path_key for path_key, is_dir in path_types.items() if not is_dir}
        for file_path_key in file_path_keys:
            if any(path_key.startswith(f"{file_path_key}/") for path_key in path_types):
                raise ValueError(f"ZIP 包含文件与目录路径冲突: {file_path_key}")

        plugin_roots = self._find_outermost_plugin_roots(file_paths)
        layouts: list[_ZipLayout] = []
        for plugin_root in plugin_roots:
            root_factory_path = next(
                path
                for path in file_paths
                if path.parent == plugin_root and path.name.endswith("_factory.py")
            )
            plugin_dir_name = (
                plugin_root.name
                if plugin_root.parts
                else root_factory_path.name.removesuffix("_factory.py")
            )
            self._validate_plugin_dir_name(plugin_dir_name)

            preview_const_path = next(
                path
                for path in file_paths
                if path.parent == plugin_root and path.name.endswith("_const.py")
            )
            preview_const_info = next(
                info for info, path in archive_members if path == preview_const_path
            )

            members: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
            for info, path in archive_members:
                if plugin_root.parts:
                    if not path.is_relative_to(plugin_root):
                        continue
                    relative_path = path.relative_to(plugin_root)
                else:
                    relative_path = path

                if relative_path.parts:
                    members.append((info, relative_path))

            layouts.append(
                _ZipLayout(
                    plugin_dir_name=plugin_dir_name,
                    members=members,
                    preview_const_info=preview_const_info,
                )
            )

        self._validate_unique_plugin_names([layout.plugin_dir_name for layout in layouts])
        return layouts

    def _find_outermost_plugin_roots(
        self,
        file_paths: list[PurePosixPath],
    ) -> list[PurePosixPath]:
        """从来源文件列表中找出互不隶属的最外层合法插件根。"""
        factory_paths = sorted(
            (path for path in file_paths if path.name.endswith("_factory.py")),
            key=lambda path: (len(path.parts), path.as_posix()),
        )
        if not factory_paths:
            raise ValueError("无效的插件结构: 缺少 *_factory.py 文件")

        factory_paths_by_dir: dict[PurePosixPath, list[PurePosixPath]] = {}
        const_paths_by_dir: dict[PurePosixPath, list[PurePosixPath]] = {}
        for path in factory_paths:
            factory_paths_by_dir.setdefault(path.parent, []).append(path)
        for path in file_paths:
            if path.name.endswith("_const.py"):
                const_paths_by_dir.setdefault(path.parent, []).append(path)

        plugin_roots: list[PurePosixPath] = []
        for factory_dir in sorted(
            factory_paths_by_dir,
            key=lambda path: (len(path.parts), path.as_posix()),
        ):
            if any(factory_dir == root or factory_dir.is_relative_to(root) for root in plugin_roots):
                continue

            root_factory_paths = factory_paths_by_dir[factory_dir]
            if len(root_factory_paths) > 1:
                raise ValueError("无效的插件结构: 插件根目录不能包含多个 *_factory.py 文件")

            root_const_paths = const_paths_by_dir.get(factory_dir, [])
            if not root_const_paths:
                raise ValueError("无效的插件结构: 插件根目录缺少 *_const.py 文件")
            if len(root_const_paths) > 1:
                raise ValueError("无效的插件结构: 插件根目录不能包含多个 *_const.py 文件")

            plugin_roots.append(factory_dir)

        return plugin_roots

    def _validate_unique_plugin_names(self, plugin_names: list[str]) -> None:
        """拒绝在 Windows 目标目录中会发生冲突的插件名。"""
        seen_names: dict[str, str] = {}
        for plugin_name in plugin_names:
            name_key = plugin_name.casefold()
            existing_name = seen_names.get(name_key)
            if existing_name is not None:
                raise ValueError(
                    f"无效的插件结构: 来源包含重复插件目录名: "
                    f"{existing_name}, {plugin_name}"
                )
            seen_names[name_key] = plugin_name

    def _normalize_zip_member_path(self, member_name: str) -> PurePosixPath:
        """把 ZIP 成员名转换为安全的相对 POSIX 路径。"""
        if not member_name or "\x00" in member_name:
            raise ValueError("ZIP 包含无效路径")

        normalized_name = member_name.replace("\\", "/")
        windows_path = PureWindowsPath(normalized_name)
        path = PurePosixPath(normalized_name)
        if windows_path.drive or windows_path.is_absolute() or path.is_absolute():
            raise ValueError(f"ZIP 包含不安全的绝对路径: {member_name}")
        if any(part == ".." for part in path.parts):
            raise ValueError(f"ZIP 包含不安全的上级路径: {member_name}")
        if any(":" in part or part.endswith((" ", ".")) for part in path.parts):
            raise ValueError(f"ZIP 包含不安全的路径: {member_name}")
        return path

    def _is_metadata_path(self, path: PurePosixPath) -> bool:
        """判断 ZIP 成员是否为可忽略的系统元数据。"""
        return bool(path.parts) and (
            path.parts[0] == "__MACOSX" or ".DS_Store" in path.parts
        )

    def _extract_plugin(self, zf: zipfile.ZipFile, target_dir: Path, layout: _ZipLayout) -> None:
        """把已校验的插件根子树写入临时插件目录。"""
        plugins_root = self._plugins_root()
        target_dir_resolved = target_dir.resolve(strict=False)
        if target_dir_resolved == plugins_root or not target_dir_resolved.is_relative_to(plugins_root):
            raise ValueError("插件临时目录不在 plugins 目录内")

        target_dir.mkdir(parents=True, exist_ok=False)
        for info, relative_path in layout.members:
            dest_path = target_dir.joinpath(*relative_path.parts)
            dest_path_resolved = dest_path.resolve(strict=False)
            if not dest_path_resolved.is_relative_to(target_dir_resolved):
                raise ValueError(f"ZIP 成员路径超出插件目录: {info.filename}")

            if info.is_dir():
                dest_path.mkdir(parents=True, exist_ok=True)
                continue

            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, "r") as source, dest_path.open("wb") as destination:
                shutil.copyfileobj(source, destination)

    def import_directory(self, dir_path: str | Path, overwrite: bool = False) -> ImportResult:
        """按旧单插件语义导入所选目录本身。"""
        dir_path = Path(dir_path)
        plugin_name = dir_path.name
        invalid_result = self._validate_directory_source_path(dir_path)
        if invalid_result is not None:
            return invalid_result

        try:
            const_file = self._find_primary_const_file(dir_path)
            self._validate_plugin_dir_name(plugin_name)
            self._validate_directory_symlinks(dir_path)
        except ValueError as e:
            return ImportResult(success=False, plugin_name=plugin_name, message=str(e))

        return self._import_directory_layout(
            _DirectoryLayout(
                plugin_dir_name=plugin_name,
                source_dir=dir_path,
                preview_const_path=const_file,
            ),
            overwrite,
        )

    def import_plugins_from_directory(
        self,
        dir_path: str | Path,
        overwrite: bool = False,
        selected_plugin_names: set[str] | None = None,
    ) -> list[ImportResult]:
        """导入一个松散目录来源中的全部或指定插件。"""
        dir_path = Path(dir_path)
        source_name = dir_path.name
        invalid_result = self._validate_directory_source_path(dir_path)
        if invalid_result is not None:
            return [invalid_result]

        try:
            layouts = self._analyze_directory(dir_path)
            if selected_plugin_names is not None:
                requested_names = {name.casefold() for name in selected_plugin_names}
                available_names = {layout.plugin_dir_name.casefold() for layout in layouts}
                missing_names = sorted(requested_names - available_names)
                if missing_names:
                    return [
                        ImportResult(
                            success=False,
                            plugin_name=source_name,
                            message=f"目录中不存在指定插件: {', '.join(missing_names)}",
                        )
                    ]
                layouts = [
                    layout
                    for layout in layouts
                    if layout.plugin_dir_name.casefold() in requested_names
                ]
        except ValueError as e:
            return [ImportResult(success=False, plugin_name=source_name, message=str(e))]

        return [
            self._import_directory_layout(layout, overwrite)
            for layout in layouts
        ]

    def _validate_directory_source_path(self, dir_path: Path) -> ImportResult | None:
        """校验目录来源路径，并在失败时返回统一结果。"""
        plugin_name = dir_path.name
        if not dir_path.exists():
            return ImportResult(
                success=False,
                plugin_name=plugin_name,
                message=f"目录不存在: {dir_path}",
            )
        if not dir_path.is_dir():
            return ImportResult(
                success=False,
                plugin_name=plugin_name,
                message="路径不是目录",
            )
        if dir_path.is_symlink():
            return ImportResult(
                success=False,
                plugin_name=plugin_name,
                message="所选插件目录不能是符号链接",
            )
        return None

    def _import_directory_layout(
        self,
        layout: _DirectoryLayout,
        overwrite: bool,
    ) -> ImportResult:
        """独立导入松散来源中的一个插件根。"""
        plugin_name = layout.plugin_dir_name
        staging_dir: Path | None = None
        try:
            target_dir = self._get_target_dir(plugin_name)
            if self._path_exists(target_dir) and not overwrite:
                return ImportResult(
                    success=False,
                    plugin_name=plugin_name,
                    message=f"插件目录已存在: {plugin_name}",
                    plugin_dir=target_dir,
                )

            self._validate_directory_symlinks(layout.source_dir)
            staging_dir = self._new_staging_dir(plugin_name)
            shutil.copytree(layout.source_dir, staging_dir)
            self._find_primary_const_file(staging_dir)
            self._replace_plugin_dir(staging_dir, target_dir, overwrite)
            log.info(f"目录插件导入成功: {plugin_name}")
            return ImportResult(
                success=True,
                plugin_name=plugin_name,
                message="导入成功",
                plugin_dir=target_dir,
            )
        except Exception as e:
            log.error(f"导入目录插件失败: {plugin_name}, {e}", exc_info=True)
            return ImportResult(
                success=False,
                plugin_name=plugin_name,
                message=f"导入失败: {e}",
            )
        finally:
            if staging_dir is not None and self._path_exists(staging_dir):
                try:
                    self._remove_path(staging_dir)
                except Exception as e:
                    log.warning(f"清理插件临时目录失败: {staging_dir}, {e}")

    def preview_directory(self, dir_path: str | Path) -> PluginPreviewInfo | None:
        """按旧单插件语义预览所选目录本身。"""
        dir_path = Path(dir_path)
        if self._validate_directory_source_path(dir_path) is not None:
            return None

        try:
            const_file = self._find_primary_const_file(dir_path)
            self._validate_directory_symlinks(dir_path)
            content = const_file.read_text(encoding="utf-8")
        except Exception:
            return None

        return PluginPreviewInfo(
            plugin_name=dir_path.name,
            version=self._extract_const_value(content, "PLUGIN_VERSION"),
            author=self._extract_const_value(content, "PLUGIN_AUTHOR"),
        )

    def preview_plugins_from_directory(
        self,
        dir_path: str | Path,
    ) -> list[PluginPreviewInfo]:
        """预览一个松散目录来源中的全部插件。"""
        dir_path = Path(dir_path)
        if self._validate_directory_source_path(dir_path) is not None:
            return []

        try:
            layouts = self._analyze_directory(dir_path)
            return [self._preview_directory_layout(layout) for layout in layouts]
        except Exception:
            return []

    def _preview_directory_layout(
        self,
        layout: _DirectoryLayout,
    ) -> PluginPreviewInfo:
        """读取松散目录中一个插件根的预览信息。"""
        content = layout.preview_const_path.read_text(encoding="utf-8")
        return PluginPreviewInfo(
            plugin_name=layout.plugin_dir_name,
            version=self._extract_const_value(content, "PLUGIN_VERSION"),
            author=self._extract_const_value(content, "PLUGIN_AUTHOR"),
        )

    def _analyze_directory(self, source_dir: Path) -> list[_DirectoryLayout]:
        """识别松散目录中的全部最外层合法插件根。"""
        file_paths = self._collect_directory_file_paths(source_dir)
        plugin_roots = self._find_outermost_plugin_roots(file_paths)
        layouts: list[_DirectoryLayout] = []
        for plugin_root in plugin_roots:
            plugin_source_dir = (
                source_dir.joinpath(*plugin_root.parts)
                if plugin_root.parts
                else source_dir
            )
            plugin_dir_name = plugin_root.name if plugin_root.parts else source_dir.name
            self._validate_plugin_dir_name(plugin_dir_name)
            preview_const_path = next(
                path
                for path in file_paths
                if path.parent == plugin_root and path.name.endswith("_const.py")
            )
            layouts.append(
                _DirectoryLayout(
                    plugin_dir_name=plugin_dir_name,
                    source_dir=plugin_source_dir,
                    preview_const_path=source_dir.joinpath(*preview_const_path.parts),
                )
            )

        self._validate_unique_plugin_names([layout.plugin_dir_name for layout in layouts])
        for layout in layouts:
            self._validate_directory_symlinks(layout.source_dir)
        return layouts

    def _collect_directory_file_paths(self, source_dir: Path) -> list[PurePosixPath]:
        """收集松散目录文件，不跟随符号链接目录。"""
        file_paths: list[PurePosixPath] = []
        for current_root, dir_names, file_names in os.walk(source_dir, followlinks=False):
            current_dir = Path(current_root)
            relative_dir = current_dir.relative_to(source_dir)
            dir_names[:] = sorted(
                name
                for name in dir_names
                if name != "__MACOSX" and not (current_dir / name).is_symlink()
            )
            for file_name in sorted(file_names):
                relative_path = PurePosixPath(*relative_dir.parts, file_name)
                if not self._is_metadata_path(relative_path):
                    file_paths.append(relative_path)
        return file_paths

    def _validate_directory_symlinks(self, plugin_dir: Path) -> None:
        """拒绝越出插件根或形成复制循环的符号链接。"""
        plugin_root = plugin_dir.resolve(strict=True)
        visited_dirs: set[Path] = set()
        active_dirs: set[Path] = set()

        def visit_directory(directory: Path) -> None:
            if directory in active_dirs:
                raise ValueError(f"插件目录包含循环符号链接: {directory}")
            if directory in visited_dirs:
                return

            active_dirs.add(directory)
            try:
                for entry_path in directory.iterdir():
                    if entry_path.is_symlink():
                        try:
                            target_path = entry_path.resolve(strict=True)
                        except (OSError, RuntimeError) as e:
                            raise ValueError(
                                f"插件目录包含无效符号链接: {entry_path}"
                            ) from e

                        if directory == plugin_root and entry_path.suffix.casefold() == ".py":
                            raise ValueError(
                                f"插件根第一层 Python 文件不能是符号链接: {entry_path}"
                            )
                        if not target_path.is_relative_to(plugin_root):
                            raise ValueError(f"插件目录包含越界符号链接: {entry_path}")
                        if target_path.is_dir():
                            if target_path in active_dirs:
                                raise ValueError(
                                    f"插件目录包含循环符号链接: {entry_path}"
                                )
                            visit_directory(target_path)
                    elif entry_path.is_dir():
                        visit_directory(entry_path.resolve(strict=True))
            finally:
                active_dirs.remove(directory)
            visited_dirs.add(directory)

        visit_directory(plugin_root)

    def _find_primary_const_file(self, plugin_dir: Path) -> Path:
        """校验插件根第一层，并返回主 factory 对应的 const 文件。"""
        root_factory_files = sorted(plugin_dir.glob("*_factory.py"))
        if not root_factory_files:
            raise ValueError("无效的插件结构: 插件根目录缺少 *_factory.py 文件")
        if len(root_factory_files) > 1:
            raise ValueError("无效的插件结构: 插件根目录不能包含多个 *_factory.py 文件")

        root_const_files = sorted(plugin_dir.glob("*_const.py"))
        if not root_const_files:
            raise ValueError("无效的插件结构: 插件根目录缺少 *_const.py 文件")
        if len(root_const_files) > 1:
            raise ValueError("无效的插件结构: 插件根目录不能包含多个 *_const.py 文件")

        return root_const_files[0]

    def _plugins_root(self) -> Path:
        """返回规范化后的 plugins 根目录。"""
        return self.plugins_dir.resolve(strict=False)

    def _validate_plugin_dir_name(self, plugin_dir_name: str) -> None:
        """确保插件目录名是单个安全目录名。"""
        path = PureWindowsPath(plugin_dir_name)
        if (
            not plugin_dir_name
            or plugin_dir_name in {".", ".."}
            or path.drive
            or len(PurePosixPath(plugin_dir_name).parts) != 1
            or len(path.parts) != 1
            or ":" in plugin_dir_name
        ):
            raise ValueError(f"无效的插件目录名: {plugin_dir_name}")

    def _get_target_dir(self, plugin_dir_name: str) -> Path:
        """返回安全的插件目标目录。"""
        self._validate_plugin_dir_name(plugin_dir_name)
        target_dir = self._plugins_root() / plugin_dir_name
        if target_dir.is_symlink():
            raise ValueError("插件目标目录不能是符号链接")
        if target_dir.exists() and not target_dir.is_dir():
            raise ValueError("插件目标路径不是目录")
        return target_dir

    def _new_staging_dir(self, plugin_dir_name: str) -> Path:
        """创建同一文件系统中的临时目录路径。"""
        plugins_root = self._plugins_root()
        plugins_root.mkdir(parents=True, exist_ok=True)
        return plugins_root / f".{plugin_dir_name}.tmp-{uuid4().hex}"

    def _replace_plugin_dir(self, staging_dir: Path, target_dir: Path, overwrite: bool) -> None:
        """用已完成的临时目录替换目标目录，失败时恢复旧版本。"""
        backup_dir: Path | None = None
        if self._path_exists(target_dir):
            if not overwrite:
                raise FileExistsError(f"插件目录已存在: {target_dir.name}")
            if target_dir.is_symlink():
                raise ValueError("插件目标目录不能是符号链接")
            if not target_dir.is_dir():
                raise ValueError("插件目标路径不是目录")
            backup_dir = target_dir.with_name(f".{target_dir.name}.backup-{uuid4().hex}")
            target_dir.replace(backup_dir)

        try:
            staging_dir.replace(target_dir)
        except Exception:
            if backup_dir is not None and self._path_exists(backup_dir) and not self._path_exists(target_dir):
                backup_dir.replace(target_dir)
            raise
        else:
            if backup_dir is not None and self._path_exists(backup_dir):
                try:
                    self._remove_path(backup_dir)
                except Exception as e:
                    log.warning(f"清理插件备份目录失败: {backup_dir}, {e}")

    def delete_plugin(self, plugin_dir: str | Path) -> ImportResult:
        """删除 plugins 根目录下的一个插件目录。"""
        plugin_path = Path(plugin_dir)
        if isinstance(plugin_dir, str) and not plugin_path.is_absolute():
            plugin_path = self.plugins_dir / plugin_path

        if plugin_path.is_symlink():
            return ImportResult(
                success=False,
                plugin_name=plugin_path.name,
                message="不能删除符号链接形式的插件目录",
            )

        plugins_root = self._plugins_root()
        plugin_dir_resolved = plugin_path.resolve(strict=False)
        plugin_name = plugin_dir_resolved.name

        if plugin_dir_resolved == plugins_root or not plugin_dir_resolved.is_relative_to(plugins_root):
            return ImportResult(
                success=False,
                plugin_name=plugin_name,
                message="只能删除 plugins 目录下的插件",
            )

        if plugin_dir_resolved.parent != plugins_root:
            return ImportResult(
                success=False,
                plugin_name=plugin_name,
                message="只能删除 plugins 目录下的顶层插件目录",
            )

        if not plugin_dir_resolved.exists():
            return ImportResult(
                success=False,
                plugin_name=plugin_name,
                message=f"插件目录不存在: {plugin_name}",
            )

        if not plugin_dir_resolved.is_dir():
            return ImportResult(
                success=False,
                plugin_name=plugin_name,
                message="只能删除插件目录",
            )

        try:
            self._remove_path(plugin_dir_resolved)
            log.info(f"插件已删除: {plugin_name}")
            return ImportResult(
                success=True,
                plugin_name=plugin_name,
                message="删除成功",
            )
        except Exception as e:
            log.error(f"删除插件失败: {e}", exc_info=True)
            return ImportResult(
                success=False,
                plugin_name=plugin_name,
                message=f"删除失败: {e}",
            )

    def _path_exists(self, path: Path) -> bool:
        """判断普通路径或符号链接是否存在。"""
        return path.exists() or path.is_symlink()

    def _remove_path(self, path: Path) -> None:
        """删除文件、符号链接或目录。"""
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.exists():
            shutil.rmtree(path)
