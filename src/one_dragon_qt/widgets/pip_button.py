from PySide6.QtCore import Qt, QTimer
from qfluentwidgets import FluentIcon, InfoBar, InfoBarPosition

from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon_qt.services.pip.pip_mode_manager import PipModeManager
from one_dragon_qt.widgets.navigation_button import NavigationToggleButton


class PipButton(NavigationToggleButton):
    """画中画导航按钮，封装画中画模式的全部开关逻辑。"""

    def __init__(self, ctx: OneDragonContext, parent) -> None:
        self._ctx = ctx
        self._pip_manager: PipModeManager | None = None

        super().__init__(
            object_name='pip_button',
            text='画中画',
            icon_off=FluentIcon.PLAY,
            icon_on=FluentIcon.PLAY_SOLID,
            tooltip_off='画中画已关闭，点击开启后游戏切到后台自动显示画中画',
            tooltip_on='画中画已开启，游戏切到后台会自动显示，点击画中画切回游戏',
            on_click=self._on_clicked,
            parent=parent,
        )

        self._state_timer = QTimer(parent)
        self._state_timer.timeout.connect(self._sync_state)
        self._state_timer.start(500)

    def _on_clicked(self) -> None:
        if self._pip_manager is not None and self._pip_manager.is_active:
            self._stop_pip()
        else:
            self._start_pip()
        self._update_state()

    def _start_pip(self) -> None:
        try:
            self._ctx.init_controller()
        except Exception as exc:
            self._show_info('提示', f'初始化控制器失败: {exc}')
            return

        if self._ctx.controller is None or not self._ctx.controller.is_game_window_ready:
            self._show_info('提示', '请先启动游戏并等待初始化完成')
            return

        if self._pip_manager is None:
            self._pip_manager = PipModeManager(self._ctx.controller)

        if not self._pip_manager.start():
            self._pip_manager = None
            self._show_info('提示', '画中画启动失败')

    def _stop_pip(self) -> None:
        if self._pip_manager is not None:
            self._pip_manager.stop()
            self._pip_manager = None

    def _sync_state(self) -> None:
        if self._pip_manager is not None and not self._pip_manager.is_active:
            self._pip_manager = None
            self._update_state()

    def _update_state(self) -> None:
        self.set_active(self._pip_manager is not None and self._pip_manager.is_active)

    def _show_info(self, title: str, content: str) -> None:
        InfoBar.info(
            title=title,
            content=content,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self.window(),
        )
