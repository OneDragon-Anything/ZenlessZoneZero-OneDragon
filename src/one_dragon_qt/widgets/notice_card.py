import time

import json
import os
import requests
import webbrowser
from PySide6.QtCore import Qt, QSize, QTimer, QThread, Signal
from PySide6.QtGui import QPixmap, QFont, QPainterPath, QRegion, QColor
from PySide6.QtWidgets import (
    QVBoxLayout,
    QListWidgetItem,
    QWidget,
    QLabel,
    QHBoxLayout,
    QStackedWidget,
    QFrame,
)
from qfluentwidgets import SimpleCardWidget, HorizontalFlipView, ListWidget

from one_dragon_qt.services.styles_manager import OdQtStyleSheet
from one_dragon_qt.widgets.pivot import CustomListItemDelegate, PhosPivot
from one_dragon.utils.log_utils import log
from .label import EllipsisLabel


class SkeletonBanner(QFrame):
    """骨架屏Banner组件 - 简化版"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SkeletonBanner")
        self.setFixedSize(345, 160)
        # 设置基础样式
        self.setStyleSheet("""
            SkeletonBanner {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(240, 240, 240, 200),
                    stop:0.5 rgba(255, 255, 255, 230),
                    stop:1 rgba(240, 240, 240, 200));
                border-radius: 10px;
                border: 2px solid rgba(200, 200, 200, 100);
            }
        """)


class SkeletonContent(QWidget):
    """骨架屏内容组件 - 简化版"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SkeletonContent")
        self.setFixedHeight(80)
        self.setupUI()

    def setupUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(8)

        # 创建多个骨架条
        for i in range(2):
            skeleton_item = QFrame()
            skeleton_item.setObjectName("SkeletonItem")
            skeleton_item.setFixedHeight(20)
            # 不同长度的骨架条
            if i == 0:
                skeleton_item.setFixedWidth(280)
            else:
                skeleton_item.setFixedWidth(220)

            # 设置骨架条样式
            skeleton_item.setStyleSheet("""
                QFrame#SkeletonItem {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 rgba(224, 224, 224, 150),
                        stop:0.5 rgba(240, 240, 240, 200),
                        stop:1 rgba(224, 224, 224, 150));
                    border-radius: 8px;
                    border: 1px solid rgba(200, 200, 200, 80);
                }
            """)
            layout.addWidget(skeleton_item)


class BannerImageLoader(QThread):
    """异步banner图片加载器"""
    image_loaded = Signal(QPixmap, str)  # pixmap, url
    all_images_loaded = Signal()

    def __init__(self, banners, device_pixel_ratio, parent=None):
        super().__init__(parent)
        self.banners = banners
        self.device_pixel_ratio = device_pixel_ratio
        self.loaded_count = 0
        self.total_count = len(banners)

    def run(self):
        """异步加载所有banner图片"""
        for banner in self.banners:
            try:
                response = requests.get(banner["image"]["url"], timeout=5)
                if response.status_code == 200:
                    pixmap = QPixmap()
                    pixmap.loadFromData(response.content)

                    # 缩放图片，确保清晰
                    size = QSize(pixmap.width(), pixmap.height())
                    pixmap = pixmap.scaled(
                        size * self.device_pixel_ratio,  # 按设备像素比缩放
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    pixmap.setDevicePixelRatio(self.device_pixel_ratio)  # 设置设备像素比
                    self.image_loaded.emit(pixmap, banner["image"]["link"])
            except Exception as e:
                log.error(f"加载banner图片失败: {e}")

            self.loaded_count += 1

        self.all_images_loaded.emit()


# 增加了缓存机制, 有效期为3天, 避免每次都请求数据
# 调整了超时时间, 避免网络问题导致程序启动缓慢
class DataFetcher(QThread):
    data_fetched = Signal(dict)

    BASE_URL = "https://hyp-api.mihoyo.com/hyp/hyp-connect/api/getGameContent"
    LAUNCHER_ID = "jGHBHlcOq1"
    GAME_ID = "x6znKlJ0xK"
    CACHE_DIR = "notice_cache"
    CACHE_FILE = os.path.join(CACHE_DIR, "notice_cache.json")
    CACHE_DURATION = 259200  # 缓存时间为3天
    TIMEOUTNUM = 3  # 超时时间

    def run(self):
        try:
            response = requests.get(
                f"{DataFetcher.BASE_URL}?launcher_id={DataFetcher.LAUNCHER_ID}&game_id={DataFetcher.GAME_ID}&language=zh-cn",
                timeout=DataFetcher.TIMEOUTNUM,
            )
            response.raise_for_status()
            data = response.json()
            self.data_fetched.emit(data)
            self.save_cache(data)
            self.download_related_files(data)
        except requests.RequestException as e:
            if self.is_cache_valid():
                with open(DataFetcher.CACHE_FILE, "r", encoding="utf-8") as cache_file:
                    cached_data = json.load(cache_file)
                    self.data_fetched.emit(cached_data)
            else:
                self.data_fetched.emit({"error": str(e)})

    def is_cache_valid(self):
        if not os.path.exists(DataFetcher.CACHE_FILE):
            return False
        cache_mtime = os.path.getmtime(DataFetcher.CACHE_FILE)
        return time.time() - cache_mtime < DataFetcher.CACHE_DURATION

    def save_cache(self, data):
        os.makedirs(DataFetcher.CACHE_DIR, exist_ok=True)
        with open(DataFetcher.CACHE_FILE, "w", encoding="utf-8") as cache_file:
            json.dump(data, cache_file)

    def download_related_files(self, data):
        related_files = data.get("related_files", [])
        for file_url in related_files:
            file_name = os.path.basename(file_url)
            file_path = os.path.join(DataFetcher.CACHE_DIR, file_name)
            try:
                response = requests.get(file_url, timeout=DataFetcher.TIMEOUTNUM)
                response.raise_for_status()
                with open(file_path, "wb") as file:
                    file.write(response.content)
            except requests.RequestException as e:
                log.error(f"下载相关文件失败: {e}")


class NoticeCard(SimpleCardWidget):
    def __init__(self):
        SimpleCardWidget.__init__(self)
        self.setBorderRadius(10)
        self.setFixedWidth(351)
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(3, 3, 0, 0)
        self.mainLayout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 骨架屏组件
        self.skeleton_banner = SkeletonBanner(self)
        self.skeleton_content = SkeletonContent(self)

        self.error_label = QLabel("无法获取数据")
        self.error_label.setWordWrap(True)
        self.error_label.setObjectName("error")
        self.error_label.hide()
        self.mainLayout.addWidget(self.error_label)

        self.banners, self.banner_urls, self.posts = (
            [],
            [],
            {"announces": [], "activities": [], "infos": []},
        )
        self._banner_loader = None
        self._is_loading_banners = False

        self.setup_ui()

        # 在setup_ui之后添加骨架屏到布局
        self.mainLayout.insertWidget(0, self.skeleton_banner)  # 在第一个位置插入
        self.mainLayout.insertWidget(1, self.skeleton_content)  # 在第二个位置插入

        self.show_skeleton()  # 初始显示骨架屏
        self.fetch_data()

    def _normalBackgroundColor(self):
        return QColor(255, 255, 255, 13)

    def show_skeleton(self):
        """显示骨架屏"""
        self.skeleton_banner.show()
        self.skeleton_content.show()
        # 确保骨架屏在最前面
        self.skeleton_banner.raise_()
        self.skeleton_content.raise_()

        if hasattr(self, 'flipView'):
            self.flipView.hide()
        if hasattr(self, 'pivot'):
            self.pivot.hide()
        if hasattr(self, 'stackedWidget'):
            self.stackedWidget.hide()

    def hide_skeleton(self):
        """隐藏骨架屏"""
        self.skeleton_banner.hide()
        self.skeleton_content.hide()
        if hasattr(self, 'flipView'):
            self.flipView.show()
        if hasattr(self, 'pivot'):
            self.pivot.show()
        if hasattr(self, 'stackedWidget'):
            self.stackedWidget.show()

    def fetch_data(self):
        self.fetcher = DataFetcher()
        self.fetcher.data_fetched.connect(self.handle_data)
        self.fetcher.start()

    def handle_data(self, content):
        if "error" in content:
            self.hide_skeleton()  # 隐藏骨架屏
            self.error_label.setText(f"无法获取数据: {content['error']}")
            self.error_label.setFixedSize(330, 160)
            self.error_label.show()
            if hasattr(self, 'flipView'):
                self.flipView.hide()
            self.update_ui()
            return
        self.load_banners_async(content["data"]["content"]["banners"])
        self.load_posts(content["data"]["content"]["posts"])
        self.error_label.hide()
        # banner加载时会自动隐藏骨架屏，这里不需要重复调用
        self.update_ui()

    def load_banners_async(self, banners):
        """
        异步加载banner图片
        """
        if self._is_loading_banners or not banners:
            return

        # 清空现有的banners，准备加载新的
        self.banners.clear()
        self.banner_urls.clear()

        self._is_loading_banners = True
        pixel_ratio = self.devicePixelRatio()

        self._banner_loader = BannerImageLoader(banners, pixel_ratio, self)
        self._banner_loader.image_loaded.connect(self._on_banner_image_loaded)
        self._banner_loader.all_images_loaded.connect(self._on_all_banners_loaded)
        self._banner_loader.finished.connect(self._on_banner_loading_finished)
        self._banner_loader.start()

    def _on_banner_image_loaded(self, pixmap: QPixmap, url: str):
        """单个banner图片加载完成的回调"""
        self.banners.append(pixmap)
        self.banner_urls.append(url)

        # 如果这是第一个加载完成的banner，隐藏骨架屏并显示内容
        if len(self.banners) == 1:
            self.hide_skeleton()

        # 实时更新UI显示新加载的图片 (单独添加，避免重复)
        if hasattr(self, 'flipView'):
            self.flipView.addImages([pixmap])

    def _on_all_banners_loaded(self):
        """所有banner图片加载完成的回调"""
        self.update_ui()

    def _on_banner_loading_finished(self):
        """banner加载线程结束的回调"""
        self._is_loading_banners = False
        if self._banner_loader:
            self._banner_loader.deleteLater()
            self._banner_loader = None

    def load_posts(self, posts):
        post_types = {
            "POST_TYPE_ANNOUNCE": "announces",
            "POST_TYPE_ACTIVITY": "activities",
            "POST_TYPE_INFO": "infos",
        }
        for post in posts:
            if (entry := post_types.get(post["type"])) is not None:
                self.posts[entry].append(
                    {"title": post["title"], "url": post["link"], "date": post["date"]}
                )

    def setup_ui(self):
        self.flipView = HorizontalFlipView(self)
        self.flipView.addImages(self.banners)
        self.flipView.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.flipView.setItemSize(QSize(345, 160))
        self.flipView.setFixedSize(QSize(345, 160))
        self.flipView.itemClicked.connect(self.open_banner_link)

        # 实现遮罩
        path = QPainterPath()
        path.addRoundedRect(self.flipView.rect(), 10, 10, Qt.SizeMode.AbsoluteSize)
        region = QRegion(path.toFillPolygon().toPolygon())
        self.flipView.setMask(region)

        self.mainLayout.addWidget(self.flipView)
        QTimer.singleShot(7000, self.scrollNext)

        self.pivot = PhosPivot()
        self.stackedWidget = QStackedWidget(self)
        self.stackedWidget.setContentsMargins(0, 0, 5, 0)
        self.stackedWidget.setFixedHeight(60)
        self.activityWidget, self.announceWidget, self.infoWidget = (
            ListWidget(),
            ListWidget(),
            ListWidget(),
        )

        types = ["activities", "announces", "infos"]
        type_names = ["活动", "公告", "资讯"]
        for i, w in enumerate(
            [self.activityWidget, self.announceWidget, self.infoWidget]
        ):
            type = types[i]
            name = type_names[i]
            self.add_posts_to_widget(w, type)
            w.setItemDelegate(CustomListItemDelegate(w))
            w.itemClicked.connect(
                lambda _, widget=w, type=type: self.open_post_link(widget, type)
            )
            self.addSubInterface(w, type, name)

        self.stackedWidget.currentChanged.connect(self.onCurrentIndexChanged)
        self.stackedWidget.setCurrentWidget(self.activityWidget)
        self.pivot.setCurrentItem(self.activityWidget.objectName())
        self.mainLayout.addWidget(self.pivot, 0, Qt.AlignmentFlag.AlignLeft)
        self.mainLayout.addWidget(self.stackedWidget)

    def update_ui(self):
        # 清空现有内容，避免重复添加
        self.flipView.clear()
        self.flipView.addImages(self.banners)

        # 清空并重新添加posts
        for widget, type in zip(
            [self.activityWidget, self.announceWidget, self.infoWidget],
            ["activities", "announces", "infos"],
        ):
            widget.clear()
            self.add_posts_to_widget(widget, type)

    def scrollNext(self):
        if self.banners:
            self.flipView.setCurrentIndex(
                (self.flipView.currentIndex() + 1) % len(self.banners)
            )

    def addSubInterface(self, widget: ListWidget, objectName: str, text: str):
        widget.setObjectName(objectName)
        self.stackedWidget.addWidget(widget)
        self.pivot.addItem(
            routeKey=objectName,
            text=text,
            onClick=lambda: self.stackedWidget.setCurrentWidget(widget),
        )

    def onCurrentIndexChanged(self, index):
        widget = self.stackedWidget.widget(index)
        self.pivot.setCurrentItem(widget.objectName())

    def open_banner_link(self):
        if self.banner_urls:
            webbrowser.open(self.banner_urls[self.flipView.currentIndex()])

    def open_post_link(self, widget: ListWidget, type: str):
        if self.posts[type]:
            webbrowser.open(self.posts[type][widget.currentIndex().row()]["url"])

    def add_posts_to_widget(self, widget: ListWidget, type: str):
        for post in self.posts[type][:2]:
            item_widget = self.create_post_widget(post)
            item = QListWidgetItem()
            item.setSizeHint(item_widget.sizeHint())
            widget.addItem(item)
            widget.setItemWidget(item, item_widget)

    def create_post_widget(self, post):
        item_widget = QWidget()
        layout = QHBoxLayout(item_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        title_label = EllipsisLabel(post["title"])
        title_label.setObjectName("title")
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title_label.setFixedWidth(280)
        title_label.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(title_label)

        date_label = QLabel(post["date"])
        date_label.setObjectName("date")
        date_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        date_label.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(date_label)

        layout.setStretch(0, 1)
        layout.setStretch(1, 0)
        return item_widget


class NoticeCardContainer(QWidget):
    """公告卡片容器 - 支持动态显示/隐藏，无需重启"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("NoticeCardContainer")

        # 创建主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 创建公告卡片
        self.notice_card = NoticeCard()
        OdQtStyleSheet.NOTICE_CARD.apply(self.notice_card)
        self.main_layout.addWidget(self.notice_card)

        # 控制状态
        self._notice_enabled = False

        # 设置固定宽度
        self.setFixedWidth(351)

        # 初始状态为隐藏
        self._apply_visibility_state()

    def set_notice_enabled(self, enabled: bool):
        """设置公告是否启用"""
        if self._notice_enabled == enabled:
            return

        self._notice_enabled = enabled
        self._apply_visibility_state()

    def _apply_visibility_state(self):
        """应用可见性状态"""
        if self._notice_enabled:
            self.notice_card.show()
            self.show()
        else:
            self.notice_card.hide()
            self.hide()

    def refresh_notice(self):
        """刷新公告内容"""
        if self.notice_card is not None and self._notice_enabled:
            # 重新获取数据
            self.notice_card.fetch_data()
