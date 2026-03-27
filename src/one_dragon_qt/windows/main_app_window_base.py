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
    - ctx.init() 完成后构建 AppSettingManager
    """

    def __init__(
        self,
        ctx: OneDragonContext,
        win_title: str,
        project_config: ProjectConfig,
        app_icon: str | None = None,
        parent=None,
    ):
        # app_setting_manager 延迟到 ctx.init() 完成后构建
        # 所有消费方已通过 getattr(window, 'app_setting_manager', None) 做了空值处理
        self.app_setting_manager: AppSettingManager | None = None

        AppWindowBase.__init__(
            self,
            win_title=win_title,
            project_config=project_config,
            app_icon=app_icon,
            parent=parent,
        )

    def init_app_setting_manager(self, ctx: OneDragonContext) -> None:
        """在 ctx.init() 完成后调用，构建应用设置管理器"""
        self.app_setting_manager = AppSettingManager(ctx)
