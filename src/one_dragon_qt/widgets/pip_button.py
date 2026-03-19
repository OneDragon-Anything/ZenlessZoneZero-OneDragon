from qfluentwidgets import FluentIcon

from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon_qt.services.pip.pip_mode_manager import PipModeManager
from one_dragon_qt.widgets.navigation_button import NavigationToggleButton


class PipButton(NavigationToggleButton):
    """画中画导航按钮，封装画中画模式的全部开关逻辑。"""

    def __init__(self, ctx: OneDragonContext, parent=None) -> None:
        self.ctx = ctx
        self._manager: PipModeManager | None = None

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

        # 自动恢复上次的开启状态
        if self.ctx.pip_config.enabled:
            self._start_pip()
            self._update_state()

    def _on_clicked(self) -> None:
        if self._manager is not None and self._manager.is_active:
            self._stop_pip()
            self.ctx.pip_config.enabled = False
        else:
            self._start_pip()
            self.ctx.pip_config.enabled = True
        self._update_state()

    def _start_pip(self) -> None:
        if self._manager is None:
            self._manager = PipModeManager(self.ctx)

        self._manager.start()

    def _stop_pip(self) -> None:
        if self._manager is not None:
            self._manager.stop()

    def _update_state(self) -> None:
        self.set_active(self._manager is not None and self._manager.is_active)

    def dispose(self) -> None:
        if self._manager is not None:
            self._manager.stop()
            self._manager = None
