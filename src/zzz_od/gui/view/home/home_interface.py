import contextlib
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

import requests
from PySide6.QtCore import QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QFontMetrics
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    PrimaryPushButton,
    SimpleCardWidget,
)

from one_dragon.base.config.custom_config import BackgroundTypeEnum
from one_dragon.utils import app_utils, os_utils
from one_dragon.utils.log_utils import log
from one_dragon_qt.services.theme_manager import ThemeManager
from one_dragon_qt.utils.color_utils import ColorUtils
from one_dragon_qt.widgets.banner import Banner
from one_dragon_qt.widgets.icon_button import IconButton
from one_dragon_qt.widgets.notice_card import NoticeCardContainer
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.context.zzz_context import ZContext


class ButtonGroup(SimpleCardWidget):
    """显示主页和 GitHub 按钮的竖直按钮组"""

    def __init__(self, ctx: ZContext, parent=None):
        super().__init__(parent=parent)
        self.ctx = ctx

        self.setBorderRadius(12)

        self.setFixedSize(70, 190)

        # 添加阴影效果
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 160))
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(8)  # 增加按钮间距
        layout.setContentsMargins(8, 8, 8, 8)  # 增加内边距

        # 存储按钮列表，用于自动提示演示
        self.buttons = []

        # 创建主页按钮
        home_button = IconButton(
            FluentIcon.HOME.icon(color=QColor("#fff")),
            tip_title="一条龙官网",
            tip_content="🏠一条龙软件说明书>>",
            isTooltip=True,
        )
        home_button.setIconSize(QSize(42, 42))
        home_button.clicked.connect(self.open_home)
        layout.addWidget(home_button)
        self.buttons.append(home_button)

        # 创建 GitHub 按钮
        github_button = IconButton(
            FluentIcon.GITHUB.icon(color=QColor("#fff")),
            tip_title="GitHub仓库",
            tip_content="⭐点击收藏关注项目动态",
            isTooltip=True,
        )
        github_button.setIconSize(QSize(42, 42))
        github_button.clicked.connect(self.open_github)
        layout.addWidget(github_button)
        self.buttons.append(github_button)

        # 创建 文档 按钮
        doc_button = IconButton(
            FluentIcon.LIBRARY.icon(color=QColor("#fff")),
            tip_title="自助排障文档",
            tip_content="📕遇到问题? 查看更详细文档教程",
            isTooltip=True,
        )
        doc_button.setIconSize(QSize(42, 42))
        doc_button.clicked.connect(self.open_doc)
        layout.addWidget(doc_button)
        self.buttons.append(doc_button)

        # 创建 频道 按钮
        chat_button = IconButton(
            FluentIcon.CHAT.icon(color=QColor("#fff")),
            tip_title="官方 社群",
            tip_content="🔥立刻点击加入火辣官方社区>>>>",
            isTooltip=True,
        )
        chat_button.setIconSize(QSize(42, 42))
        chat_button.clicked.connect(self.open_chat)
        layout.addWidget(chat_button)
        self.buttons.append(chat_button)

        # 创建 官方店铺 按钮 (当然没有)
        shop_button = IconButton(
            FluentIcon.SHOPPING_CART.icon(color=QColor("#fff")),
            tip_title="🏅官方店铺???",
            tip_content="💵限时劲爆特惠仅需0元点击马上加入会员>>",
            isTooltip=True,
        )
        shop_button.setIconSize(QSize(42, 42))
        shop_button.clicked.connect(self.open_sales)
        layout.addWidget(shop_button)
        self.buttons.append(shop_button)

        # 初始化自动提示定时器
        self.tooltip_timer = QTimer(self)
        self.tooltip_timer.timeout.connect(self._show_next_tooltip)
        self.tooltip_demo_active = False

        # 未完工区域, 暂时隐藏
        # # 添加一个可伸缩的空白区域
        # layout.addStretch()

        # # 创建 同步 按钮
        # sync_button = IconButton(
        #     FluentIcon.SYNC.icon(color=QColor("#fff")), tip_title="未完工", tip_content="开发中", isTooltip=True
        # )
        # sync_button.setIconSize(QSize(32, 32))
        # layout.addWidget(sync_button)

    def start_tooltip_demo(self):
        """启动自动提示演示"""
        if self.tooltip_demo_active:
            return

        self.tooltip_demo_active = True
        # 临时禁用所有按钮的鼠标悬停事件处理
        self._disable_buttons_hover()

        # 延迟2秒后同时显示所有提示（使用对象持有的单次定时器）
        if not hasattr(self, "_show_timer"):
            self._show_timer = QTimer(self)
            self._show_timer.setSingleShot(True)
            self._show_timer.timeout.connect(self._show_all_tooltips)
        if not hasattr(self, "_hide_timer"):
            self._hide_timer = QTimer(self)
            self._hide_timer.setSingleShot(True)
            self._hide_timer.timeout.connect(self._hide_all_tooltips)
        self._show_timer.start(2000)

    def _show_all_tooltips(self):
        """同时显示所有按钮的提示"""
        if not self.tooltip_demo_active:
            return

        # 同时显示所有按钮的提示（优先使用公开方法）
        for btn in self.buttons:
            show_fn = getattr(btn, "show_tooltip", None) or getattr(btn, "_show_tooltip", None)
            if callable(show_fn):
                show_fn()

        # 3秒后自动隐藏所有提示（对象级计时器，便于 stop 时取消）
        if hasattr(self, "_hide_timer"):
            self._hide_timer.start(3000)

    def _hide_all_tooltips(self):
        """隐藏所有按钮的提示"""
        for btn in self.buttons:
            hide_fn = getattr(btn, "hide_tooltip", None) or getattr(btn, "_hide_tooltip", None)
            if callable(hide_fn):
                hide_fn()
        self.tooltip_demo_active = False
        # 重新启用所有按钮的鼠标悬停事件处理
        self._enable_buttons_hover()

    def stop_tooltip_demo(self):
        """停止提示演示并立即隐藏所有提示"""
        self.tooltip_demo_active = False
        self.tooltip_timer.stop()
        if hasattr(self, "_show_timer"):
            self._show_timer.stop()
        if hasattr(self, "_hide_timer"):
            self._hide_timer.stop()
        self._hide_all_tooltips()

    def _disable_buttons_hover(self):
        """临时禁用所有按钮的鼠标悬停事件处理"""
        for btn in self.buttons:
            if hasattr(btn, 'removeEventFilter'):
                btn.removeEventFilter(btn)
                btn._hover_disabled = True

    def _enable_buttons_hover(self):
        """重新启用所有按钮的鼠标悬停事件处理"""
        for btn in self.buttons:
            if hasattr(btn, '_hover_disabled') and btn._hover_disabled:
                btn.installEventFilter(btn)
                btn._hover_disabled = False

    def _start_demo_timer(self):
        """开始演示定时器 - 不再使用，保留以兼容"""
        pass

    def _show_next_tooltip(self):
        """显示下一个按钮的提示 - 不再使用，保留以兼容"""
        pass

    def _normalBackgroundColor(self):
        # 使用更鲜艳的渐变背景，增强视觉效果
        return QColor(0, 0, 0, 140)  # 增加透明度使其更显眼

    def open_home(self):
        """打开主页链接"""
        QDesktopServices.openUrl(QUrl(self.ctx.project_config.home_page_link))

    def open_github(self):
        """打开 GitHub 链接"""
        QDesktopServices.openUrl(QUrl(self.ctx.project_config.github_homepage))

    def open_chat(self):
        """打开 频道 链接"""
        QDesktopServices.openUrl(QUrl(self.ctx.project_config.qq_link))

    def open_doc(self):
        """打开 腾讯文档 链接, 感谢历任薪王的付出 """
        QDesktopServices.openUrl(QUrl(self.ctx.project_config.doc_link))

    def open_sales(self):
        """打开 Q群 链接"""
        QDesktopServices.openUrl(QUrl(self.ctx.project_config.qq_link))

class BaseThread(QThread):
    """基础线程类，提供统一的 _is_running 管理"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_running = False

    def run(self):
        self._is_running = True
        try:
            self._run_impl()  # 子类实现具体逻辑
        finally:
            self._is_running = False

    def _run_impl(self):
        """子类需要实现的具体逻辑"""
        raise NotImplementedError

    def stop(self):
        """安全停止线程"""
        self._is_running = False
        if self.isRunning():
            self.quit()
            self.wait(3000)  # 等待最多3秒
            if self.isRunning():
                self.terminate()
                self.wait()


class CheckRunner(BaseThread):
    """通用的检查更新线程"""

    need_update = Signal(bool)

    def __init__(self, ctx: ZContext, check_func: Callable[[ZContext], bool], parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.check_func = check_func

    def _run_impl(self):
        try:
            self.need_update.emit(self.check_func(self.ctx))
        except Exception as e:
            log.error(f"Check runner failed: {e}")

class BackgroundImageDownloader(BaseThread):
    """背景图片下载器"""
    image_downloaded = Signal(bool)
    download_starting = Signal()

    def __init__(self, ctx: ZContext, download_type: str, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.download_type = download_type

        ui_dir = Path(os_utils.get_path_under_work_dir('assets', 'ui'))

        if download_type == "version_poster":
            self.save_path = ui_dir / 'version_poster.webp'
            self.url = "https://hyp-api.mihoyo.com/hyp/hyp-connect/api/getGames?launcher_id=jGHBHlcOq1&language=zh-cn"
            self.config_key = f'last_{download_type}_fetch_time'
            self.error_msg = "版本海报异步获取失败"
        elif download_type == "static_background":
            self.save_path = ui_dir / 'static_background.webp'
            self.url = "https://hyp-api.mihoyo.com/hyp/hyp-connect/api/getAllGameBasicInfo?launcher_id=jGHBHlcOq1&language=zh-cn"
            self.config_key = f'last_{download_type}_fetch_time'
            self.error_msg = "静态背景异步获取失败"
        elif download_type == "dynamic_background":
            self.save_path = ui_dir / 'dynamic_background.webm'
            self.url = "https://hyp-api.mihoyo.com/hyp/hyp-connect/api/getAllGameBasicInfo?launcher_id=jGHBHlcOq1&language=zh-cn"
            self.config_key = f'last_{download_type}_fetch_time'
            self.error_msg = "动态背景异步获取失败"

    def _run_impl(self):
        if not self.save_path.exists():
            self.get()

        last_fetch_time_str = getattr(self.ctx.custom_config, self.config_key)
        if last_fetch_time_str:
            try:
                last_fetch_time = datetime.strptime(last_fetch_time_str, '%Y-%m-%d %H:%M:%S')
                if datetime.now() - last_fetch_time >= timedelta(days=1):
                    self.get()
            except ValueError:
                self.get()
        else:
            self.get()

    def get(self):
        if not self._is_running:
            return

        success = False
        try:
            with requests.get(self.url, timeout=5) as resp:
                data = resp.json()

            result = self._extract_media_url(data)
            if not result:
                return

            # 动态背景使用流式下载避免内存溢出
            if self.download_type == "dynamic_background":
                success = self._download_dynamic_background_video(result)
            else:
                # 普通图片下载
                with requests.get(result, timeout=5) as img_resp:
                    if img_resp.status_code == 200:
                        self._save_image(img_resp.content)
                        success = True

            if success:
                setattr(self.ctx.custom_config, self.config_key, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                # 使用队列连接确保线程安全
                self.image_downloaded.emit(True)

        except Exception as e:
            log.error(f"{self.error_msg}: {e}")

    def _extract_media_url(self, data):
        """提取图片/视频URL"""
        if self.download_type == "version_poster":
            for game in data.get("data", {}).get("games", []):
                if game.get("biz") != "nap_cn":
                    continue

                display = game.get("display", {})
                background = display.get("background", {})
                if background:
                    return background.get("url")
        elif self.download_type == "static_background":
            for game in data.get("data", {}).get("game_info_list", []):
                if game.get("game", {}).get("biz") != "nap_cn":
                    continue

                backgrounds = game.get("backgrounds", [])
                if backgrounds:
                    return backgrounds[0]["background"]["url"]
        elif self.download_type == "dynamic_background":
            for game in data.get("data", {}).get("game_info_list", []):
                if game.get("game", {}).get("biz") != "nap_cn":
                    continue

                backgrounds = game.get("backgrounds", [])
                for bg in backgrounds:
                    if bg.get("type") == "BACKGROUND_TYPE_VIDEO":
                        video_url = bg.get("video", {}).get("url")
                        if video_url:
                            return video_url
        return None

    def _save_image(self, content: bytes):
        """保存图片，确保临时文件被正确清理"""
        temp_path: Path = self.save_path.with_suffix(self.save_path.suffix + '.tmp')
        try:
            with temp_path.open('wb') as f:
                f.write(content)
                f.flush()
            temp_path.replace(self.save_path)
        except Exception:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception as cleanup_err:
                    log.warning(f"清理临时文件失败: {cleanup_err}")
            raise

    def _download_dynamic_background_video(self, video_url: str) -> bool:
        """下载动态背景视频，确保取消时清理临时文件"""
        self.download_starting.emit()

        temp_path: Path = self.save_path.with_suffix(self.save_path.suffix + '.tmp')
        download_success = False
        cancelled = False
        status_ok = False

        try:
            with requests.get(video_url, stream=True, timeout=30) as r:
                try:
                    r.raise_for_status()
                    status_ok = True
                except Exception:
                    status_ok = False

                if status_ok:
                    with temp_path.open('wb') as f:
                        for chunk in r.iter_content(chunk_size=256 * 1024):
                            if not self._is_running:
                                cancelled = True
                                break
                            if chunk:
                                f.write(chunk)
                        if not cancelled:
                            f.flush()
                            download_success = True
        finally:
            if temp_path.exists() and not download_success:
                with contextlib.suppress(Exception):
                    temp_path.unlink()

        if not status_ok or cancelled or not download_success:
            return False

        try:
            temp_path.replace(self.save_path)
        except Exception:
            if temp_path.exists():
                with contextlib.suppress(Exception):
                    temp_path.unlink()
            raise

        return True

class HomeInterface(VerticalScrollInterface):
    """主页界面"""

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx
        self.main_window = parent

        self._banner_widget = Banner(self.choose_banner_media())
        self._banner_widget.set_percentage_size(0.8, 0.5)

        v_layout = QVBoxLayout(self._banner_widget)
        v_layout.setContentsMargins(20, 20, 20, 0)
        v_layout.setSpacing(5)
        v_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignJustify)

        # 空白占位符
        v_layout.addItem(QSpacerItem(10, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum))

        # 顶部部分 (按钮组)
        h1_layout = QHBoxLayout()
        h1_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 左边留白区域
        h1_layout.addStretch()

        # 按钮组
        self.button_group = ButtonGroup(self.ctx)
        self.button_group.setMaximumHeight(320)
        h1_layout.addWidget(self.button_group)

        # 空白占位符
        h1_layout.addItem(QSpacerItem(20, 10, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum))

        # 将顶部水平布局添加到垂直布局
        v_layout.addLayout(h1_layout)

        # 中间留白区域
        v_layout.addItem(QSpacerItem(10, 10, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum))
        v_layout.addStretch()

        # 底部部分 (公告卡片 + 启动按钮)
        bottom_bar = QWidget()
        h2_layout = QHBoxLayout(bottom_bar)
        h2_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)

        h2_layout.setContentsMargins(20, 20, 20, 20)  # 整体底部边距20px，包含阴影

        # 公告卡片
        self.notice_container = NoticeCardContainer(self.ctx.project_config.notice_url)
        notice_wrap = QWidget()
        self._notice_wrap_layout = QVBoxLayout(notice_wrap)
        self._notice_wrap_layout.setContentsMargins(0, 0, 0, 0)
        self._notice_wrap_layout.addWidget(self.notice_container)
        h2_layout.addWidget(notice_wrap)

        h2_layout.addStretch()

        # 启动游戏按钮布局
        self.start_button = PrimaryPushButton(text="启动一条龙🚀")
        self.start_button.setObjectName("start_button")
        self.start_button.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        # 动态计算宽度：文本宽度 + 左右内边距（约 48px）
        fm = QFontMetrics(self.start_button.font())
        text_width = fm.horizontalAdvance(self.start_button.text())
        self.start_button.setFixedSize(max(180, text_width + 48), 48)
        self.start_button.clicked.connect(self._on_start_game)

        # 按钮阴影
        shadow = QGraphicsDropShadowEffect(self.start_button)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.start_button.setGraphicsEffect(shadow)

        # @A-nony-mous 2025-08-15T03:50:00+01:00
        # noticecard的高度和启动一条龙按钮的高度 谁能修谁自己tm修吧我是修不明白了
        # 核心是阴影+到底部margin的高度=20px

        # 计算阴影向下扩展：min(20, max(0, offsetY + blurRadius/2))
        shadow_down_extent = max(0, int(8 + 24 / 2))  # 8 偏移 + 12 模糊半径的一半 ≈ 20
        shadow_down_extent = min(20, shadow_down_extent)
        # 20px = 阴影高度 + 阴影到底部的高度 ⇒ 按钮容器底边距 = 阴影高度

        # 与按钮对齐：提升公告卡片相同的底边距

        if hasattr(self, '_notice_wrap_layout'):
            self._notice_wrap_layout.setContentsMargins(0, 0, 0, shadow_down_extent)

        # 按钮容器，整体距离底部20px（包含阴影）
        button_container = QWidget()
        button_v_layout = QVBoxLayout(button_container)
        button_v_layout.setContentsMargins(0, 0, 0, shadow_down_extent)
        button_v_layout.addStretch()
        button_v_layout.addWidget(self.start_button, alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)

        h2_layout.addWidget(button_container)

        # 将底部容器添加到主垂直布局
        v_layout.addWidget(bottom_bar)

        # 初始化父类
        super().__init__(
            parent=parent,
            content_widget=self._banner_widget,
            object_name="home_interface",
            nav_text_cn="仪表盘",
            nav_icon=FluentIcon.HOME,
        )

        QTimer.singleShot(0, self._update_start_button_style_from_banner)

        self.ctx = ctx
        self._init_check_runners()

        # 监听背景刷新信号，确保主题色在背景变化时更新
        self._last_reload_banner_signal = False

        # 记录上次自动检查更新的时间
        self._last_auto_check_time = 0
        self._auto_check_interval = 300  # 5分钟冷却时间

    def _init_check_runners(self):
        """初始化检查更新的线程"""
        self._check_code_runner = CheckRunner(
            self.ctx,
            lambda ctx: not ctx.git_service.is_current_branch_latest()[0],
            self
        )
        self._check_code_runner.need_update.connect(
            self._need_to_update_code,
            Qt.ConnectionType.QueuedConnection
        )

        self._check_model_runner = CheckRunner(
            self.ctx,
            lambda ctx: ctx.model_config.using_old_model(),
            self
        )
        self._check_model_runner.need_update.connect(
            self._need_to_update_model,
            Qt.ConnectionType.QueuedConnection
        )

        def check_launcher_update(ctx: ZContext) -> bool:
            current_version = app_utils.get_launcher_version()
            latest_stable, latest_beta = ctx.git_service.get_latest_tag()

            # 根据当前版本是否包含 -beta 来确定比较通道
            if current_version and '-beta' in current_version:
                # 测试通道：与最新测试版比较；若不存在测试版，则和稳定版比较
                target_latest = latest_beta or latest_stable
            else:
                # 稳定通道：与最新稳定版比较；若不存在稳定版，则视为已最新
                target_latest = latest_stable or current_version

            return current_version != target_latest

        self._check_launcher_runner = CheckRunner(
            self.ctx,
            check_launcher_update,
            self
        )
        self._check_launcher_runner.need_update.connect(
            self._need_to_update_launcher,
            Qt.ConnectionType.QueuedConnection
        )

        self._check_banner_runner = CheckRunner(
            self.ctx,
            lambda ctx: ctx.signal.reload_banner,
            self
        )
        self._check_banner_runner.need_update.connect(
            self.reload_banner,
            Qt.ConnectionType.QueuedConnection
        )

        # 初始化背景下载器
        self._version_poster_downloader = BackgroundImageDownloader(self.ctx, "version_poster", self)
        self._version_poster_downloader.image_downloaded.connect(
            self.reload_banner,
            Qt.ConnectionType.QueuedConnection
        )

        self._static_background_downloader = BackgroundImageDownloader(self.ctx, "static_background", self)
        self._static_background_downloader.image_downloaded.connect(
            self.reload_banner,
            Qt.ConnectionType.QueuedConnection
        )

        self._dynamic_background_downloader = BackgroundImageDownloader(self.ctx, "dynamic_background", self)
        self._dynamic_background_downloader.image_downloaded.connect(
            self.reload_banner,
            Qt.ConnectionType.QueuedConnection
        )
        self._dynamic_background_downloader.download_starting.connect(
            self._on_dynamic_background_download_start,
            Qt.ConnectionType.BlockingQueuedConnection
        )

    def _on_dynamic_background_download_start(self) -> None:
        """在后台下载新的视频前释放当前播放器占用"""
        if not self._banner_widget:
            return

        if self.ctx.custom_config.background_type != BackgroundTypeEnum.DYNAMIC.value.value:
            return

        if hasattr(self._banner_widget, "release_media"):
            self._banner_widget.release_media()

    def on_interface_shown(self) -> None:
        """界面显示时启动检查更新的线程"""
        super().on_interface_shown()
        if self._banner_widget:
            self._banner_widget.resume_media()

        # 检查是否满足自动检查的冷却时间
        current_time = time.time()
        should_check = (current_time - self._last_auto_check_time) > self._auto_check_interval

        if should_check:
            if not self._check_code_runner.isRunning():
                self._check_code_runner.start()
            if not self._check_model_runner.isRunning():
                self._check_model_runner.start()
            if not self._check_launcher_runner.isRunning():
                self._check_launcher_runner.start()
            self._last_auto_check_time = current_time

        # Banner 刷新检查不需要冷却，因为它依赖信号
        if not self._check_banner_runner.isRunning():
            self._check_banner_runner.start()

        # 根据配置启动相应的背景下载器
        background_type = self.ctx.custom_config.background_type
        if background_type == BackgroundTypeEnum.VERSION_POSTER.value.value:
            if not self._version_poster_downloader.isRunning():
                self._version_poster_downloader.start()
        elif background_type == BackgroundTypeEnum.STATIC.value.value:
            if not self._static_background_downloader.isRunning():
                self._static_background_downloader.start()
        elif background_type == BackgroundTypeEnum.DYNAMIC.value.value:
            if not self._dynamic_background_downloader.isRunning():
                self._dynamic_background_downloader.start()

        # 检查背景是否需要刷新
        self._check_banner_reload_signal()

        # 初始化主题色，避免navbar颜色闪烁
        self._update_start_button_style_from_banner()

        # 启动导航栏按钮自动提示演示
        self.button_group.start_tooltip_demo()

    def on_interface_hidden(self) -> None:
        """界面隐藏时的处理"""
        super().on_interface_hidden()
        if self._banner_widget:
            self._banner_widget.pause_media()

        # 停止所有下载器，避免后台占用资源
        if self._version_poster_downloader.isRunning():
            self._version_poster_downloader.stop()
        if self._static_background_downloader.isRunning():
            self._static_background_downloader.stop()
        if self._dynamic_background_downloader.isRunning():
            self._dynamic_background_downloader.stop()

        # 立即停止并隐藏所有提示
        self.button_group.stop_tooltip_demo()

    def _need_to_update_code(self, with_new: bool):
        if not with_new:
            self._show_info_bar("代码已是最新版本", "Enjoy it & have fun!")
            return
        else:
            self._show_info_bar("有新版本啦", "稍安勿躁~")

    def _need_to_update_model(self, with_new: bool):
        if with_new:
            self._show_info_bar("有新模型啦", "到[设置-资源下载]更新吧~", 5000)

    def _need_to_update_launcher(self, with_new: bool):
        if with_new:
            self._show_info_bar("有新启动器啦", "到[设置-资源下载]更新吧~", 5000)

    def _show_info_bar(self, title: str, content: str, duration: int = 20000):
        """显示信息条"""
        InfoBar.success(
            title=title,
            content=content,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=duration,
            parent=self,
        ).setCustomBackgroundColor("white", "#202020")

    def _on_start_game(self):
        """启动一条龙按钮点击事件处理"""
        # app.py中一条龙界面为第三个添加的
        self.ctx.signal.start_onedragon = True
        one_dragon_interface = self.main_window.stackedWidget.widget(2)
        self.main_window.switchTo(one_dragon_interface)

    def reload_banner(self, show_notification: bool = False) -> None:
        """
        刷新主页背景显示
        :param show_notification: 是否显示提示
        :return:
        """
        # 检查widget是否仍然有效
        if not self._banner_widget or not self._banner_widget.isVisible():
            return

        try:
            # 强制清空主题色缓存，确保重新提取
            self._clear_theme_color_cache()

            # 更新背景图片
            self._banner_widget.set_media(self.choose_banner_media())
            # 依据背景重新计算按钮配色
            self._update_start_button_style_from_banner()
            self.ctx.signal.reload_banner = False
            if show_notification:
                self._show_info_bar("背景已更新", "新的背景已成功应用", 3000)
        except Exception as e:
            log.error(f"刷新背景时出错: {e}")

    def choose_banner_media(self) -> str:
        """选择主页背景媒体文件"""
        # 获取背景图片路径
        custom_banner_path = Path(os_utils.get_path_under_work_dir('custom', 'assets', 'ui')) / 'banner'
        ui_dir = Path(os_utils.get_path_under_work_dir('assets', 'ui'))
        version_poster_path = ui_dir / 'version_poster.webp'
        static_background_path = ui_dir / 'static_background.webp'
        dynamic_background_path = ui_dir / 'dynamic_background.webm'
        index_banner_path = ui_dir / 'index.png'

        # 主页背景优先级：自定义 > 枚举选项 > index.png
        # 检测自定义背景文件（支持图片和视频）
        if self.ctx.custom_config.custom_banner and custom_banner_path.exists() and custom_banner_path.is_file():
            return str(custom_banner_path)

        # 根据枚举类型选择背景
        background_type = self.ctx.custom_config.background_type
        if background_type == BackgroundTypeEnum.VERSION_POSTER.value.value and version_poster_path.exists():
            return str(version_poster_path)
        elif background_type == BackgroundTypeEnum.STATIC.value.value and static_background_path.exists():
            return str(static_background_path)
        elif background_type == BackgroundTypeEnum.DYNAMIC.value.value and dynamic_background_path.exists():
            return str(dynamic_background_path)
        else:
            return str(index_banner_path)

    def _check_banner_reload_signal(self):
        """检查背景重新加载信号"""
        if self.ctx.signal.reload_banner != self._last_reload_banner_signal:
            if self.ctx.signal.reload_banner:
                self._update_start_button_style_from_banner()
            self._last_reload_banner_signal = self.ctx.signal.reload_banner

    def _update_start_button_style_from_banner(self) -> None:
        """从当前背景取主色，应用到启动按钮。"""
        # 确保按钮存在
        if not hasattr(self, 'start_button'):
            log.debug("start_button 不存在，跳过样式更新")
            return

        # 检查是否能使用缓存
        current_banner_path = self.choose_banner_media()
        if self._can_use_cached_theme_color(current_banner_path):
            log.debug(f"使用缓存的主题色，跳过样式更新: {current_banner_path}")
            return

        # 获取主题色
        theme_color = self._get_theme_color()
        self.ctx.custom_config.theme_color = theme_color

        # 更新全局主题色
        ThemeManager.set_theme_color(theme_color)

        # 应用按钮样式
        self._apply_button_style(theme_color)

    def _get_theme_color(self) -> tuple[int, int, int]:
        """获取主题色，优先使用缓存，否则从图片提取"""
        # 如果是自定义模式，直接返回自定义颜色
        if self.ctx.custom_config.custom_theme_color:
            return self.ctx.custom_config.theme_color

        current_banner_path = self.choose_banner_media()

        # 检查是否能使用缓存的主题色
        if self._can_use_cached_theme_color(current_banner_path):
            lr, lg, lb = self.ctx.custom_config.theme_color
            log.debug(f"使用缓存的主题色: ({lr}, {lg}, {lb})")
            return lr, lg, lb

        # 背景图片改变了，需要重新提取颜色
        theme_color = self._extract_color_from_image()

        # 更新缓存
        self._update_theme_color_cache(current_banner_path)

        return theme_color

    def _extract_color_from_image(self) -> tuple[int, int, int]:
        """从背景图片提取主题色"""
        image = self._banner_widget.banner_image
        log.debug(f"图片状态: image={image is not None}, isNull={image.isNull() if image else 'N/A'}")

        if image is None or image.isNull():
            log.debug("使用默认蓝色主题")
            return 64, 158, 255  # 默认蓝色

        # 取右下角区域的平均色，代表按钮附近背景
        w, h = image.width(), image.height()
        x0 = int(w * 0.65)
        y0 = int(h * 0.65)
        x1, y1 = w, h

        # 提取区域平均颜色
        r, g, b = ColorUtils.extract_average_color_from_region(image, x0, y0, x1, y1)

        if r == 64 and g == 158 and b == 255:  # 如果返回默认色，说明提取失败
            log.debug("无法从图片获取颜色，使用默认蓝色")
            return r, g, b

        # 处理提取的颜色
        return self._process_extracted_color(r, g, b)

    def _process_extracted_color(self, r: int, g: int, b: int) -> tuple[int, int, int]:
        """处理从图片提取的颜色，增强鲜艳度和亮度，并限制在舒适的范围内"""
        # 增强颜色鲜艳度
        lr, lg, lb = ColorUtils.enhance_color_vibrancy(r, g, b)

        # 如果太暗则适当提亮
        lr, lg, lb = ColorUtils.brighten_if_too_dark(lr, lg, lb)

        # 限制颜色强度，避免过于鲜艳，保持人眼舒适度
        lr, lg, lb = ColorUtils.limit_color_intensity(lr, lg, lb)

        return lr, lg, lb

    def _apply_button_style(self, theme_color: tuple[int, int, int]) -> None:
        """应用样式到启动按钮"""
        lr, lg, lb = theme_color
        text_color = ColorUtils.get_text_color_for_background(lr, lg, lb)

        # 本按钮局部样式：圆角与主页按钮组统一为12px，背景从图取色
        radius = 12  # 与ButtonGroup保持一致的圆角

        style_sheet = f"""
        background-color: rgb({lr}, {lg}, {lb});
        color: {text_color};
        border-radius: {radius}px;
        border: none;
        font-weight: bold;
        margin: 0px;
        padding: 0px;
        """
        self.start_button.setStyleSheet(style_sheet)

    def _clear_theme_color_cache(self) -> None:
        """清空主题色缓存"""
        self.ctx.custom_config.theme_color_banner_path = ''
        self.ctx.custom_config.theme_color_banner_mtime = 0.0

    def _can_use_cached_theme_color(self, current_banner_path: str) -> bool:
        """检查是否可以使用缓存的主题色"""
        cached_path = self.ctx.custom_config.theme_color_banner_path
        current_path = Path(current_banner_path)

        if cached_path != current_banner_path or not current_path.exists():
            return False

        # 检查文件修改时间是否改变
        try:
            current_mtime = current_path.stat().st_mtime
            cached_mtime = self.ctx.custom_config.theme_color_banner_mtime

            if current_mtime != cached_mtime:
                # 文件已被修改，不能使用缓存
                return False

        except OSError:
            # 无法获取文件时间戳，为安全起见不使用缓存
            return False

        return True

    def _update_theme_color_cache(self, banner_path: str) -> None:
        """更新主题色缓存"""
        self.ctx.custom_config.theme_color_banner_path = banner_path
        try:
            self.ctx.custom_config.theme_color_banner_mtime = Path(banner_path).stat().st_mtime
        except OSError:
            self.ctx.custom_config.theme_color_banner_mtime = 0.0
