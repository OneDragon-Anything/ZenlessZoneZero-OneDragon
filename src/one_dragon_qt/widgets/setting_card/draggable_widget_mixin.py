from abc import abstractmethod
from typing import List
from PySide6.QtCore import Signal, QPoint, Qt, QTimer, QEvent
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QWidget
from one_dragon.utils.log_utils import log


class DraggableWidgetMixin:
    """拖拽功能混入类，提供通用的拖拽能力"""

    # 拖拽相关信号
    drag_started = Signal(str)
    drag_moved = Signal(str, int, int)
    drag_finished = Signal(str, int, int)

    def __init__(self, *args, **kwargs):

        # 拖拽相关属性
        self._is_dragging: bool = False
        self._drag_start_pos = QPoint()
        self._drag_threshold: int = 10
        self._original_style: str = ""
        self._drag_monitored_widgets: List[QWidget] = []
        self._drag_parent_watchers: List[QWidget] = []

        # 拖拽定时器
        self._drag_timer = QTimer()
        self._drag_timer.timeout.connect(self._on_drag_timer_timeout)
        self._drag_timer.setInterval(100)

    def init_draggable(self) -> None:
        """初始化拖拽功能"""
        # 保存初始样式
        self._original_style = self.styleSheet()

        # 设置提示文本和光标
        self.setToolTip('按住拖拽以调整顺序')
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        # 安装事件过滤器：自身 + 所有子控件
        self._drag_monitored_widgets = [self]
        try:
            self._drag_monitored_widgets.extend(self.findChildren(QWidget))
        except Exception:
            pass
        for w in self._drag_monitored_widgets:
            w.installEventFilter(self)
        log.debug(f"[Drag] init_draggable: installed filters on {len(self._drag_monitored_widgets)} widgets for {self.objectName() or type(self).__name__}")

    def attach_parent_event_filters(self) -> None:
        """将事件过滤器安装到父级链上，解决父级/遮罩控件拦截鼠标事件的问题"""
        # 清理旧的
        for w in self._drag_parent_watchers:
            try:
                w.removeEventFilter(self)
            except Exception:
                pass
        self._drag_parent_watchers.clear()

        p = self.parentWidget()
        steps = 0
        while p is not None and steps < 4:
            p.installEventFilter(self)
            self._drag_parent_watchers.append(p)
            steps += 1
            p = p.parentWidget()
        log.debug(f"[Drag] attach_parent_event_filters: watchers={len(self._drag_parent_watchers)} for {self.objectName() or type(self).__name__}")

    @abstractmethod
    def get_drag_id(self) -> str:
        """获取拖拽项的唯一标识符"""
        pass

    def _set_dragging_style(self, is_dragging: bool) -> None:
        """设置拖拽状态的样式"""
        if is_dragging:
            # 添加拖拽样式，保留原有样式
            drag_style = """
                QFrame {
                    background-color: rgba(0, 120, 212, 0.1);
                    border: 2px dashed #0078d4;
                    border-radius: 6px;
                }
            """
            self.setStyleSheet(self._original_style + drag_style)
        else:
            # 恢复原有样式
            self.setStyleSheet(self._original_style)
            # 强制刷新显示
            self.update_display()

    def _on_drag_timer_timeout(self) -> None:
        """定时器回调函数：在拖拽状态下，周期性触发 drag_moved，便于外部做吸附/滚动等效果"""
        if self._is_dragging:
            global_cursor_pos = QCursor.pos()
            parent_pos = self.parent().mapFromGlobal(global_cursor_pos)
            self.drag_moved.emit(self.get_drag_id(), parent_pos.x(), parent_pos.y())
            log.debug(f"[Drag] timer moved: id={self.get_drag_id()} x={parent_pos.x()} y={parent_pos.y()}")

    def eventFilter(self, obj, event):
        """处理拖拽的鼠标事件"""
        if isinstance(obj, QWidget) and (obj in self._drag_monitored_widgets or obj in self._drag_parent_watchers):
            et = event.type()
            if et == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    # 记录起点（转换为自身坐标）。若来自父级，则需判断是否点击在自身区域内
                    global_pos = obj.mapToGlobal(event.pos())
                    local_pos = self.mapFromGlobal(global_pos)
                    if obj in self._drag_parent_watchers and not self.rect().contains(local_pos):
                        return False
                    self._drag_start_pos = local_pos
                    log.debug(f"[Drag] press on {type(obj).__name__}: startPos={self._drag_start_pos}")
                    return False
            elif et == QEvent.Type.MouseMove:
                if (event.buttons() & Qt.MouseButton.LeftButton and not self._is_dragging):
                    # 检查是否超过拖拽阈值（统一到自身坐标系比较）
                    global_pos = obj.mapToGlobal(event.pos())
                    local_pos = self.mapFromGlobal(global_pos)
                    if obj in self._drag_parent_watchers and not self.rect().contains(local_pos):
                        return False
                    if (local_pos - self._drag_start_pos).manhattanLength() > self._drag_threshold:
                        self._is_dragging = True
                        self.setCursor(Qt.CursorShape.ClosedHandCursor)
                        self.drag_started.emit(self.get_drag_id())
                        self._set_dragging_style(True)
                        self._drag_timer.start()
                        log.debug(f"[Drag] started: id={self.get_drag_id()} start={self._drag_start_pos} now={local_pos}")

                if self._is_dragging:
                    # 将位置转换到父级坐标后发射
                    global_pos = obj.mapToGlobal(event.pos())
                    parent_pos = self.parent().mapFromGlobal(global_pos)
                    self.drag_moved.emit(self.get_drag_id(), parent_pos.x(), parent_pos.y())
                    log.debug(f"[Drag] moved: id={self.get_drag_id()} x={parent_pos.x()} y={parent_pos.y()}")
                    return True
            elif et == QEvent.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.LeftButton and self._is_dragging:
                    self._drag_timer.stop()
                    global_pos = obj.mapToGlobal(event.pos())
                    parent_pos = self.parent().mapFromGlobal(global_pos)
                    self.drag_finished.emit(self.get_drag_id(), parent_pos.x(), parent_pos.y())
                    log.debug(f"[Drag] finished: id={self.get_drag_id()} x={parent_pos.x()} y={parent_pos.y()}")
                    self._is_dragging = False
                    self.setCursor(Qt.CursorShape.OpenHandCursor)
                    self._set_dragging_style(False)
                    return True

        return super().eventFilter(obj, event)

    def is_dragging(self) -> bool:
        """返回当前是否正在拖拽"""
        return self._is_dragging

    @abstractmethod
    def update_display(self) -> None:
        """更新显示，由子类实现"""
        pass
