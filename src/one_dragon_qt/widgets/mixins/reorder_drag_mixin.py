from typing import Callable, List, Optional

from PySide6.QtCore import QObject, Qt, QPoint, QEvent, QTimer
from PySide6.QtGui import QCursor, QPixmap
from PySide6.QtWidgets import QWidget, QFrame, QLabel, QGraphicsOpacityEffect, QGraphicsDropShadowEffect


class ReorderDragOptions:
    def __init__(self,
                 preview_scale: float = 0.7,
                 preview_opacity: float = 0.75,
                 shadow_blur: int = 18,
                 shadow_offset: tuple[int, int] = (0, 6),
                 insert_line_color: str = "#0078d4",
                 placeholder_css: str = "border: 2px dashed #0078d4; background-color: rgba(0,120,212,0.06); border-radius: 6px;",
                 auto_scroll_margin: int = 64,
                 auto_scroll_base: int = 8,
                 auto_scroll_max: int = 28):
        self.preview_scale = preview_scale
        self.preview_opacity = preview_opacity
        self.shadow_blur = shadow_blur
        self.shadow_offset = shadow_offset
        self.insert_line_color = insert_line_color
        self.placeholder_css = placeholder_css
        self.auto_scroll_margin = auto_scroll_margin
        self.auto_scroll_base = auto_scroll_base
        self.auto_scroll_max = auto_scroll_max


class ReorderDragMixin(QObject):
    """容器级拖拽排序混入。使用方式：
    mixin = ReorderDragMixin(parent)
    mixin.attach(container=group_widget,
                 scroll_area=scroll_area,
                 get_items=lambda: items,
                 get_item_id=lambda w: w.app.app_id,
                 on_reorder=lambda item_id, idx: ...,
                 get_drop_parent=lambda: drop_parent,
                 options=ReorderDragOptions())
    """

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

        # 外部注入
        self._container: Optional[QWidget] = None
        self._scroll_area = None
        self._get_items: Optional[Callable[[], List[QWidget]]] = None
        self._get_item_id: Optional[Callable[[QWidget], str]] = None
        self._on_reorder: Optional[Callable[[str, int], None]] = None
        self._get_drop_parent: Optional[Callable[[], QWidget]] = None
        self._opt: ReorderDragOptions = ReorderDragOptions()

        # 拖拽状态
        self._dragging_id: Optional[str] = None
        self._container_drag_active: bool = False
        self._container_drag_started: bool = False
        self._container_drag_threshold: int = 10
        self._container_drag_start_pos: QPoint = QPoint()

        # 预览/指示
        self._float_container: Optional[QFrame] = None
        self._float_label: Optional[QLabel] = None
        self._insert_line: Optional[QFrame] = None
        self._placeholder: Optional[QWidget] = None

        # 自动滚动
        self._auto_scroll_timer: QTimer = QTimer(self)
        self._auto_scroll_timer.setInterval(16)
        self._auto_scroll_timer.timeout.connect(self._on_auto_scroll_tick)
        self._auto_scroll_dir: int = 0
        self._auto_scroll_step: int = 0

        # 事件源
        self._watchers: list[QWidget] = []

        # 光标管理
        self._cursor_widget: Optional[QWidget] = None
        self._cursor_state: Optional[Qt.CursorShape] = None

    def attach(self,
               container: QWidget,
               scroll_area,
               get_items: Callable[[], List[QWidget]],
               get_item_id: Callable[[QWidget], str],
               on_reorder: Callable[[str, int], None],
               get_drop_parent: Optional[Callable[[], QWidget]] = None,
               options: Optional[ReorderDragOptions] = None) -> None:
        self._container = container
        self._scroll_area = scroll_area
        self._get_items = get_items
        self._get_item_id = get_item_id
        self._on_reorder = on_reorder
        self._get_drop_parent = get_drop_parent
        if options is not None:
            self._opt = options

        self._install_watchers()
        # 光标目标优先使用 viewport，其次容器
        self._cursor_widget = self._scroll_area.viewport() if (self._scroll_area is not None and self._scroll_area.viewport() is not None) else self._container

    # ---------------- internal -----------------

    def _install_watchers(self) -> None:
        self._watchers.clear()
        if self._container is None:
            return
        self._watchers.append(self._container)
        if self._container.parentWidget() is not None:
            self._watchers.append(self._container.parentWidget())
        if self._scroll_area is not None and self._scroll_area.viewport() is not None:
            self._watchers.append(self._scroll_area.viewport())
        for w in self._watchers:
            w.installEventFilter(self)

    def eventFilter(self, obj, event):
        if not isinstance(obj, QWidget) or obj not in self._watchers:
            return super().eventFilter(obj, event)

        et = event.type()
        if et == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._on_press(obj, event)
            return False
        elif et == QEvent.Type.MouseMove:
            if self._container_drag_active:
                self._on_move(obj, event)
                return True
            # 未进入拖拽，更新 hover 光标
            self._on_hover(obj, event)
            return False
        elif et == QEvent.Type.MouseButtonRelease and self._container_drag_active:
            self._on_release(obj, event)
            return True
        elif et == QEvent.Type.Leave:
            # 移出时恢复默认光标
            self._apply_cursor(None)
            return False
        return super().eventFilter(obj, event)

    def _on_press(self, obj: QWidget, event) -> None:
        if self._get_items is None or self._get_item_id is None:
            return
        global_pos = obj.mapToGlobal(event.pos())
        container_pos = self._container.mapFromGlobal(global_pos)
        # 命中卡片
        items = self._get_items() or []
        hit_idx = -1
        for idx, w in enumerate(items):
            if w.geometry().contains(container_pos):
                hit_idx = idx
                break
        if hit_idx == -1:
            return
        self._container_drag_active = True
        self._container_drag_started = False
        self._container_drag_start_pos = container_pos
        self._dragging_id = self._get_item_id(items[hit_idx])
        # 开启自动滚动
        self._auto_scroll_dir = 0
        self._auto_scroll_timer.start()

    def _on_move(self, obj: QWidget, event) -> None:
        global_pos = obj.mapToGlobal(event.pos())
        container_pos = self._container.mapFromGlobal(global_pos)
        if not self._container_drag_started:
            if (container_pos - self._container_drag_start_pos).manhattanLength() > self._container_drag_threshold:
                self._container_drag_started = True
                if self._dragging_id:
                    self._start_preview()
                    self._apply_cursor(Qt.CursorShape.ClosedHandCursor)
        if self._container_drag_started and self._dragging_id:
            self._move_preview(container_pos.x(), container_pos.y())
            self._show_drop_indicator(container_pos.y())
            self._update_auto_scroll(container_pos.y())

    def _on_hover(self, obj: QWidget, event) -> None:
        if self._get_items is None:
            return
        global_pos = obj.mapToGlobal(event.pos())
        container_pos = self._container.mapFromGlobal(global_pos)
        items = self._get_items() or []
        hit = any((w.geometry().contains(container_pos) for w in items))
        self._apply_cursor(Qt.CursorShape.OpenHandCursor if hit else None)

    def _on_release(self, obj: QWidget, event) -> None:
        global_pos = obj.mapToGlobal(event.pos())
        drop_parent = self._get_drop_parent() if self._get_drop_parent else self._container
        parent_pos = drop_parent.mapFromGlobal(global_pos)
        if self._container_drag_started and self._dragging_id and self._on_reorder is not None:
            idx = self._calculate_drop_position(parent_pos.y())
            if idx is not None:
                self._on_reorder(self._dragging_id, idx)
        self._end_drag()

    def _start_preview(self) -> None:
        items = self._get_items() or []
        card = next((w for w in items if self._get_item_id(w) == self._dragging_id), None)
        if card is None:
            return
        pm: QPixmap = card.grab()
        scale = self._opt.preview_scale
        w = max(1, int(pm.width() * scale))
        h = max(1, int(pm.height() * scale))
        pm = pm.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        drop_parent = self._get_drop_parent() if self._get_drop_parent else self._container
        if drop_parent is None:
            return
        if self._float_container is None:
            self._float_container = QFrame(drop_parent)
            self._float_container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self._float_container.setStyleSheet("QFrame { border: 1px solid rgba(0,120,212,0.35); border-radius: 6px; background: transparent; }")
            shadow = QGraphicsDropShadowEffect(self._float_container)
            shadow.setBlurRadius(self._opt.shadow_blur)
            shadow.setOffset(*self._opt.shadow_offset)
            self._float_container.setGraphicsEffect(shadow)
            self._float_label = QLabel(self._float_container)
            self._float_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            opacity = QGraphicsOpacityEffect(self._float_label)
            opacity.setOpacity(self._opt.preview_opacity)
            self._float_label.setGraphicsEffect(opacity)
        self._float_label.setPixmap(pm)
        self._float_label.resize(pm.size())
        self._float_container.resize(self._float_label.size())
        self._float_container.show()
        self._float_container.raise_()

    def _move_preview(self, x: int, y: int) -> None:
        if self._float_container is not None and self._float_container.isVisible():
            self._float_container.move(int(x - self._float_container.width() / 2),
                                       int(y - self._float_container.height() / 2))

    def _show_drop_indicator(self, y: int) -> None:
        items = self._get_items() or []
        if not items:
            return
        drop_parent = self._get_drop_parent() if self._get_drop_parent else self._container
        if drop_parent is None:
            return
        idx = self._calculate_drop_position(y)
        if idx is None:
            return
        # 插入线
        if self._insert_line is None:
            self._insert_line = QFrame(drop_parent)
            self._insert_line.setFrameShape(QFrame.Shape.HLine)
            self._insert_line.setStyleSheet(f"QFrame {{ background-color: {self._opt.insert_line_color}; }}")
            self._insert_line.setFixedHeight(2)
        # 基于上一项底部
        if idx <= 0:
            line_y = items[0].geometry().y() - 1
        else:
            prev_rect = items[idx - 1].geometry()
            line_y = prev_rect.y() + prev_rect.height() + 1
        self._insert_line.setGeometry(0, line_y, drop_parent.width(), 2)
        self._insert_line.show()

        # 占位虚框
        if self._placeholder is None:
            self._placeholder = QWidget(drop_parent)
            self._placeholder.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self._placeholder.setStyleSheet(f"QWidget {{ {self._opt.placeholder_css} }}")
        target_rect = items[idx].geometry() if 0 <= idx < len(items) else items[-1].geometry()
        ph = max(24, target_rect.height())
        py = max(0, line_y - ph // 2)
        self._placeholder.setGeometry(6, py, drop_parent.width() - 12, ph)
        self._placeholder.show()
        self._placeholder.raise_()

    def _hide_drop_indicator(self) -> None:
        if self._insert_line is not None:
            self._insert_line.hide()
        if self._placeholder is not None:
            self._placeholder.hide()

    def _update_auto_scroll(self, y: int) -> None:
        if self._scroll_area is None:
            return
        # 使用 container 顶部/底部判断
        top = self._container.y()
        bottom = top + self._container.height()
        margin = self._opt.auto_scroll_margin
        base = self._opt.auto_scroll_base
        max_step = self._opt.auto_scroll_max
        if y < top + margin:
            self._auto_scroll_dir = -1
            dist = max(1, (y - top))
            factor = max(0.0, min(1.0, 1.0 - dist / margin))
            self._auto_scroll_step = int(base + (max_step - base) * factor)
        elif y > bottom - margin:
            self._auto_scroll_dir = 1
            dist = max(1, (bottom - y))
            factor = max(0.0, min(1.0, 1.0 - dist / margin))
            self._auto_scroll_step = int(base + (max_step - base) * factor)
        else:
            self._auto_scroll_dir = 0
            self._auto_scroll_step = 0

    def _on_auto_scroll_tick(self) -> None:
        if self._scroll_area is None or self._auto_scroll_dir == 0 or self._auto_scroll_step <= 0:
            return
        bar = self._scroll_area.verticalScrollBar()
        bar.setValue(bar.value() + self._auto_scroll_dir * self._auto_scroll_step)
        # 让浮动预览跟随鼠标（避免滚动时错位）
        if self._float_container is not None and self._float_container.isVisible():
            global_pos = QCursor.pos()
            drop_parent = self._get_drop_parent() if self._get_drop_parent else self._container
            if drop_parent is not None:
                parent_pos = drop_parent.mapFromGlobal(global_pos)
                self._float_container.move(int(parent_pos.x() - self._float_container.width() / 2),
                                           int(parent_pos.y() - self._float_container.height() / 2))

    def _calculate_drop_position(self, y: int) -> Optional[int]:
        items = self._get_items() or []
        if not items:
            return None
        for idx, w in enumerate(items):
            rect = w.geometry()
            mid = rect.y() + rect.height() // 2
            if y < mid:
                return idx
        return len(items) - 1

    def _end_drag(self) -> None:
        self._hide_drop_indicator()
        if self._float_container is not None:
            self._float_container.hide()
        self._auto_scroll_timer.stop()
        self._auto_scroll_dir = 0
        self._dragging_id = None
        # 结束后根据当前 hover 状态更新光标
        try:
            global_pos = QCursor.pos()
            if self._container is not None and self._cursor_widget is not None:
                container_pos = self._container.mapFromGlobal(global_pos)
                items = self._get_items() or []
                hit = any((w.geometry().contains(container_pos) for w in items))
                self._apply_cursor(Qt.CursorShape.OpenHandCursor if hit else None)
        except Exception:
            self._apply_cursor(None)

    # 光标抓手
    def _apply_cursor(self, shape: Optional[Qt.CursorShape]) -> None:
        target = self._cursor_widget
        if target is None:
            return
        if shape is None:
            if self._cursor_state is not None:
                try:
                    target.unsetCursor()
                except Exception:
                    pass
                self._cursor_state = None
            return
        if self._cursor_state == shape:
            return
        try:
            target.setCursor(shape)
            self._cursor_state = shape
        except Exception:
            pass
