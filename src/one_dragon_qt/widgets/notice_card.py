import time
import random

import json
import os
import requests
import webbrowser
from PySide6.QtCore import Qt, QSize, QTimer, QThread, Signal, QRectF
from PySide6.QtGui import QPixmap, QFont, QPainterPath, QColor, QPainter, QImage
from PySide6.QtWidgets import (
    QVBoxLayout,
    QListWidgetItem,
    QWidget,
    QLabel,
    QHBoxLayout,
    QStackedWidget,
    QFrame, QGraphicsDropShadowEffect,
)
from qfluentwidgets import SimpleCardWidget, HorizontalFlipView, ListWidget, qconfig, Theme, PipsPager, PipsScrollButtonDisplayMode

from one_dragon_qt.services.styles_manager import OdQtStyleSheet
from one_dragon_qt.widgets.pivot import CustomListItemDelegate, PhosPivot
from one_dragon.utils.log_utils import log
from .label import EllipsisLabel


def get_notice_theme_palette():
    """返回与主题相关的颜色配置。

    返回:
        dict: {
            'tint': QColor,           # 背景半透明色
            'title': str,             # 标题文本颜色
            'date': str,              # 日期文本颜色
            'shadow': QColor          # 外部阴影颜色
        }
    """
    if qconfig.theme == Theme.DARK:
        return {
            'tint': QColor(20, 20, 20, 160),
            'title': '#fff',
            'date': '#ddd',
            'shadow': QColor(0, 0, 0, 170),
        }
    return {
        'tint': QColor(245, 245, 245, 160),
        'title': '#000',
        'date': '#333',
        'shadow': QColor(0, 0, 0, 150),
    }

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
                border-radius: 4px;
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

        # 创建骨架条
        widths = [280, 220]
        for width in widths:
            skeleton_item = QFrame()
            skeleton_item.setObjectName("SkeletonItem")
            skeleton_item.setFixedSize(width, 20)
            skeleton_item.setStyleSheet("""
                QFrame#SkeletonItem {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 rgba(224, 224, 224, 150),
                        stop:0.5 rgba(240, 240, 240, 200),
                        stop:1 rgba(224, 224, 224, 150));
                    border-radius: 4px;
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

                    # 按设备像素比缩放
                    size = QSize(pixmap.width(), pixmap.height())
                    pixmap = pixmap.scaled(
                        size * self.device_pixel_ratio,
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    pixmap.setDevicePixelRatio(self.device_pixel_ratio)
                    self.image_loaded.emit(pixmap, banner["image"]["link"])
            except Exception as e:
                log.error(f"加载banner图片失败: {e}")

            self.loaded_count += 1

        self.all_images_loaded.emit()


class RoundedBannerView(HorizontalFlipView):
    """抗锯齿圆角 Banner 视图，避免 QRegion 掩膜造成的锯齿边缘"""

    def __init__(self, radius: int = 4, parent=None):
        super().__init__(parent)
        self._radius = radius
        self.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)


class BannerWithPips(QWidget):
    """Banner容器，内嵌PipsPager指示点"""
    
    # 定义信号
    itemClicked = Signal()
    currentIndexChanged = Signal(int)
    
    def __init__(self, radius: int = 4, parent=None):
        super().__init__(parent)
        self.radius = radius
        self.setFixedSize(345, 160)
        
        # 创建FlipView
        self.flipView = RoundedBannerView(radius=radius, parent=self)
        self.flipView.setGeometry(0, 0, 345, 160)
        self.flipView.itemClicked.connect(self.itemClicked.emit)
        self.flipView.currentIndexChanged.connect(self._on_flip_index_changed)
        
        # 创建PipsPager，定位在底部
        self.pipsPager = PipsPager(parent=self)
        self.pipsPager.setNextButtonDisplayMode(PipsScrollButtonDisplayMode.NEVER)
        self.pipsPager.setPreviousButtonDisplayMode(PipsScrollButtonDisplayMode.NEVER)
        self.pipsPager.currentIndexChanged.connect(self._on_pips_index_changed)
        
        # 设置PipsPager样式，让它更融入图片
        self.pipsPager.setStyleSheet("""
            PipsPager {
                background: transparent;
            }
            /* 设置指示点容器的半透明背景 */
            PipsPager > QWidget {
                background: rgba(0, 0, 0, 120);
                border-radius: 12px;
                padding: 4px 8px;
            }
            /* 设置指示点样式 */
            PipsPager QToolButton {
                background: rgba(255, 255, 255, 100);
                border: none;
                border-radius: 3px;
                width: 6px;
                height: 6px;
                margin: 2px;
            }
            /* 当前激活的指示点 */
            PipsPager QToolButton:checked {
                background: rgba(255, 255, 255, 200);
            }
            /* 悬停效果 */
            PipsPager QToolButton:hover {
                background: rgba(255, 255, 255, 150);
            }
        """)
        
        # 初始化位置
        self._update_pips_position()
        
        # 确保PipsPager在最上层
        self.pipsPager.raise_()
        
    def _update_pips_position(self):
        """更新PipsPager位置 - 居中并置于底部"""
        pips_width = self.pipsPager.sizeHint().width()
        pips_height = self.pipsPager.sizeHint().height()
        
        # 计算居中位置，距离底部15像素
        x = (self.width() - pips_width) // 2
        y = self.height() - pips_height - 15
        
        self.pipsPager.setGeometry(x, y, pips_width, pips_height)
    
    def _on_flip_index_changed(self, index):
        """FlipView页面改变时同步PipsPager"""
        self.pipsPager.setCurrentIndex(index)
        self.currentIndexChanged.emit(index)
    
    def _on_pips_index_changed(self, index):
        """PipsPager点击时切换FlipView"""
        if index != self.flipView.currentIndex():
            self.flipView.setCurrentIndex(index)
    
    # 代理方法，让外部可以直接操作FlipView
    def addImages(self, images):
        """添加图片"""
        self.flipView.addImages(images)
        # 更新PipsPager
        self.pipsPager.setPageNumber(len(images) if images else 1)
        self.pipsPager.setVisibleNumber(min(8, len(images) if images else 1))
        self.pipsPager.setCurrentIndex(0)
        self._update_pips_position()
    
    def clear(self):
        """清空图片"""
        self.flipView.clear()
    
    def setCurrentIndex(self, index):
        """设置当前页面"""
        self.flipView.setCurrentIndex(index)
    
    def currentIndex(self):
        """获取当前页面索引"""
        return self.flipView.currentIndex()
    
    def setItemSize(self, size):
        """设置项目大小"""
        self.flipView.setItemSize(size)
    
    def resizeEvent(self, event):
        """窗口大小改变时更新子组件位置"""
        super().resizeEvent(event)
        if hasattr(self, 'flipView'):
            self.flipView.setGeometry(0, 0, self.width(), self.height())
        if hasattr(self, 'pipsPager'):
            self._update_pips_position()


# 增加了缓存机制, 有效期为3天, 避免每次都请求数据
# 调整了超时时间, 避免网络问题导致程序启动缓慢
class DataFetcher(QThread):
    data_fetched = Signal(dict)

    CACHE_DIR = "notice_cache"
    CACHE_FILE = os.path.join(CACHE_DIR, "notice_cache.json")
    CACHE_DURATION = 259200  # 缓存时间为3天
    TIMEOUTNUM = 3  # 超时时间

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        try:
            response = requests.get(self.url, timeout=DataFetcher.TIMEOUTNUM)
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
        for file_url in data.get("related_files", []):
            file_path = os.path.join(DataFetcher.CACHE_DIR, os.path.basename(file_url))
            try:
                response = requests.get(file_url, timeout=DataFetcher.TIMEOUTNUM)
                response.raise_for_status()
                with open(file_path, "wb") as file:
                    file.write(response.content)
            except requests.RequestException as e:
                log.error(f"下载相关文件失败: {e}")


class AcrylicBackground(QWidget):
    """“虚化”背景：半透明底色 + 轻噪声 + 细描边"""

    def __init__(self, parent=None, radius: int = 4, tint: QColor = QColor(245, 245, 245, 130)):
        super().__init__(parent)
        self.radius = radius
        self.tint = tint
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self._noise_tile = self._generate_noise_tile(64, 64)

    def _generate_noise_tile(self, width: int, height: int) -> QPixmap:
        img = QImage(width, height, QImage.Format.Format_ARGB32)
        for y in range(height):
            for x in range(width):
                v = max(0, min(255, 240 + random.randint(-10, 10)))
                img.setPixel(x, y, QColor(v, v, v, 255).rgba())
        return QPixmap.fromImage(img)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rectF = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rectF, self.radius, self.radius)

        # 半透明底色
        painter.fillPath(path, self.tint)

        # 轻度噪声覆盖
        painter.save()
        painter.setClipPath(path)
        painter.setOpacity(0.05)
        painter.drawTiledPixmap(self.rect(), self._noise_tile)
        painter.restore()

        # 细描边
        painter.setPen(QColor(255, 255, 255, 36))
        painter.drawPath(path)


class NoticeCard(SimpleCardWidget):
    def __init__(self, notice_url):
        SimpleCardWidget.__init__(self)
        self.setBorderRadius(4)
        self.setFixedWidth(351)
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(3, 3, 0, 0)
        self.mainLayout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.notice_url = notice_url
        self.banners, self.banner_urls, self.posts = [], [], {"announces": [], "activities": [], "infos": []}
        self._banner_loader = None
        self._is_loading_banners = False

        # 自动滚动定时器
        self.auto_scroll_timer = QTimer()
        self.auto_scroll_timer.timeout.connect(self.scrollNext)
        self.auto_scroll_interval = 5000  # 5秒滚动一次
        self.auto_scroll_enabled = True

        # 初始化和显示
        self._create_components()
        self.setup_ui()
        self.show_skeleton()
        self.fetch_data()

        # 主题设置
        qconfig.themeChanged.connect(self._on_theme_changed)
        self.apply_theme_colors()
        self.update()

    def _create_components(self):
        """创建组件"""
        # 亚克力背景层
        palette = get_notice_theme_palette()
        self._acrylic = AcrylicBackground(self, radius=4, tint=palette['tint'])
        self._acrylic.stackUnder(self)

        # 骨架屏组件
        self.skeleton_banner = SkeletonBanner(self)
        self.skeleton_content = SkeletonContent(self)
        self.mainLayout.insertWidget(0, self.skeleton_banner)
        self.mainLayout.insertWidget(1, self.skeleton_content)

        self.error_label = QLabel("无法获取数据")
        self.error_label.setWordWrap(True)
        self.error_label.setObjectName("error")
        self.error_label.hide()
        self.mainLayout.addWidget(self.error_label)

    def _normalBackgroundColor(self):
        return QColor(255, 255, 255, 13)

    def show_skeleton(self):
        """显示骨架屏"""
        self.skeleton_banner.show()
        self.skeleton_content.show()
        # 确保骨架屏在最前面
        self.skeleton_banner.raise_()
        self.skeleton_content.raise_()

        for widget_name in ['bannerWithPips', 'pivot', 'stackedWidget']:
            if hasattr(self, widget_name):
                getattr(self, widget_name).hide()

    def hide_skeleton(self):
        """隐藏骨架屏"""
        self.skeleton_banner.hide()
        self.skeleton_content.hide()

        for widget_name in ['bannerWithPips', 'pivot', 'stackedWidget']:
            if hasattr(self, widget_name):
                getattr(self, widget_name).show()

    def fetch_data(self):
        self.fetcher = DataFetcher(url=self.notice_url)
        # 使用队列连接确保线程安全
        self.fetcher.data_fetched.connect(
            self.handle_data,
            Qt.ConnectionType.QueuedConnection
        )
        self.fetcher.start()

    def handle_data(self, content):
        if "error" in content:
            self.hide_skeleton()  # 隐藏骨架屏
            self.error_label.setText(f"无法获取数据: {content['error']}")
            self.error_label.setFixedSize(330, 160)
            self.error_label.show()
            if hasattr(self, 'bannerWithPips'):
                self.bannerWithPips.hide()
            self.update_ui()
            return
        self.load_banners_async(content["data"]["content"]["banners"])
        self.load_posts(content["data"]["content"]["posts"])
        self.error_label.hide()
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
        self._banner_loader.image_loaded.connect(self._on_banner_image_loaded,Qt.ConnectionType.QueuedConnection)
        self._banner_loader.all_images_loaded.connect(self._on_all_banners_loaded,Qt.ConnectionType.QueuedConnection)
        self._banner_loader.finished.connect(self._on_banner_loading_finished,Qt.ConnectionType.QueuedConnection)
        self._banner_loader.start()

    def _on_banner_image_loaded(self, pixmap: QPixmap, url: str):
        """单个banner图片加载完成的回调"""
        self.banners.append(pixmap)
        self.banner_urls.append(url)

        # 如果这是第一个加载完成的banner，隐藏骨架屏并显示内容
        if len(self.banners) == 1:
            self.hide_skeleton()

        # 实时更新UI显示新加载的图片 (单独添加，避免重复)
        if hasattr(self, 'bannerWithPips'):
            # 重新设置所有图片，因为BannerWithPips需要完整的图片列表
            self.bannerWithPips.clear()
            self.bannerWithPips.addImages(self.banners)

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
            if post_type := post_types.get(post["type"]):
                self.posts[post_type].append({
                    "title": post["title"],
                    "url": post["link"],
                    "date": post["date"]
                })

    def setup_ui(self):
        # 使用带嵌入式PipsPager的Banner容器
        self.bannerWithPips = BannerWithPips(radius=4, parent=self)
        self.bannerWithPips.addImages(self.banners)
        self.bannerWithPips.itemClicked.connect(self.open_banner_link)
        self.bannerWithPips.currentIndexChanged.connect(self._on_banner_index_changed)
        
        self.mainLayout.addWidget(self.bannerWithPips)

        # 启动自动滚动（延迟5秒开始）
        if len(self.banners) > 1:
            QTimer.singleShot(5000, self._start_auto_scroll)

        self.pivot = PhosPivot()
        self.stackedWidget = QStackedWidget(self)
        self.stackedWidget.setContentsMargins(0, 0, 5, 0)
        self.stackedWidget.setFixedHeight(60)

        # 创建三个列表组件
        widgets = [ListWidget() for _ in range(3)]
        self.activityWidget, self.announceWidget, self.infoWidget = widgets

        types = ["activities", "announces", "infos"]
        type_names = ["活动", "公告", "资讯"]

        for widget, post_type, name in zip(widgets, types, type_names):
            self.add_posts_to_widget(widget, post_type)
            widget.setItemDelegate(CustomListItemDelegate(widget))
            widget.itemClicked.connect(
                lambda _, w=widget, t=post_type: self.open_post_link(w, t)
            )
            self.addSubInterface(widget, post_type, name)

        self.stackedWidget.currentChanged.connect(self.onCurrentIndexChanged)
        self.stackedWidget.setCurrentWidget(self.activityWidget)
        self.pivot.setCurrentItem(self.activityWidget.objectName())
        self.mainLayout.addWidget(self.pivot, 0, Qt.AlignmentFlag.AlignLeft)
        self.mainLayout.addWidget(self.stackedWidget)

    def update_ui(self):
        # 更新banner显示
        if hasattr(self, 'bannerWithPips'):
            self.bannerWithPips.clear()
            self.bannerWithPips.addImages(self.banners)

        # 启动自动滚动
        if len(self.banners) > 1 and self.auto_scroll_enabled:
            self._start_auto_scroll()

        # 清空并重新添加posts
        widgets = [self.activityWidget, self.announceWidget, self.infoWidget]
        types = ["activities", "announces", "infos"]

        for widget, post_type in zip(widgets, types):
            widget.clear()
            self.add_posts_to_widget(widget, post_type)

    def apply_theme_colors(self):
        """在现有样式后附加文本颜色规则，确保覆盖资源 QSS。"""
        palette = get_notice_theme_palette()
        extra = (
            f"\nQWidget#title, QLabel#title{{color:{palette['title']} !important;}}"
            f"\nQWidget#date, QLabel#date{{color:{palette['date']} !important;}}\n"
        )
        self.setStyleSheet(self.styleSheet() + extra)

    def _on_theme_changed(self):
        if hasattr(self, '_acrylic'):
            self._acrylic.tint = get_notice_theme_palette()['tint']
            self._acrylic.update()
        self.apply_theme_colors()

    def scrollNext(self):
        if self.banners and hasattr(self, 'bannerWithPips'):
            current = self.bannerWithPips.currentIndex()
            next_index = (current + 1) % len(self.banners)
            self.bannerWithPips.setCurrentIndex(next_index)

    def _start_auto_scroll(self):
        """启动自动滚动"""
        if self.auto_scroll_enabled and len(self.banners) > 1:
            self.auto_scroll_timer.start(self.auto_scroll_interval)

    def _stop_auto_scroll(self):
        """停止自动滚动"""
        self.auto_scroll_timer.stop()

    def _pause_auto_scroll(self, duration=10000):
        """暂停自动滚动一段时间（用户交互时）"""
        self._stop_auto_scroll()
        if self.auto_scroll_enabled:
            QTimer.singleShot(duration, self._start_auto_scroll)

    def _on_banner_index_changed(self, index):
        """Banner页面改变时的回调（已由BannerWithPips内部处理同步）"""
        # PipsPager同步已在BannerWithPips内部处理，这里可以添加其他逻辑
        pass

    def _on_pips_index_changed(self, index):
        """PipsPager点击时切换Banner并暂停自动滚动（已由BannerWithPips内部处理）"""
        # Banner切换已在BannerWithPips内部处理
        self._pause_auto_scroll()  # 用户手动操作时暂停自动滚动

    def set_auto_scroll_enabled(self, enabled: bool):
        """设置自动滚动开关"""
        self.auto_scroll_enabled = enabled
        if enabled and len(self.banners) > 1:
            self._start_auto_scroll()
        else:
            self._stop_auto_scroll()

    def set_auto_scroll_interval(self, interval: int):
        """设置自动滚动间隔（毫秒）"""
        self.auto_scroll_interval = interval
        if self.auto_scroll_timer.isActive():
            self._stop_auto_scroll()
            self._start_auto_scroll()

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

    def resizeEvent(self, event):
        # 背景层充满圆角卡片
        if hasattr(self, '_acrylic') and self._acrylic:
            self._acrylic.setGeometry(self.rect())
        return SimpleCardWidget.resizeEvent(self, event)

    def open_banner_link(self):
        if self.banner_urls and hasattr(self, 'bannerWithPips'):
            current_index = self.bannerWithPips.currentIndex()
            if current_index < len(self.banner_urls):
                webbrowser.open(self.banner_urls[current_index])

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

        date_label = QLabel(post["date"])
        date_label.setObjectName("date")
        date_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        date_label.setFont(QFont("Microsoft YaHei", 10))

        layout.addWidget(title_label)
        layout.addWidget(date_label)

        layout.setStretch(0, 1)
        layout.setStretch(1, 0)
        return item_widget


class NoticeCardContainer(QWidget):
    """公告卡片容器 - 支持动态显示/隐藏，无需重启"""

    def __init__(self, notice_url, parent=None):
        super().__init__(parent)
        self.setObjectName("NoticeCardContainer")

        # 创建主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 创建公告卡片
        self.notice_card = NoticeCard(notice_url)
        OdQtStyleSheet.NOTICE_CARD.apply(self.notice_card)
        self.main_layout.addWidget(self.notice_card)

        # 给容器加外部阴影（阴影在卡片外侧）
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 12)
        shadow.setColor(get_notice_theme_palette()['shadow'])
        self.setGraphicsEffect(shadow)

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

    def set_auto_scroll_enabled(self, enabled: bool):
        """设置banner自动滚动"""
        if self.notice_card:
            self.notice_card.set_auto_scroll_enabled(enabled)

    def set_auto_scroll_interval(self, interval: int):
        """设置banner自动滚动间隔（毫秒）"""
        if self.notice_card:
            self.notice_card.set_auto_scroll_interval(interval)
