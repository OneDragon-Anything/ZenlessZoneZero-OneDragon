from __future__ import annotations

from typing import TYPE_CHECKING

import psutil
from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, InfoBar, PushButton

from one_dragon.base.controller.window_error import WindowAmbiguousError
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.view.setting.setting_instance_interface import (
    SettingInstanceInterface,
)
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import (
    MultiPushSettingCard,
)

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class ZSettingInstanceInterface(SettingInstanceInterface):

    def __init__(self, ctx: ZContext, parent: QWidget | None = None) -> None:
        """创建绝区零账户设置页面。"""
        super().__init__(ctx=ctx, parent=parent)

    def init_game_account_config(self) -> None:
        """初始化设置，首次开启自定义标题前提供可编辑的默认值。"""
        super().init_game_account_config()
        if not self.custom_win_title_input.text() and not self.ctx.game_account_config.use_custom_win_title:
            self.custom_win_title_input.setText(self.ctx.get_window_titles()[0])

    def _create_game_path_card(self) -> MultiPushSettingCard:
        """在手动选择旁提供运行窗口路径读取。"""
        choose_button = PushButton(gt('选择'))
        choose_button.clicked.connect(self._on_game_path_clicked)
        read_button = PushButton(gt('从运行游戏读取'))
        read_button.clicked.connect(self._read_game_path)
        return MultiPushSettingCard(
            icon=FluentIcon.FOLDER, title='游戏路径',
            btn_list=[choose_button, read_button],
        )

    def _read_game_path(self) -> None:
        """从唯一绑定窗口读取路径，失败不覆盖已有配置。"""
        try:
            if self.ctx.controller is None:
                self.ctx.init_controller()
            path = self.ctx.controller.game_win.get_executable_path()
        except psutil.AccessDenied:
            log.warning('系统拒绝读取游戏进程路径', exc_info=True)
            InfoBar.warning(
                gt('读取失败'), gt('权限不足，请检查程序运行权限或手动选择游戏路径'),
                parent=self, duration=5000,
            )
            return
        except (WindowAmbiguousError, OSError, psutil.Error) as error:
            log.warning('读取游戏路径失败', exc_info=True)
            InfoBar.warning(gt('读取失败'), str(error), parent=self, duration=5000)
            return
        self._on_game_path_chosen(path)
        InfoBar.success(gt('读取成功'), gt('已保存当前账户的游戏路径'), parent=self)

    def _update_custom_win_title(self) -> None:
        """只同步标题配置，避免重建控制器导致无关窗口切换。"""
        title = self.custom_win_title_input.text()
        if self.ctx.game_account_config.use_custom_win_title and not title.strip():
            previous_title = self.ctx.game_account_config.custom_win_title
            if previous_title.strip():
                self.custom_win_title_input.setText(previous_title)
            else:
                self.ctx.game_account_config.use_custom_win_title = False
                self.custom_win_title_opt.init_with_adapter(
                    self.ctx.game_account_config.get_prop_adapter('use_custom_win_title')
                )
            InfoBar.warning(gt('设置失败'), gt('自定义窗口标题不能为空'), parent=self)
            return
        self.ctx.game_account_config.custom_win_title = title
        if self.ctx.controller is not None:
            self.ctx.controller.set_window_titles(self.ctx.get_window_titles())

    def on_game_region_opt_changed(self, _: int, value: str) -> None:
        """区服只更新登录设置界面，不改变窗口绑定。"""
        self.set_ui_of_game_region(value)
