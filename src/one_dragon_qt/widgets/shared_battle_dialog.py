import glob
import os
import requests
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QSpacerItem,
    QSizePolicy,
    QTableWidgetItem,
)
from dataclasses import dataclass
from qfluentwidgets import FluentIcon, SimpleCardWidget, PushButton, ToolButton, LineEdit, Dialog, TableWidget
from qframelesswindow import FramelessDialog

from one_dragon.utils.i18_utils import gt
from one_dragon_qt.services.styles_manager import OdQtStyleSheet

BASE_URL = "http://116.205.232.21"
COLUMN_HEADERS = ["配置名称", "上传者", "上传时间"]
CONFIG_FOLDER = "config/auto_battle"


@dataclass
class BattleInfo:
    id: int
    battle_name: str
    battle_url: str
    creation_name: str
    creation_date: str


class SharedConfigDialog(FramelessDialog):
    def __init__(self, parent=None):
        """
        TODO 改造成资源下载
        @param parent:
        """
        FramelessDialog.__init__(self, parent)
        self.setWindowTitle(gt('共享配置'))
        self.resize(800, 600)

        self.init_ui()
        QTimer.singleShot(0, self.load_data_from_api)  # 延迟加载网络数据
        self.load_local_configs()  # 加载本地配置文件

    def init_ui(self):
        self.widget = SimpleCardWidget()
        layout = QVBoxLayout(self.widget)

        self.setLayout(layout)

        # 搜索栏布局
        search_layout = QHBoxLayout()
        self.search_bar = LineEdit()
        self.search_bar.setPlaceholderText(gt('输入关键字进行搜索...'))
        self.search_bar.textChanged.connect(self.filter_table)
        search_layout.addWidget(QLabel(f"{gt('搜索')}: "))
        search_layout.addWidget(self.search_bar)
        search_layout.addItem(
            QSpacerItem(40, 5, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        )
        layout.addLayout(search_layout)

        # 在线配置表格视图
        self.online_table_widget = TableWidget(self)
        self.online_table_widget.setColumnCount(3)
        self.online_table_widget.setHorizontalHeaderLabels(COLUMN_HEADERS)
        self.online_table_widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.online_table_widget.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        # 添加在线配置标签
        layout.addWidget(QLabel(gt('在线配置')))
        layout.addWidget(self.online_table_widget)

        # 本地配置表格视图
        self.local_table_widget = TableWidget(self)
        self.local_table_widget.setColumnCount(2)
        self.local_table_widget.setHorizontalHeaderLabels([gt('配置名称'), gt('操作')])
        self.local_table_widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.local_table_widget.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.local_table_widget.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Fixed
        )

        # 设置第二列宽度
        self.local_table_widget.setColumnWidth(1, 80)

        # 添加本地配置标签
        layout.addWidget(QLabel(gt('本地配置')))
        layout.addWidget(self.local_table_widget)

        # 底部按钮布局
        button_layout = QHBoxLayout()
        self.download_button = PushButton(text=gt('下载'))
        self.download_button.clicked.connect(self.on_download_clicked)
        self.cancel_button = PushButton(text=gt('取消'))
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.download_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        OdQtStyleSheet.SHARED_BATTLE_DIALOG.apply(self)

    def find_project_root(self, start_path, marker="src"):
        current_path = os.path.abspath(start_path)
        while True:
            if os.path.exists(os.path.join(current_path, marker)):
                return current_path
            if current_path == os.path.dirname(current_path):
                raise FileNotFoundError(f"无法找到包含 {marker} 的项目根目录")
            current_path = os.path.dirname(current_path)

    def save_downloaded_file(self, file_name, data, base_folder):
        save_path = os.path.join(base_folder, CONFIG_FOLDER)
        os.makedirs(save_path, exist_ok=True)
        file_path = os.path.join(save_path, file_name)

        if os.path.exists(file_path):
            w = Dialog(
                title=gt('文件已存在'),
                content=f"{file_name} {gt('已存在，是否覆盖？')}",
                parent=self,
            )
            if w.exec():
                with open(file_path, "wb") as f:
                    f.write(data)
                return file_path
            else:
                return None
        else:
            with open(file_path, "wb") as f:
                f.write(data)
            return file_path

    def load_data_from_api(self):
        try:
            response = requests.post(f"{BASE_URL}/getBattleInfo")
            response.raise_for_status()
            json_data = response.json()

            if not json_data.get("data"):
                self.show_error(gt('数据错误'), gt('服务器返回的数据格式不正确'))
                return

            data = [
                BattleInfo(
                    battle_name=item["battle_name"],
                    creation_name=item["creation_name"],
                    creation_date=item["creation_date"],
                    battle_url=item["battle_url"],
                    id=item["id"],
                )
                for item in json_data["data"]
            ]

            self.populate_online_table(data)
        except requests.RequestException as e:
            self.show_error(gt('服务异常'), f"{gt('无法连接服务器')}: {str(e)}")
        except Exception as e:
            self.show_error(gt('未知错误'), f"{gt('发生了一个未知错误')}: {str(e)}")

    def populate_online_table(self, data: list[BattleInfo]):
        self.online_table_widget.setRowCount(0)  # 清空当前行

        for item in data:
            row_position = self.online_table_widget.rowCount()
            self.online_table_widget.insertRow(row_position)

            # 创建新的 QTableWidgetItem，并设置 ID
            widget = QTableWidgetItem(item.battle_name)
            widget.setData(Qt.ItemDataRole.UserRole, item.id)

            # 设置战斗信息
            self.online_table_widget.setItem(row_position, 0, widget)
            self.online_table_widget.setItem(
                row_position, 1, QTableWidgetItem(item.creation_name)
            )
            self.online_table_widget.setItem(
                row_position, 2, QTableWidgetItem(item.creation_date)
            )

    def on_download_clicked(self):
        indexes = self.online_table_widget.selectedIndexes()
        if not indexes:
            w = Dialog(title=gt('未选择'), content=gt('请选择一条配置进行下载。'), parent=self)
            w.cancelButton.hide()
            w.buttonLayout.insertStretch(1)
            w.exec()
            return

        selected_row = indexes[0].row()
        battle_id = self.online_table_widget.item(selected_row, 0).data(
            Qt.ItemDataRole.UserRole
        )
        battle_name = self.online_table_widget.item(selected_row, 0).text()

        if battle_id is None:
            self.show_error(gt('错误'), gt('下载链接无法构建，战斗 ID 为 None'))
            return

        battle_url = f"{BASE_URL}/downloadBattleInfo/{battle_id}"

        try:
            response = requests.get(battle_url, stream=True)
            response.raise_for_status()

            project_root = self.find_project_root(__file__)
            file_path = self.save_downloaded_file(
                f"{battle_name}.yml", response.content, project_root
            )

            if file_path:
                w = Dialog(
                    title=gt('成功'), content=f"{gt('文件已下载并保存到')} {file_path}", parent=self
                )
                w.cancelButton.hide()
                w.buttonLayout.insertStretch(1)
                w.exec()
                self.load_local_configs()
        except requests.RequestException as e:
            self.show_error(gt('下载失败'), f"{gt('下载过程中出错')}: {str(e)}")

    def load_local_configs(self):
        project_root = self.find_project_root(__file__)
        config_path = os.path.join(project_root, CONFIG_FOLDER)
        os.makedirs(config_path, exist_ok=True)

        local_files = glob.glob(os.path.join(config_path, "*.yml"))
        self.local_table_widget.setRowCount(0)  # 清空当前行

        for file_path in local_files:
            file_name = os.path.basename(file_path)
            is_sample = file_name.endswith(".sample.yml")

            if not is_sample:
                row_position = self.local_table_widget.rowCount()
                self.local_table_widget.insertRow(row_position)

                # 设置文件名
                self.local_table_widget.setItem(
                    row_position, 0, QTableWidgetItem(file_name)
                )

                # 创建删除按钮
                delete_button = ToolButton(FluentIcon.DELETE)
                delete_button.setFixedSize(60, 30)
                delete_button.clicked.connect(
                    lambda checked, path=file_path: self.delete_local_config(path)
                )

                # 将按钮放入表格
                self.local_table_widget.setCellWidget(row_position, 1, delete_button)

    def delete_local_config(self, file_path):
        if os.path.exists(file_path):
            os.remove(file_path)
            self.load_local_configs()  # 重新加载本地配置列表
            self.show_error(gt('成功'), gt('文件已成功删除'))
        else:
            self.show_error(gt('错误'), gt('文件不存在'))

    def filter_table(self, text: str):
        for i in range(self.online_table_widget.rowCount()):
            item = self.online_table_widget.item(i, 0)
            if item and text.lower() in item.text().lower():
                self.online_table_widget.showRow(i)
            else:
                self.online_table_widget.hideRow(i)

    def show_error(self, title: str, content: str):
        w = Dialog(title=title, content=content, parent=self)
        w.cancelButton.hide()
        w.buttonLayout.insertStretch(1)
        w.exec()
