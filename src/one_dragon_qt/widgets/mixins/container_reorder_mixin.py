from typing import Callable, List, Optional

import time
from PySide6.QtCore import Qt, QPoint, QEvent, QTimer, QPropertyAnimation
from PySide6.QtGui import QCursor, QPixmap
from PySide6.QtWidgets import QWidget, QFrame, QLabel, QGraphicsOpacityEffect, QGraphicsDropShadowEffect

class ReorderDragOptions:
    def __init__(self,
                 preview_enabled: bool = True,
                 preview_scale: float = 1.0,
                 preview_opacity: float = 1.0,
                 shadow_blur: int = 18,
                 shadow_offset: tuple[int, int] = (0, 6),
                 insert_line_color: str = "#0078d4",
                 placeholder_css: str = "border: 2px dashed #0078d4; background-color: rgba(0,120,212,0.06); border-radius: 6px;",
                 auto_scroll_margin: int = 64,
                 auto_scroll_base: int = 8,
                 auto_scroll_max: int = 28,
                 handle_left_width: Optional[int] = 24,
                 hide_original_on_drag: bool = True,
                 highlight_duration_ms: int = 600,
                 highlight_css: str = "background-color: rgba(0, 120, 212, 0.20); border-radius: 6px;",
                 preview_anchor_mode: str = "grab",  # grab | left | center
                 anchor_left_padding: int = 8
                 ):
        self.preview_enabled = preview_enabled
        self.preview_scale = preview_scale
        self.preview_opacity = preview_opacity
        self.shadow_blur = shadow_blur
        self.shadow_offset = shadow_offset
        self.insert_line_color = insert_line_color
        self.placeholder_css = placeholder_css
        self.auto_scroll_margin = auto_scroll_margin
        self.auto_scroll_base = auto_scroll_base
        self.auto_scroll_max = auto_scroll_max
        self.handle_left_width = handle_left_width
        self.hide_original_on_drag = hide_original_on_drag
        self.highlight_duration_ms = highlight_duration_ms
        self.highlight_css = highlight_css
        self.preview_anchor_mode = preview_anchor_mode
        self.anchor_left_padding = anchor_left_padding


class ContainerReorderMixin:
    """
    将拖拽重排能力以 Mixin 的方式混入 QWidget 子类。

    用法：
      class MyInterface(ContainerReorderMixin, QWidget):
          def __init__(self, ...):
              QWidget.__init__(self, ...)
              self.init_reorder_drag()
              self.attach(container=..., scroll_area=..., get_items=..., get_item_id=..., on_reorder=...)
    """

    def init_reorder_drag(self) -> None:
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
        # 防抖机制 - 添加最后按下时间来防止重复事件
        self._last_press_time: float = 0.0
        self._press_debounce_ms: int = 200
        self._drag_cooldown_ms: int = 500

        # 性能优化：移动事件节流
        self._last_move_time: float = 0.0
        self._move_throttle_ms: int = 16

        # 缓存机制
        self._cached_items: Optional[List[QWidget]] = None
        self._cached_items_time: float = 0.0
        self._cache_valid_duration_ms: int = 50

        # 上次位置缓存，避免重复更新
        self._last_preview_pos: Optional[tuple[int, int]] = None
        self._last_drop_y: Optional[int] = None

        # 预览/指示
        self._float_container: Optional[QFrame] = None
        self._float_label: Optional[QLabel] = None
        self._insert_line: Optional[QFrame] = None
        self._placeholder: Optional[QWidget] = None  # overlay 占位
        self._dragging_widget: Optional[QWidget] = None
        self._original_index: int = -1
        self._drag_anchor_in_card_x: Optional[int] = None

        # 自动滚动（以宿主 QWidget 为父对象）
        self._auto_scroll_timer: QTimer = QTimer(self)
        self._auto_scroll_timer.setInterval(33)
        self._auto_scroll_timer.timeout.connect(self._on_auto_scroll_tick)
        self._auto_scroll_dir: int = 0
        self._auto_scroll_step: int = 0

        # 事件源
        self._watchers: list[QWidget] = []

        # 光标管理
        self._cursor_widget: Optional[QWidget] = None
        self._cursor_state: Optional[Qt.CursorShape] = None

    def _reset_drag_state(self) -> None:
        """完全重置拖拽状态，用于清理可能残留的状态"""
        self._dragging_id = None
        self._container_drag_active = False
        self._container_drag_started = False
        self._drag_anchor_in_card_x = None
        self._auto_scroll_dir = 0
        self._auto_scroll_step = 0
        self._dragging_widget = None
        self._original_index = -1

        # 设置冷却时间
        current_time = time.time() * 1000
        self._last_press_time = current_time
        self._last_move_time = 0.0

        # 清理缓存
        self._cached_items = None
        self._cached_items_time = 0.0
        self._last_preview_pos = None
        self._last_drop_y = None

        # 停止自动滚动定时器
        if self._auto_scroll_timer.isActive():
            self._auto_scroll_timer.stop()

        # 隐藏和清理预览控件
        if self._float_container is not None:
            self._float_container.hide()
            if self._float_label is not None:
                self._float_label.clear()

        # 隐藏拖放指示器
        self._hide_drop_indicator()

    def attach(self,
               container: QWidget,
               scroll_area,
               get_items: Callable[[], List[QWidget]],
               get_item_id: Callable[[QWidget], str],
               on_reorder: Callable[[str, int], None],
               get_drop_parent: Optional[Callable[[], QWidget]] = None,
               get_drag_handle: Optional[Callable[[QWidget], Optional[QWidget]]] = None,
               options: Optional[ReorderDragOptions] = None) -> None:
        self._container = container
        self._scroll_area = scroll_area
        self._get_items = get_items
        self._get_item_id = get_item_id
        self._on_reorder = on_reorder
        self._get_drop_parent = get_drop_parent
        self._get_drag_handle = get_drag_handle
        if options is not None:
            self._opt = options

        self._install_watchers()
        # 光标目标优先使用 viewport，其次容器
        self._cursor_widget = self._scroll_area.viewport() if (self._scroll_area is not None and self._scroll_area.viewport() is not None) else self._container

    # ---------------- internal -----------------

    def _get_cached_items(self) -> List[QWidget]:
        """获取缓存的items列表，减少重复计算"""
        current_time = time.time() * 1000

        # 检查缓存是否有效
        if (self._cached_items is not None and
            current_time - self._cached_items_time < self._cache_valid_duration_ms):
            return self._cached_items

        # 重新获取并缓存
        if self._get_items is not None:
            self._cached_items = self._get_items() or []
            self._cached_items_time = current_time
            return self._cached_items

        return []

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
            # 早期重复事件检测，在eventFilter级别就阻止
            current_time = time.time() * 1000
            time_since_last = current_time - self._last_press_time
            if self._container_drag_active or time_since_last < self._press_debounce_ms:
                return True  # 阻止事件传播

            self._on_press(obj, event)
            return False
        elif et == QEvent.Type.MouseMove:
            if self._container_drag_active:
                self._on_move(obj, event)
                return True
            # 未进入拖拽，更新 hover 光标
            self._on_hover(obj, event)
            return False
        elif et == QEvent.Type.MouseButtonRelease:
            if self._container_drag_active:
                self._on_release(obj, event)
                return True
            else:
                # 确保状态清理，防止状态残留
                self._reset_drag_state()
                return False
        elif et == QEvent.Type.Leave:
            # 移出时恢复默认光标
            self._apply_cursor(None)
            return False
        return super().eventFilter(obj, event)

    def _on_press(self, obj: QWidget, event) -> None:
        current_time = time.time() * 1000

        # 防抖检查 - 如果距离上次按下时间太短，忽略此次事件
        time_since_last_press = current_time - self._last_press_time
        if time_since_last_press < self._press_debounce_ms:
            return

        # 检查是否在冷却期内（重置后的额外保护）
        if self._container_drag_active and time_since_last_press < self._drag_cooldown_ms:
            return

        self._last_press_time = current_time
        # 如果当前正在拖拽，立即重置状态并退出，不允许继续处理
        if self._container_drag_active:
            self._reset_drag_state()
            return

        if self._get_items is None or self._get_item_id is None:
            return
        global_pos = obj.mapToGlobal(event.pos())
        container_pos = self._container.mapFromGlobal(global_pos)
        items = self._get_cached_items()
        hit_idx = -1
        for idx, w in enumerate(items):
            if w.geometry().contains(container_pos):
                hit_idx = idx
                break
        if hit_idx == -1:
            return
        if self._opt.handle_left_width is not None or self._get_drag_handle is not None:
            card = items[hit_idx]
            item_pos = card.mapFromGlobal(global_pos)
            allowed = True
            if self._get_drag_handle is not None:
                handle = self._get_drag_handle(card)
                if handle is not None:
                    allowed = handle.geometry().contains(item_pos)
            if allowed and self._opt.handle_left_width is not None:
                allowed = item_pos.x() <= max(0, self._opt.handle_left_width)
            if not allowed:
                return
        self._container_drag_active = True
        self._container_drag_started = False
        self._container_drag_start_pos = container_pos
        drag_item_id = self._get_item_id(items[hit_idx])
        self._dragging_id = drag_item_id
        # 开启自动滚动
        self._auto_scroll_dir = 0
        self._auto_scroll_timer.start()

    def _on_move(self, obj: QWidget, event) -> None:
        if not self._container_drag_active:
            return

        current_time = time.time() * 1000

        # 性能优化：移动事件节流，避免过于频繁的UI更新
        if current_time - self._last_move_time < self._move_throttle_ms:
            return
        self._last_move_time = current_time

        global_pos = obj.mapToGlobal(event.pos())
        container_pos = self._container.mapFromGlobal(global_pos)
        drop_parent = self._get_drop_parent() if self._get_drop_parent else self._container
        parent_pos = drop_parent.mapFromGlobal(global_pos)

        if not self._container_drag_started:
            if (container_pos - self._container_drag_start_pos).manhattanLength() > self._container_drag_threshold:
                self._container_drag_started = True
                if self._dragging_id:
                    self._start_preview()
                    self._apply_cursor(Qt.CursorShape.ClosedHandCursor)
        if self._container_drag_started and self._dragging_id:
            # 性能优化：只在位置真正变化时才更新预览
            current_preview_pos = (parent_pos.x(), parent_pos.y())
            if self._last_preview_pos != current_preview_pos:
                self._move_preview(parent_pos.x(), parent_pos.y())
                self._last_preview_pos = current_preview_pos

            # 性能优化：只在Y位置变化时才更新拖放指示器
            if self._last_drop_y != parent_pos.y():
                self._show_drop_indicator(parent_pos.y())
                self._last_drop_y = parent_pos.y()

            self._update_auto_scroll(container_pos.y())

    def _on_hover(self, obj: QWidget, event) -> None:
        if self._get_items is None:
            return
        global_pos = obj.mapToGlobal(event.pos())
        container_pos = self._container.mapFromGlobal(global_pos)
        items = self._get_cached_items()
        # 仅在把手区域显示抓手光标
        hit = False
        for w in items:
            if w.geometry().contains(container_pos):
                if self._opt.handle_left_width is None and self._get_drag_handle is None:
                    hit = True
                else:
                    item_pos = w.mapFromGlobal(global_pos)
                    allowed = True
                    if self._get_drag_handle is not None:
                        handle = self._get_drag_handle(w)
                        if handle is not None:
                            allowed = handle.geometry().contains(item_pos)
                    if allowed and self._opt.handle_left_width is not None:
                        allowed = item_pos.x() <= max(0, self._opt.handle_left_width)
                    hit = allowed
                break
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
        # 记录被拖拽控件与原始位置
        self._dragging_widget = card
        self._original_index = next((i for i, w in enumerate(items) if w is card), -1)
        # 拖拽时隐藏原卡片（可选）
        if self._opt.hide_original_on_drag:
            card.setVisible(False)
        # 计算锚点
        grab_x = None
        if self._opt.preview_anchor_mode == "grab":
            global_pos = QCursor.pos()
            local = card.mapFromGlobal(global_pos)
            grab_x = max(0, min(local.x(), card.width()))
        elif self._opt.preview_anchor_mode == "left":
            grab_x = self._opt.anchor_left_padding
        elif self._opt.preview_anchor_mode == "center":
            grab_x = card.width() // 2
        self._drag_anchor_in_card_x = grab_x

        if not self._opt.preview_enabled:
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
            self._float_container.setStyleSheet("QFrame { border: none; background: transparent; }")
            shadow = QGraphicsDropShadowEffect(self._float_container)
            shadow.setBlurRadius(self._opt.shadow_blur)
            shadow.setOffset(*self._opt.shadow_offset)
            self._float_container.setGraphicsEffect(shadow)
            self._float_label = QLabel(self._float_container)
            self._float_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            opacity = QGraphicsOpacityEffect(self._float_label)
            opacity.setOpacity(self._opt.preview_opacity)
            self._float_label.setGraphicsEffect(opacity)
        else:
            # 清理之前的预览内容，防止内存泄漏
            if self._float_label is not None:
                self._float_label.clear()
            # 确保父对象正确
            self._float_container.setParent(drop_parent)

        self._float_label.setPixmap(pm)
        self._float_label.resize(pm.size())
        self._float_container.resize(self._float_label.size())
        self._float_container.show()
        self._float_container.raise_()

    def _move_preview(self, x: int, y: int) -> None:
        if self._float_container is not None and self._float_container.isVisible():
            # 根据锚点决定水平对齐，保证拖动时显示的是卡片的左侧或抓取处
            if self._drag_anchor_in_card_x is None:
                dx = self._float_container.width() // 2
            else:
                dx = max(0, min(self._drag_anchor_in_card_x, self._float_container.width()))
            self._float_container.move(int(x - dx), int(y - self._float_container.height() / 2))

    def _show_drop_indicator(self, y: int) -> None:
        # 性能优化：使用缓存并减少重复计算
        all_items = self._get_cached_items()
        items = [w for w in all_items if self._get_item_id(w) != self._dragging_id]
        if not items:
            return
        drop_parent = self._get_drop_parent() if self._get_drop_parent else self._container
        if drop_parent is None:
            return
        idx = self._calculate_drop_position(y)
        if idx is None:
            return
        if self._insert_line is not None:
            self._insert_line.hide()

        if self._placeholder is None:
            self._placeholder = QWidget(drop_parent)
            self._placeholder.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self._placeholder.setStyleSheet(f"QWidget {{ {self._opt.placeholder_css} }}")
        # 目标项矩形（插入到 idx 位置之前）
        # 支持 idx == len(items) 表示插入到末尾
        if 0 <= idx < len(items):
            base_rect = items[idx].geometry()
            ph = max(24, base_rect.height())
            py = base_rect.y()
        else:
            last_rect = items[-1].geometry()
            ph = max(24, last_rect.height())
            py = last_rect.y() + last_rect.height()
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
        # 基于“移除被拖项后的列表”计算目标插入索引
        items_all = self._get_cached_items()
        items = [w for w in items_all if self._get_item_id(w) != self._dragging_id]
        if not items:
            return 0
        for idx, w in enumerate(items):
            rect = w.geometry()
            mid = rect.y() + rect.height() // 2
            if y < mid:
                return idx
        # 放到末尾（append）
        return len(items)

    def _end_drag(self) -> None:
        self._hide_drop_indicator()
        # 清理浮动预览控件
        if self._float_container is not None:
            self._float_container.hide()
            if self._float_label is not None:
                self._float_label.clear()
        # 停止自动滚动并重置相关状态
        self._auto_scroll_timer.stop()
        self._auto_scroll_dir = 0
        self._auto_scroll_step = 0
        # 保存拖拽ID用于后续处理
        dragging_id = self._dragging_id
        # 重置所有拖拽状态
        self._dragging_id = None
        self._container_drag_active = False
        self._container_drag_started = False
        self._drag_anchor_in_card_x = None
        # 结束后根据当前 hover 状态更新光标
        global_pos = QCursor.pos()
        if self._container is not None and self._cursor_widget is not None:
            container_pos = self._container.mapFromGlobal(global_pos)
            items = self._get_cached_items()
            hit = any((w.geometry().contains(container_pos) for w in items))
            self._apply_cursor(Qt.CursorShape.OpenHandCursor if hit else None)

        # 恢复原卡片可见
        items = self._get_cached_items()
        card = self._dragging_widget or next((w for w in items if self._get_item_id(w) == dragging_id), None)
        if card is not None:
            card.setVisible(True)
        # 高亮效果
        if dragging_id is not None and self._opt.highlight_duration_ms > 0:
            from PySide6.QtCore import QTimer as _QTimer
            def _highlight():
                items2 = self._get_cached_items()
                target = next((w for w in items2 if self._get_item_id(w) == dragging_id), None)
                if target is None:
                    return
                overlay = QFrame(target)
                overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                overlay.setStyleSheet(f"QFrame {{ {self._opt.highlight_css} }}")
                overlay.setGeometry(0, 0, target.width(), target.height())
                overlay.raise_()
                overlay.show()
                effect = QGraphicsOpacityEffect(overlay)
                overlay.setGraphicsEffect(effect)
                effect.setOpacity(1.0)
                anim = QPropertyAnimation(effect, b"opacity", overlay)
                anim.setDuration(self._opt.highlight_duration_ms)
                anim.setStartValue(1.0)
                anim.setEndValue(0.0)
                def _cleanup():
                    overlay.deleteLater()
                anim.finished.connect(_cleanup)
                # 保持引用防止被 GC
                overlay._anim = anim
                anim.start()
            _QTimer.singleShot(0, _highlight)
        # 重置拖拽控件引用
        self._dragging_widget = None
        self._original_index = -1

    def _apply_cursor(self, shape: Optional[Qt.CursorShape]) -> None:
        """光标抓手"""
        target = self._cursor_widget
        if target is None:
            return
        if shape is None:
            if self._cursor_state is not None:
                target.unsetCursor()
                self._cursor_state = None
            return
        if self._cursor_state == shape:
            return
