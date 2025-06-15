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
)
from qfluentwidgets import SimpleCardWidget, HorizontalFlipView, ListWidget

from one_dragon_qt.widgets.pivot import CustomListItemDelegate, PhosPivot
from .label import EllipsisLabel


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
                print(f"异步加载图片失败: {e}")

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
                print(f"Failed to download {file_url}: {e}")


class NoticeCard(SimpleCardWidget):
    def __init__(self):
        SimpleCardWidget.__init__(self)
        self.setBorderRadius(10)
        self.setFixedWidth(351)
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(3, 3, 0, 0)
        self.mainLayout.setAlignment(Qt.AlignmentFlag.AlignCenter)

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
        self.fetch_data()

    def _normalBackgroundColor(self):
        return QColor(255, 255, 255, 13)

    def fetch_data(self):
        self.fetcher = DataFetcher()
        self.fetcher.data_fetched.connect(self.handle_data)
        self.fetcher.start()

    def handle_data(self, content):
        if "error" in content:
            self.error_label.setText(f"无法获取数据: {content['error']}")
            self.error_label.setFixedSize(330, 160)
            self.error_label.show()
            self.flipView.hide()
            self.update_ui()
            return
        self.load_banners_async(content["data"]["content"]["banners"])
        self.load_posts(content["data"]["content"]["posts"])
        self.error_label.hide()
        self.update_ui()

    # @deprecated
    def load_banners(self, banners):
        """
        同步加载banner图片
        @deprecated: see load_banners_async
        """
        pixel_ratio = self.devicePixelRatio()  # 获取设备像素比
        for banner in banners:
            try:
                response = requests.get(banner["image"]["url"])
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)

                # 缩放图片，确保清晰
                size = QSize(pixmap.width(), pixmap.height())
                pixmap = pixmap.scaled(
                    size * pixel_ratio,  # 按设备像素比缩放
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                pixmap.setDevicePixelRatio(pixel_ratio)  # 设置设备像素比
                self.banners.append(pixmap)
                self.banner_urls.append(banner["image"]["link"])
            except Exception as e:
                print(f"加载图片失败: {e}")

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
        # 实时更新UI显示新加载的图片 (单独添加，避免重复)
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
