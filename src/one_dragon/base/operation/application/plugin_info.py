"""插件信息数据模型

提供插件元数据的数据结构定义，包括：
- PluginSource: 插件来源枚举（内置/第三方）
- PluginInfo: 单个插件的元数据
- PluginScanResult: 插件扫描结果
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class PluginSource(str, Enum):
    """插件来源枚举

    用于区分插件的来源，由 ApplicationFactoryManager 在扫描时自动设置。
    - BUILTIN: 内置插件，位于 application 目录下，由项目维护
    - THIRD_PARTY: 第三方插件，位于 plugins 目录下，由用户安装，支持相对导入
    """
    BUILTIN = 'builtin'
    THIRD_PARTY = 'third_party'


@dataclass
class PluginInfo:
    """插件信息

    存储单个插件的元数据信息，包括核心信息、来源、元数据和目录信息。

    Attributes:
        app_id: 应用唯一标识符
        app_name: 应用显示名称
        default_group: 是否属于默认应用组
        source: 插件来源（由扫描器设置，非用户可控）
        author: 作者名称（可选）
        homepage: 项目主页 URL（可选）
        version: 版本号（可选）
        description: 简短描述（可选）
        plugin_dir: 插件目录路径
        factory_module: 工厂模块名
        const_module: 常量模块名
    """

    # 核心信息（从 factory 获取）
    app_id: str
    app_name: str
    default_group: bool

    # 插件来源
    source: PluginSource = PluginSource.BUILTIN

    # 插件元数据（从 const 获取，可选）
    author: str = ''
    homepage: str = ''
    version: str = ''
    description: str = ''

    # 插件目录信息
    plugin_dir: Path | None = None

    # 工厂信息
    factory_module: str = ''
    const_module: str = ''

    @property
    def is_third_party(self) -> bool:
        """是否为第三方插件"""
        return self.source == PluginSource.THIRD_PARTY


@dataclass
class PluginScanResult:
    """插件扫描结果

    存储插件目录扫描的完整结果，包括成功加载的插件和失败记录。

    Attributes:
        plugins: 成功加载的插件信息列表
        failed_plugins: 加载失败的记录列表，每项为 (文件路径, 错误信息)
    """

    plugins: list[PluginInfo] = field(default_factory=list)
    failed_plugins: list[tuple[Path, str]] = field(default_factory=list)

    @property
    def non_default_plugins(self) -> list[PluginInfo]:
        """获取非默认组插件"""
        return [p for p in self.plugins if not p.default_group]

    @property
    def default_plugins(self) -> list[PluginInfo]:
        """获取默认组插件"""
        return [p for p in self.plugins if p.default_group]

    @property
    def third_party_plugins(self) -> list[PluginInfo]:
        """获取第三方插件"""
        return [p for p in self.plugins if p.is_third_party]

    @property
    def builtin_plugins(self) -> list[PluginInfo]:
        """获取内置插件"""
        return [p for p in self.plugins if not p.is_third_party]
