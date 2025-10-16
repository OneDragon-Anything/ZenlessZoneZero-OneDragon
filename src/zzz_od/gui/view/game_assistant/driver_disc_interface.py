from PySide6.QtWidgets import QWidget, QHeaderView, QTableWidgetItem
from qfluentwidgets import FluentIcon, PushButton, TableWidget

from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.row import Row
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from zzz_od.application.driver_disc_read import driver_disc_read_const
from zzz_od.context.zzz_context import ZContext


class DriverDiscInterface(AppRunInterface):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx

        AppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=driver_disc_read_const.APP_ID,
            object_name='driver_disc_interface',
            nav_text_cn='驱动盘识别',
            parent=parent,
        )

    def get_widget_at_top(self) -> QWidget:
        content = Column()

        # 帮助卡片
        self.help_opt = HelpCard(
            title='驱动盘识别',
            content='自动识别驱动盘属性并导出'
        )
        content.add_widget(self.help_opt)

        # 表格区域
        table_row = Row()
        
        # 创建表格
        self.disc_table = TableWidget()
        self.disc_table.setMinimumHeight(300)
        
        # 启用边框和圆角
        self.disc_table.setBorderVisible(True)
        self.disc_table.setBorderRadius(8)
        
        # 设置表头
        headers = ['驱动盘名称', '套装', '主属性', '副属性1', '副属性2', '副属性3', '副属性4']
        self.disc_table.setColumnCount(len(headers))
        self.disc_table.setHorizontalHeaderLabels(headers)
        
        # 设置表格属性
        self.disc_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.disc_table.setEditTriggers(TableWidget.EditTrigger.NoEditTriggers)  # 只读
        self.disc_table.setWordWrap(False)
        
        # 添加一些占位数据
        placeholder_data = [
            ['占位数据1', '套装A', '攻击力', '暴击率 5%', '暴击伤害 10%', '属性伤害 8%', '攻击力 5%'],
            ['占位数据2', '套装B', '生命值', '防御力 5%', '生命值 10%', '能量恢复 8%', '防御力 5%'],
            ['占位数据3', '套装C', '防御力', '生命值 5%', '防御力 10%', '效果命中 8%', '生命值 5%'],
        ]
        self.disc_table.setRowCount(len(placeholder_data))
        for i, row_data in enumerate(placeholder_data):
            for j, cell_data in enumerate(row_data):
                self.disc_table.setItem(i, j, QTableWidgetItem(cell_data))
        
        table_row.add_widget(self.disc_table, stretch=1)
        content.add_widget(table_row)

        # 导出按钮行
        button_row = Row()
        
        self.export_btn = PushButton(
            text='导出数据',
            icon=FluentIcon.SAVE
        )
        self.export_btn.clicked.connect(self._on_export_clicked)
        button_row.add_widget(self.export_btn)
        button_row.add_stretch(1)
        
        content.add_widget(button_row)

        return content

    def _on_export_clicked(self) -> None:
        """导出按钮点击事件"""
        # TODO: 实现导出逻辑
        pass

    def on_interface_shown(self) -> None:
        AppRunInterface.on_interface_shown(self)
        # TODO: 加载驱动盘数据
