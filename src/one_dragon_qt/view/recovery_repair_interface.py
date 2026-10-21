from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import (
    Dialog,
    HyperlinkButton,
    MessageBoxBase,
    PrimaryPushButton,
    ProgressRing,
    PushButton,
    SubtitleLabel,
)

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.envs.recovery_repair_service import (
    RecoveryRepairChannel,
    RecoveryRepairEvent,
    RecoveryRepairStage,
)
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.services.recovery_repair_adapter import RecoveryRepairQtAdapter
from one_dragon_qt.utils.image_utils import scale_pixmap_for_high_dpi
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.setting_card.download_source_settings_group import (
    DownloadSourceSettingsGroup,
)


class RecoveryRepairInterface(QWidget):
    """恢复模式固定布局页面，不使用纵向滚动容器。"""

    def __init__(
        self,
        ctx: OneDragonEnvContext,
        adapter: RecoveryRepairQtAdapter,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.ctx: OneDragonEnvContext = ctx
        self.recovery_adapter: RecoveryRepairQtAdapter = adapter
        self.recovery_settings_dialog: MessageBoxBase | None = None
        self._build_download_settings()
        self._build_layout()
        self._connect_adapter()

    def _build_layout(self) -> None:
        """照安装器一键安装模式创建左右固定布局。"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        center_layout = QHBoxLayout()
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        logo_widget = QWidget(self)
        logo_layout = QVBoxLayout(logo_widget)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setSpacing(0)
        logo_layout.addStretch(1)

        self.logo_label = QLabel(logo_widget)
        target_size = QSize(160, 160)
        logo_pixmap = scale_pixmap_for_high_dpi(
            QPixmap('assets/ui/logo.ico'),
            target_size,
            self.devicePixelRatio(),
        )
        self.logo_label.setPixmap(logo_pixmap)
        self.logo_label.setFixedSize(target_size)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        logo_layout.addWidget(
            self.logo_label,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        logo_layout.addStretch(1)
        center_layout.addWidget(logo_widget, stretch=1)

        action_widget = QWidget(self)
        action_layout = QVBoxLayout(action_widget)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(16)
        action_layout.addStretch(1)

        self.repair_button = PrimaryPushButton(gt('一键重装'), action_widget)
        self.repair_button.setFixedSize(320, 60)
        repair_font = self.repair_button.font()
        repair_font.setPointSize(18)
        self.repair_button.setFont(repair_font)
        self.repair_button.setEnabled(True)
        action_layout.addWidget(
            self.repair_button,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        self.channel_combo = ComboBox(action_widget)
        self.channel_combo.setFixedWidth(320)
        self.channel_combo.addItem(
            gt('正式版'),
            userData=RecoveryRepairChannel.STABLE.value,
        )
        self.channel_combo.addItem(
            gt('测试版'),
            userData=RecoveryRepairChannel.BETA.value,
        )
        self.channel_combo.setCurrentIndex(0)
        action_layout.addWidget(
            self.channel_combo,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        self.settings_button = HyperlinkButton('', gt('设置'), action_widget)
        action_layout.addWidget(
            self.settings_button,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        self.progress_ring = ProgressRing(action_widget)
        self.progress_ring.setRange(0, 100)
        self.progress_ring.setValue(0)
        self.progress_ring.setFixedSize(64, 64)
        self.progress_ring.hide()
        action_layout.addWidget(
            self.progress_ring,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        self.status_label = SubtitleLabel('', action_widget)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setMaximumWidth(420)
        self.status_label.hide()
        action_layout.addWidget(
            self.status_label,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        self.cancel_button = PushButton(gt('取消'), action_widget)
        self.cancel_button.setFixedWidth(160)
        self.cancel_button.hide()
        action_layout.addWidget(
            self.cancel_button,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        action_layout.addStretch(1)
        center_layout.addWidget(action_widget, stretch=2)

        main_layout.addStretch(1)
        main_layout.addLayout(center_layout)
        main_layout.addStretch(1)
        main_layout.addSpacing(40)

        self.repair_button.clicked.connect(self._start_repair)
        self.channel_combo.currentIndexChanged.connect(self._on_channel_changed)
        self.settings_button.clicked.connect(self._show_recovery_settings)
        self.cancel_button.clicked.connect(self._cancel_repair)

    def _build_download_settings(self) -> None:
        """创建设置弹窗中的下载源和代理设置。"""
        self.download_settings_group = DownloadSourceSettingsGroup(
            self.ctx,
            proxy_content='为启动器下载配置网络代理',
        )

    def _connect_adapter(self) -> None:
        """连接恢复服务状态回调。"""
        self.recovery_adapter.event_received.connect(self._on_repair_event)

    def on_interface_shown(self) -> None:
        """初始化设置适配器。"""
        self.download_settings_group.init_adapters()

    def on_interface_hidden(self) -> None:
        """固定布局页面隐藏时的生命周期钩子。"""

    def has_recovery_active_task(self) -> bool:
        """返回恢复重装是否仍在执行。"""
        return self.recovery_adapter.is_active()

    def cancel_recovery_task(self) -> None:
        """请求取消恢复服务。"""
        self.recovery_adapter.cancel()

    def selected_channel(self) -> str:
        """返回当前选择的版本通道。"""
        value = self.channel_combo.currentData()
        return str(value) if value is not None else ''

    def _start_repair(self) -> None:
        """按当前版本通道启动一键重装。"""
        channel = self.selected_channel()
        if not channel:
            self._set_status(gt('请选择版本通道'))
            return
        channel_name = gt('测试版') if channel == 'beta' else gt('正式版')
        self._set_running(True)
        self._set_status(f'{gt("准备重装")} {channel_name}')
        if not self.recovery_adapter.start(channel):
            self._set_running(False)
            self._set_status(gt('恢复任务未能启动'))

    def _cancel_repair(self) -> None:
        """请求取消当前重装。"""
        self.cancel_button.setEnabled(False)
        self._set_status(gt('正在取消'))
        self.recovery_adapter.cancel()

    def _set_running(self, running: bool) -> None:
        """切换安装器式空闲布局和进度布局。"""
        self.repair_button.setVisible(not running)
        self.channel_combo.setVisible(not running)
        self.settings_button.setVisible(not running)
        self.progress_ring.setVisible(running)
        self.cancel_button.setVisible(running)
        self.cancel_button.setEnabled(running)

        self.channel_combo.setDisabled(running)
        self.settings_button.setDisabled(running)
        self.download_settings_group.setDisabled(running)
        self.repair_button.setEnabled(
            not running and self.channel_combo.currentIndex() >= 0
        )

    def _set_status(self, message: str) -> None:
        """显示或隐藏当前状态文字。"""
        self.status_label.setText(gt(message))
        self.status_label.setVisible(bool(message))

    def _show_recovery_settings(self) -> None:
        """打开设置弹窗。"""
        if self.recovery_settings_dialog is None:
            dialog = MessageBoxBase(self.window())
            dialog.yesButton.setText(gt('关闭'))
            dialog.cancelButton.hide()
            dialog.viewLayout.addWidget(SubtitleLabel(gt('下载设置')))
            dialog.viewLayout.addWidget(self.download_settings_group)
            dialog.widget.setMinimumWidth(720)
            self.recovery_settings_dialog = dialog
        self.recovery_settings_dialog.exec()

    def _on_repair_event(self, event: RecoveryRepairEvent) -> None:
        """按恢复阶段更新进度、确认框和按钮状态。"""
        self.progress_ring.setValue(max(0, min(100, int(event.progress * 100))))
        if event.message:
            self._set_status(event.message)
        if event.stage == RecoveryRepairStage.WAITING_FORCE_CONFIRM:
            self._show_force_confirmation()
        elif event.stage == RecoveryRepairStage.COMMITTING:
            self.cancel_button.setEnabled(False)
        elif event.stage in (
            RecoveryRepairStage.SUCCEEDED,
            RecoveryRepairStage.FAILED,
            RecoveryRepairStage.CANCELLED,
        ):
            self._set_running(False)
            if event.error:
                self._set_status(event.error)

    def _show_force_confirmation(self) -> None:
        """询问是否覆盖工作区里未提交的改动。"""
        dialog = Dialog(
            gt('确认强制更新'),
            gt('当前代码工作区有未提交改动，继续后这些改动可能被覆盖。是否继续？'),
            self,
        )
        dialog.yesButton.setText(gt('继续更新'))
        dialog.cancelButton.setText(gt('取消'))
        self.recovery_adapter.respond_force_confirmation(bool(dialog.exec()))

    def _on_channel_changed(self, _index: int) -> None:
        """版本通道变化后更新重装按钮是否可点。"""
        self.repair_button.setEnabled(self.channel_combo.currentIndex() >= 0)
