import builtins
import contextlib
import json
import os
import random
import time
import webbrowser

import requests
from PySide6.QtCore import QEvent, QModelIndex, QRect, QRectF, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QStackedWidget,
    QStyledItemDelegate,
    QStyle,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    HorizontalFlipView,
    ListWidget,
    PipsPager,
    PipsScrollButtonDisplayMode,
    SimpleCardWidget,
    Theme,
    qconfig,
)

from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log
from one_dragon_qt.services.styles_manager import OdQtStyleSheet
from one_dragon_qt.utils.image_utils import scale_pixmap_for_high_dpi
from one_dragon_qt.widgets.pivot import CustomListItemDelegate, PhosPivot

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
            'tint': QColor(18, 20, 30, 168),
            'title': '#f7f9ff',
            'date': '#d8e0f0',
            'shadow': QColor(0, 0, 0, 170),
        }
    # 主页公告卡统一使用深色玻璃风，避免亮底在浅色主题下影响可读性
    return {
        'tint': QColor(22, 24, 35, 160),
        'title': '#f2f6ff',
        'date': '#d2daea',
        'shadow': QColor(0, 0, 0, 150),
    }

class BannerImageLoader(QThread):
    """异步banner图片加载器"""
    image_loaded = Signal(QImage, str)  # image, url
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
                # 尝试从缓存加载图片
                cached_image = self._load_from_cache(banner["image"]["url"])
                if cached_image:
                    self.image_loaded.emit(cached_image, banner["image"]["link"])
                else:
                    # 从网络下载图片
                    response = requests.get(banner["image"]["url"], timeout=5)
                    if response.status_code == 200:
                        image = QImage.fromData(response.content)
                        # 保存到缓存
                        self._save_to_cache(banner["image"]["url"], response.content)
                        self.image_loaded.emit(image, banner["image"]["link"])
            except Exception as e:
                log.error(f"加载banner图片失败: {e}")

            self.loaded_count += 1

        self.all_images_loaded.emit()

    def _get_cache_filename(self, url: str) -> str:
        """根据URL生成缓存文件名"""
        import hashlib
        # 使用URL的MD5哈希作为文件名，保留原始扩展名
        url_hash = hashlib.md5(url.encode()).hexdigest()
        # 尝试从URL获取扩展名
        ext = url.split('.')[-1].lower()
        if ext in ['png', 'jpg', 'jpeg', 'webp', 'gif']:
            return f"{url_hash}.{ext}"
        else:
            return f"{url_hash}.png"  # 默认使用png扩展名

    def _get_cache_path(self, url: str) -> str:
        """获取缓存文件的完整路径"""
        cache_filename = self._get_cache_filename(url)
        return os.path.join(DataFetcher.CACHE_DIR, cache_filename)

    def _load_from_cache(self, url: str) -> QImage:
        """从缓存加载图片"""
        cache_path = self._get_cache_path(url)
        if os.path.exists(cache_path):
            # 检查缓存是否过期（使用与JSON缓存相同的过期时间）
            cache_mtime = os.path.getmtime(cache_path)
            if time.time() - cache_mtime < DataFetcher.CACHE_DURATION:
                try:
                    image = QImage(cache_path)
                    if not image.isNull():
                        log.debug(f"从缓存加载banner图片: {cache_path}")
                        return image
                except Exception as e:
                    log.error(f"从缓存加载图片失败: {e}")
        return None

    def _save_to_cache(self, url: str, image_data: bytes):
        """保存图片到缓存"""
        try:
            os.makedirs(DataFetcher.CACHE_DIR, exist_ok=True)
            cache_path = self._get_cache_path(url)
            # 使用临时文件确保原子性写入
            temp_path = cache_path + '.tmp'
            with open(temp_path, "wb") as f:
                f.write(image_data)
            # 原子性重命名
            if os.path.exists(cache_path):
                os.remove(cache_path)
            os.rename(temp_path, cache_path)
            log.debug(f"banner图片已缓存: {cache_path}")
        except Exception as e:
            log.error(f"保存banner图片到缓存失败: {e}")
            # 清理临时文件
            temp_path = self._get_cache_path(url) + '.tmp'
            if os.path.exists(temp_path):
                with contextlib.suppress(builtins.BaseException):
                    os.remove(temp_path)


class RoundedBannerView(HorizontalFlipView):
    """抗锯齿圆角 Banner 视图，避免 QRegion 掩膜造成的锯齿边缘"""

    def __init__(self, radius: int = 4, parent=None):
        super().__init__(parent)
        self._radius = radius
        self.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatioByExpanding)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        # 使用官方的 setBorderRadius 方法设置圆角
        self.setBorderRadius(radius)


# 增加了缓存机制, 有效期为3天, 避免每次都请求数据
# 调整了超时时间, 避免网络问题导致程序启动缓慢
class DataFetcher(QThread):
    data_fetched = Signal(dict)

    CACHE_DIR = os_utils.get_path_under_work_dir("notice_cache")
    CACHE_FILE = os.path.join(CACHE_DIR, "notice_cache.json")
    CACHE_DURATION = 259200  # 缓存时间为3天
    TIMEOUTNUM = 3  # 超时时间

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        # 确保缓存目录存在
        self.ensure_cache_dir()

        try:
            response = requests.get(self.url, timeout=DataFetcher.TIMEOUTNUM)
            response.raise_for_status()
            data = response.json()
            self.data_fetched.emit(data)
            self.save_cache(data)
            self.download_related_files(data)
        except requests.RequestException as e:
            if self.is_cache_valid():
                try:
                    with open(DataFetcher.CACHE_FILE, encoding="utf-8") as cache_file:
                        cached_data = json.load(cache_file)
                        self.data_fetched.emit(cached_data)
                except (FileNotFoundError, json.JSONDecodeError) as cache_error:
                    log.error(f"读取缓存文件失败: {cache_error}")
                    self.data_fetched.emit({"error": str(e)})
            else:
                self.data_fetched.emit({"error": str(e)})

    def ensure_cache_dir(self):
        """确保缓存目录存在"""
        try:
            os.makedirs(DataFetcher.CACHE_DIR, exist_ok=True)
            log.debug(f"缓存目录已确保存在: {DataFetcher.CACHE_DIR}")
        except Exception as e:
            log.error(f"创建缓存目录失败: {e}")

    def is_cache_valid(self):
        if not os.path.exists(DataFetcher.CACHE_FILE):
            return False
        try:
            cache_mtime = os.path.getmtime(DataFetcher.CACHE_FILE)
            return time.time() - cache_mtime < DataFetcher.CACHE_DURATION
        except OSError as e:
            log.error(f"检查缓存文件时间失败: {e}")
            return False

    def save_cache(self, data):
        try:
            self.ensure_cache_dir()
            with open(DataFetcher.CACHE_FILE, "w", encoding="utf-8") as cache_file:
                json.dump(data, cache_file, ensure_ascii=False, indent=2)
            log.debug(f"JSON缓存已保存: {DataFetcher.CACHE_FILE}")
        except Exception as e:
            log.error(f"保存JSON缓存失败: {e}")

    def download_related_files(self, data):
        for file_url in data.get("related_files", []):
            file_path = os.path.join(DataFetcher.CACHE_DIR, os.path.basename(file_url))
            try:
                self.ensure_cache_dir()
                response = requests.get(file_url, timeout=DataFetcher.TIMEOUTNUM)
                response.raise_for_status()
                with open(file_path, "wb") as file:
                    file.write(response.content)
                log.debug(f"相关文件已下载: {file_path}")
            except requests.RequestException as e:
                log.error(f"下载相关文件失败: {e}")
            except Exception as e:
                log.error(f"保存相关文件失败: {e}")


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
        self.setBorderRadius(8)
        self.setFixedSize(345, 374)  # 230 + 36 + 108 = 374
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)

        self.notice_url = notice_url
        self.banners, self.banner_urls, self.posts = [], [], {"announcements": [], "software_research": [], "game_guides": []}
        self._banner_loader = None
        self._is_loading_banners = False

        # 自动滚动定时器
        self.auto_scroll_timer = QTimer()
        self.auto_scroll_timer.timeout.connect(self.scrollNext)
        self.auto_scroll_interval = 5000  # 5秒滚动一次
        self.auto_scroll_enabled = True

        # 显示/隐藏状态
        self._notice_enabled = True

        # 应用样式
        OdQtStyleSheet.NOTICE_CARD.apply(self)

        # 初始化和显示
        self._create_components()
        self.setup_ui()
        self.fetch_data()

        # 主题设置
        qconfig.themeChanged.connect(self._on_theme_changed)
        self.apply_theme_colors()
        self.update()

    def set_notice_enabled(self, enabled: bool):
        """设置公告是否启用"""
        if self._notice_enabled == enabled:
            return

        self._notice_enabled = enabled
        self._apply_visibility_state()

    def _apply_visibility_state(self):
        """应用可见性状态"""
        if self._notice_enabled:
            self.show()
        else:
            self.hide()

    def _create_components(self):
        """创建组件"""
        # 亚克力背景层
        palette = get_notice_theme_palette()
        self._acrylic = AcrylicBackground(self, radius=8, tint=palette['tint'])
        self._acrylic.stackUnder(self)

    def _normalBackgroundColor(self):
        return QColor(0, 0, 0, 24)

    def fetch_data(self):
        # 如果已有fetcher在运行，先停止它
        if hasattr(self, 'fetcher') and self.fetcher is not None:
            if self.fetcher.isRunning():
                self.fetcher.quit()
                self.fetcher.wait()
            self.fetcher.deleteLater()

        self.fetcher = DataFetcher(url=self.notice_url, parent=self)
        # 使用队列连接确保线程安全
        self.fetcher.data_fetched.connect(
            self.handle_data,
            Qt.ConnectionType.QueuedConnection
        )
        self.fetcher.start()

    def handle_data(self, content):
        if "error" in content:
            self.update_ui()
            return
        self.load_banners_async(content["data"]["content"]["banners"])
        self.load_posts(content["data"]["content"]["posts"])
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

    def _on_banner_image_loaded(self, image: QImage, url: str):
        """单个banner图片加载完成的回调"""
        pixmap = QPixmap.fromImage(image)
        pixmap = scale_pixmap_for_high_dpi(
            pixmap,
            pixmap.size(),
            self.devicePixelRatioF(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
        )
        self.banners.append(pixmap)
        self.banner_urls.append(url)

        # 实时更新UI显示新加载的图片
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
            "POST_TYPE_ANNOUNCE": "announcements",
            "POST_TYPE_RESEARCHS": "software_research",
            "POST_TYPE_GUIDES": "game_guides",
        }
        for post in posts:
            if post_type := post_types.get(post["type"]):
                self.posts[post_type].append({
                    "title": post["title"],
                    "url": post["link"],
                    "date": post["date"]
                })

    def setup_ui(self):
        # Banner 视图容器 - 固定高度 230px
        self.banner_wrapper = QWidget()
        self.banner_wrapper.setFixedSize(QSize(345, 230))
        # 使其可追踪鼠标进入离开事件
        self.banner_wrapper.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.banner_wrapper.installEventFilter(self)
        banner_layout = QVBoxLayout(self.banner_wrapper)
        banner_layout.setContentsMargins(0, 0, 0, 0)
        banner_layout.setSpacing(0)

        # Banner 视图
        self.flipView = RoundedBannerView(radius=8)
        self.flipView.addImages(self.banners)
        self.flipView.setItemSize(QSize(345, 230))
        self.flipView.setFixedSize(QSize(345, 230))
        self.flipView.itemClicked.connect(self.open_banner_link)
        banner_layout.addWidget(self.flipView)

        # 监听 FlipView 的页面变化，用于同步 PipsPager
        self.flipView.currentIndexChanged.connect(self._on_banner_index_changed)

        # PipsPager - 页面指示器
        self.pipsPager = PipsPager(self.banner_wrapper)
        self.pipsPager.setPageNumber(len(self.banners) if self.banners else 1)
        self.pipsPager.setVisibleNumber(min(8, len(self.banners) if self.banners else 1))
        self.pipsPager.setNextButtonDisplayMode(PipsScrollButtonDisplayMode.NEVER)
        self.pipsPager.setPreviousButtonDisplayMode(PipsScrollButtonDisplayMode.NEVER)
        self.pipsPager.setCurrentIndex(0)
        self.pipsPager.currentIndexChanged.connect(self._on_pips_index_changed)

        # 外壳（带半透明背景与圆角）
        self.pipsHolder = QWidget(self.banner_wrapper)
        self.pipsHolder.setObjectName("pipsHolder")
        holder_layout = QHBoxLayout(self.pipsHolder)
        holder_layout.setContentsMargins(10, 4, 10, 4)
        holder_layout.setSpacing(6)
        holder_layout.addWidget(self.pipsPager)
        self.pipsHolder.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.pipsHolder.raise_()

        # 悬停显示/自动隐藏 定时器
        self._pips_hide_timer = QTimer(self)
        self._pips_hide_timer.setSingleShot(True)
        self._pips_hide_timer.timeout.connect(lambda: self.pipsHolder.hide())

        # 样式
        self._apply_pips_theme_style()
        # 初始默认隐藏 pips
        self.pipsHolder.hide()

        # 添加 banner 容器到主布局
        self.mainLayout.addWidget(self.banner_wrapper)
        self._update_pips_position()  # 初始定位

        # 启动自动滚动（延迟5秒开始）
        if len(self.banners) > 1:
            QTimer.singleShot(5000, self._start_auto_scroll)

        # Pivot 标签页 - 固定高度 36px
        self.pivot = PhosPivot()
        self.pivot.setFixedHeight(36)
        self.mainLayout.addWidget(self.pivot, 0, Qt.AlignmentFlag.AlignCenter)

        # StackedWidget 内容堆栈 - 固定高度 90px
        self.stackedWidget = QStackedWidget(self)
        self.stackedWidget.setContentsMargins(0, 0, 5, 0)
        self.stackedWidget.setFixedHeight(90)

        # 创建三个列表组件
        widgets = [ListWidget() for _ in range(3)]
        self.announcementsWidget, self.softwareResearchWidget, self.gameGuidesWidget = widgets

        types = ["announcements", "software_research", "game_guides"]
        type_names = ["公告要闻", "软件科研", "游戏攻略"]

        for widget, post_type, name in zip(widgets, types, type_names):
            widget.setSpacing(0)
            widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.add_posts_to_widget(widget, post_type)
            widget.itemClicked.connect(
                lambda _, w=widget, t=post_type: self.open_post_link(w, t)
            )
            self.addSubInterface(widget, post_type, name)

        self.stackedWidget.currentChanged.connect(self.onCurrentIndexChanged)
        self.stackedWidget.setCurrentWidget(self.announcementsWidget)
        self.pivot.setCurrentItem(self.announcementsWidget.objectName())
        self.mainLayout.addWidget(self.stackedWidget)

    def eventFilter(self, obj, event):
        # 悬停控制 pips 显示/隐藏
        if obj is getattr(self, 'banner_wrapper', None):
            et = event.type()
            if et in (QEvent.Type.Enter, QEvent.Type.HoverEnter):
                if hasattr(self, 'pipsHolder'):
                    self.pipsHolder.show()
                if hasattr(self, '_pips_hide_timer'):
                    self._pips_hide_timer.stop()
            elif et in (QEvent.Type.Leave, QEvent.Type.HoverLeave):
                if hasattr(self, '_pips_hide_timer'):
                    self._pips_hide_timer.start(5000)  # 5s 后隐藏
        return super().eventFilter(obj, event)

    def update_ui(self):
        # 清空现有内容，避免重复添加
        self.flipView.clear()
        self.flipView.addImages(self.banners)

        # 更新PipsPager
        if hasattr(self, 'pipsPager'):
            self.pipsPager.setPageNumber(len(self.banners) if self.banners else 1)
            self.pipsPager.setVisibleNumber(min(8, len(self.banners) if self.banners else 1))
            self.pipsPager.setCurrentIndex(0)
            # 尝试重新定位 pips（可能尺寸变化）
            if hasattr(self, '_update_pips_position'):
                QTimer.singleShot(0, self._update_pips_position)

        # 启动自动滚动
        if len(self.banners) > 1 and self.auto_scroll_enabled:
            self._start_auto_scroll()

        # 清空并重新添加posts
        widgets = [self.announcementsWidget, self.softwareResearchWidget, self.gameGuidesWidget]
        types = ["announcements", "software_research", "game_guides"]

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
        # 同步 pips holder 主题
        if hasattr(self, '_apply_pips_theme_style'):
            self._apply_pips_theme_style()

    def _apply_pips_theme_style(self):
        """根据当前主题应用 pipsHolder 样式（浅色白底+阴影，深色黑半透明）"""
        if not hasattr(self, 'pipsHolder'):
            return
        is_dark = qconfig.theme == Theme.DARK
        if is_dark:
            bg = 'rgba(0,0,0,110)'
            shadow = '0 0 0 0 rgba(0,0,0,0)'  # 不额外加
        else:
            # 白色半透明 + 轻投影增强可见性
            bg = 'rgba(255,255,255,180)'
            # 使用自定义阴影（通过盒阴影模拟，Qt 样式对 box-shadow 支持有限，退化为边框方案）
            shadow = "1px solid rgba(0,0,0,35)"
        # 采用边框方式模拟浅色模式下的描边
        self.pipsHolder.setStyleSheet(f"""
            QWidget#pipsHolder {{
                background: {bg};
                border-radius: 10px;
                border: {'none' if is_dark else shadow};
            }}
        """)

    def scrollNext(self):
        if self.banners:
            self.flipView.blockSignals(True)
            self.flipView.setCurrentIndex(
                (self.flipView.currentIndex() + 1) % len(self.banners)
            )
            self.flipView.blockSignals(False)

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
        """Banner页面改变时同步PipsPager"""
        if hasattr(self, 'pipsPager'):
            self.pipsPager.setCurrentIndex(index)

    def _on_pips_index_changed(self, index):
        """PipsPager点击时切换Banner并暂停自动滚动"""
        if hasattr(self, 'flipView') and index < len(self.banners):
            self.flipView.setCurrentIndex(index)
            self._pause_auto_scroll()  # 用户手动操作时暂停自动滚动

    def _update_pips_position(self):
        """在 banner 内部重新定位 pips 位置 (底部居中)"""
        if not hasattr(self, 'pipsHolder'):
            return
        # 尺寸自适应
        self.pipsHolder.adjustSize()
        bw = 345  # banner_wrapper 的固定宽度
        bh = 230  # banner_wrapper 的固定高度
        hw = self.pipsHolder.width()
        hh = self.pipsHolder.height()
        # 底部偏移量（可根据视觉微调）
        bottom_margin = 12
        x = (bw - hw) // 2
        y = bh - hh - bottom_margin
        self.pipsHolder.move(x, y)
        self.pipsHolder.raise_()

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
        # 更新 pips 位置
        if hasattr(self, '_update_pips_position'):
            self._update_pips_position()
        return SimpleCardWidget.resizeEvent(self, event)

    def open_banner_link(self):
        if self.banner_urls:
            webbrowser.open(self.banner_urls[self.flipView.currentIndex()])

    def open_post_link(self, widget: ListWidget, type: str):
        if self.posts[type]:
            webbrowser.open(self.posts[type][widget.currentIndex().row()]["url"])

    def add_posts_to_widget(self, widget: ListWidget, type: str):
        widget.setItemDelegate(NoticePostDelegate(widget))
        for post in self.posts[type][:3]:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.DisplayRole, post["title"])
            item.setData(Qt.ItemDataRole.UserRole, post["date"])
            widget.addItem(item)


class NoticePostDelegate(QStyledItemDelegate):
    """公告列表项代理 - 直接绘制，避免创建 widget"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.title_font = QFont("Microsoft YaHei", 10)
        self.date_font = QFont("Microsoft YaHei", 10)
        self._hover_row = -1

    def setHoverRow(self, row: int):
        """设置悬停行号（兼容 qfluentwidgets ListWidget）"""
        self._hover_row = row

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        # 初始化绘制选项
        painter.save()

        # 设置背景透明
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        # 获取数据
        title = index.data(Qt.ItemDataRole.DisplayRole)
        date = index.data(Qt.ItemDataRole.UserRole)

        # 计算布局
        rect = option.rect
        title_width = 220
        title_rect = QRect(rect.left() + 12, rect.top() + 2, title_width, rect.height() - 4)
        date_rect = QRect(title_rect.right(), rect.top() + 2, rect.width() - title_rect.right() - 12, rect.height() - 4)

        # 绘制标题（不使用省略号，让标题自然延伸）
        painter.setFont(self.title_font)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)

        # 绘制日期（后绘制，会覆盖延伸过来的标题文本）
        painter.setFont(self.date_font)
        painter.setPen(QColor("#dddddd"))
        painter.drawText(date_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, date)

        # 悬停效果
        if option.state & QStyle.StateFlag.State_MouseOver or index.row() == self._hover_row:
            painter.fillRect(rect, QColor(255, 255, 255, 20))

        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex):
        return QSize(330, 26)
