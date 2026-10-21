import os
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent, QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget
from qfluentwidgets import Theme, isDarkTheme, setTheme

from one_dragon.utils import runtime_source
from one_dragon.utils.app_utils import start_one_dragon
from one_dragon.version import __version__
from one_dragon_qt.services.recovery_repair_adapter import RecoveryRepairQtAdapter
from one_dragon_qt.services.styles_manager import OdQtStyleSheet
from one_dragon_qt.view.recovery_repair_interface import RecoveryRepairInterface
from one_dragon_qt.windows.window import PhosFluentWindowBase, PhosTitleBar
from zzz_od.context.recovery_context import RecoveryContext


class RecoveryWindow(PhosFluentWindowBase):
    """直接显示集成启动器资源管理页面的恢复窗口。"""

    titleBar: PhosTitleBar

    def __init__(
        self,
        ctx: RecoveryContext,
        failure_reason: str,
        launcher_version: str,
        parent: QWidget | None = None,
    ) -> None:
        self._isMicaEnabled = False
        self._lightBackgroundColor = QColor(248, 249, 252)
        self._darkBackgroundColor = QColor(39, 39, 39)
        super().__init__(parent)
        self.ctx: RecoveryContext = ctx
        self.failure_reason: str = failure_reason
        self.launcher_version: str = launcher_version
        self._closing_after_cancel: bool = False
        self._close_retry_timer: QTimer = QTimer(self)
        self._close_retry_timer.setInterval(50)
        self._close_retry_timer.setSingleShot(True)
        self._close_retry_timer.timeout.connect(self._continue_close_after_cancel)
        ctx.update_service.restore_interrupted_launcher_update()
        self.recovery_adapter = RecoveryRepairQtAdapter(
            ctx,
            restart_callback=lambda: start_one_dragon(restart=True),
            parent=self,
        )
        self.recovery_adapter.event_received.connect(
            lambda *_args: self._continue_close_after_cancel()
        )

        self.setTitleBar(PhosTitleBar(self))
        self.titleBar.setObjectName('TitleBar')
        self.titleBar.setProperty('homeMode', False)
        self.titleBar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        OdQtStyleSheet.TITLE_BAR.apply(self.titleBar)
        self.titleBar.issue_url = f'{ctx.project_config.github_homepage}/issues'
        self.titleBar.setLauncherVersion(launcher_version)
        self.setWindowTitle(f'绝区零 一条龙 恢复模式 {launcher_version}')
        self.resize(1000, 760)

        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(0, self.titleBar.height(), 0, 0)
        self.content_layout.setSpacing(0)

        self.resource_interface = RecoveryRepairInterface(
            ctx,
            self.recovery_adapter,
            parent=self,
        )
        self.content_layout.addWidget(self.resource_interface)
        self.resource_interface.on_interface_shown()

    def _normalBackgroundColor(self) -> QColor:
        """返回与当前 Fluent 主题一致的窗口背景色。"""
        if isDarkTheme():
            return self._darkBackgroundColor
        return self._lightBackgroundColor

    def paintEvent(self, event: QPaintEvent) -> None:
        """绘制与当前主题一致的窗口背景。"""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.backgroundColor)
        painter.drawRect(self.rect())

    def _continue_close_after_cancel(self) -> None:
        """等待取消完成后关闭窗口。"""
        if not self._closing_after_cancel:
            return
        if self.resource_interface.has_recovery_active_task():
            self._close_retry_timer.start()
            return
        self._closing_after_cancel = False
        self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        """关闭窗口前先取消仍在执行的恢复任务。"""
        if self.resource_interface.has_recovery_active_task():
            self.resource_interface.cancel_recovery_task()
            self._closing_after_cancel = True
            self._close_retry_timer.start()
            event.ignore()
            return
        self.resource_interface.on_interface_hidden()
        super().closeEvent(event)


def main(failure_reason: str, launcher_version: str) -> int:
    """启动内置源码恢复界面。"""
    if not runtime_source.is_recovery_mode():
        raise RuntimeError('恢复界面只能由集成启动器恢复模式启动')

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication([sys.argv[0]])
    app.setAttribute(Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings)
    setTheme(Theme.AUTO)

    ctx = RecoveryContext()
    window = RecoveryWindow(ctx, failure_reason, launcher_version)
    window.show()
    window.activateWindow()
    exit_code = app.exec()
    ctx.after_app_shutdown()
    return exit_code


if __name__ == '__main__':
    os.environ.setdefault('ONE_DRAGON_RUNTIME_MODE', 'recovery')
    raise SystemExit(main('手动进入恢复模式', __version__))
