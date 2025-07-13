import json
import os
import requests
from datetime import datetime
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QColor, QPainter, QLinearGradient
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QScrollArea,
    QFrame,
    QTextBrowser,
    QStackedWidget,
    QGraphicsDropShadowEffect,
)
from qfluentwidgets import (
    SimpleCardWidget,
    PushButton,
    FluentIcon,
    BodyLabel,
    CaptionLabel,
    isDarkTheme,
    ProgressRing,
)

from one_dragon.utils.log_utils import log
from one_dragon_qt.widgets.pivot import PhosPivot


class NoticeContentWidgetV2(QWidget):
    
    def __init__(self, notice_data: dict, parent=None):
        super().__init__(parent)
        self.notice_data = notice_data
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # 标题和日期行
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        
        # 标题
        title_label = BodyLabel(self.notice_data.get('title', ''))
        title_label.setFont(QFont("Microsoft YaHei", 13, QFont.Weight.Bold))
        if isDarkTheme():
            title_label.setStyleSheet("QLabel { color: #ffffff; }")
        else:
            title_label.setStyleSheet("QLabel { color: #202020; }")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # 日期标签（右上角）
        date_label = CaptionLabel(self.notice_data.get('date', ''))
        date_label.setStyleSheet("QLabel { color: #888888; font-size: 10pt; }")
        header_layout.addWidget(date_label)
        
        layout.addLayout(header_layout)
        
        # 内容
        content_text = QTextBrowser()
        content_text.setReadOnly(True)
        content_text.setOpenExternalLinks(True)  # 启用外部链接
        content_text.setMarkdown(self.notice_data.get('content', ''))
        content_text.setMaximumHeight(140)
        content_text.setMinimumHeight(80)
        
        # 设置样式 - 弱化边框，增加毛玻璃效果
        if isDarkTheme():
            content_text.setStyleSheet("""
                QTextBrowser {
                    background-color: rgba(60, 60, 60, 0.2);
                    border: 1px solid rgba(255, 255, 255, 0.05);
                    border-radius: 16px;
                    padding: 16px;
                    font-family: "Microsoft YaHei";
                    font-size: 10pt;
                    line-height: 1.6;
                    color: #e0e0e0;
                }
                QTextBrowser a {
                    color: #4FC3F7;
                    text-decoration: underline;
                }
                QTextBrowser h1, QTextBrowser h2 {
                    color: #ffffff;
                    font-weight: bold;
                }
                QScrollBar:vertical {
                    background: transparent;
                    width: 6px;
                    border-radius: 3px;
                }
                QScrollBar::handle:vertical {
                    background: rgba(128, 128, 128, 0.3);
                    border-radius: 3px;
                    min-height: 20px;
                }
                QScrollBar::handle:vertical:hover {
                    background: rgba(128, 128, 128, 0.5);
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    border: none;
                    background: none;
                }
            """)
        else:
            content_text.setStyleSheet("""
                QTextBrowser {
                    background-color: rgba(248, 248, 248, 0.6);
                    border: 1px solid rgba(200, 200, 200, 0.15);
                    border-radius: 16px;
                    padding: 16px;
                    font-family: "Microsoft YaHei";
                    font-size: 10pt;
                    line-height: 1.6;
                    color: #333333;
                }
                QTextBrowser a {
                    color: #0078d4;
                    text-decoration: underline;
                }
                QTextBrowser h1, QTextBrowser h2 {
                    color: #202020;
                    font-weight: bold;
                }
                QScrollBar:vertical {
                    background: transparent;
                    width: 6px;
                    border-radius: 3px;
                }
                QScrollBar::handle:vertical {
                    background: rgba(128, 128, 128, 0.3);
                    border-radius: 3px;
                    min-height: 20px;
                }
                QScrollBar::handle:vertical:hover {
                    background: rgba(128, 128, 128, 0.5);
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    border: none;
                    background: none;
                }
            """)
        
        layout.addWidget(content_text)


class NoticeDownloadThread(QThread):
    """异步下载通知数据的线程"""
    download_finished = Signal(dict)  # 下载完成信号，传递数据
    download_failed = Signal(str)     # 下载失败信号，传递错误信息

    def __init__(self, parent=None):
        super().__init__(parent)
        # todo 推生产的时候更新这个url
        self.url = "https://raw.githubusercontent.com/Paper-white/OneDragon-Home/refs/heads/notice/src/zzz/notice.json"

    def run(self):
        try:
            log.info(f"开始异步下载通知数据: {self.url}")
            response = requests.get(self.url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            log.info(f"成功下载通知数据，包含 {len(data.get('notices', []))} 条通知")
            self.download_finished.emit(data)
            
        except requests.exceptions.RequestException as e:
            log.error(f"下载通知数据失败 - 网络错误: {e}")
            self.download_failed.emit(f"网络错误: {str(e)}")
        except json.JSONDecodeError as e:
            log.error(f"下载通知数据失败 - JSON解析错误: {e}")
            self.download_failed.emit(f"数据格式错误: {str(e)}")
        except Exception as e:
            log.error(f"下载通知数据失败 - 未知错误: {e}")
            self.download_failed.emit(f"未知错误: {str(e)}")


class SkeletonWidget(QWidget):
    """骨架屏组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 加载图标
        progress_ring = ProgressRing()
        progress_ring.setFixedSize(40, 40)
        layout.addWidget(progress_ring, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # 加载文本
        loading_label = BodyLabel("正在获取最新通知...")
        loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if isDarkTheme():
            loading_label.setStyleSheet("QLabel { color: #e0e0e0; font-size: 12pt; }")
        else:
            loading_label.setStyleSheet("QLabel { color: #606060; font-size: 12pt; }")
        layout.addWidget(loading_label)


class NoticeViewerV2(SimpleCardWidget):

    def __init__(self, assets_dir: str, parent=None):
        super().__init__(parent)
        self.assets_dir = assets_dir
        self.notices_data = []
        
        # 设置固定大小
        self.setFixedSize(400, 300)
        self.setBorderRadius(20)
        
        # 设置阴影效果 - 增强浮起感
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 6)
        self.setGraphicsEffect(shadow)
        
        # 创建堆叠布局用于切换骨架屏和内容
        self.stacked_widget = QStackedWidget()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)
        main_layout.addWidget(self.stacked_widget)
        
        # 创建骨架屏
        self.skeleton_widget = SkeletonWidget()
        self.stacked_widget.addWidget(self.skeleton_widget)
        
        # 创建内容容器
        self.content_widget = QWidget()
        self.stacked_widget.addWidget(self.content_widget)
        
        # 初始显示骨架屏
        self.stacked_widget.setCurrentWidget(self.skeleton_widget)
        
        # 创建并启动下载线程
        self.download_thread = NoticeDownloadThread()
        self.download_thread.download_finished.connect(self.on_download_finished)
        self.download_thread.download_failed.connect(self.on_download_failed)
        self.download_thread.start()
    
    def _normalBackgroundColor(self):
        if isDarkTheme():
            return QColor(45, 45, 45, 160)
        else:
            return QColor(255, 255, 255, 160)
    
    def on_download_finished(self, data: dict):
        """下载成功回调"""
        log.info("通知数据下载成功")
        self.notices_data = data.get('notices', [])
        self.setup_content_ui()
        self.stacked_widget.setCurrentWidget(self.content_widget)
    
    def on_download_failed(self, error_msg: str):
        """下载失败回调，显示默认数据"""
        log.warning(f"通知数据下载失败: {error_msg}，使用默认数据")
        self.notices_data = self.get_default_notices()
        self.setup_content_ui()
        self.stacked_widget.setCurrentWidget(self.content_widget)
    
    def get_default_notices(self):
        """获取默认通知数据"""
        # todo 写个默认兜底url
        return [
            {
                "title": "默认更新日志",
                "date": "2025-7-13",
                "content": "网络连接失败，显示默认内容。请检查网络连接后重启应用。"
            },
            {
                "title": "默认帮助",
                "date": "2025-7-13", 
                "content": "这是默认的帮助内容。如需最新信息，请确保网络连接正常。"
            }
        ]
    
    def setup_content_ui(self):
        """设置内容UI"""
        # 清空现有内容
        layout = self.content_widget.layout()
        if layout:
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
        else:
            layout = QVBoxLayout(self.content_widget)
        
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)
        
        # 过滤掉调试标题
        filtered_notices = [notice for notice in self.notices_data if 'title_debug' not in notice]
        
        # 内容区域
        if filtered_notices:
            # 创建选项卡
            self.pivot = PhosPivot()
            self.pivot.setFixedHeight(44)
            
            # 设置选中状态样式
            if isDarkTheme():
                self.pivot.setStyleSheet("""
                    PhosPivot {
                        background-color: rgba(60, 60, 60, 0.3);
                        border-radius: 12px;
                        padding: 6px;
                    }
                    PhosPivot > QWidget {
                        background-color: transparent;
                        color: #cccccc;
                        border-radius: 8px;
                        padding: 8px 16px;
                        margin: 2px;
                    }
                    PhosPivot > QWidget[selected="true"] {
                        background-color: rgba(79, 195, 247, 0.25);
                        border: 1px solid rgba(79, 195, 247, 0.5);
                        color: #4FC3F7;
                        font-weight: bold;
                    }
                    PhosPivot > QWidget:hover {
                        background-color: rgba(255, 255, 255, 0.1);
                    }
                """)
            else:
                self.pivot.setStyleSheet("""
                    PhosPivot {
                        background-color: rgba(248, 248, 248, 0.8);
                        border-radius: 12px;
                        padding: 6px;
                    }
                    PhosPivot > QWidget {
                        background-color: transparent;
                        color: #666666;
                        border-radius: 8px;
                        padding: 8px 16px;
                        margin: 2px;
                    }
                    PhosPivot > QWidget[selected="true"] {
                        background-color: rgba(0, 120, 212, 0.2);
                        border: 1px solid rgba(0, 120, 212, 0.4);
                        color: #0078d4;
                        font-weight: bold;
                    }
                    PhosPivot > QWidget:hover {
                        background-color: rgba(0, 0, 0, 0.08);
                    }
                """)
            
            layout.addWidget(self.pivot)
            
            # 内容卡片
            content_card = SimpleCardWidget()
            content_card.setBorderRadius(16)
            content_card.setFixedHeight(190)
            
            # 内容卡片阴影
            card_shadow = QGraphicsDropShadowEffect()
            card_shadow.setBlurRadius(20)
            card_shadow.setColor(QColor(0, 0, 0, 30))
            card_shadow.setOffset(0, 4)
            content_card.setGraphicsEffect(card_shadow)
            
            # 内容卡片背景
            if isDarkTheme():
                content_card.setStyleSheet("""
                    SimpleCardWidget {
                        background-color: rgba(55, 55, 55, 0.7);
                        border: 1px solid rgba(255, 255, 255, 0.08);
                        border-radius: 16px;
                    }
                """)
            else:
                content_card.setStyleSheet("""
                    SimpleCardWidget {
                        background-color: rgba(255, 255, 255, 0.85);
                        border: 1px solid rgba(200, 200, 200, 0.15);
                        border-radius: 16px;
                    }
                """)
            
            layout.addWidget(content_card)
            
            # 使用QStackedWidget管理内容页面
            self.content_stacked_widget = QStackedWidget()
            content_card_layout = QVBoxLayout(content_card)
            content_card_layout.setContentsMargins(0, 0, 0, 0)
            content_card_layout.addWidget(self.content_stacked_widget)
            
            # 为每个通知创建页面
            for i, notice in enumerate(filtered_notices):
                # 创建包含滚动区域的页面
                scroll_area = QScrollArea()
                scroll_area.setWidgetResizable(True)
                scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
                
                # 创建通知内容widget
                notice_widget = NoticeContentWidgetV2(notice, parent=scroll_area)
                scroll_area.setWidget(notice_widget)
                
                # 添加到stacked widget
                self.content_stacked_widget.addWidget(scroll_area)
                
                # 截取标题用于选项卡显示
                tab_title = notice['title']
                if len(tab_title) > 6:
                    tab_title = tab_title[:6] + "..."
                
                # 添加到pivot
                self.add_sub_interface(scroll_area, f"notice_{i}", tab_title)
            
            # 默认显示第一个通知
            if self.content_stacked_widget.count() > 0:
                self.content_stacked_widget.setCurrentIndex(0)
                self.pivot.setCurrentItem("notice_0")
        else:
            # 空状态
            self.show_empty_state(layout)
    
    def add_sub_interface(self, widget: QWidget, object_name: str, text: str):
        """添加子界面到pivot"""
        widget.setObjectName(object_name)
        self.pivot.addItem(
            routeKey=object_name,
            text=text,
            onClick=lambda: self.content_stacked_widget.setCurrentWidget(widget),
        )
    
    def show_empty_state(self, layout):
        """显示空状态"""
        empty_widget = QWidget()
        empty_layout = QVBoxLayout(empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 空状态图标
        empty_icon = QLabel("📭")
        empty_icon.setFont(QFont("", 24))
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_icon)
        
        # 空状态文本
        empty_label = BodyLabel("暂无通知")
        empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_label.setStyleSheet("QLabel { color: #888; }")
        empty_layout.addWidget(empty_label)
        
        layout.addWidget(empty_widget)
    
    def refresh_notices(self):
        """刷新通知"""
        try:
            # 重新显示骨架屏
            self.stacked_widget.setCurrentWidget(self.skeleton_widget)
            
            # 重新创建并启动下载线程
            if hasattr(self, 'download_thread'):
                self.download_thread.quit()
                self.download_thread.wait()
            
            self.download_thread = NoticeDownloadThread()
            self.download_thread.download_finished.connect(self.on_download_finished)
            self.download_thread.download_failed.connect(self.on_download_failed)
            self.download_thread.start()
            
            log.info("通知内容已刷新")
        except Exception as e:
            log.error(f"刷新通知失败: {e}")
    
    def clear_layout(self):
        """清空布局"""
        layout = self.layout()
        if layout:
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
                elif child.layout():
                    self.clear_sub_layout(child.layout())
    
    def clear_sub_layout(self, layout):
        """递归清空子布局"""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self.clear_sub_layout(child.layout())


class NoticeViewerContainerV2(QWidget):
    
    def __init__(self, notice_cache_dir: str, parent=None):
        super().__init__(parent)
        self.notice_cache_dir = notice_cache_dir
        self.setObjectName("NoticeViewerContainerV2")
        
        # 创建主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # 创建通知查看器
        self.notice_viewer = NoticeViewerV2(notice_cache_dir)
        self.main_layout.addWidget(self.notice_viewer)
        
        # 控制状态
        self._notice_enabled = False
        
        # 设置固定宽度
        self.setFixedWidth(400)
        
        # 初始状态为隐藏
        self._apply_visibility_state()
    
    def set_notice_enabled(self, enabled: bool):
        """设置通知是否启用"""
        if self._notice_enabled == enabled:
            return
        
        self._notice_enabled = enabled
        self._apply_visibility_state()
    
    def _apply_visibility_state(self):
        """应用可见性状态"""
        if self._notice_enabled:
            self.notice_viewer.show()
            self.show()
        else:
            self.notice_viewer.hide()
            self.hide()
    
    def refresh_notice(self):
        """刷新通知内容"""
        if self.notice_viewer and self._notice_enabled:
            self.notice_viewer.refresh_notices()
