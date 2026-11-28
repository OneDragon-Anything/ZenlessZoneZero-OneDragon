"""插件信息数据模型

提供插件元数据的数据结构定义，包括：
- PluginSource: 插件来源枚举（内置/第三方）
- PluginInfo: 单个插件的元数据
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class PluginSource(str, Enum):
    """插件来源枚举

    用于区分插件的来源，由 ApplicationFactoryManager 在扫描时自动设置。
    - BUILTIN: 内置插件，位于 application 目录下，由项目维护
    - THIRD_PARTY: 第三方插件，位于 plugins 目录下，由用户安装，支持相对导入
    - DEV: 开发版插件，位于 plugins/.dev 目录下，用于本地开发调试
    """
    BUILTIN = 'builtin'
    THIRD_PARTY = 'third_party'
    DEV = 'dev'


@dataclass
class InactiveCopy:
    """同 ID 下未生效的那份副本（只读展示，不导入）。

    Attributes:
        source: 副本来源（THIRD_PARTY 或 DEV）
        plugin_dir: 副本目录
        version: 副本 plugin.json 里的版本号，读不到为空
    """

    source: PluginSource
    plugin_dir: Path
    version: str = ''


@dataclass
class PluginInfo:
    """插件信息

    存储单个插件的元数据信息，包括核心信息、来源、元数据和目录信息。

    Attributes:
        app_id: 应用唯一标识符
        app_name: 应用显示名称
        default_group: 是否默认进入一条龙列表
        internal_app: 是否只能由代码固定入口调用，不出现在通用应用列表
        source: 插件来源（由扫描器设置，非用户可控）
        author: 作者名称（可选）
        homepage: 项目主页 URL（可选）
        version: 版本号（可选）
        description: 简短描述（可选）
        cover_path: 封面图路径（可选，相对插件根目录解析后的绝对路径）
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

    # 应用入口
    internal_app: bool = False

    # 插件元数据（从插件包内的 plugin.json 获取，可选）
    author: str = ''
    homepage: str = ''
    version: str = ''
    description: str = ''
    cover_path: Path | None = None

    # 插件目录信息
    plugin_dir: Path | None = None

    # 同 ID 下未生效的副本（开发版与商店版并存时才有）
    inactive_copy: InactiveCopy | None = None

    # 键鼠脚本目录名（相对 plugin_dir；空 = 插件不附带键鼠脚本）
    key_sim_dir: str = ''

    # 插件画面目录名（相对 plugin_dir；空 = 插件不附带画面）
    screen_info_dir: str = 'screen_info'

    # 工厂信息
    factory_module: str = ''
    const_module: str = ''

    @property
    def is_third_party(self) -> bool:
        """是否为第三方插件（含开发版）"""
        return self.source in (PluginSource.THIRD_PARTY, PluginSource.DEV)

    @property
    def is_dev(self) -> bool:
        """是否为开发版插件。

        开发版放在 plugins/.dev 下，与商店版同 ID；同 ID 两份并存时
        只导入其中一份，由插件的切换选项决定。不参与商店的更新与卸载。
        """
        return self.source == PluginSource.DEV

    @property
    def has_both_copies(self) -> bool:
        """是否同时存在商店版和开发版两份副本（可切换）。"""
        return self.inactive_copy is not None
