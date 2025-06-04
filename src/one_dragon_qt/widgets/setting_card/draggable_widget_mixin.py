from abc import abstractmethod
from PySide6.QtCore import Signal, QPoint, Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QWidget


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
        
        # 安装事件过滤器
        self.installEventFilter(self)

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
        """定时器回调函数，在拖拽状态下定期发送拖拽完成事件"""
        if self._is_dragging:
            # 获取当前鼠标位置并发送拖拽完成事件
            global_cursor_pos = QCursor.pos()
            parent_pos = self.parent().mapFromGlobal(global_cursor_pos)
            self.drag_finished.emit(self.get_drag_id(), parent_pos.x(), parent_pos.y())
            self.drag_started.emit(self.get_drag_id())

    def eventFilter(self, obj, event):
        """处理拖拽的鼠标事件"""
        if obj == self:
            if event.type() == event.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._drag_start_pos = event.pos()
                    return True
            elif event.type() == event.Type.MouseMove:
                if (event.buttons() & Qt.MouseButton.LeftButton and 
                    not self._is_dragging):
                    # 检查是否超过拖拽阈值
                    if ((event.pos() - self._drag_start_pos).manhattanLength() > 
                        self._drag_threshold):
                        self._is_dragging = True
                        self.setCursor(Qt.CursorShape.ClosedHandCursor)
                        self.drag_started.emit(self.get_drag_id())
                        # 设置拖拽样式
                        self._set_dragging_style(True)
                        # 启动定时器
                        self._drag_timer.start()
                
                if self._is_dragging:
                    # 转换为全局坐标
                    global_pos = self.mapToGlobal(event.pos())
                    parent_pos = self.parent().mapFromGlobal(global_pos)
                    self.drag_moved.emit(self.get_drag_id(), parent_pos.x(), parent_pos.y())
                    return True
            elif event.type() == event.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.LeftButton and self._is_dragging:
                    # 停止定时器
                    self._drag_timer.stop()
                    # 转换为全局坐标
                    global_pos = self.mapToGlobal(event.pos())
                    parent_pos = self.parent().mapFromGlobal(global_pos)
                    self.drag_finished.emit(self.get_drag_id(), parent_pos.x(), parent_pos.y())
                    self._is_dragging = False
                    self.setCursor(Qt.CursorShape.OpenHandCursor)
                    # 恢复原有样式
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
