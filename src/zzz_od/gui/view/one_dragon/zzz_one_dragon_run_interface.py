from pathlib import Path
from typing import cast

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QFileDialog, QWidget
from qfluentwidgets import (
    FluentIcon,
    InfoBarIcon,
    MessageBox,
    PushButton,
    SettingCardGroup,
)

from one_dragon.utils.i18_utils import gt
from one_dragon_qt.view.one_dragon.one_dragon_run_interface import OneDragonRunInterface
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import (
    MultiPushSettingCard,
)
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
        profile_group = SettingCardGroup(gt('游戏画质配置'))
        top.add_widget(profile_group)

        self.profile_switch: SwitchSettingCard = SwitchSettingCard(
            icon=FluentIcon.SPEED_HIGH,
            title='自动切换游戏画质配置',
            content='开始时重启游戏并导入一条龙画质，结束时关闭游戏并恢复正常画质',
        )
        profile_group.addSettingCard(self.profile_switch)

        self.run_profile_choose_btn: PushButton = PushButton(
            icon=FluentIcon.FOLDER,
            text='选择文件',
            parent=self,
        )
        self.run_profile_choose_btn.clicked.connect(self._on_choose_run_profile)
        self.run_profile_export_btn: PushButton = PushButton(
            icon=FluentIcon.SAVE,
            text='保存当前',
            parent=self,
        )
        self.run_profile_export_btn.clicked.connect(self._on_export_run_profile)
        self.run_profile_card: MultiPushSettingCard = MultiPushSettingCard(
            icon=FluentIcon.FOLDER,
            title='一条龙画质配置',
            content='未选择 .reg 文件',
            btn_list=[
                self.run_profile_choose_btn,
                self.run_profile_export_btn,
            ],
        )
        profile_group.addSettingCard(self.run_profile_card)

        self.normal_profile_choose_btn: PushButton = PushButton(
            icon=FluentIcon.FOLDER,
            text='选择文件',
            parent=self,
        )
        self.normal_profile_choose_btn.clicked.connect(self._on_choose_normal_profile)
        self.normal_profile_export_btn: PushButton = PushButton(
            icon=FluentIcon.SAVE,
            text='保存当前',
            parent=self,
        )
        self.normal_profile_export_btn.clicked.connect(self._on_export_normal_profile)
        self.normal_profile_card: MultiPushSettingCard = MultiPushSettingCard(
            icon=FluentIcon.FOLDER,
            title='正常画质配置',
            content='未选择 .reg 文件',
            btn_list=[
                self.normal_profile_choose_btn,
                self.normal_profile_export_btn,
            ],
        )
        profile_group.addSettingCard(self.normal_profile_card)

        self.restore_profile_card: PushSettingCard = PushSettingCard(
            icon=FluentIcon.SYNC,
            title='立即恢复正常画质',
            text='恢复',
            content='关闭正在运行的游戏并导入正常画质配置',
        )
        self.restore_profile_card.clicked.connect(self._on_restore_normal_profile)
        profile_group.addSettingCard(self.restore_profile_card)
        return top

    def on_interface_shown(self) -> None:
        OneDragonRunInterface.on_interface_shown(self)
        self.profile_switch.init_with_adapter(
            self.ctx.one_dragon_config.get_prop_adapter('game_settings_profile_enabled')
        )
        self._refresh_profile_cards()

    def _on_choose_run_profile(self) -> None:
        file_path = self._choose_profile(
            '选择一条龙画质配置',
            self.ctx.one_dragon_config.game_settings_profile_run_path,
        )
        if file_path is None:
            return
        self.ctx.one_dragon_config.game_settings_profile_run_path = file_path
        self._refresh_profile_cards()

    def _on_choose_normal_profile(self) -> None:
        file_path = self._choose_profile(
            '选择正常画质配置',
            self.ctx.one_dragon_config.game_settings_profile_normal_path,
        )
        if file_path is None:
            return
        self.ctx.one_dragon_config.game_settings_profile_normal_path = file_path
        self._refresh_profile_cards()

    def _on_export_run_profile(self) -> None:
        file_path = self._export_profile(
            '保存当前配置为一条龙画质',
            '绝区零-一条龙画质.reg',
            self.ctx.one_dragon_config.game_settings_profile_run_path,
        )
        if file_path is None:
            return
        self.ctx.one_dragon_config.game_settings_profile_run_path = file_path
        self._refresh_profile_cards()

    def _on_export_normal_profile(self) -> None:
        file_path = self._export_profile(
            '保存当前配置为正常画质',
            '绝区零-正常画质.reg',
            self.ctx.one_dragon_config.game_settings_profile_normal_path,
        )
        if file_path is None:
            return
        self.ctx.one_dragon_config.game_settings_profile_normal_path = file_path
        self._refresh_profile_cards()

    def _choose_profile(self, title: str, current_path: str) -> str | None:
        initial_dir = str(Path(current_path).parent) if current_path else ''
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            gt(title),
            dir=initial_dir,
            filter='Windows Registry (*.reg)',
        )
        if not file_path:
            return None

        try:
            profile_path = self.ctx.game_settings_profile_service.validate_profile(
                file_path
            )
        except (GameSettingsProfileError, OSError) as error:
            self._show_profile_error('配置文件无效', error)
            return None
        return str(profile_path)

    def _export_profile(
        self,
        title: str,
        default_file_name: str,
        current_path: str,
    ) -> str | None:
        initial_path = current_path or self._get_default_export_path(default_file_name)
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            gt(title),
            dir=initial_path,
            filter='Windows Registry (*.reg)',
        )
        if not file_path:
            return None

        try:
            profile_path = self.ctx.game_settings_profile_service.export_profile(
                file_path
            )
        except (GameSettingsProfileError, OSError) as error:
            self._show_profile_error('保存画质配置失败', error)
            return None

        self.show_info_bar(
            gt('画质配置已保存'),
            gt('配置文件可能包含登录或设备信息，请勿分享给他人'),
            icon=InfoBarIcon.SUCCESS,
            duration=8000,
        )
        return str(profile_path)

    def _on_restore_normal_profile(self) -> None:
        message_box = MessageBox(
            gt('恢复正常画质'),
            gt('将关闭正在运行的游戏并导入正常画质配置，是否继续？'),
            self,
        )
        message_box.yesButton.setText(gt('确定'))
        message_box.cancelButton.setText(gt('取消'))
        if not message_box.exec():
            return

        try:
            self.ctx.game_settings_profile_service.restore_normal_profile()
        except (GameSettingsProfileError, OSError) as error:
            self._show_profile_error('恢复正常画质失败', error)
            return

        self.show_info_bar(
            gt('正常画质已恢复'),
            gt('重新启动游戏后生效'),
            icon=InfoBarIcon.SUCCESS,
            duration=5000,
        )

    @staticmethod
    def _get_default_export_path(file_name: str) -> str:
        documents_path = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )
        base_path = Path(documents_path) if documents_path else Path.home()
        return str(base_path / file_name)

    def _show_profile_error(
        self,
        title: str,
        error: GameSettingsProfileError | OSError,
    ) -> None:
        self.show_info_bar(
            gt(title),
            str(error),
            icon=InfoBarIcon.ERROR,
            duration=5000,
        )

    def _refresh_profile_cards(self) -> None:
        run_path = self.ctx.one_dragon_config.game_settings_profile_run_path
        normal_path = self.ctx.one_dragon_config.game_settings_profile_normal_path
        self.run_profile_card.setContent(run_path or '未选择 .reg 文件')
        self.normal_profile_card.setContent(normal_path or '未选择 .reg 文件')
