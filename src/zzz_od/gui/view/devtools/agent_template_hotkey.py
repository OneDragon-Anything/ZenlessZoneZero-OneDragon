from __future__ import annotations

from pynput import keyboard
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    MessageBoxBase,
    PushButton,
    SubtitleLabel,
)

from one_dragon.utils.i18_utils import gt
from zzz_od.gui.view.devtools.agent_template_widgets import ShortcutButton

MODIFIER_ORDER: tuple[str, ...] = ('ctrl', 'alt', 'shift', 'win')

# 截图键可批量设置的修饰键
BATCH_MODIFIERS: list[str] = ['ctrl', 'alt', 'shift', 'ctrl+shift', 'ctrl+alt']

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


class HotkeyListDialog(MessageBoxBase):
    """修改全部快捷键，点击一项后按下新的组合键。"""

    def __init__(self, listener: HotkeyListener, items: list[tuple[str, str, str]], values: dict[str, str],
                 batch_keys: list[str], parent: QWidget | None = None) -> None:
        """
        :param items: (key, 名称, 默认值)
        :param values: 当前快捷键
        :param batch_keys: 可批量修改修饰键的快捷键
        """
        MessageBoxBase.__init__(self, parent)
        self._listener: HotkeyListener = listener
        self._defaults: dict[str, str] = {key: default_value for key, _, default_value in items}
        self._batch_keys: list[str] = batch_keys
        self.values: dict[str, str] = dict(values)
        self._recording_key: str | None = None

        self.viewLayout.setSpacing(12)
        self.viewLayout.addWidget(SubtitleLabel(gt('快捷键')))

        modifier_row = QHBoxLayout()
        modifier_row.setContentsMargins(0, 0, 0, 0)
        modifier_row.addWidget(BodyLabel(gt('截图键修饰键')))
        modifier_row.addStretch(1)
        self.modifier_box = ComboBox()
        self.modifier_box.addItems([' + '.join(hotkey_keys(m + '+x')[:-1]) for m in BATCH_MODIFIERS])
        self.modifier_box.setPlaceholderText(gt('自定义'))
        self.modifier_box.setMinimumWidth(140)
        self.modifier_box.currentIndexChanged.connect(self._on_modifier_changed)
        modifier_row.addWidget(self.modifier_box)
        self.viewLayout.addLayout(modifier_row)
        self.buttons: dict[str, ShortcutButton] = {}
        for key, name, _ in items:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(BodyLabel(name))
            row.addStretch(1)
            btn = ShortcutButton()
            btn.setAccessibleName(name)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(lambda _=False, k=key: self._start_recording(k))
            row.addWidget(btn)
            self.viewLayout.addLayout(row)
            self.buttons[key] = btn
        self._refresh_buttons()

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
        listener.start()

    def _refresh_buttons(self) -> None:
        for key, btn in self.buttons.items():
            if key == self._recording_key:
                btn.set_keys([], gt('请按键'))
            else:
                btn.set_keys(hotkey_keys(self.values[key]))

        # 截图键的修饰键都相同时显示该修饰键 否则显示自定义
        modifiers = {self.values[key].rpartition('+')[0] for key in self._batch_keys}
        self.modifier_box.blockSignals(True)
        self.modifier_box.setCurrentIndex(-1)  # 设置相同的下标不会刷新显示
        if len(modifiers) == 1 and (modifier := modifiers.pop()) in BATCH_MODIFIERS:
            self.modifier_box.setCurrentIndex(BATCH_MODIFIERS.index(modifier))
        self.modifier_box.blockSignals(False)

    def _on_modifier_changed(self, index: int) -> None:
        """批量修改截图键的修饰键，保留各自的按键。"""
        if index < 0:
            return
        modifier = BATCH_MODIFIERS[index]
        for key in self._batch_keys:
            base = (self.values[key] or self._defaults[key]).rpartition('+')[2]
            self._assign(key, f'{modifier}+{base}')
        self._refresh_buttons()

    def _start_recording(self, key: str) -> None:
        self._recording_key = key
        self._listener.recording = True
        self._refresh_buttons()

    def _on_combo_changed(self, combo: str) -> None:
        if self._recording_key is not None and combo:
            self.buttons[self._recording_key].set_keys(hotkey_keys(combo))

    def _on_recorded(self, combo: str) -> None:
        if self._recording_key is None:
            return
        self._assign(self._recording_key, normalize_hotkey(combo))
        self._recording_key = None
        self._listener.recording = False
        self._refresh_buttons()

    def _assign(self, key: str, combo: str) -> None:
        """同一个组合只能对应一个操作，已被占用时清空原来的。"""
        for other, value in self.values.items():
            if other != key and value == combo:
                self.values[other] = ''
        self.values[key] = combo

    def _on_reset(self) -> None:
        self.values = dict(self._defaults)
        self._recording_key = None
        self._listener.recording = False
        self._refresh_buttons()

    def keyPressEvent(self, e: QKeyEvent) -> None:
        # 录制时按下的 Enter / Esc 不关闭对话框
        e.accept()

    def done(self, code: int) -> None:
        self._listener.recording = False
        self._listener.combo_changed.disconnect(self._on_combo_changed)
        self._listener.recorded.disconnect(self._on_recorded)
        MessageBoxBase.done(self, code)
