"""虚拟手柄控制器基类 —— Xbox / DS4 的公共逻辑。

子类只需提供 ``pad`` 实例并调用 ``_register_*`` 系列方法注册按键，
基类自动构建 ``tap / press / release`` 的字符串分发。
"""

import time
from collections.abc import Callable

from one_dragon.base.controller.pc_button.pc_button_controller import PcButtonController


class VirtualGamepadController(PcButtonController):
    """数据驱动的虚拟手柄控制器。

    内部维护 ``_key_bindings: dict[str, tuple[activate, deactivate]]``，
    ``activate()`` 将手柄状态设为"按下"，``deactivate()`` 将其重置。
    ``pad.update()`` 由基类统一调用。
    """

    def __init__(self) -> None:
        PcButtonController.__init__(self)
        self.pad = None
        self._key_bindings: dict[str, tuple[Callable[[], None], Callable[[], None]]] = {}

    def _register_button(self, key: str, btn_const: int) -> None:
        """注册普通按钮（press_button / release_button）。"""
        self._key_bindings[key] = (
            lambda b=btn_const: self.pad.press_button(b),
            lambda b=btn_const: self.pad.release_button(b),
        )

    def _register_trigger(self, key: str, *, left: bool) -> None:
        """注册扳机（left_trigger / right_trigger）。"""
        trigger = 'left_trigger' if left else 'right_trigger'
        self._key_bindings[key] = (
            lambda t=trigger: getattr(self.pad, t)(value=255),
            lambda t=trigger: getattr(self.pad, t)(value=0),
        )

    def _register_stick(
        self, key: str, *, stick: str, x: float, y: float
    ) -> None:
        """注册摇杆方向。

        Args:
            key: 按键标识
            stick: ``'left'`` 或 ``'right'``
            x: 偏转 x
            y: 偏转 y
        """
        fn_name = f'{stick}_joystick_float'
        self._key_bindings[key] = (
            lambda f=fn_name, _x=x, _y=y: getattr(self.pad, f)(_x, _y),
            lambda f=fn_name: getattr(self.pad, f)(0, 0),
        )

    def _do_action(
        self,
        activate: Callable[[], None],
        deactivate: Callable[[], None],
        *,
        press: bool,
        press_time: float | None,
    ) -> None:
        """执行按键动作，统一处理按下时长和释放逻辑。"""
        activate()
        self.pad.update()

        if press:
            if press_time is None:  # 按住不放
                return
        else:
            if press_time is None:
                press_time = self.key_press_time

        time.sleep(max(self.key_press_time, press_time))
        deactivate()
        self.pad.update()

    def tap(self, key: str) -> None:
        if key is None:
            return
        activate, deactivate = self._key_bindings[key]
        self._do_action(activate, deactivate, press=False, press_time=None)

    def press(self, key: str, press_time: float | None = None) -> None:
        if key is None:
            return
        activate, deactivate = self._key_bindings[key]
        self._do_action(activate, deactivate, press=True, press_time=press_time)

    def release(self, key: str) -> None:
        if key is None:
            return
        _, deactivate = self._key_bindings[key]
        deactivate()
        self.pad.update()

    def reset(self) -> None:
        self.pad.reset()
        self.pad.update()
