"""插件导入服务

处理第三方插件的导入、解压和验证。

支持的导入方式：
- ZIP 文件：自动解压到 plugins 目录
- 目录：复制到 plugins 目录

主要功能：
- 验证插件结构（必须包含 *_factory.py）
- 预览插件信息（从 *_const.py 读取）
- 覆盖安装（可选）
- 删除插件
"""

from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

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


class PluginImportService:
    """插件导入服务

    处理第三方插件的导入、解压、验证和删除。
    """

    def __init__(self, ctx: OneDragonContext):
        self.ctx = ctx

    @property
    def plugins_dir(self) -> Path:
        """获取插件目录

        返回项目根目录下的 plugins 目录。
        """
        import inspect
        cls_file = inspect.getfile(self.ctx.__class__)
        # 从 src 目录往上找项目根目录
        parts = Path(cls_file).parts
        try:
            src_index = parts.index('src')
            project_root = Path(*parts[:src_index])
            return project_root / 'plugins'
        except ValueError:
            # 如果找不到 src 目录，使用旧逻辑作为后备
            return Path(cls_file).parent.parent / 'plugins'

    def import_plugins(self, zip_paths: list[str | Path], overwrite: bool = False) -> list[ImportResult]:
        """导入多个插件

        Args:
            zip_paths: zip 文件路径列表
            overwrite: 是否覆盖已存在的插件

        Returns:
            list[ImportResult]: 导入结果列表
        """
        results = []
        for zip_path in zip_paths:
            result = self.import_plugin(zip_path, overwrite=overwrite)
            results.append(result)
        return results

    def import_plugin(self, zip_path: str | Path, overwrite: bool = False) -> ImportResult:
        """导入单个插件

        从 zip 文件解压插件到 plugins 目录。

        Args:
            zip_path: zip 文件路径
            overwrite: 是否覆盖已存在的插件

        Returns:
            ImportResult: 导入结果
        """
        zip_path = Path(zip_path)

        if not zip_path.exists():
            return ImportResult(
                success=False,
                plugin_name=zip_path.stem,
                message=f"文件不存在: {zip_path}"
            )

        if zip_path.suffix.lower() != '.zip':
            return ImportResult(
                success=False,
                plugin_name=zip_path.stem,
                message="只支持 .zip 格式的文件"
            )

        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # 验证 zip 文件结构
                validation = self._validate_zip_structure(zf)
                if not validation.success:
                    return validation

                # 获取插件目录名
                plugin_dir_name = self._get_plugin_dir_name(zf)
                if not plugin_dir_name:
                    return ImportResult(
                        success=False,
                        plugin_name=zip_path.stem,
                        message="无法确定插件目录名"
                    )

                target_dir = self.plugins_dir / plugin_dir_name

                # 检查目录是否已存在
                if target_dir.exists():
                    if overwrite:
                        # 覆盖安装：先删除旧目录
                        shutil.rmtree(target_dir)
                        log.info(f"覆盖安装: 已删除旧插件目录 {plugin_dir_name}")
                    else:
                        return ImportResult(
                            success=False,
                            plugin_name=plugin_dir_name,
                            message=f"插件目录已存在: {plugin_dir_name}",
                            plugin_dir=target_dir
                        )

                # 解压文件
                self._extract_plugin(zf, target_dir, plugin_dir_name)

                log.info(f"插件导入成功: {plugin_dir_name}")
                return ImportResult(
                    success=True,
                    plugin_name=plugin_dir_name,
                    message="导入成功",
                    plugin_dir=target_dir
                )

        except zipfile.BadZipFile:
            return ImportResult(
                success=False,
                plugin_name=zip_path.stem,
                message="无效的 zip 文件"
            )
        except Exception as e:
            log.error(f"导入插件失败: {e}", exc_info=True)
            return ImportResult(
                success=False,
                plugin_name=zip_path.stem,
                message=f"导入失败: {e}"
            )

    def _validate_zip_structure(self, zf: zipfile.ZipFile) -> ImportResult:
        """验证 zip 文件结构

        检查 zip 文件是否包含有效的插件结构（至少一个 *_factory.py 文件）。

        Args:
            zf: ZipFile 对象

        Returns:
            ImportResult: 验证结果
        """
        file_list = zf.namelist()

        # 检查是否有 factory 文件
        has_factory = any(name.endswith('_factory.py') for name in file_list)
        if not has_factory:
            return ImportResult(
                success=False,
                plugin_name="",
                message="无效的插件结构：缺少 *_factory.py 文件"
            )

        return ImportResult(success=True, plugin_name="", message="")

    def preview_plugin(self, zip_path: str | Path) -> PluginPreviewInfo | None:
        """预览 zip 中的插件信息（不解压）

        Args:
            zip_path: zip 文件路径

        Returns:
            PluginPreviewInfo | None: 插件预览信息
        """
        zip_path = Path(zip_path)
        if not zip_path.exists() or zip_path.suffix.lower() != '.zip':
            return None

        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                plugin_dir_name = self._get_plugin_dir_name(zf)
                if not plugin_dir_name:
                    return None

                # 查找 const 文件并读取版本信息
                version = None
                author = None
                for name in zf.namelist():
                    if name.endswith('_const.py'):
                        try:
                            content = zf.read(name).decode('utf-8')
                            version = self._extract_const_value(content, 'PLUGIN_VERSION')
                            author = self._extract_const_value(content, 'PLUGIN_AUTHOR')
                            break
                        except Exception:
                            pass

                return PluginPreviewInfo(
                    plugin_name=plugin_dir_name,
                    version=version,
                    author=author
                )
        except Exception:
            return None

    def _extract_const_value(self, content: str, const_name: str) -> str | None:
        """从代码内容中提取常量值

        Args:
            content: 代码内容
            const_name: 常量名

        Returns:
            str | None: 常量值
        """
        import re
        # 匹配 CONST_NAME = 'value' 或 CONST_NAME = "value"
        pattern = rf"{const_name}\s*=\s*['\"](.+?)['\"]"
        match = re.search(pattern, content)
        return match.group(1) if match else None

    def _get_plugin_dir_name(self, zf: zipfile.ZipFile) -> str | None:
        """从 zip 文件获取插件目录名

        Args:
            zf: ZipFile 对象

        Returns:
            str | None: 插件目录名
        """
        file_list = zf.namelist()

        # 查找第一个 factory 文件，确定插件目录
        for name in file_list:
            if name.endswith('_factory.py'):
                parts = name.split('/')
                if len(parts) >= 2:
                    # 如果 factory 文件在子目录中，使用父目录名
                    return parts[0]
                # 如果 factory 直接在根目录，使用文件名（去掉 _factory.py）
                return name.replace('_factory.py', '')

        return None

    def _extract_plugin(
        self,
        zf: zipfile.ZipFile,
        target_dir: Path,
        plugin_dir_name: str
    ) -> None:
        """解压插件到目标目录

        Args:
            zf: ZipFile 对象
            target_dir: 目标目录
            plugin_dir_name: 插件目录名
        """
        # 确保 plugins 目录存在
        self.plugins_dir.mkdir(parents=True, exist_ok=True)

        file_list = zf.namelist()

        # 检查 zip 文件结构
        # 情况1: 所有文件都在一个同名子目录下（例如 my_plugin/xxx.py）
        # 情况2: 文件直接在根目录（例如 xxx_factory.py）
        has_root_dir = all(
            name.startswith(plugin_dir_name + '/') or name == plugin_dir_name + '/'
            for name in file_list if name
        )

        if has_root_dir:
            # 直接解压，zip 内部已经有目录结构
            zf.extractall(self.plugins_dir)
        else:
            # 需要创建目录并解压到其中
            target_dir.mkdir(parents=True, exist_ok=True)
            for member in file_list:
                if member.endswith('/'):
                    # 创建目录
                    (target_dir / member).mkdir(parents=True, exist_ok=True)
                else:
                    # 解压文件
                    source = zf.read(member)
                    dest_path = target_dir / member
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    dest_path.write_bytes(source)

    def import_directory(self, dir_path: str | Path, overwrite: bool = False) -> ImportResult:
        """导入目录格式的插件

        将插件目录复制到 plugins 目录。

        Args:
            dir_path: 插件目录路径
            overwrite: 是否覆盖已存在的插件

        Returns:
            ImportResult: 导入结果
        """
        dir_path = Path(dir_path)

        if not dir_path.exists():
            return ImportResult(
                success=False,
                plugin_name=dir_path.name,
                message=f"目录不存在: {dir_path}"
            )

        if not dir_path.is_dir():
            return ImportResult(
                success=False,
                plugin_name=dir_path.name,
                message="路径不是目录"
            )

        # 验证目录结构
        has_factory = any(dir_path.glob('*_factory.py'))
        if not has_factory:
            return ImportResult(
                success=False,
                plugin_name=dir_path.name,
                message="无效的插件结构：缺少 *_factory.py 文件"
            )

        plugin_name = dir_path.name
        target_dir = self.plugins_dir / plugin_name

        # 检查目录是否已存在
        if target_dir.exists():
            if overwrite:
                shutil.rmtree(target_dir)
                log.info(f"覆盖安装: 已删除旧插件目录 {plugin_name}")
            else:
                return ImportResult(
                    success=False,
                    plugin_name=plugin_name,
                    message=f"插件目录已存在: {plugin_name}",
                    plugin_dir=target_dir
                )

        try:
            # 确保 plugins 目录存在
            self.plugins_dir.mkdir(parents=True, exist_ok=True)

            # 复制目录
            shutil.copytree(dir_path, target_dir)
            log.info(f"目录插件导入成功: {plugin_name}")
            return ImportResult(
                success=True,
                plugin_name=plugin_name,
                message="导入成功",
                plugin_dir=target_dir
            )
        except Exception as e:
            log.error(f"导入目录插件失败: {e}", exc_info=True)
            return ImportResult(
                success=False,
                plugin_name=plugin_name,
                message=f"导入失败: {e}"
            )

    def preview_directory(self, dir_path: str | Path) -> PluginPreviewInfo | None:
        """预览目录中的插件信息

        Args:
            dir_path: 插件目录路径

        Returns:
            PluginPreviewInfo | None: 插件预览信息
        """
        dir_path = Path(dir_path)
        if not dir_path.exists() or not dir_path.is_dir():
            return None

        # 检查是否有 factory 文件
        has_factory = any(dir_path.glob('*_factory.py'))
        if not has_factory:
            return None

        # 查找 const 文件并读取信息
        version = None
        author = None
        for const_file in dir_path.glob('*_const.py'):
            try:
                content = const_file.read_text(encoding='utf-8')
                version = self._extract_const_value(content, 'PLUGIN_VERSION')
                author = self._extract_const_value(content, 'PLUGIN_AUTHOR')
                break
            except Exception:
                pass

        return PluginPreviewInfo(
            plugin_name=dir_path.name,
            version=version,
            author=author
        )

    def delete_plugin(self, plugin_dir: str | Path) -> ImportResult:
        """删除插件

        Args:
            plugin_dir: 插件目录路径或名称

        Returns:
            ImportResult: 删除结果
        """
        if isinstance(plugin_dir, str):
            # 如果只是目录名，构建完整路径
            if not Path(plugin_dir).is_absolute():
                plugin_dir = self.plugins_dir / plugin_dir

        plugin_dir = Path(plugin_dir)
        plugin_name = plugin_dir.name

        if not plugin_dir.exists():
            return ImportResult(
                success=False,
                plugin_name=plugin_name,
                message=f"插件目录不存在: {plugin_name}"
            )

        # 安全检查：确保删除的是 plugins 目录下的内容
        if self.plugins_dir not in plugin_dir.parents and plugin_dir != self.plugins_dir:
            return ImportResult(
                success=False,
                plugin_name=plugin_name,
                message="只能删除 plugins 目录下的插件"
            )

        try:
            shutil.rmtree(plugin_dir)
            log.info(f"插件已删除: {plugin_name}")
            return ImportResult(
                success=True,
                plugin_name=plugin_name,
                message="删除成功"
            )
        except Exception as e:
            log.error(f"删除插件失败: {e}", exc_info=True)
            return ImportResult(
                success=False,
                plugin_name=plugin_name,
                message=f"删除失败: {e}"
            )
