from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.envs.project_config import ProjectConfig
from one_dragon_qt.services.app_setting.app_setting_manager import AppSettingManager
from one_dragon_qt.windows.app_window_base import AppWindowBase

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_context import OneDragonContext


class MainAppWindowBase(AppWindowBase):
    """主应用窗口基类。

    在 AppWindowBase 基础上增加：
    - 接收 OneDragonContext
    - 持有 AppSettingManager，ctx.init() 完成后执行设置发现
    """

    def __init__(
        self,
        ctx: OneDragonContext,
        win_title: str,
        project_config: ProjectConfig,
        app_icon: str | None = None,
        parent=None,
    ):
        self.app_setting_manager = AppSettingManager(ctx)

        AppWindowBase.__init__(
            self,
            win_title=win_title,
            project_config=project_config,
            app_icon=app_icon,
            parent=parent,
        )

    def on_ctx_ready(self) -> None:
        """在 ctx.init() 完成后调用，执行设置提供者扫描"""
        self.app_setting_manager.discover()
