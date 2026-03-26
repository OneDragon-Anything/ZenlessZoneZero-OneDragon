from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.envs.project_config import ProjectConfig
from one_dragon_qt.services.app_setting.app_setting_manager import AppSettingManager
from one_dragon_qt.services.app_setting.app_setting_scanner import scan_app_settings
from one_dragon_qt.windows.app_window_base import AppWindowBase

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_context import OneDragonContext


class MainAppWindowBase(AppWindowBase):
    """主应用窗口基类。

    在 AppWindowBase 基础上增加：
    - 接收 OneDragonContext
    - 自动扫描 *_app_setting.py 并构建 AppSettingManager
    """

    def __init__(
        self,
        ctx: OneDragonContext,
        win_title: str,
        project_config: ProjectConfig,
        app_icon: str | None = None,
        parent=None,
    ):
        # 扫描并构建应用设置管理器
        providers = scan_app_settings(ctx.application_plugin_dirs)
        self.app_setting_manager: AppSettingManager = AppSettingManager(ctx, providers)

        AppWindowBase.__init__(
            self,
            win_title=win_title,
            project_config=project_config,
            app_icon=app_icon,
            parent=parent,
        )
