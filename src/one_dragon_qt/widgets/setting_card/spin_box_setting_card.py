from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from qfluentwidgets import FluentIconBase, SpinBox, DoubleSpinBox
from typing import Union, Optional

from one_dragon_qt.utils.layout_utils import Margins, IconSize
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase
from one_dragon_qt.widgets.setting_card.yaml_config_adapter import YamlConfigAdapter


class SpinBoxSettingCardBase(SettingCardBase):
    """带微调框的设置卡片基类"""

    value_changed = Signal(object)

    def __init__(self,
                 icon: Union[str, QIcon, FluentIconBase], title: str, content: Optional[str] = None,
                 icon_size: IconSize = IconSize(16, 16),
                 margins: Margins = Margins(16, 16, 0, 16),
                 adapter: Optional[YamlConfigAdapter] = None,
                 parent=None):

        SettingCardBase.__init__(
            self,
            icon=icon,
            title=title,
            content=content,
            icon_size=icon_size,
            margins=margins,
            parent=parent
        )

        # 创建输入框控件
        self.spin_box = self._create_spin_box()
        self.hBoxLayout.addWidget(self.spin_box, 0)
        self.hBoxLayout.addSpacing(16)

        self.adapter: YamlConfigAdapter = adapter

        # 绑定输入框内容变化信号
        self.spin_box.valueChanged.connect(self._on_value_changed)

    def _create_spin_box(self) -> Union[SpinBox, DoubleSpinBox]:
        """创建微调框控件"""
        raise NotImplementedError()

    def _on_value_changed(self) -> None:
        """处理值更改事件"""
        val = self.spin_box.value()

        if isinstance(self.spin_box, DoubleSpinBox):
            val = round(val, self.spin_box.decimals())

        if self.adapter is not None:
            self.adapter.set_value(val)

        self.value_changed.emit(val)

    def init_with_adapter(self, adapter: Optional[YamlConfigAdapter]) -> None:
        """使用配置适配器初始化值"""
        self.adapter = adapter

        if self.adapter is None:
            self.setValue(0, emit_signal=False)
        else:
            self.setValue(self.adapter.get_value(), emit_signal=False)

    def setValue(self, value, emit_signal: bool = True) -> None:
        """设置输入框的值"""
        if not emit_signal:
            self.spin_box.blockSignals(True)
        self.spin_box.setValue(value)
        if not emit_signal:
            self.spin_box.blockSignals(False)

    def set_range(self, minimum: Union[int, float], maximum: Union[int, float]) -> None:
        """设置微调框的范围"""
        self.spin_box.setRange(minimum, maximum)

    def set_step(self, step: Union[int, float]) -> None:
        """设置微调框的步长"""
        self.spin_box.setSingleStep(step)

class SpinBoxSettingCard(SpinBoxSettingCardBase):
    """带整数微调框的设置卡片类"""

    def __init__(self,
                 icon: Union[str, QIcon, FluentIconBase], title: str, content: Optional[str] = None,
                 step: int = 1,
                 minimum: int = 0,
                 maximum: int = 99,
                 min_width: int = 140,
                 max_width: int = 300,
                 icon_size: IconSize = IconSize(16, 16),
                 margins: Margins = Margins(16, 16, 0, 16),
                 adapter: Optional[YamlConfigAdapter] = None,
                 parent=None):

        self.step = step
        self.minimum = minimum
        self.maximum = maximum
        self.min_width = min_width
        self.max_width = max_width

        SpinBoxSettingCardBase.__init__(
            self,
            icon=icon,
            title=title,
            content=content,
            icon_size=icon_size,
            margins= margins,
            adapter=adapter,
            parent=parent
        )

    def _create_spin_box(self) -> Union[SpinBox, DoubleSpinBox]:
        spin_box = SpinBox(self)
        spin_box.setMinimumWidth(self.min_width)
        spin_box.setMaximumWidth(self.max_width)
        spin_box.setRange(self.minimum, self.maximum)
        spin_box.setSingleStep(self.step)
        return spin_box


class DoubleSpinBoxSettingCard(SpinBoxSettingCardBase):
    """带双精度微调框的设置卡片类"""

    def __init__(self,
                 icon: Union[str, QIcon, FluentIconBase], title: str, content: Optional[str] = None,
                 step: float = 0.01,
                 minimum: float = 0.00,
                 maximum: float = 10.00,
                 min_width: int = 140,
                 max_width: int = 300,
                 icon_size: IconSize = IconSize(16, 16),
                 margins: Margins = Margins(16, 16, 0, 16),
                 adapter: Optional[YamlConfigAdapter] = None,
                 parent=None):

        self.step = step
        self.minimum = minimum
        self.maximum = maximum
        self.min_width = min_width
        self.max_width = max_width

        SpinBoxSettingCardBase.__init__(
            self,
            icon=icon,
            title=title,
            content=content,
            icon_size=icon_size,
            margins= margins,
            adapter=adapter,
            parent=parent
        )

    def _create_spin_box(self) -> Union[SpinBox, DoubleSpinBox]:
        spin_box = DoubleSpinBox(self)
        spin_box.setMinimumWidth(self.min_width)
        spin_box.setMaximumWidth(self.max_width)
        spin_box.setDecimals(2)
        spin_box.setRange(self.minimum, self.maximum)
        spin_box.setSingleStep(self.step)
        return spin_box
