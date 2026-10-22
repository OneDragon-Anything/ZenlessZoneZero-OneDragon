from __future__ import annotations

from pynput import keyboard
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import MessageBoxBase, PushButton, SubtitleLabel

from one_dragon.utils.i18_utils import gt
from zzz_od.gui.view.devtools.agent_template_widgets import KeyCapRow

MODIFIER_ORDER: tuple[str, ...] = ('ctrl', 'alt', 'shift', 'win')

MODIFIER_KEYS: dict[keyboard.Key, str] = {
    keyboard.Key.ctrl: 'ctrl',
    keyboard.Key.ctrl_l: 'ctrl',
    keyboard.Key.ctrl_r: 'ctrl',
    keyboard.Key.alt: 'alt',
    keyboard.Key.alt_l: 'alt',
    keyboard.Key.alt_r: 'alt',
    keyboard.Key.alt_gr: 'alt',
    keyboard.Key.shift: 'shift',
    keyboard.Key.shift_l: 'shift',
    keyboard.Key.shift_r: 'shift',
    keyboard.Key.cmd: 'win',
    keyboard.Key.cmd_l: 'win',
    keyboard.Key.cmd_r: 'win',
}


def normalize_hotkey(value: str | None) -> str:
    """统一快捷键格式，例如 'Ctrl + F8' -> 'ctrl+f8'，空字符串表示未设置。"""
    parts = [p.strip().lower() for p in (value or '').split('+') if p.strip()]
    if not parts:
        return ''
    modifiers = [m for m in MODIFIER_ORDER if m in parts[:-1]]
    return '+'.join([*modifiers, parts[-1]])


def hotkey_keys(value: str) -> list[str]:
    """显示用的按键列表，例如 'ctrl+f8' -> ['Ctrl', 'F8']。"""
    if not value:
        return []
    return [p.capitalize() if p in MODIFIER_ORDER or len(p) > 3 else p.upper() for p in value.split('+')]


def key_to_name(key: keyboard.Key | keyboard.KeyCode | None) -> str | None:
    """按键转为名称。字母和数字优先用虚拟键码，按住 Ctrl 时 char 会变成控制字符。"""
    if key is None:
        return None
    if isinstance(key, keyboard.Key):
        return key.name.lower()
    vk = getattr(key, 'vk', None)
    if vk is not None:
        if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
            return chr(vk).lower()
        if 0x60 <= vk <= 0x69:
            return f'numpad_{vk - 0x60}'
    if key.char and key.char.isprintable():
        return key.char.lower()
    return f'vk_{vk}' if vk is not None else None


class HotkeyListener(QObject):
    """全局快捷键监听，支持组合键，信号在主线程触发。"""

    pressed = Signal(str)  # 按下了 combos 中的组合
    combo_changed = Signal(str)  # 录制中当前按下的组合
    recorded = Signal(str)  # 录制完成的组合

    def __init__(self, parent: QObject | None = None) -> None:
        QObject.__init__(self, parent)
        self.combos: set[str] = set()
        self.recording: bool = False
        self._modifiers: set[str] = set()
        self._pressed: set[str] = set()
        self._listener: keyboard.Listener | None = None

    @property
    def is_running(self) -> bool:
        return self._listener is not None

    def start(self) -> None:
        if self._listener is not None:
            return
        self._modifiers.clear()
        self._pressed.clear()
        self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self._listener.start()

    def stop(self) -> None:
        listener = self._listener
        self._listener = None
        if listener is not None:
            listener.stop()

    def _current_modifiers(self) -> list[str]:
        return [m for m in MODIFIER_ORDER if m in self._modifiers]

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        modifier = MODIFIER_KEYS.get(key) if isinstance(key, keyboard.Key) else None
        if modifier is not None:
            self._modifiers.add(modifier)
            if self.recording:
                self.combo_changed.emit('+'.join(self._current_modifiers()))
            return

        name = key_to_name(key)
        if name is None or name in self._pressed:  # 长按会重复触发 只处理第一次
            return
        self._pressed.add(name)

        combo = '+'.join([*self._current_modifiers(), name])
        if self.recording:
            self.combo_changed.emit(combo)
            self.recorded.emit(combo)
        elif combo in self.combos:
            self.pressed.emit(combo)

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        modifier = MODIFIER_KEYS.get(key) if isinstance(key, keyboard.Key) else None
        if modifier is not None:
            self._modifiers.discard(modifier)
            return
        name = key_to_name(key)
        if name is not None:
            self._pressed.discard(name)


class HotkeyDialog(MessageBoxBase):
    """录制一个快捷键。"""

    def __init__(self, listener: HotkeyListener, title: str, value: str, default_value: str,
                 parent: QWidget | None = None) -> None:
        MessageBoxBase.__init__(self, parent)
        self._listener: HotkeyListener = listener
        self._default_value: str = default_value
        self.value: str = value

        self.viewLayout.setSpacing(24)
        self.viewLayout.addWidget(SubtitleLabel(title))

        caps_row = QHBoxLayout()
        caps_row.setContentsMargins(0, 0, 0, 0)
        caps_row.addStretch(1)
        self.caps = KeyCapRow(large=True)
        caps_row.addWidget(self.caps)
        caps_row.addStretch(1)
        self.viewLayout.addLayout(caps_row)
        self.caps.set_keys(hotkey_keys(self.value))

        self.yesButton.setText(gt('保存'))
        self.cancelButton.setText(gt('取消'))
        self.reset_button = PushButton(gt('重置'))
        self.reset_button.clicked.connect(self._on_reset)
        self.buttonLayout.insertWidget(1, self.reset_button, 1)
        # 录制时按下的空格等按键不能触发按钮
        for btn in (self.yesButton, self.reset_button, self.cancelButton):
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.widget.setMinimumWidth(400)

        listener.combo_changed.connect(self._on_combo_changed)
        listener.recorded.connect(self._on_recorded)
        listener.recording = True
        listener.start()

    def _on_combo_changed(self, combo: str) -> None:
        if combo:
            self.caps.set_keys(hotkey_keys(combo))

    def _on_recorded(self, combo: str) -> None:
        self.value = normalize_hotkey(combo)
        self.caps.set_keys(hotkey_keys(self.value))

    def _on_reset(self) -> None:
        self.value = self._default_value
        self.caps.set_keys(hotkey_keys(self.value))

    def keyPressEvent(self, e: QKeyEvent) -> None:
        # 录制时按下的 Enter / Esc 不关闭对话框
        e.accept()

    def done(self, code: int) -> None:
        self._listener.recording = False
        self._listener.combo_changed.disconnect(self._on_combo_changed)
        self._listener.recorded.disconnect(self._on_recorded)
        MessageBoxBase.done(self, code)
