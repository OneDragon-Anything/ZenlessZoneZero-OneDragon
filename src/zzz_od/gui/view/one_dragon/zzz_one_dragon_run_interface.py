from pathlib import Path
from typing import cast

from PySide6.QtWidgets import QFileDialog, QWidget
from qfluentwidgets import FluentIcon, InfoBarIcon, SettingCardGroup

from one_dragon.utils.i18_utils import gt
from one_dragon_qt.view.one_dragon.one_dragon_run_interface import OneDragonRunInterface
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.push_setting_card import PushSettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_settings.game_settings_profile_service import (
    GameSettingsProfileError,
)


class ZOneDragonRunInterface(OneDragonRunInterface):

    def __init__(self, ctx: ZContext, parent: QWidget | None = None) -> None:
        self.ctx: ZContext = ctx
        OneDragonRunInterface.__init__(
            self,
            ctx=ctx,
            parent=parent,
            help_url='https://one-dragon.com/zzz/zh/feat/feat_one_dragon/onedragon.html',
        )

    def get_widget_at_top(self) -> QWidget:
        top = cast(Column, OneDragonRunInterface.get_widget_at_top(self))
        profile_group = SettingCardGroup(gt("游戏画质配置"))
        top.add_widget(profile_group)

        self.profile_switch: SwitchSettingCard = SwitchSettingCard(
            icon=FluentIcon.SPEED_HIGH,
            title="自动切换游戏画质配置",
            content="开始时重启游戏并导入一条龙画质，结束时关闭游戏并恢复正常画质",
        )
        profile_group.addSettingCard(self.profile_switch)

        self.run_profile_card: PushSettingCard = PushSettingCard(
            icon=FluentIcon.FOLDER,
            title="一条龙画质配置",
            text="选择",
            content="未选择 .reg 文件",
        )
        self.run_profile_card.clicked.connect(self._on_choose_run_profile)
        profile_group.addSettingCard(self.run_profile_card)

        self.normal_profile_card: PushSettingCard = PushSettingCard(
            icon=FluentIcon.FOLDER,
            title="正常画质配置",
            text="选择",
            content="未选择 .reg 文件",
        )
        self.normal_profile_card.clicked.connect(self._on_choose_normal_profile)
        profile_group.addSettingCard(self.normal_profile_card)
        return top

    def on_interface_shown(self) -> None:
        OneDragonRunInterface.on_interface_shown(self)
        self.profile_switch.init_with_adapter(
            self.ctx.one_dragon_config.get_prop_adapter(
                "game_settings_profile_enabled"
            )
        )
        self._refresh_profile_cards()

    def _on_choose_run_profile(self) -> None:
        file_path = self._choose_profile(
            "选择一条龙画质配置",
            self.ctx.one_dragon_config.game_settings_profile_run_path,
        )
        if file_path is None:
            return
        self.ctx.one_dragon_config.game_settings_profile_run_path = file_path
        self._refresh_profile_cards()

    def _on_choose_normal_profile(self) -> None:
        file_path = self._choose_profile(
            "选择正常画质配置",
            self.ctx.one_dragon_config.game_settings_profile_normal_path,
        )
        if file_path is None:
            return
        self.ctx.one_dragon_config.game_settings_profile_normal_path = file_path
        self._refresh_profile_cards()

    def _choose_profile(self, title: str, current_path: str) -> str | None:
        initial_dir = str(Path(current_path).parent) if current_path else ""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            gt(title),
            dir=initial_dir,
            filter="Windows Registry (*.reg)",
        )
        if not file_path:
            return None

        try:
            profile_path = self.ctx.game_settings_profile_service.validate_profile(
                file_path
            )
        except GameSettingsProfileError as error:
            self.show_info_bar(
                gt("配置文件无效"),
                str(error),
                icon=InfoBarIcon.ERROR,
                duration=5000,
            )
            return None
        return str(profile_path)

    def _refresh_profile_cards(self) -> None:
        run_path = self.ctx.one_dragon_config.game_settings_profile_run_path
        normal_path = self.ctx.one_dragon_config.game_settings_profile_normal_path
        self.run_profile_card.setContent(run_path or "未选择 .reg 文件")
        self.normal_profile_card.setContent(normal_path or "未选择 .reg 文件")
