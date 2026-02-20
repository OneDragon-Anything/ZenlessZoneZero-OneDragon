"""
可拖动列表组件

支持通过拖拽来交换列表中元素的位置。
符合 Microsoft Fluent Design 设计规范。

⚠️ 重要使用限制：
    本组件使用 QGraphicsOpacityEffect 实现拖拽时的透明度动画。
    不能在 MessageBoxBase、MaskDialogBase 等已使用 QGraphicsEffect 的对话框中使用。

    为什么有这个限制？
    -------------------
    QGraphicsEffect 会创建额外的离屏绘制层。当对话框容器已使用 QGraphicsDropShadowEffect
    或 QGraphicsOpacityEffect 时，子组件再使用 QGraphicsOpacityEffect 会产生嵌套的 Effect，
    导致 Qt 图形系统的坐标计算偏差，出现视觉位置与交互位置不一致的偏移问题。

    推荐用法：
    ---------
    - ✅ 在普通窗口（QMainWindow、QWidget）中使用：完美的透明度动画
    - ✅ 在 MessageBoxBase 中使用但不拖拽：正常显示，无偏移
    - ⚠️ 在 MessageBoxBase 中拖拽：可能出现位置偏移，但功能可用

    技术实现：
    ---------
    本组件采用延迟创建策略：不在 __init__ 中创建 QGraphicsOpacityEffect，
    只在首次调用 fade_out()/fade_in() 时才创建。这样在 MessageBoxBase 中
    初始显示不会偏移，只有拖拽时才可能偏移。
"""

from typing import Any, Optional

from PySide6.QtCore import (
    QEasingCurve,
    QMimeData,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QDrag, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import Theme, qconfig


# Fluent Design 常量
class FluentDesignConst:
    """Fluent Design 相关常量"""
    ACCENT_COLOR = "#0078d4"
    INDICATOR_HEIGHT = 3
    INDICATOR_OFFSET = 1  # 指示器偏移量
    DRAG_OPACITY = 0.3
    NORMAL_OPACITY = 1.0
    DRAG_PREVIEW_OPACITY = 0.9
    ANIMATION_DURATION = 150  # ms
    DRAG_THRESHOLD = 10  # pixels
    SHADOW_RADIUS = 8
    SHADOW_OFFSET = 2  # 阴影偏移
    LAYOUT_SPACING = 4
    ITEM_MARGIN = 8

    # 自动滚动相关常量
    SCROLL_MARGIN = 40  # 触发自动滚动的边缘距离（像素）
    SCROLL_STEP = 15  # 每次滚动的像素数
    SCROLL_INTERVAL = 30  # 自动滚动的时间间隔（毫秒）

    # 根据主题选择阴影颜色
    @staticmethod
    def get_shadow_color() -> QColor:
        """
        根据当前主题获取阴影颜色

        Fluent Design 规范：
        - 浅色主题：使用深色阴影（黑色）
        - 暗色主题：使用浅色阴影（白色）

        Returns:
            适合当前主题的阴影颜色
        """
        if qconfig.theme == Theme.DARK:
            # 暗色主题：白色阴影
            return QColor(255, 255, 255, 50)
        else:
            # 浅色主题：黑色阴影
            return QColor(0, 0, 0, 30)


class FluentDropIndicator(QFrame):
    """
    Fluent Design 风格的放置指示器

    显示为一条带有圆角的蓝色指示线，符合 Fluent Design 规范。
    """

    def __init__(self, parent=None):
        """
        初始化 Fluent Design 放置指示器

        Args:
            parent: 父组件
        """
        super().__init__(parent=parent)

        # Fluent Design 强调色
        self._accent_color = QColor(FluentDesignConst.ACCENT_COLOR)

        # 设置固定高度和样式
        self.setFixedHeight(FluentDesignConst.INDICATOR_HEIGHT)
        self.setAutoFillBackground(True)

        # 设置样式表
        self._update_stylesheet()

        # 初始隐藏
        self.hide()

    def _update_stylesheet(self):
        """更新 Fluent Design 样式"""
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {self._accent_color.name()};
                border: none;
                border-radius: 1px;
            }}
        """)


class DraggableListItem(QWidget):
    """
    可拖动的列表项

    每个列表项都是一个可拖动的组件，显示自定义内容。
    符合 Fluent Design 设计规范，具有平滑的动画和视觉反馈。

    ⚠️ 使用限制：
        不要在 MessageBoxBase、MaskDialogBase 等已使用 QGraphicsEffect 的对话框中
        触发拖拽操作，否则会导致视觉位置与交互位置不一致的偏移。
        如果只是在对话框中显示而不拖拽，则不会有问题。
    """

    def __init__(self, data: Any, index: int, content_widget: QWidget, parent=None,
                 enable_opacity_effect: bool = False):
        """
        初始化可拖动列表项

        Args:
            data: 列表项关联的数据
            index: 列表项的索引
            content_widget: 显示内容的组件
            parent: 父组件
            enable_opacity_effect: 是否启用透明度效果（默认 False）
                默认禁用，只有通过 DraggableList 添加时才会启用

        Note:
            默认值为 False，因为独立创建的 ListItem 不应该有拖拽动画。
            当通过 DraggableList.add_list_item() 添加时，会自动更新此设置。
        """
        QWidget.__init__(self, parent=parent)
        self.data = data
        self.index = index
        self.content_widget = content_widget
        self._is_hidden_for_drag = False  # 标记是否因为拖拽而隐藏
        self._enable_opacity_effect = enable_opacity_effect  # 是否启用透明效果

        # 延迟创建透明度效果（避免在 MessageBoxBase 等环境中导致初始偏移）
        # 只在需要动画时（fade_out/fade_in 被调用）才创建 effect
        self._opacity_effect: QGraphicsOpacityEffect | None = None
        self._opacity_animation: QPropertyAnimation | None = None

        # 初始化拖拽起始位置
        self._drag_start_position = QPoint()

        # 创建布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            FluentDesignConst.ITEM_MARGIN,
            FluentDesignConst.ITEM_MARGIN,
            FluentDesignConst.ITEM_MARGIN,
            FluentDesignConst.ITEM_MARGIN
        )
        layout.addWidget(self.content_widget)

    def update_item(self, data: Any, index: int) -> None:
        """
        更新列表项关联的数据和索引
        :param data: 关联的数据
        :param index: 列表项的索引
        """
        self.data = data
        self.index = index
        self.after_update_item()

    def after_update_item(self) -> None:
        """
        更新后的钩子函数，子类可以重写以实现特定逻辑
        """
        pass

    def _ensure_opacity_effect(self) -> None:
        """
        确保 QGraphicsOpacityEffect 已创建（延迟创建）

        只在需要动画时才创建，避免在 MessageBoxBase 等环境中导致初始偏移。
        首次调用 fade_out/fade_in 时会创建 effect。
        """
        if self._opacity_effect is None:
            self._opacity_effect = QGraphicsOpacityEffect(self)
            self._opacity_effect.setOpacity(FluentDesignConst.NORMAL_OPACITY)
            self.setGraphicsEffect(self._opacity_effect)

            # 创建动画对象并设置父对象（避免内存泄漏）
            self._opacity_animation = QPropertyAnimation(self._opacity_effect, b"opacity")
            self._opacity_animation.setParent(self)
            self._opacity_animation.setDuration(FluentDesignConst.ANIMATION_DURATION)
            self._opacity_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

    def fade_out(self):
        """淡出动画 - Fluent Design 透明度变化"""
        if not self._enable_opacity_effect:
            return  # 透明效果已禁用
        self._ensure_opacity_effect()
        if self._opacity_animation is None or self._opacity_effect is None:
            return
        self._opacity_animation.stop()
        current_opacity = self._opacity_effect.opacity()
        self._opacity_animation.setStartValue(current_opacity)
        self._opacity_animation.setEndValue(FluentDesignConst.DRAG_OPACITY)
        self._opacity_animation.start()

    def fade_in(self):
        """淡入动画 - Fluent Design 透明度变化"""
        if not self._enable_opacity_effect:
            return  # 透明效果已禁用
        self._ensure_opacity_effect()
        if self._opacity_animation is None or self._opacity_effect is None:
            return
        self._opacity_animation.stop()
        current_opacity = self._opacity_effect.opacity()
        self._opacity_animation.setStartValue(current_opacity)
        self._opacity_animation.setEndValue(FluentDesignConst.NORMAL_OPACITY)
        self._opacity_animation.start()

    def set_opacity(self, value: float):
        """
        直接设置透明度（不使用动画）

        Args:
            value: 透明度值 (0.0 - 1.0)
        """
        if not self._enable_opacity_effect:
            return  # 透明效果已禁用
        self._ensure_opacity_effect()
        if self._opacity_effect is None:
            return
        # 停止动画（如果有）
        if self._opacity_animation is not None:
            self._opacity_animation.stop()
        self._opacity_effect.setOpacity(value)

    def create_drag_pixmap(self) -> QPixmap:
        """
        创建符合 Fluent Design 的拖拽预览图

        Returns:
            带有半透明效果的拖拽预览图
        """
        # 获取当前快照
        pixmap = self.grab()

        # 创建结果 pixmap，继承原始 pixmap 的 devicePixelRatio 确保高 DPI 下不模糊
        result = QPixmap(pixmap.size())
        result.setDevicePixelRatio(pixmap.devicePixelRatio())
        result.fill(Qt.GlobalColor.transparent)

        painter = QPainter(result)

        # 直接绘制原始内容，应用半透明效果
        painter.setOpacity(FluentDesignConst.DRAG_PREVIEW_OPACITY)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()

        return result

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_position = event.pos()
            # 按下时显示手掌光标，表示可以拖拽
            self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 开始拖拽"""
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return

        # Fluent Design 规范：拖拽阈值
        if (event.pos() - self._drag_start_position).manhattanLength() < FluentDesignConst.DRAG_THRESHOLD:
            super().mouseMoveEvent(event)
            return

        # 创建拖拽对象
        drag = QDrag(self)
        mime_data = QMimeData()

        # 使用自定义 MIME 类型存储索引（更安全）
        mime_data.setData("application/x-draggablelist-index", str(self.index).encode())
        drag.setMimeData(mime_data)

        # 设置 Fluent Design 风格的拖拽预览
        drag.setPixmap(self.create_drag_pixmap())
        drag.setHotSpot(self._drag_start_position)

        # 执行拖拽
        drag.exec(Qt.DropAction.MoveAction)

        # 拖拽完成后恢复箭头光标
        self.setCursor(Qt.CursorShape.ArrowCursor)

        # 调用父类方法
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            # 释放时恢复箭头光标
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(event)

    def enterEvent(self, event):
        """鼠标进入事件"""
        # 不改变光标，保持箭头
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开事件"""
        # 离开时恢复箭头光标
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)


class DraggableList(QWidget):
    """
    可拖动元素的列表

    支持通过拖拽来交换列表中元素的位置。
    列表行的具体内容可以由使用者自行传入。
    符合 Microsoft Fluent Design 设计规范。

    Usage:
        # 创建列表
        drag_list = DraggableList()

        # 添加项目（传入数据和自定义内容组件）
        for i, item in enumerate(items):
            content_widget = QLabel(f"Item {item}")
            drag_list.add_item(item, content_widget)

        # 监听顺序变化
        drag_list.order_changed.connect(on_order_changed)

        # 获取当前顺序的数据列表
        current_data = drag_list.get_data_list()
    """

    # 顺序变化信号，参数为新的数据列表
    order_changed = Signal(list)

    def __init__(self, parent=None, enable_opacity_effect: bool = True):
        """
        初始化可拖动列表

        Args:
            parent: 父组件
            enable_opacity_effect: 是否启用拖拽透明度效果（默认 True）
                在 MessageBoxBase 等对话框中建议设为 False，避免位置偏移
                此设置会应用到所有列表项
        """
        QWidget.__init__(self, parent=parent)

        # 存储透明度效果设置
        self._enable_opacity_effect = enable_opacity_effect

        # 存储所有列表项
        self._items: list[DraggableListItem] = []

        # 创建主布局
        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(FluentDesignConst.LAYOUT_SPACING)
        self._layout.setContentsMargins(0, 0, 0, 0)

        # 创建 Fluent Design 风格的位置指示器
        self._drop_indicator = FluentDropIndicator(self)

        # 拖拽相关状态
        self._dragging_item: DraggableListItem | None = None

        # 自动滚动相关
        self._scroll_timer = QTimer(self)
        self._scroll_timer.timeout.connect(self._on_auto_scroll)
        self._scroll_direction = 0  # -1: 向上, 0: 不滚动, 1: 向下

        # 设置接受拖拽
        self.setAcceptDrops(True)

    def add_item(self, data: Any, content_widget: QWidget) -> None:
        """
        添加一个列表项

        Args:
            data: 列表项关联的数据
            content_widget: 显示内容的组件

        Note:
            透明度效果由 DraggableList 的 enable_opacity_effect 参数统一控制
        """
        index = len(self._items)
        item = DraggableListItem(data, index, content_widget, parent=self,
                                enable_opacity_effect=self._enable_opacity_effect)
        self._items.append(item)
        self._layout.addWidget(item)

    def add_list_item(self, item: DraggableListItem) -> None:
        """
        直接添加一个已存在的 DraggableListItem

        Args:
            item: 已存在的 DraggableListItem 实例

        Note:
            会将 item 的透明效果设置更新为与 DraggableList 一致
        """
        index = len(self._items)
        item.index = index
        item.setParent(self)
        # 更新 item 的透明效果设置以匹配当前 list
        item._enable_opacity_effect = self._enable_opacity_effect
        self._items.append(item)
        self._layout.addWidget(item)

    def insert_item(self, position: int, data: Any, content_widget: QWidget) -> None:
        """
        在指定位置插入一个列表项

        Args:
            position: 插入位置（索引）
            data: 列表项关联的数据
            content_widget: 显示内容的组件

        Raises:
            IndexError: 当位置超出范围时抛出

        Note:
            透明度效果由 DraggableList 的 enable_opacity_effect 参数统一控制
        """
        if position < 0 or position > len(self._items):
            raise IndexError(f"位置 {position} 超出范围")

        item = DraggableListItem(data, position, content_widget, parent=self,
                                enable_opacity_effect=self._enable_opacity_effect)
        self._items.insert(position, item)
        self._layout.insertWidget(position, item)

        # 更新后续项的索引
        self._update_indices()

    def remove_item(self, position: int) -> None:
        """
        移除指定位置的列表项

        Args:
            position: 要移除的位置（索引）

        Raises:
            IndexError: 当位置超出范围时抛出
        """
        if position < 0 or position >= len(self._items):
            raise IndexError(f"位置 {position} 超出范围")

        item = self._items.pop(position)
        self._layout.removeWidget(item)
        item.deleteLater()

        # 更新后续项的索引
        self._update_indices()

    def clear(self) -> None:
        """
        清空所有列表项

        同时重置拖拽状态和停止自动滚动。
        """
        # 停止自动滚动（如果有）
        self._scroll_direction = 0
        if self._scroll_timer.isActive():
            self._scroll_timer.stop()

        # 清空列表项
        for item in self._items:
            self._layout.removeWidget(item)
            item.deleteLater()
        self._items.clear()

        # 重置拖拽状态
        self._drop_indicator.hide()
        self._dragging_item = None

    def get_data_list(self) -> list[Any]:
        """
        获取当前顺序的数据列表

        Returns:
            按当前顺序排列的数据列表
        """
        return [item.data for item in self._items]

    def get_item_count(self) -> int:
        """
        获取列表项的数量

        Returns:
            列表项的数量
        """
        return len(self._items)

    def _update_indices(self) -> None:
        """更新所有列表项的索引"""
        for index, item in enumerate(self._items):
            item.index = index

    def _find_scroll_area_parent(self) -> Optional[QScrollArea]:
        """
        查找父级滚动区域

        Returns:
            找到的 QScrollArea 对象，如果找不到返回 None
        """
        parent = self.parent()
        while parent:
            # 检查是否有 viewport 属性（QScrollArea 的特征）
            if hasattr(parent, 'viewport') and hasattr(parent, 'verticalScrollBar'):
                return parent
            parent = parent.parent()
        return None

    def _handle_auto_scroll(self, pos: QPoint, scroll_area: QScrollArea) -> None:
        """
        处理自动滚动逻辑

        Args:
            pos: 鼠标在列表中的位置
            scroll_area: 滚动区域对象
        """
        # 获取滚动区域的视口高度
        viewport = scroll_area.viewport()
        viewport_height = viewport.height()

        # 将列表坐标映射到滚动区域视口坐标
        global_pos = self.mapToGlobal(pos)
        viewport_pos = viewport.mapFromGlobal(global_pos)

        # 判断是否接近边缘
        margin = FluentDesignConst.SCROLL_MARGIN

        if viewport_pos.y() < margin:
            # 接近顶部，向上滚动
            self._scroll_direction = -1
            if not self._scroll_timer.isActive():
                self._scroll_timer.start(FluentDesignConst.SCROLL_INTERVAL)
        elif viewport_pos.y() > viewport_height - margin:
            # 接近底部，向下滚动
            self._scroll_direction = 1
            if not self._scroll_timer.isActive():
                self._scroll_timer.start(FluentDesignConst.SCROLL_INTERVAL)
        else:
            # 不在边缘，停止滚动
            self._scroll_direction = 0
            if self._scroll_timer.isActive():
                self._scroll_timer.stop()

    def _on_auto_scroll(self) -> None:
        """
        自动滚动定时器回调

        执行实际的滚动操作
        """
        if self._scroll_direction == 0:
            return

        scroll_area = self._find_scroll_area_parent()
        if not scroll_area:
            self._scroll_timer.stop()
            return

        scroll_bar = scroll_area.verticalScrollBar()
        step = FluentDesignConst.SCROLL_STEP

        if self._scroll_direction == -1:
            # 向上滚动（检查边界）
            if scroll_bar.value() > 0:
                new_value = scroll_bar.value() - step
                scroll_bar.setValue(max(0, new_value))
            else:
                # 已经到顶部，停止滚动
                self._scroll_timer.stop()
        else:
            # 向下滚动（检查边界）
            if scroll_bar.value() < scroll_bar.maximum():
                new_value = scroll_bar.value() + step
                scroll_bar.setValue(min(scroll_bar.maximum(), new_value))
            else:
                # 已经到底部，停止滚动
                self._scroll_timer.stop()

    def _accept_drag_event(self, event) -> bool:
        """
        检查并接受拖拽事件

        Args:
            event: 拖拽事件

        Returns:
            是否接受该拖拽事件
        """
        # 检查是否包含我们自定义的 MIME 类型
        return event.mimeData().hasFormat("application/x-draggablelist-index")

    def dragEnterEvent(self, event):
        """
        拖拽进入事件

        保存被拖拽项的引用并淡出显示
        """
        if not self._accept_drag_event(event):
            return

        # 从自定义 MIME 类型读取索引
        data = event.mimeData().data("application/x-draggablelist-index")
        if data.isEmpty():
            return

        try:
            from_index = int(data.data().decode())
        except (ValueError, UnicodeDecodeError):
            return

        # 保存被拖拽项的引用（仅用于透明度恢复）
        if 0 <= from_index < len(self._items):
            self._dragging_item = self._items[from_index]
            self._dragging_item.fade_out()
            self._dragging_item._is_hidden_for_drag = True
        else:
            self._dragging_item = None

        event.acceptProposedAction()

    def dragMoveEvent(self, event):
        """
        拖拽移动事件

        更新位置指示器并处理自动滚动
        """
        if not self._accept_drag_event(event):
            return

        # 尝试查找并处理滚动区域
        scroll_area = self._find_scroll_area_parent()
        if scroll_area:
            self._handle_auto_scroll(event.pos(), scroll_area)

        # 找到放置位置
        to_index = self._find_drop_position(event.pos())

        # 更新位置指示器
        self._update_drop_indicator(to_index)

        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        """
        拖拽离开事件

        停止自动滚动并恢复状态

        Note:
            Qt 的 dragLeaveEvent 本身就意味着鼠标离开了组件区域。
            不需要额外检查位置（Qt6 的 event.position() 在此事件中是未定义行为）。
        """
        # 停止自动滚动
        self._scroll_direction = 0
        if self._scroll_timer.isActive():
            self._scroll_timer.stop()

        # 直接恢复状态（Qt 的 dragLeaveEvent 表示真正离开了）
        self._drop_indicator.hide()
        self._cleanup_drag_state()

        event.accept()

    def dropEvent(self, event):
        """
        拖拽放下事件 - 执行位置交换
        """
        # 停止自动滚动
        self._scroll_direction = 0
        if self._scroll_timer.isActive():
            self._scroll_timer.stop()

        if not self._accept_drag_event(event):
            self._cleanup_drag_state()
            return

        # 隐藏指示器
        self._drop_indicator.hide()

        # 使用保存的拖拽项引用来查找当前索引
        if self._dragging_item is None:
            event.acceptProposedAction()
            return

        # 在当前 _items 中找到被拖拽项的实际索引
        try:
            from_index = self._items.index(self._dragging_item)
        except ValueError:
            # 找不到项，清理状态
            self._cleanup_drag_state()
            event.acceptProposedAction()
            return

        # 找到放置位置
        to_index = self._find_drop_position(event.pos())

        if to_index == -1 or from_index == to_index:
            # 如果位置没有变化，只需要恢复显示
            self._cleanup_drag_state()
            event.acceptProposedAction()
            return

        # 执行真正的交换
        self._swap_items(from_index, to_index)

        # Fluent Design: 立即恢复被拖拽项的透明度
        if self._dragging_item:
            self._dragging_item.set_opacity(FluentDesignConst.NORMAL_OPACITY)

        # 清理拖拽状态
        self._cleanup_drag_state()

        event.acceptProposedAction()

    def _find_drop_position(self, pos: QPoint) -> int:
        """
        根据鼠标位置找到放置的索引位置

        Args:
            pos: 鼠标位置

        Returns:
            放置位置的索引
            - 空列表时返回 0（插入到开头/末尾）
            - 找不到合适位置时返回 -1
        """
        # 空列表：插入到开头（也是末尾）
        if not self._items:
            return 0

        for i, item in enumerate(self._items):
            if item.geometry().contains(pos):
                # 判断是在上半部分还是下半部分
                if pos.y() < item.geometry().center().y():
                    return i
                else:
                    return i + 1
        return -1

    def _get_indicator_y_position(self, index: int) -> int:
        """
        计算指示器的 Y 坐标

        Args:
            index: 目标索引

        Returns:
            指示器的 Y 坐标
        """
        if not self._items:
            return 0

        if index >= len(self._items):
            # 插入到末尾
            return self._items[-1].geometry().bottom()
        elif index == 0:
            # 插入到开头
            return self._items[0].geometry().top()
        else:
            # 插入到中间位置
            return self._items[index].geometry().top()

    def _swap_items(self, from_index: int, to_index: int) -> None:
        """
        交换两个列表项的位置

        Args:
            from_index: 源索引，必须是有效索引 [0, len(self._items)-1]
            to_index: 目标插入位置 [0, len(self._items)]
                      可以等于 len(self._items)，表示插入到末尾
        """
        # 边界检查
        if not (0 <= from_index < len(self._items)):
            return
        if not (0 <= to_index <= len(self._items)):
            return

        # 从列表中移除项
        item = self._items.pop(from_index)

        # 插入到新位置
        # 注意：如果 to_index > from_index，由于已经移除了一个元素，需要调整索引
        # to_index 可以等于 len(self._items)，表示插入到末尾
        adjusted_to_index = to_index - 1 if to_index > from_index else to_index
        self._items.insert(adjusted_to_index, item)

        # 重新构建布局
        self._rebuild_layout()

        # 更新索引
        self._update_indices()

        # 发出顺序变化信号
        self.order_changed.emit(self.get_data_list())

    def _rebuild_layout(self) -> None:
        """重新构建布局"""
        # 移除所有组件
        while self._layout.count():
            child = self._layout.takeAt(0)
            if child.widget():
                # 不删除，只是从布局中移除
                pass

        # 按新顺序添加组件
        for item in self._items:
            self._layout.addWidget(item)

    def _update_drop_indicator(self, index: int) -> None:
        """
        更新位置指示器的显示位置

        Args:
            index: 目标插入位置的索引
        """
        if index == -1:
            self._drop_indicator.hide()
            return

        # 显示指示器
        self._drop_indicator.show()
        self._drop_indicator.raise_()  # 确保在最上层

        # 计算指示器位置
        y = self._get_indicator_y_position(index)

        # 更新指示器位置和大小
        self._drop_indicator.setGeometry(
            0,
            y - FluentDesignConst.INDICATOR_OFFSET,
            self.width(),
            FluentDesignConst.INDICATOR_HEIGHT
        )

    def _restore_opacity_all(self) -> None:
        """恢复所有项的透明度"""
        for item in self._items:
            if item._is_hidden_for_drag:
                item.set_opacity(FluentDesignConst.NORMAL_OPACITY)
                item._is_hidden_for_drag = False

    def _cleanup_drag_state(self) -> None:
        """
        清理拖拽状态

        统一的状态清理逻辑，用于拖拽取消、失败或完成时。
        """
        self._restore_opacity_all()
        if self._dragging_item:
            self._dragging_item._is_hidden_for_drag = False
            self._dragging_item = None
