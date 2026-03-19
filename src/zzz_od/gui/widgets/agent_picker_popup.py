from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import BodyLabel, CaptionLabel, LineEdit, ListWidget, StrongBodyLabel, isDarkTheme

from zzz_od.gui.widgets.agent_avatar_slot import (
    PLACEHOLDER_TEXT,
    draw_cover_pixmap,
    get_agent_avatar_pixmap,
    get_all_agent_options,
    get_agent_display_name,
    normalize_agent_id,
)


class AgentOptionPreview(QFrame):

    def __init__(self, agent_id: str, parent=None):
        super().__init__(parent)
        self.agent_id = normalize_agent_id(agent_id)
        self.setFixedSize(32, 32)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        is_dark = isDarkTheme()
        painter.fillPath(path, QColor(34, 36, 43) if is_dark else QColor(242, 245, 249))

        pixmap = get_agent_avatar_pixmap(self.agent_id)
        if pixmap is not None:
            draw_cover_pixmap(painter, rect, pixmap, 8)
        else:
            painter.setPen(QColor(212, 216, 224) if is_dark else QColor(95, 107, 122))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, PLACEHOLDER_TEXT[:2])

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(86, 92, 104) if is_dark else QColor(188, 196, 208), 1.5))
        painter.drawRoundedRect(rect, 8, 8)


class AgentOptionItem(QWidget):

    def __init__(self, agent_id: str, parent=None):
        super().__init__(parent)
        self.setObjectName("agentOptionItem")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        self.preview = AgentOptionPreview(agent_id, self)
        layout.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignVCenter)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)
        self.name_label = BodyLabel(get_agent_display_name(agent_id))
        self.id_label = CaptionLabel(agent_id)
        text_layout.addWidget(self.name_label)
        text_layout.addWidget(self.id_label)
        layout.addLayout(text_layout, 1)

    def sizeHint(self) -> QSize:
        return QSize(280, 42)


class AgentPickerPopup(QFrame):

    agent_selected = Signal(str)
    _current_popup: AgentPickerPopup | None = None

    def __init__(self, current_agent_id: str, parent=None):
        super().__init__(parent)
        self.current_agent_id = normalize_agent_id(current_agent_id)
        self._all_options = get_all_agent_options()

        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setObjectName("agentPickerPopup")

        self._setup_ui()
        self._apply_shadow()
        self._apply_theme_style()
        self._refresh_options()

    def _setup_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 14)
        root_layout.setSpacing(0)

        self.panel = QFrame(self)
        self.panel.setObjectName("agentPickerPanel")
        root_layout.addWidget(self.panel)

        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.title_label = StrongBodyLabel(self.panel)
        self.title_label.setText("选择代理人")
        layout.addWidget(self.title_label)

        self.search_input = LineEdit(self.panel)
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setPlaceholderText("搜索代理人名称或 ID")
        self.search_input.setFixedHeight(34)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.search_input.returnPressed.connect(self._select_current_item)
        layout.addWidget(self.search_input)

        self.list_widget = ListWidget(self.panel)
        self.list_widget.setMinimumWidth(320)
        self.list_widget.setMinimumHeight(280)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)

        self._item_map: dict[str, QListWidgetItem] = {}
        self._empty_item: QListWidgetItem | None = None
        self._init_all_options()

    def _init_all_options(self) -> None:
        for agent_id, _ in self._all_options:
            item_widget = AgentOptionItem(agent_id, self.list_widget)
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, agent_id)
            item.setSizeHint(item_widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, item_widget)
            self._item_map[agent_id] = item

        empty_item = QListWidgetItem()
        empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
        empty_widget = CaptionLabel("未找到匹配代理人")
        empty_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_widget.setMinimumHeight(48)
        empty_item.setSizeHint(empty_widget.sizeHint())
        self.list_widget.addItem(empty_item)
        self.list_widget.setItemWidget(empty_item, empty_widget)
        empty_item.setHidden(True)
        self._empty_item = empty_item

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.search_input.setFocus()
        self.search_input.selectAll()

    def _on_search_text_changed(self, text: str) -> None:
        self._refresh_options()

    def _refresh_options(self) -> None:
        keyword = self.search_input.text().strip().lower()

        current_item: QListWidgetItem | None = None
        matched = False
        for agent_id, agent_name in self._all_options:
            item = self._item_map[agent_id]
            if keyword and keyword not in agent_name.lower() and keyword not in agent_id.lower():
                item.setHidden(True)
                continue

            item.setHidden(False)
            matched = True
            if agent_id == self.current_agent_id:
                current_item = item

        if self._empty_item is not None:
            self._empty_item.setHidden(matched)

        if not matched:
            return

        if current_item is not None:
            self.list_widget.setCurrentItem(current_item)
            self.list_widget.scrollToItem(current_item)
        elif self.list_widget.count() > 0:
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                if not item.isHidden() and item != self._empty_item:
                    self.list_widget.setCurrentRow(i)
                    break

    def _select_current_item(self) -> None:
        current_item = self.list_widget.currentItem()
        if current_item is None:
            return
        self._emit_selection(current_item)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        self._emit_selection(item)

    def _emit_selection(self, item: QListWidgetItem) -> None:
        agent_id = item.data(Qt.ItemDataRole.UserRole)
        if agent_id is None:
            return
        self.agent_selected.emit(agent_id)
        self.close()

    def _apply_theme_style(self) -> None:
        is_dark = isDarkTheme()
        bg_color = "rgba(24, 26, 31, 246)" if is_dark else "rgba(255, 255, 255, 246)"
        border_color = "rgba(80, 88, 100, 168)" if is_dark else "rgba(191, 198, 210, 188)"
        panel_color = "rgba(34, 38, 46, 224)" if is_dark else "rgba(247, 249, 252, 255)"
        text_color = "#f5f7fa" if is_dark else "#1f2329"
        secondary_text_color = "#c5ccd6" if is_dark else "#5f6b7a"
        hover_bg = "rgba(255, 255, 255, 0.05)" if is_dark else "rgba(31, 35, 41, 0.035)"
        selected_bg = "rgba(45, 140, 255, 0.18)" if is_dark else "rgba(45, 140, 255, 0.10)"

        self.setStyleSheet(
            f"""
            QFrame#agentPickerPopup {{
                background: transparent;
                border: none;
            }}
            QFrame#agentPickerPanel {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 12px;
            }}
            LineEdit {{
                background-color: {panel_color};
                border: 1px solid {border_color};
                border-radius: 6px;
                color: {text_color};
                padding: 0 12px;
                min-height: 34px;
            }}
            LineEdit:focus {{
                border: 1px solid rgba(82, 142, 248, 220);
            }}
            ListWidget {{
                background-color: {panel_color};
                border: 1px solid {border_color};
                border-radius: 8px;
                color: {text_color};
                outline: none;
            }}
            ListWidget::item {{
                margin: 2px 4px;
                border-radius: 8px;
            }}
            ListWidget::item:hover {{
                background: {hover_bg};
            }}
            ListWidget::item:selected {{
                background: {selected_bg};
            }}
            QWidget#agentOptionItem {{
                background: transparent;
            }}
            BodyLabel {{
                color: {text_color};
                background: transparent;
            }}
            CaptionLabel {{
                color: {secondary_text_color};
                background: transparent;
            }}
            """
        )
        self.title_label.setStyleSheet(f"color: {text_color};")

    def _apply_shadow(self) -> None:
        shadow = QGraphicsDropShadowEffect(self.panel)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 90))
        self.panel.setGraphicsEffect(shadow)

    @classmethod
    def show_popup(
        cls,
        target: QWidget,
        current_agent_id: str,
        on_agent_selected: Callable[[str], None] | None = None,
        parent: QWidget | None = None,
    ) -> AgentPickerPopup:
        if cls._current_popup is not None:
            try:
                cls._current_popup.close()
            except RuntimeError:
                pass
            cls._current_popup = None

        popup = AgentPickerPopup(current_agent_id, parent)
        if on_agent_selected is not None:
            popup.agent_selected.connect(on_agent_selected)
        popup.destroyed.connect(lambda: setattr(cls, "_current_popup", None))

        cls._current_popup = popup
        popup.adjustSize()
        popup_width = max(popup.width(), 348)
        popup.resize(popup_width, popup.height())

        from PySide6.QtWidgets import QApplication

        global_pos = target.mapToGlobal(QPoint(0, target.height() + 6))
        screen = QApplication.screenAt(global_pos)
        if screen is not None:
            screen_rect = screen.availableGeometry()
            if global_pos.y() + popup.height() > screen_rect.bottom():
                global_pos = target.mapToGlobal(QPoint(0, -popup.height() - 6))

        popup.move(global_pos)
        popup.show()
        return popup
