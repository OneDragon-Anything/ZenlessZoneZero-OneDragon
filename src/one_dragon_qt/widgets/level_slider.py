from collections.abc import Sequence

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget
from qfluentwidgets import Slider, isDarkTheme

from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.adapter_init_mixin import AdapterInitMixin


class TickSlider(Slider):
    """每个档位下方画一条刻度线的滑条（qfluentwidgets 的 Slider 默认不画刻度）。"""

    def _drawHorizonTick(self, painter: QPainter) -> None:
        count = self.maximum() - self.minimum()
        if count <= 0:
            return
        r = self.handle.width() / 2
        span = self.width() - r * 2
        painter.setBrush(QColor(255, 255, 255, 140) if isDarkTheme() else QColor(0, 0, 0, 120))
        for i in range(count + 1):
            x = r + span * i / count
            # 刻度画在滑块（高 22）正下方，避免被滑块盖住
            painter.drawRoundedRect(QRectF(x - 1, r * 2 + 2, 2, 6), 1, 1)


class LevelSlider(QWidget, AdapterInitMixin):
    """带档位的滑条控件：滑条每一格对应一个档位，可选在左侧显示一个名称（如"宽"）。

    默认不显示档位名；需要时传入 ``level_names``（或之后调用 ``set_level_names``），
    滑条右侧会显示当前档位的名字，传入后档数以名字个数为准。

    值为档位下标（0 ~ levels - 1）。可作为普通控件放进
    ``MultiLineSettingCard`` 等容器，也支持 ``init_with_adapter`` 绑定配置。
    """

    value_changed = Signal(int)

    def __init__(self, levels: int = 5, title: str = '', slider_width: int = 180,
                 level_names: Sequence[str] | None = None, parent=None):
        QWidget.__init__(self, parent)
        AdapterInitMixin.__init__(self)

        self.slider = TickSlider(Qt.Orientation.Horizontal, self)
        self.slider.setFixedWidth(slider_width)
        self.slider.setFixedHeight(32)  # 滑块 22 + 下方刻度线
        self.level_names: list[str] = []
        self.name_label = QLabel(self)
        self.name_label.setMinimumWidth(40)
        self.name_label.setFixedHeight(22)
        self.name_label.setVisible(False)
        self.slider.setRange(0, max(0, levels - 1))
        self.slider.setSingleStep(1)
        self.slider.setPageStep(1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        if title:
            self.title_label = QLabel(gt(title), self)
            # 和滑块（高 22）等高并顶对齐，文字才会和滑槽垂直居中
            self.title_label.setFixedHeight(22)
            layout.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.slider)
        layout.addWidget(self.name_label, 0, Qt.AlignmentFlag.AlignTop)

        # 不能用 blockSignals：Slider 内部靠 valueChanged 同步滑块位置，被屏蔽会导致位置不更新
        self._silent: bool = False
        self.slider.valueChanged.connect(self._on_value_changed)
        if level_names:
            self.set_level_names(level_names)

    def set_level_names(self, names: Sequence[str] | None) -> None:
        """设置档位名（None 或空则隐藏）。名字个数会成为新的档数。"""
        self.level_names = [gt(n) for n in names] if names else []
        if self.level_names:
            self.slider.setRange(0, len(self.level_names) - 1)
        self.name_label.setVisible(bool(self.level_names))
        self._update_name_label()

    def current_level_name(self) -> str:
        """当前档位名；没有设置档位名时返回空字符串。"""
        value = self.slider.value()
        return self.level_names[value] if 0 <= value < len(self.level_names) else ''

    def _update_name_label(self) -> None:
        self.name_label.setText(self.current_level_name())

    def _on_value_changed(self, value: int) -> None:
        self._update_name_label()
        if self._silent:
            return
        if self.adapter is not None:
            self.adapter.set_value(value)
        self.value_changed.emit(value)

    def setValue(self, value: int, emit_signal: bool = True) -> None:
        """设置档位下标"""
        value = max(self.slider.minimum(), min(self.slider.maximum(), int(value)))
        self._silent = not emit_signal
        try:
            self.slider.setValue(value)
        finally:
            self._silent = False
        self._update_name_label()

    def default_adapter_value(self) -> int:
        return 0
