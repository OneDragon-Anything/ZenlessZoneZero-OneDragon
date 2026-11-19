from collections.abc import Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from qfluentwidgets import FluentIconBase

from one_dragon_qt.utils.layout_utils import IconSize, Margins
from one_dragon_qt.widgets.adapter_init_mixin import AdapterInitMixin
from one_dragon_qt.widgets.level_slider import LevelSlider
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase


class SliderSettingCard(SettingCardBase, AdapterInitMixin):
    """带档位滑条的设置卡片：滑条每一格对应一个档位。

    值为档位下标（0 ~ levels - 1）。滑条本身是 ``LevelSlider``，
    需要把多条滑条放进同一张卡片时，直接用 ``LevelSlider`` 配合 ``MultiLineSettingCard``。
    """

    value_changed = Signal(int)

    def __init__(self,
                 icon: str | QIcon | FluentIconBase, title: str, content: str | None = None,
                 levels: int = 5,
                 level_names: Sequence[str] | None = None,
                 slider_width: int = 180,
                 icon_size: IconSize | None = None,
                 margins: Margins | None = None,
                 parent=None):
        SettingCardBase.__init__(
            self,
            icon=icon,
            title=title,
            content=content,
            icon_size=icon_size if icon_size is not None else IconSize(16, 16),
            margins=margins if margins is not None else Margins(16, 16, 0, 16),
            parent=parent,
        )
        AdapterInitMixin.__init__(self)

        self.level_slider = LevelSlider(levels, slider_width=slider_width, level_names=level_names, parent=self)
        self.hBoxLayout.addWidget(self.level_slider, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

        self.level_slider.value_changed.connect(self._on_value_changed)

    def _on_value_changed(self, value: int) -> None:
        if self.adapter is not None:
            self.adapter.set_value(value)
        self.value_changed.emit(value)

    def setValue(self, value: int, emit_signal: bool = True) -> None:
        """设置档位下标"""
        self.level_slider.setValue(value, emit_signal=emit_signal)

    def set_level_names(self, names: Sequence[str] | None) -> None:
        """设置档位名，会显示在滑条右侧；None 则隐藏"""
        self.level_slider.set_level_names(names)

    def current_level_name(self) -> str:
        return self.level_slider.current_level_name()

    def default_adapter_value(self) -> int:
        return 0
