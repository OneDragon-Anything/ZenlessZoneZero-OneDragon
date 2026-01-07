from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontMetrics, QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    Action,
    BodyLabel,
    CaptionLabel,
    CheckableMenu,
    FluentIcon,
    FlowLayout,
    MenuAnimationType,
    TransparentToolButton,
)

from one_dragon.base.config.config_item import ConfigItem
from one_dragon_qt.services.styles_manager import OdQtStyleSheet
from one_dragon_qt.widgets.adapter_init_mixin import AdapterInitMixin

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


class FluentTagLabel(QFrame):
    """Fluent 风格标签控件，显示选中的项，带关闭按钮"""

    close_clicked = Signal(object)  # 当关闭按钮被点击时发出信号，传递 value

    def __init__(self, text: str, value: object, parent=None) -> None:
        """初始化标签

        Args:
            text: 标签显示的文本
            value: 标签对应的值
            parent: 父组件
        """
        super().__init__(parent)
        self._text = text
        self._value = value
        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self) -> None:
        """设置UI"""
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setObjectName("fluentTag")

        # 设置尺寸策略：固定大小，不被压缩
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 6, 2)  # 调整边距，上下增加2px让按钮更居中
        layout.setSpacing(6)

        # 文本标签 - 使用 BodyLabel 自动继承主题样式
        text_label = BodyLabel(text=self._text)
        text_label.setObjectName("tagTextLabel")

        # 关闭按钮 - 使用 TransparentToolButton 自动继承主题样式
        close_btn = TransparentToolButton(FluentIcon.CLOSE, None)
        close_btn.setFixedSize(14, 14)  # 从 18x18 缩小到 14x14
        close_btn.setIconSize(close_btn.iconSize().scaled(10, 10, Qt.AspectRatioMode.KeepAspectRatio))  # 图标也缩小
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setObjectName("tagCloseButton")
        close_btn.clicked.connect(lambda: self.close_clicked.emit(self._value))

        layout.addWidget(text_label, 0, Qt.AlignmentFlag.AlignVCenter)  # 文本垂直居中
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignVCenter)  # 关闭按钮垂直居中

    def _apply_theme(self) -> None:
        """应用主题样式"""
        # 从 qss 文件加载样式，而不是使用内联样式表
        OdQtStyleSheet.MULTI_SELECTION_COMBO_BOX.apply(self)

    def get_text_width(self) -> int:
        """获取标签文本的实际宽度（使用 QFontMetrics 精确计算）

        注意：不使用 sizeHint() 的原因是，标签刚创建时样式表可能未完全应用，
        sizeHint() 会基于默认字体计算，导致宽度不准确。使用 QFontMetrics 直接计算
        可以确保在标签创建时立即获得准确的宽度。

        Returns:
            标签的总宽度（像素），包括边距、文本、间距和关闭按钮
        """
        # 创建与样式表一致的字体（12px, Segoe UI / Microsoft YaHei UI）
        font = QFont()
        font.setFamily("Segoe UI, Microsoft YaHei UI, sans-serif")
        font.setPointSize(12)

        # 使用 QFontMetrics 计算文本的实际渲染宽度
        font_metrics = QFontMetrics(font)
        text_width = font_metrics.horizontalAdvance(self._text)

        # 计算标签总宽度 = 左边距(8) + 文本宽度 + 文本与按钮间距(6) + 关闭按钮(14) + 右边距(4)
        total_width = 8 + text_width + 6 + 14 + 4

        return total_width


class FluentDropdownButton(QFrame):
    """Fluent 风格下拉按钮，内部显示标签（自动换行）"""

    clicked = Signal()  # 当按钮被点击时发出信号

    def __init__(self, placeholder_text: str = "请选择...", max_width: int = None, parent=None) -> None:
        """初始化下拉按钮

        Args:
            placeholder_text: 占位符文本
            max_width: 最大宽度限制，None 表示不限制
            parent: 父组件
        """
        super().__init__(parent)
        self._placeholder_text = placeholder_text
        self._max_width = max_width
        self._tags: list[FluentTagLabel] = []
        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self) -> None:
        """设置UI"""
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setObjectName("fluentDropdown")
        self.setMinimumHeight(32)  # Fluent 标准高度
        self.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)

        # 主容器（使用水平布局，左侧内容+右侧箭头）
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 0, 10, 0)
        main_layout.setSpacing(0)

        # 左侧内容容器
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 4, 0, 4)
        content_layout.setSpacing(2)

        # 占位符标签 - 使用 CaptionLabel 自动继承主题样式
        self._placeholder_label = CaptionLabel(text=self._placeholder_text)
        self._placeholder_label.setObjectName("placeholderLabel")
        content_layout.addWidget(self._placeholder_label)

        # 标签流式容器（使用 FlowLayout 实现自动换行）
        self._flow_widget = QWidget()
        self._flow_widget.setObjectName("flowWidget")
        self._flow_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred
        )
        self._flow_layout = FlowLayout(self._flow_widget)
        self._flow_layout.setContentsMargins(0, 0, 0, 0)
        self._flow_layout.setVerticalSpacing(4)
        self._flow_layout.setHorizontalSpacing(4)
        content_layout.addWidget(self._flow_widget, 1)
        self._flow_widget.hide()

        # 下拉箭头 - 使用 BodyLabel 自动继承主题样式
        # 使用更细长的 V 形箭头，符合 Fluent Design 标准
        self._arrow_label = BodyLabel(text="▾")
        self._arrow_label.setObjectName("arrowLabel")

        # 添加到主布局
        main_layout.addWidget(content_widget, 1)  # 内容占据剩余空间
        main_layout.addWidget(self._arrow_label)  # 箭头固定在右侧

    def _apply_theme(self) -> None:
        """应用主题样式"""
        # 从 qss 文件加载样式，而不是使用内联样式表
        OdQtStyleSheet.MULTI_SELECTION_COMBO_BOX.apply(self)

    def _update_grid_layout(self):
        """使用 FlowLayout 更新标签布局，并动态调整父组件宽度

        核心逻辑：
        1. 在添加标签到 FlowLayout 之前，先计算所有标签需要的总宽度
        2. 使用 get_text_width() 精确计算每个标签的宽度（不依赖 sizeHint()）
        3. 根据计算的宽度设置父组件的 minimumWidth
        4. 将标签添加到 FlowLayout，此时 FlowLayout 会按照正确的宽度进行布局

        这样可以避免标签提前换行的问题。
        """
        if not self._tags:
            return

        parent = self.parent()
        # 仅在动态宽度模式下调整宽度（非 fixed_width 模式）
        if parent and hasattr(parent, '_fixed_width') and parent._fixed_width is None:
            # 步骤1：计算所有标签需要的总宽度
            tag_spacing = 4  # FlowLayout 的水平间距
            total_width = 0

            for tag in self._tags:
                # 使用 get_text_width() 获取准确的标签宽度
                # 该方法使用 QFontMetrics 直接计算，不依赖 sizeHint()，避免样式表未应用导致的宽度偏差
                tag_width = tag.get_text_width()
                total_width += tag_width + tag_spacing

            # 减去最后一个标签的间距（不需要）
            if self._tags:
                total_width -= tag_spacing

            # 添加左右边距（10px + 10px）
            total_width += 20

            # 步骤2：确定宽度范围（在 min_width 到 max_width 之间）
            min_w = parent._min_width if parent._min_width is not None else 200
            max_w = parent._max_width if parent._max_width is not None else float('inf')

            # 计算需要的宽度：确保在 [min_w, max_w] 范围内
            needed_width = max(min_w, min(total_width, max_w))

            # 步骤3：在添加标签之前设置正确的宽度（关键步骤）
            # 这样 FlowLayout 会按照正确的宽度进行布局，避免提前换行
            parent.setMinimumWidth(int(needed_width))

        # 步骤4：清除 FlowLayout 中的所有现有元素
        while self._flow_layout.count():
            item = self._flow_layout.takeAt(0)
            if item is not None:
                item.setParent(None)

        # 步骤5：将所有标签添加到 FlowLayout
        # 此时组件已经有了正确的宽度，FlowLayout 会正确布局，不会提前换行
        for tag in self._tags:
            # 设置固定尺寸策略，防止标签被压缩
            tag.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            self._flow_layout.addWidget(tag)

    def mousePressEvent(self, event):
        """鼠标点击事件"""
        self.clicked.emit()
        super().mousePressEvent(event)

    def update_tags(self, tags: list[QWidget]) -> None:
        """更新显示的标签

        Args:
            tags: FluentTagLabel 对象列表
        """
        # 过滤出 FluentTagLabel 类型的标签
        self._tags = [tag for tag in tags if isinstance(tag, FluentTagLabel)]

        if not self._tags:
            # 无标签时显示占位符，隐藏 FlowLayout
            self._placeholder_label.show()
            self._flow_widget.hide()
            self._arrow_label.show()
            self.setMinimumHeight(32)
        else:
            # 有标签时隐藏占位符，显示 FlowLayout
            self._placeholder_label.hide()
            self._flow_widget.show()
            self._arrow_label.show()

            # 更新标签布局，并动态调整宽度
            self._update_grid_layout()


class MultiSelectionComboBox(QWidget, AdapterInitMixin):
    """支持多选的下拉框组件，集成 qfluentwidgets 主题系统

    样式文件：
        - 暗色主题：src/one_dragon_qt/_rc/qss/dark/multi_selection_combo_box.qss
        - 亮色主题：src/one_dragon_qt/_rc/qss/light/multi_selection_combo_box.qss

    宽度设置与标签显示策略：

    宽度设置与标签显示策略：
    1. fixed_width 模式：固定宽度，标签在固定宽度内自动换行
       - 适用场景：需要精确控制组件宽度的场合
       - 示例：fixed_width=400，组件始终保持 400px 宽度，标签多时自动换行

    2. max_width + min_width 模式：动态宽度，从最小宽度扩展到最大宽度
       - 适用场景：SettingCard 等需要自适应的场景
       - 初始显示 min_width（如 200px）
       - 添加标签后，宽度自动增加以容纳更多标签
       - 达到 max_width 后，开始换行
       - 示例：min_width=200, max_width=400，宽度从 200px 逐步增加到 400px，超过后换行

    3. 只有 min_width（无 max_width）：宽度无限制扩展
       - 适用场景：基础组件，需要自由扩展
       - 从 min_width 开始，宽度随标签数量无限增长
       - 示例：min_width=200, max_width=None，宽度从 200px 开始无限增加
    """

    selection_changed = Signal(list)  # 当选项改变时发出信号，传递选中的值列表

    def __init__(self, parent=None, max_width: int = None, fixed_width: int = None, min_width: int = None) -> None:
        """初始化多选下拉框

        Args:
            parent: 父组件
            max_width: FlowLayout 的最大宽度限制，None 表示不限制宽度，可自由扩展
            fixed_width: 固定宽度，如果设置则忽略 max_width，默认为 None
            min_width: 最小宽度，默认为 None（使用 fixed_width 的默认值 200）
        """
        QWidget.__init__(self, parent)
        AdapterInitMixin.__init__(self)

        self._items: list[ConfigItem] = []  # 所有 ConfigItem 列表
        self._selected_items: list[ConfigItem] = []  # 选中的 ConfigItem 列表
        self._placeholder_text: str = "请选择..."
        self._max_width = max_width
        self._fixed_width = fixed_width
        self._min_width = min_width if min_width is not None else (200 if fixed_width is None else None)
        self._menu = None  # 下拉菜单实例

        self._setup_ui()

        # 加载样式（StyleSheetBase 会自动监听主题变化并重新应用样式）
        self._apply_theme()

    def _setup_ui(self) -> None:
        """设置UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._dropdown_btn = FluentDropdownButton(self._placeholder_text, self._max_width)
        self._dropdown_btn.clicked.connect(self._toggle_dropdown_menu)

        layout.addWidget(self._dropdown_btn)

        # 设置宽度
        if self._fixed_width is not None:
            # 如果指定了固定宽度，使用固定宽度
            self.setFixedWidth(self._fixed_width)
        else:
            # 否则设置最小宽度
            if self._min_width is not None:
                self.setMinimumWidth(self._min_width)
            else:
                self.setMinimumWidth(200)

            self.setSizePolicy(
                QSizePolicy.Policy.Preferred,
                QSizePolicy.Policy.Preferred
            )

    def _apply_theme(self) -> None:
        """应用主题样式"""
        # 从 qss 文件加载样式
        OdQtStyleSheet.MULTI_SELECTION_COMBO_BOX.apply(self)

    def add_item(self, item: ConfigItem) -> None:
        """添加一个选项

        Args:
            item: ConfigItem 对象
        """
        if item not in self._items:
            self._items.append(item)

    def add_items(self, items: list[ConfigItem]) -> None:
        """批量添加选项

        Args:
            items: ConfigItem 对象列表
        """
        for item in items:
            if item not in self._items:
                self._items.append(item)

    def set_items(self, items: list[ConfigItem]) -> None:
        """设置选项列表（会清空现有选项）

        Args:
            items: ConfigItem 对象列表
        """
        self.clear_items()
        self.add_items(items)

    def clear_items(self) -> None:
        """清空所有选项"""
        self._items.clear()
        self.clear_selection()

    def clear_selection(self) -> None:
        """清空选中"""
        self._selected_items.clear()
        self._update_tags()

    def get_selected_items(self) -> list[ConfigItem]:
        """获取当前选中的 ConfigItem 对象列表"""
        return self._selected_items.copy()

    def set_value(self, value: list, emit_signal: bool = True) -> None:
        """设置选中的值

        Args:
            value: 选中的值列表（可以是显示文本列表或实际值列表，通过 ConfigItem.value 匹配）
            emit_signal: 是否发射信号
        """
        if not emit_signal:
            self.blockSignals(True)

        if value is None or len(value) == 0:
            self._selected_items = []
        else:
            # 通过 ConfigItem.value 匹配
            self._selected_items = []
            for item in self._items:
                if item.value in value:
                    self._selected_items.append(item)

        self._update_tags()

        if not emit_signal:
            self.blockSignals(False)

    def get_value(self) -> list:
        """获取选中的值列表（实际值，不是显示文本）

        Returns:
            选中的实际值列表
        """
        return [item.value for item in self._selected_items]

    def init_with_value(self, target_value: list = None) -> None:
        """根据目标值初始化，不抛出事件

        Args:
            target_value: 目标值列表
        """
        self.set_value(target_value, emit_signal=False)

    def set_placeholder_text(self, text: str) -> None:
        """设置占位符文本"""
        self._placeholder_text = text
        self._dropdown_btn._placeholder_label.setText(text)
        if not self._selected_items:
            self._dropdown_btn._placeholder_label.show()

    def setMinimumWidth(self, min_width: int) -> None:
        """设置最小宽度"""
        super().setMinimumWidth(min_width)
        self._dropdown_btn.setMinimumWidth(min_width)

    def setMaximumWidth(self, max_width: int) -> None:
        """设置最大宽度"""
        super().setMaximumWidth(max_width)
        self._dropdown_btn.setMaximumWidth(max_width)

    def setDynamicWidth(self, width: int) -> None:
        """动态设置宽度（同时设置最小和最大宽度）"""
        self.setMinimumWidth(width)
        self.setMaximumWidth(width)

    def setFixedWidth(self, width: int) -> None:
        """设置固定宽度"""
        super().setFixedWidth(width)
        self._dropdown_btn.setFixedWidth(width)
        self._dropdown_btn._update_grid_layout()

    def _toggle_dropdown_menu(self) -> None:
        """切换下拉菜单显示/隐藏"""
        # 如果菜单已显示，则隐藏它
        if self._menu is not None and self._menu.isVisible():
            self._menu.close()
            self._menu = None
        else:
            self._show_dropdown_menu()

    def _show_dropdown_menu(self) -> None:
        """显示下拉菜单"""
        # 使用 CheckableMenu，自动继承主题样式，支持多选
        self._menu = CheckableMenu(parent=self)

        # 为每个选项创建 Action
        for item in self._items:
            action = Action(text=item.ui_text, checkable=True)
            action.setChecked(item in self._selected_items)
            # 使用 lambda 捕获 item，避免闭包问题
            action.triggered.connect(lambda checked, i=item: self._on_item_triggered(i, checked))
            self._menu.addAction(action)

        # 显示菜单，使用 DROP_DOWN 动画
        button_rect = self._dropdown_btn.geometry()
        self._menu.exec(
            self._dropdown_btn.mapToGlobal(button_rect.bottomLeft()),
            aniType=MenuAnimationType.DROP_DOWN
        )

    def _on_item_triggered(self, item: ConfigItem, checked: bool) -> None:
        """当菜单项被点击时处理选中状态

        Args:
            item: 被点击的 ConfigItem 对象
            checked: 是否选中
        """
        if checked:
            if item not in self._selected_items:
                self._selected_items.append(item)
        else:
            if item in self._selected_items:
                self._selected_items.remove(item)

        # 更新标签显示
        self._update_tags()
        # 发射选中变化信号
        self.selection_changed.emit(self.get_value())

        # 通过 adapter 更新配置（如果存在）
        if self.adapter is not None:
            self.adapter.set_value(self.get_value())

    def _on_tag_close_clicked(self, value: object) -> None:
        """当标签关闭按钮被点击时移除对应项

        Args:
            value: 被关闭标签的 value 值
        """
        # 通过 value 查找并移除对应的 ConfigItem
        for item in self._selected_items:
            if item.value == value:
                self._selected_items.remove(item)
                # 更新标签显示
                self._update_tags()
                # 发射选中变化信号
                self.selection_changed.emit(self.get_value())

                # 通过 adapter 更新配置（如果存在）
                if self.adapter is not None:
                    self.adapter.set_value(self.get_value())
                break

    def _update_tags(self) -> None:
        """更新标签显示

        根据 _selected_items 创建 FluentTagLabel，并更新到 dropdown_btn 中。
        这个方法会在选中状态改变时被调用。
        """
        tags = []
        for item in self._selected_items:
            # 为每个选中项创建标签
            tag = FluentTagLabel(item.ui_text, item.value)
            # 连接标签的关闭信号
            tag.close_clicked.connect(self._on_tag_close_clicked)
            tags.append(tag)

        # 更新下拉按钮中的标签显示（会触发 _update_grid_layout）
        self._dropdown_btn.update_tags(tags)
