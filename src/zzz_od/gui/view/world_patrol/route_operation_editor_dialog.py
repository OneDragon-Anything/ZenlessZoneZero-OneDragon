from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                               QTableWidgetItem, QPushButton, QHeaderView, 
                               QComboBox, QLineEdit, QSpinBox, QMessageBox)
from qfluentwidgets import FluentIcon

from zzz_od.application.world_patrol.world_patrol_route import WorldPatrolOperation, WorldPatrolOpType


class RouteOperationEditorDialog(QDialog):
    """路线操作编辑器对话框"""
    
    operations_updated = Signal(list)  # 发送更新后的操作列表
    
    def __init__(self, op_list: list[WorldPatrolOperation], parent=None):
        super().__init__(parent)
        self.original_op_list = op_list
        self.current_op_list = []
        
        self.setWindowTitle('编辑路线操作')
        self.setModal(True)  # 模态对话框
        self.resize(800, 600)
        
        # 设置窗口图标
        self.setWindowIcon(FluentIcon.EDIT.icon())
        
        self._init_ui()
        self._load_data()
        
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 创建表格
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['序号', '操作类型', '数据1', '数据2'])
        
        # 设置表格列宽
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 80)
        self.table.setColumnWidth(1, 120)
        
        layout.addWidget(self.table)
        
        # 操作按钮行
        button_layout = QHBoxLayout()
        
        self.add_btn = QPushButton('添加操作')
        self.add_btn.clicked.connect(self._on_add_clicked)
        button_layout.addWidget(self.add_btn)
        
        self.delete_btn = QPushButton('删除选中')
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        button_layout.addWidget(self.delete_btn)
        
        self.move_up_btn = QPushButton('上移')
        self.move_up_btn.clicked.connect(self._on_move_up_clicked)
        button_layout.addWidget(self.move_up_btn)
        
        self.move_down_btn = QPushButton('下移')
        self.move_down_btn.clicked.connect(self._on_move_down_clicked)
        button_layout.addWidget(self.move_down_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # 确认/取消按钮
        confirm_layout = QHBoxLayout()
        confirm_layout.addStretch()
        
        self.save_btn = QPushButton('保存')
        self.save_btn.clicked.connect(self._on_save_clicked)
        confirm_layout.addWidget(self.save_btn)
        
        self.cancel_btn = QPushButton('取消')
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        confirm_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(confirm_layout)
        
    def _load_data(self):
        """加载数据到表格"""
        # 深拷贝原始数据
        self.current_op_list = []
        for op in self.original_op_list:
            new_op = WorldPatrolOperation(op.op_type, op.data.copy())
            self.current_op_list.append(new_op)
        
        self._refresh_table()
        
    def _refresh_table(self):
        """刷新表格显示"""
        self.table.setRowCount(len(self.current_op_list))
        
        for i, op in enumerate(self.current_op_list):
            # 序号（只读）
            index_item = QTableWidgetItem(str(i))
            index_item.setFlags(index_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 0, index_item)
            
            # 操作类型下拉框
            op_type_combo = QComboBox()
            op_type_combo.addItems([WorldPatrolOpType.MOVE])  # 目前只有MOVE类型
            op_type_combo.setCurrentText(op.op_type)
            op_type_combo.currentTextChanged.connect(lambda text, row=i: self._on_op_type_changed(row, text))
            self.table.setCellWidget(i, 1, op_type_combo)
            
            # 数据1（通常是x坐标）
            data1_item = QTableWidgetItem(op.data[0] if len(op.data) > 0 else '')
            self.table.setItem(i, 2, data1_item)
            
            # 数据2（通常是y坐标）
            data2_item = QTableWidgetItem(op.data[1] if len(op.data) > 1 else '')
            self.table.setItem(i, 3, data2_item)
        
        # 连接单元格变化事件
        self.table.itemChanged.connect(self._on_item_changed)
        
    def _on_op_type_changed(self, row: int, op_type: str):
        """操作类型变化"""
        if 0 <= row < len(self.current_op_list):
            self.current_op_list[row].op_type = op_type
            
    def _on_item_changed(self, item: QTableWidgetItem):
        """表格项变化"""
        row = item.row()
        col = item.column()
        
        if 0 <= row < len(self.current_op_list):
            if col == 2:  # 数据1
                if len(self.current_op_list[row].data) == 0:
                    self.current_op_list[row].data = ['', '']
                self.current_op_list[row].data[0] = item.text()
            elif col == 3:  # 数据2
                if len(self.current_op_list[row].data) < 2:
                    self.current_op_list[row].data = [
                        self.current_op_list[row].data[0] if len(self.current_op_list[row].data) > 0 else '',
                        ''
                    ]
                self.current_op_list[row].data[1] = item.text()
                
    def _on_add_clicked(self):
        """添加操作"""
        new_op = WorldPatrolOperation(WorldPatrolOpType.MOVE, ['0', '0'])
        self.current_op_list.append(new_op)
        self._refresh_table()
        
    def _on_delete_clicked(self):
        """删除选中的操作"""
        current_row = self.table.currentRow()
        if 0 <= current_row < len(self.current_op_list):
            reply = QMessageBox.question(self, '确认删除', 
                                       f'确定要删除第{current_row}个操作吗？',
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                del self.current_op_list[current_row]
                self._refresh_table()
                
    def _on_move_up_clicked(self):
        """上移操作"""
        current_row = self.table.currentRow()
        if current_row > 0:
            # 交换位置
            self.current_op_list[current_row], self.current_op_list[current_row - 1] = \
                self.current_op_list[current_row - 1], self.current_op_list[current_row]
            self._refresh_table()
            self.table.setCurrentCell(current_row - 1, 0)
            
    def _on_move_down_clicked(self):
        """下移操作"""
        current_row = self.table.currentRow()
        if 0 <= current_row < len(self.current_op_list) - 1:
            # 交换位置
            self.current_op_list[current_row], self.current_op_list[current_row + 1] = \
                self.current_op_list[current_row + 1], self.current_op_list[current_row]
            self._refresh_table()
            self.table.setCurrentCell(current_row + 1, 0)
            
    def _on_save_clicked(self):
        """保存按钮点击"""
        # 验证数据
        for i, op in enumerate(self.current_op_list):
            if len(op.data) < 2:
                QMessageBox.warning(self, '数据错误', f'第{i}个操作的数据不完整')
                return
            try:
                # 验证坐标是否为数字
                float(op.data[0])
                float(op.data[1])
            except ValueError:
                QMessageBox.warning(self, '数据错误', f'第{i}个操作的坐标数据必须是数字')
                return
        
        self.operations_updated.emit(self.current_op_list)
        self.accept()
        
    def _on_cancel_clicked(self):
        """取消按钮点击"""
        self.reject()
