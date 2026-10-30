from enum import Enum
from typing import Iterable, List, Optional, Union

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QShowEvent
from qfluentwidgets import FluentIconBase, ToolTip

from one_dragon.base.config.config_item import ConfigItem
from one_dragon_qt.services.styles_manager import OdQtStyleSheet
from one_dragon_qt.utils.layout_utils import IconSize, Margins
from one_dragon_qt.widgets.adapter_init_mixin import AdapterInitMixin
from one_dragon_qt.widgets.multi_selection_combo_box import MultiSelectionComboBox
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase


class MultiSelectionComboBoxSettingCard(SettingCardBase, AdapterInitMixin):
    """包含多选下拉框的自定义设置卡片类。

    高度与宽度特性：
    1. 高度自适应：
       - 默认状态（无选中）：高度固定为 50px，与其他 SettingCard 一致
       - 有选中项时：根据 combo_box 的高度自动调整，使用 setMinimumHeight
       - 移除父类的 setFixedHeight(50) 限制，改为 setMaximumHeight(16777215)

    2. Combo Box 宽度计算：
       - 自动计算 setting card 可用宽度
       - 可用宽度 = card总宽度 - 左边内容（图标+标题+间距） - 右边距
       - 设置 min_width=200（最小宽度）
       - 设置 max_width=可用宽度（最大宽度，不超过 setting card 宽度）

    3. 标签显示策略：
       - 初始显示 200px 宽度
       - 添加标签后，宽度从 200px 逐步增加到 max_width
       - 达到 max_width 后，标签自动换行，不会导致 setting card 变宽
    """

    value_changed = Signal(list)

    def __init__(self,
                 icon: Union[str, QIcon, FluentIconBase],
                 title: str,
                 content: Optional[str] = None,
                 icon_size: IconSize = IconSize(16, 16),
                 margins: Margins = Margins(16, 16, 0, 16),
                 options_enum: Optional[Iterable[Enum]] = None,
                 options_list: Optional[List[ConfigItem]] = None,
                 tooltip: Optional[str] = None,
                 parent=None
                 ):

        SettingCardBase.__init__(
            self,
            icon=icon,
            title=title,
            content=content,
            icon_size=icon_size,
            margins=margins,
            parent=parent
        )
        AdapterInitMixin.__init__(self)

        # 保存 margins 值用于后续计算
        self._margins = margins

        # 移除父类的固定高度限制，改为最小高度，支持自适应
        self.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX

        # 标记是否已经计算过 max_width
        self._max_width_calculated = False

        # 初始化多选下拉框（先使用默认宽度）
        self.combo_box = MultiSelectionComboBox(self, min_width=200)
        # 设置上下边距，使默认高度(32px)与其他card的50px一致
        # 上边距9px + combo_box高度32px + 下边距9px = 50px
        self.combo_box.setContentsMargins(0, 9, 0, 9)
        self.hBoxLayout.addWidget(self.combo_box, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

        # 处理工具提示
        self.tooltip_text: str = tooltip
        self._tooltip: Optional[ToolTip] = None
        if self.with_tooltip:
            self.titleLabel.installEventFilter(self)

        # 初始化选项
        self._opts_list: List[ConfigItem] = []
        self._initialize_options(options_enum, options_list)

        # 连接信号与槽
        self.combo_box.selection_changed.connect(self._on_selection_changed)

        # 监听 combo_box 的尺寸变化，更新卡片高度
        self.combo_box.installEventFilter(self)

        # 加载样式（需要在 combo_box 创建后加载）
        OdQtStyleSheet.MULTI_SELECTION_COMBO_BOX.apply(self.combo_box)

    def showEvent(self, event: QShowEvent) -> None:
        """组件显示时计算 combo_box 的最大宽度"""
        super().showEvent(event)

        # 只在第一次显示时计算
        if not self._max_width_calculated:
            self._max_width_calculated = True
            # 延迟一帧，确保布局完全完成
            QTimer.singleShot(0, self._update_combo_box_max_width)

    def _initialize_options(self, options_enum: Optional[Iterable[Enum]], options_list: Optional[List[ConfigItem]]) -> None:
        """从枚举或列表初始化多选下拉框选项。"""
        if options_enum:
            opts = []
            for opt in options_enum:
                if isinstance(opt.value, ConfigItem):
                    self._opts_list.append(opt.value)
                    opts.append(opt.value)
            self.combo_box.add_items(opts)
        elif options_list:
            self._opts_list = options_list.copy()
            self.combo_box.add_items(options_list)

    def eventFilter(self, obj, event: QEvent) -> bool:
        """处理标题标签的鼠标事件和下拉框的尺寸变化。"""
        # 处理工具提示
        if obj == self.titleLabel:
            if event.type() == QEvent.Type.Enter:
                self._show_tooltip()
            elif event.type() == QEvent.Type.Leave:
                self._hide_tooltip()

        # 处理 combo_box 尺寸变化，更新卡片高度
        if obj == self.combo_box and event.type() == QEvent.Type.Resize:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self._update_card_height)

        return super().eventFilter(obj, event)

    def _update_card_height(self) -> None:
        """更新卡片高度以适应 combo_box"""
        # 获取 combo_box 的总高度（包含 contentsMargins）
        combo_margins = self.combo_box.contentsMargins()
        dropdown_btn = self.combo_box._dropdown_btn
        dropdown_height = dropdown_btn.minimumHeight()
        combo_box_height = dropdown_height + combo_margins.top() + combo_margins.bottom()

        # 更新卡片的最小高度
        card_margins = self.contentsMargins()
        new_min_height = combo_box_height + card_margins.top() + card_margins.bottom()
        self.setMinimumHeight(new_min_height)

        # 强制更新几何信息
        self.updateGeometry()

    def _update_combo_box_max_width(self) -> None:
        """延迟计算并设置 combo_box 的最大宽度（等待布局完成后）"""
        # 获取 setting card 的总宽度
        card_width = self.width()

        # 计算左边内容占用的宽度
        left_content_width = 0

        # 图标宽度
        if hasattr(self, 'iconLabel'):
            left_content_width += self.iconLabel.width()

        # 图标后的间距
        left_content_width += self._margins.top  # margins.top 被用作图标后的间距

        # vBoxLayout 的宽度（包含标题和内容）
        # 使用 sizeHint() 获取更准确的宽度，因为 width() 有时返回0
        title_width = self.titleLabel.sizeHint().width()
        content_width = self.contentLabel.sizeHint().width() if self.contentLabel.isVisible() else 0
        vbox_width = max(title_width, content_width)
        left_content_width += vbox_width

        # vBoxLayout 后的间距
        left_content_width += self._margins.bottom  # margins.bottom 被用作 vBox 后的间距

        # 右边固定的 16px 间距
        right_spacing = 16

        # card 的左右边距
        card_margins = self.contentsMargins()

        # 计算可用宽度 = card总宽度 - 左边内容宽度 - 右边间距 - 左右边距
        available_width = card_width - left_content_width - right_spacing - card_margins.left() - card_margins.right()

        # 确保 available_width 至少为 200px
        available_width = max(200, available_width)

        # 更新 combo_box 的 _max_width 属性
        self.combo_box._max_width = available_width

        # 调用 setMaximumWidth 方法，使最大宽度生效
        self.combo_box.setMaximumWidth(available_width)

        # 如果已经有标签选中，触发布局更新以重新计算宽度
        if self.combo_box._selected_items:
            self.combo_box._dropdown_btn._update_grid_layout()

    @property
    def with_tooltip(self) -> bool:
        """是否有tooltip"""
        return self.tooltip_text is not None and len(self.tooltip_text) > 0

    def _show_tooltip(self) -> None:
        """显示工具提示。"""
        if self.with_tooltip:
            if self._tooltip:
                self._tooltip.close()
            self._tooltip = ToolTip(self.tooltip_text, self)
            self._tooltip.shadowEffect.setColor(QColor(0, 0, 0, 15))
            self._tooltip.shadowEffect.setOffset(0, 1)
            self._tooltip.setDuration(0)

            # 计算工具提示位置
            label_pos = self.titleLabel.mapToGlobal(self.titleLabel.rect().topLeft())
            x = label_pos.x() - 64
            y = label_pos.y() - self._tooltip.size().height() - 10
            self._tooltip.move(x, y)
            self._tooltip.show()

    def _hide_tooltip(self) -> None:
        """隐藏工具提示。"""
        if self._tooltip:
            self._tooltip.close()
            self._tooltip = None

    def set_options_by_list(self, options: List[ConfigItem]) -> None:
        """通过 ConfigItem 列表设置多选下拉框选项。"""
        self._opts_list = options.copy()
        self.combo_box.set_items(options)

    def _on_selection_changed(self, values: list) -> None:
        """选择变化时发射信号。"""
        self._update_desc()

        if self.adapter is not None:
            self.adapter.set_value(values)

        self.value_changed.emit(values)

        # 延迟更新卡片高度，确保 combo_box 的布局已经完成
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._update_card_height)

    def _update_desc(self) -> None:
        """更新描述显示。"""
        selected_items = self.combo_box.get_selected_items()
        if selected_items:
            # 获取第一个选中项的描述
            desc = selected_items[0].desc
            if len(selected_items) > 1:
                desc = f"已选 {len(selected_items)} 项"
            self.setContent(desc)
        else:
            self.setContent("未选择")

    def set_value(self, value: list, emit_signal: bool = True) -> None:
        """设置多选下拉框的值。"""
        self.combo_box.set_value(value, emit_signal=emit_signal)
        if not emit_signal:
            self._update_desc()

    def get_value(self) -> list:
        """获取当前选中的值列表。"""
        return self.combo_box.get_value()
