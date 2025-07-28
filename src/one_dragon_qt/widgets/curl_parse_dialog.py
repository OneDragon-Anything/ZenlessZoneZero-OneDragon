import json
from typing import Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QLabel
from qfluentwidgets import (MessageBoxBase, BodyLabel, CaptionLabel,
                           CardWidget, SimpleCardWidget, VBoxLayout, ScrollArea)


class CurlParseDialog(MessageBoxBase):
    """cURL 解析结果确认对话框"""

    def __init__(self, parsed_config: Dict[str, str], parent=None):
        super().__init__(parent)
        self.parsed_config = parsed_config
        self.setWindowTitle('cURL 解析结果')
        self._setup_ui()

    def _setup_ui(self):
        """设置对话框界面"""
        # 标题
        self.titleLabel = BodyLabel('解析到以下配置，是否应用到当前设置？', self.widget)

        # 创建滚动区域
        self.scrollArea = ScrollArea(self.widget)
        self.scrollWidget = QWidget()
        self.scrollLayout = VBoxLayout(self.scrollWidget)

        # 配置项映射
        title_map = {
            'method': 'HTTP 方法',
            'url': 'URL 地址',
            'content_type': '内容类型',
            'headers': '请求头',
            'body': '请求体'
        }

        # 为每个配置项创建卡片
        for key, value in self.parsed_config.items():
            if not value or value == '{}':
                continue

            # 创建配置卡片
            card = SimpleCardWidget(self.scrollWidget)
            card_layout = VBoxLayout(card)
            card_layout.setContentsMargins(16, 12, 16, 12)

            # 配置标题
            title_label = BodyLabel(title_map.get(key, key))
            title_label.setObjectName('titleLabel')
            card_layout.addWidget(title_label)

            # 配置值
            if key in ['headers', 'body'] and len(value) > 50:
                # 长文本显示前几行，可展开
                preview = value[:100] + '...' if len(value) > 100 else value
                content_label = CaptionLabel(preview)
                content_label.setWordWrap(True)
                content_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            else:
                # 短文本直接显示
                content_label = CaptionLabel(value)
                content_label.setWordWrap(True)
                content_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

            content_label.setObjectName('contentLabel')
            card_layout.addWidget(content_label)

            self.scrollLayout.addWidget(card)

        # 设置滚动区域
        self.scrollArea.setWidget(self.scrollWidget)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setMaximumHeight(400)
        self.scrollArea.setMinimumWidth(600)

        # 添加到主布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.scrollArea, 1)

        # 设置按钮文本
        self.yesButton.setText('应用配置')
        self.cancelButton.setText('取消')

        # 设置样式
        self.widget.setMinimumSize(650, 480)

    def validate(self) -> bool:
        """验证数据，这里总是返回 True"""
        return True