from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
                               QTableWidgetItem, QPushButton, QHeaderView, QAbstractItemView, QLabel)
from qfluentwidgets import FluentIcon, PushButton

from zzz_od.application.world_patrol.world_patrol_area import WorldPatrolLargeMapIcon


class IconEditorDialog(QDialog):
    """图标编辑器对话框"""
    
    icon_selected = Signal(int)  # 发送选中的图标索引
    icons_saved = Signal(list)   # 发送保存的图标列表
    
    def __init__(self, icon_list: list[WorldPatrolLargeMapIcon], parent=None):
        super().__init__(parent)
        self.original_icon_list = icon_list
        self.current_icon_list = []
        self.selected_row = -1
        
        self.setWindowTitle('图标编辑器')
        self.setModal(False)  # 非模态对话框，允许与主窗口交互
        self.resize(700, 500)

        # 设置窗口图标
        self.setWindowIcon(FluentIcon.EDIT.icon())
        
        self._init_ui()
        self._load_data()
        
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 创建表格
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(['图标名称', '模板ID', 'X坐标', 'Y坐标', '传送X', '传送Y'])
        
        # 设置表格属性
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        
        # 设置列宽
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # 图标名称列可拉伸
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        
        # 连接选择信号
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        
        layout.addWidget(self.table)

        # 状态标签
        self.status_label = QLabel('提示：点击表格行可在主窗口地图上高亮对应图标位置；选中行后可设置传送坐标')
        self.status_label.setStyleSheet("color: #666; font-size: 12px; padding: 5px;")
        layout.addWidget(self.status_label)

        # 按钮布局
        button_layout = QHBoxLayout()

        self.set_tp_pos_btn = PushButton('设置传送坐标', self)
        self.set_tp_pos_btn.setIcon(FluentIcon.GLOBE)
        self.set_tp_pos_btn.setToolTip('将主窗口当前计算坐标设置为选中图标的传送坐标')
        self.set_tp_pos_btn.clicked.connect(self._on_set_tp_pos_clicked)
        self.set_tp_pos_btn.setEnabled(False)  # 初始状态禁用

        self.save_btn = PushButton('保存', self)
        self.save_btn.setIcon(FluentIcon.SAVE)
        self.save_btn.setToolTip('保存图标名称修改')
        self.save_btn.clicked.connect(self._on_save_clicked)

        self.cancel_btn = PushButton('取消', self)
        self.cancel_btn.setIcon(FluentIcon.CANCEL)
        self.cancel_btn.setToolTip('取消修改并关闭')
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)

        button_layout.addWidget(self.set_tp_pos_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
    def _load_data(self):
        """加载数据到表格"""
        # 深拷贝图标列表
        self.current_icon_list = [
            WorldPatrolLargeMapIcon(
                icon_name=icon.icon_name,
                template_id=icon.template_id,
                lm_pos=[icon.lm_pos.x, icon.lm_pos.y],
                tp_pos=[icon.tp_pos.x, icon.tp_pos.y] if icon.tp_pos else None,
            )
            for icon in self.original_icon_list
        ]
        
        self.table.setRowCount(len(self.current_icon_list))
        
        for row, icon in enumerate(self.current_icon_list):
            # 图标名称 - 可编辑
            name_item = QTableWidgetItem(icon.icon_name)
            name_item.setFlags(name_item.flags() | Qt.ItemIsEditable)
            self.table.setItem(row, 0, name_item)
            
            # 模板ID - 只读
            template_item = QTableWidgetItem(icon.template_id)
            template_item.setFlags(template_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 1, template_item)
            
            # X坐标 - 只读
            x_item = QTableWidgetItem(str(icon.lm_pos.x))
            x_item.setFlags(x_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 2, x_item)
            
            # Y坐标 - 只读
            y_item = QTableWidgetItem(str(icon.lm_pos.y))
            y_item.setFlags(y_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 3, y_item)

            # 传送X坐标 - 只读
            tp_x_item = QTableWidgetItem(str(icon.tp_pos.x) if icon.tp_pos else '')
            tp_x_item.setFlags(tp_x_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 4, tp_x_item)

            # 传送Y坐标 - 只读
            tp_y_item = QTableWidgetItem(str(icon.tp_pos.y) if icon.tp_pos else '')
            tp_y_item.setFlags(tp_y_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 5, tp_y_item)
            
        # 连接数据变化信号
        self.table.itemChanged.connect(self._on_item_changed)
        
    def _on_selection_changed(self):
        """处理选择变化"""
        selected_items = self.table.selectedItems()
        if selected_items:
            self.selected_row = selected_items[0].row()
            self.set_tp_pos_btn.setEnabled(True)  # 有选中行时启用按钮
            self.icon_selected.emit(self.selected_row)
        else:
            self.selected_row = -1
            self.set_tp_pos_btn.setEnabled(False)  # 无选中行时禁用按钮
            
    def _on_item_changed(self, item):
        """处理项目变化"""
        if item.column() == 0:  # 只有图标名称可以编辑
            row = item.row()
            if 0 <= row < len(self.current_icon_list):
                self.current_icon_list[row].icon_name = item.text()
                
    def _on_save_clicked(self):
        """保存按钮点击"""
        self.icons_saved.emit(self.current_icon_list)
        self.accept()
        
    def _on_cancel_clicked(self):
        """取消按钮点击"""
        self.reject()

    def _on_set_tp_pos_clicked(self):
        """设置传送坐标按钮点击"""
        if self.selected_row >= 0:
            # 通过父窗口获取当前坐标
            if hasattr(self.parent(), 'get_current_calculated_pos'):
                pos = self.parent().get_current_calculated_pos()
                if pos is not None:
                    self.set_tp_pos_for_selected_icon(pos)
                else:
                    # 可以添加提示信息
                    print("当前没有可用的计算坐标")
            else:
                print("无法获取主窗口坐标")

    def set_tp_pos_for_selected_icon(self, pos):
        """为选中的图标设置传送坐标"""
        if 0 <= self.selected_row < len(self.current_icon_list):
            icon = self.current_icon_list[self.selected_row]
            icon.tp_pos = pos

            # 更新表格显示
            tp_x_item = QTableWidgetItem(str(pos.x))
            tp_y_item = QTableWidgetItem(str(pos.y))
            self.table.setItem(self.selected_row, 4, tp_x_item)
            self.table.setItem(self.selected_row, 5, tp_y_item)

            # 设置为只读
            tp_x_item.setFlags(tp_x_item.flags() & ~Qt.ItemIsEditable)
            tp_y_item.setFlags(tp_y_item.flags() & ~Qt.ItemIsEditable)

    def highlight_icon(self, row: int):
        """高亮指定行的图标"""
        if 0 <= row < self.table.rowCount():
            self.table.selectRow(row)
            self.table.scrollToItem(self.table.item(row, 0))
