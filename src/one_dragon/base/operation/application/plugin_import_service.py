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
    """已校验的 ZIP 插件目录结构。"""

    plugin_dir_name: str
    root_prefix: str | None
    members: list[tuple[zipfile.ZipInfo, PurePosixPath]]
    preview_const_path: PurePosixPath


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
        """导入多个插件

        Args:
            zip_paths: zip 文件路径列表
            overwrite: 是否覆盖已存在的插件

        Returns:
            list[ImportResult]: 导入结果列表
        """
        results: list[ImportResult] = []
        for zip_path in zip_paths:
            results.append(self.import_plugin(zip_path, overwrite=overwrite))
        return results

    def import_plugin(self, zip_path: str | Path, overwrite: bool = False) -> ImportResult:
        """导入单个 ZIP 插件

        Args:
            zip_path: zip 文件路径
            overwrite: 是否覆盖已存在的插件

        Returns:
            ImportResult: 导入结果
        """
        zip_path = Path(zip_path)
        plugin_name = zip_path.stem

        if not zip_path.exists():
            return ImportResult(
                success=False,
                plugin_name=plugin_name,
                message=f"文件不存在: {zip_path}",
            )

        if zip_path.suffix.lower() != ".zip":
            return ImportResult(
                success=False,
                plugin_name=plugin_name,
                message="只支持 .zip 格式的文件",
            )

        staging_dir: Path | None = None
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                try:
                    layout = self._analyze_zip(zf)
                except ValueError as e:
                    return ImportResult(
                        success=False,
                        plugin_name=plugin_name,
                        message=str(e),
                    )

                plugin_name = layout.plugin_dir_name
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

        except zipfile.BadZipFile:
            return ImportResult(
                success=False,
                plugin_name=plugin_name,
                message="无效的 zip 文件",
            )
        except Exception as e:
            log.error(f"导入插件失败: {e}", exc_info=True)
            return ImportResult(
                success=False,
                plugin_name=plugin_name,
                message=f"导入失败: {e}",
            )
        finally:
            if staging_dir is not None and self._path_exists(staging_dir):
                self._remove_path(staging_dir)

    def _validate_zip_structure(self, zf: zipfile.ZipFile) -> ImportResult:
        """验证 ZIP 文件结构。"""
        try:
            layout = self._analyze_zip(zf)
        except ValueError as e:
            return ImportResult(success=False, plugin_name="", message=str(e))
        return ImportResult(success=True, plugin_name=layout.plugin_dir_name, message="")

    def preview_plugin(self, zip_path: str | Path) -> PluginPreviewInfo | None:
        """预览 ZIP 中的插件信息（不解压）。"""
        zip_path = Path(zip_path)
        if not zip_path.exists() or zip_path.suffix.lower() != ".zip":
            return None

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                layout = self._analyze_zip(zf)
                const_info = next(
                    info
                    for info, path in layout.members
                    if path == layout.preview_const_path
                )
                content = zf.read(const_info).decode("utf-8")
                return PluginPreviewInfo(
                    plugin_name=layout.plugin_dir_name,
                    version=self._extract_const_value(content, "PLUGIN_VERSION"),
                    author=self._extract_const_value(content, "PLUGIN_AUTHOR"),
                )
        except Exception:
            return None

    def _extract_const_value(self, content: str, const_name: str) -> str | None:
        """从代码内容中提取字符串常量值。"""
        pattern = rf"{const_name}\s*=\s*['\"](.+?)['\"]"
        match = re.search(pattern, content)
        return match.group(1) if match else None

    def _analyze_zip(self, zf: zipfile.ZipFile) -> _ZipLayout:
        """校验 ZIP 成员并确定插件根目录和预览 const 文件。"""
        members: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
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
            members.append((info, path))
            if not info.is_dir():
                file_paths.append(path)

        file_path_keys = {path_key for path_key, is_dir in path_types.items() if not is_dir}
        for file_path_key in file_path_keys:
            if any(path_key.startswith(f"{file_path_key}/") for path_key in path_types):
                raise ValueError(f"ZIP 包含文件与目录路径冲突: {file_path_key}")

        factory_paths = sorted(
            (path for path in file_paths if path.name.endswith("_factory.py")),
            key=lambda path: (len(path.parts), path.as_posix()),
        )
        if not factory_paths:
            raise ValueError("无效的插件结构: 缺少 *_factory.py 文件")

        const_paths = [path for path in file_paths if path.name.endswith("_const.py")]
        factory_paths_by_dir: dict[PurePosixPath, list[PurePosixPath]] = {}
        const_paths_by_dir: dict[PurePosixPath, list[PurePosixPath]] = {}
        for factory_path in factory_paths:
            factory_paths_by_dir.setdefault(factory_path.parent, []).append(factory_path)
        for const_path in const_paths:
            const_paths_by_dir.setdefault(const_path.parent, []).append(const_path)

        for factory_dir, files in factory_paths_by_dir.items():
            if len(files) > 1:
                raise ValueError("无效的插件结构: 同一目录不能包含多个 *_factory.py 文件")
            const_files = const_paths_by_dir.get(factory_dir, [])
            if not const_files:
                raise ValueError("无效的插件结构: factory 文件所在目录缺少 *_const.py 文件")
            if len(const_files) > 1:
                raise ValueError("无效的插件结构: 同一目录不能包含多个 *_const.py 文件")

        root_factories = [path for path in factory_paths if len(path.parts) == 1]

        if root_factories:
            primary_factory = root_factories[0]
            root_prefix = None
            plugin_dir_name = primary_factory.name.removesuffix("_factory.py")
        else:
            factory_roots = {path.parts[0] for path in factory_paths}
            if len(factory_roots) != 1:
                raise ValueError("无效的插件结构: ZIP 只能包含一个顶层插件目录")
            root_prefix = next(iter(factory_roots))
            plugin_dir_name = root_prefix
            primary_factory = factory_paths[0]

        self._validate_plugin_dir_name(plugin_dir_name)
        preview_const_path = min(
            (path for path in const_paths if path.parent == primary_factory.parent),
            key=lambda path: path.as_posix(),
        )

        return _ZipLayout(
            plugin_dir_name=plugin_dir_name,
            root_prefix=root_prefix,
            members=members,
            preview_const_path=preview_const_path,
        )

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
        """把已校验的 ZIP 内容写入临时插件目录。"""
        plugins_root = self._plugins_root()
        target_dir_resolved = target_dir.resolve(strict=False)
        if target_dir_resolved == plugins_root or not target_dir_resolved.is_relative_to(plugins_root):
            raise ValueError("插件临时目录不在 plugins 目录内")

        target_dir.mkdir(parents=True, exist_ok=False)
        for info, member_path in layout.members:
            relative_path = member_path
            if layout.root_prefix is not None and member_path.parts[0] == layout.root_prefix:
                relative_parts = member_path.parts[1:]
                if not relative_parts:
                    continue
                relative_path = PurePosixPath(*relative_parts)

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
        """导入目录格式的插件。"""
        dir_path = Path(dir_path)
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

        try:
            self._find_primary_const_file(dir_path)
            target_dir = self._get_target_dir(plugin_name)
        except ValueError as e:
            return ImportResult(success=False, plugin_name=plugin_name, message=str(e))

        if self._path_exists(target_dir) and not overwrite:
            return ImportResult(
                success=False,
                plugin_name=plugin_name,
                message=f"插件目录已存在: {plugin_name}",
                plugin_dir=target_dir,
            )

        staging_dir = self._new_staging_dir(plugin_name)
        try:
            shutil.copytree(dir_path, staging_dir)
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
            log.error(f"导入目录插件失败: {e}", exc_info=True)
            return ImportResult(
                success=False,
                plugin_name=plugin_name,
                message=f"导入失败: {e}",
            )
        finally:
            if self._path_exists(staging_dir):
                self._remove_path(staging_dir)

    def preview_directory(self, dir_path: str | Path) -> PluginPreviewInfo | None:
        """预览目录中的插件信息。"""
        dir_path = Path(dir_path)
        if not dir_path.exists() or not dir_path.is_dir():
            return None

        try:
            const_file = self._find_primary_const_file(dir_path)
            content = const_file.read_text(encoding="utf-8")
        except Exception:
            return None

        return PluginPreviewInfo(
            plugin_name=dir_path.name,
            version=self._extract_const_value(content, "PLUGIN_VERSION"),
            author=self._extract_const_value(content, "PLUGIN_AUTHOR"),
        )

    def _find_primary_const_file(self, plugin_dir: Path) -> Path:
        """查找最浅层 factory 对应的同目录 const 文件。"""
        factory_files = sorted(
            plugin_dir.rglob("*_factory.py"),
            key=lambda path: (len(path.relative_to(plugin_dir).parts), path.as_posix()),
        )
        if not factory_files:
            raise ValueError("无效的插件结构: 缺少 *_factory.py 文件")

        factory_files_by_dir: dict[Path, list[Path]] = {}
        for factory_file in factory_files:
            factory_files_by_dir.setdefault(factory_file.parent, []).append(factory_file)

        for factory_dir, files in factory_files_by_dir.items():
            if len(files) > 1:
                raise ValueError("无效的插件结构: 同一目录不能包含多个 *_factory.py 文件")
            const_files = sorted(factory_dir.glob("*_const.py"))
            if not const_files:
                raise ValueError("无效的插件结构: factory 文件所在目录缺少 *_const.py 文件")
            if len(const_files) > 1:
                raise ValueError("无效的插件结构: 同一目录不能包含多个 *_const.py 文件")

        primary_factory = factory_files[0]
        return next(primary_factory.parent.glob("*_const.py"))

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
