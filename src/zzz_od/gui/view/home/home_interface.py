import os
import requests
from datetime import datetime, timedelta
from PySide6.QtCore import Qt, QThread, Signal, QSize, QUrl, QTimer
from PySide6.QtWidgets import QGraphicsDropShadowEffect
from PySide6.QtGui import (
    QFont,
    QFontMetrics,
    QDesktopServices, QColor
)
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QSpacerItem,
    QSizePolicy,
    QWidget,
)
from qfluentwidgets import (
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    SimpleCardWidget,
    PrimaryPushButton,
)

from one_dragon.utils import os_utils
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

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.setBorderRadius(4)

        self.setFixedSize(56, 180)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 创建主页按钮
        home_button = IconButton(
            FluentIcon.HOME.icon(color=QColor("#fff")),
            tip_title="一条龙官网",
            tip_content="使用说明都能在这找到",
            isTooltip=True,
        )
        home_button.setIconSize(QSize(32, 32))
        home_button.clicked.connect(self.open_home)
        layout.addWidget(home_button)

        # 创建 GitHub 按钮
        github_button = IconButton(
            FluentIcon.GITHUB.icon(color=QColor("#fff")),
            tip_title="GitHub仓库",
            tip_content="如果本项目有帮助到您~\n不妨给项目点一个Star⭐",
            isTooltip=True,
        )
        github_button.setIconSize(QSize(32, 32))
        github_button.clicked.connect(self.open_github)
        layout.addWidget(github_button)

        # 创建 文档 按钮
        doc_button = IconButton(
            FluentIcon.LIBRARY.icon(color=QColor("#fff")),
            tip_title="自助排障文档",
            tip_content="点击打开自助排障文档,好孩子都能看懂",
            isTooltip=True,
        )
        doc_button.setIconSize(QSize(32, 32))
        doc_button.clicked.connect(self.open_doc)
        layout.addWidget(doc_button)

        # 创建 Q群 按钮
        doc_button = IconButton(
            FluentIcon.CHAT.icon(color=QColor("#fff")),
            tip_title="官方社群",
            tip_content="点击加入官方频道【一条龍】",
            isTooltip=True,
        )
        doc_button.setIconSize(QSize(32, 32))
        doc_button.clicked.connect(self.open_chat)
        layout.addWidget(doc_button)

        # 创建 官方店铺 按钮 (当然没有)
        doc_button = IconButton(
            FluentIcon.SHOPPING_CART.icon(color=QColor("#fff")),
            tip_title="官方店铺",
            tip_content="当然没有官方店铺,本软件完全免费, 速速加入官方社群!",
            isTooltip=True,
        )
        doc_button.setIconSize(QSize(32, 32))
        doc_button.clicked.connect(self.open_sales)
        layout.addWidget(doc_button)

        # 未完工区域, 暂时隐藏
        # # 添加一个可伸缩的空白区域
        # layout.addStretch()

        # # 创建 同步 按钮
        # sync_button = IconButton(
        #     FluentIcon.SYNC.icon(color=QColor("#fff")), tip_title="未完工", tip_content="开发中", isTooltip=True
        # )
        # sync_button.setIconSize(QSize(32, 32))
        # layout.addWidget(sync_button)

    def _normalBackgroundColor(self):
        return QColor(0, 0, 0, 96)

    def open_home(self):
        """打开主页链接"""
        QDesktopServices.openUrl(QUrl("https://one-dragon.com/zzz/zh/home.html"))

    def open_github(self):
        """打开 GitHub 链接"""
        QDesktopServices.openUrl(
            QUrl("https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon")
        )

    def open_chat(self):
        """打开 频道 链接"""
        QDesktopServices.openUrl(QUrl("https://pd.qq.com/s/fumylgkj4"))

    def open_doc(self):
        """打开 巡夜的金山文档 链接"""
        QDesktopServices.openUrl(QUrl("https://kdocs.cn/l/cbSJUUNotJ3Z"))

    def open_sales(self):
        """打开 Q群 链接"""
        QDesktopServices.openUrl(QUrl("https://qm.qq.com/q/N5iEy8sTu0"))

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
            if not self.wait(2000):  # 等待最多2秒
                log.warning(f"线程 {self.__class__.__name__} 无法正常退出，强制终止")
                self.terminate()
                self.wait(1000)  # 再等待1秒确保终止完成
                
    def is_stop_requested(self):
        """检查是否请求停止"""
        return not self._is_running


class CheckRunnerBase(BaseThread):
    """检查更新的基础线程类"""

    need_update = Signal(bool)

    def __init__(self, ctx: ZContext):
        super().__init__()
        self.ctx = ctx

class CheckCodeRunner(CheckRunnerBase):
    def _run_impl(self):
        if self.is_stop_requested():
            return
        is_latest, msg = self.ctx.git_service.is_current_branch_latest()
        if self.is_stop_requested():
            return
        if msg == "与远程分支不一致":
            self.need_update.emit(True)
        elif msg != "获取远程代码失败":
            self.need_update.emit(not is_latest)

class CheckModelRunner(CheckRunnerBase):
    def _run_impl(self):
        if self.is_stop_requested():
            return
        result = self.ctx.model_config.using_old_model()
        if not self.is_stop_requested():
            self.need_update.emit(result)

class CheckBannerRunner(CheckRunnerBase):
    def _run_impl(self):
        if self.is_stop_requested():
            return
        if self.ctx.signal.reload_banner:
            self.need_update.emit(True)

class BackgroundImageDownloader(BaseThread):
    """背景图片下载器"""
    image_downloaded = Signal(bool)

    def __init__(self, ctx: ZContext, download_type: str, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.download_type = download_type

        if download_type == "version_poster":
            self.save_path = os.path.join(os_utils.get_path_under_work_dir('assets', 'ui'), 'version_poster.webp')
            self.url = "https://hyp-api.mihoyo.com/hyp/hyp-connect/api/getGames?launcher_id=jGHBHlcOq1&language=zh-cn"
            self.config_key = f'last_{download_type}_fetch_time'
            self.error_msg = "版本海报异步获取失败"
        elif download_type == "remote_banner":
            self.save_path = os.path.join(os_utils.get_path_under_work_dir('assets', 'ui'), 'remote_banner.webp')
            self.url = "https://hyp-api.mihoyo.com/hyp/hyp-connect/api/getAllGameBasicInfo?launcher_id=jGHBHlcOq1&language=zh-cn"
            self.config_key = f'last_{download_type}_fetch_time'
            self.error_msg = "当前版本主页背景异步获取失败"

    def _run_impl(self):
        if not os.path.exists(self.save_path):
            self.get()

        # 检查是否被请求停止
        if self.is_stop_requested():
            return

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
        if not self._is_running or self.is_stop_requested():
            return

        try:
            resp = requests.get(self.url, timeout=5)
            data = resp.json()

            img_url = self._extract_image_url(data)
            if not img_url:
                return

            # 在开始下载图片前检查一次停止请求（因为网络下载可能耗时）
            if self.is_stop_requested():
                return

            img_resp = requests.get(img_url, timeout=5)
            if img_resp.status_code != 200:
                return

            self._save_image(img_resp.content)
            setattr(self.ctx.custom_config, self.config_key, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            # 使用队列连接确保线程安全
            self.image_downloaded.emit(True)

        except Exception as e:
            log.error(f"{self.error_msg}: {e}")

    def _extract_image_url(self, data):
        """提取图片URL"""
        if self.download_type == "version_poster":
            for game in data.get("data", {}).get("games", []):
                if game.get("biz") != "nap_cn":
                    continue

                display = game.get("display", {})
                background = display.get("background", {})
                if background:
                    return background.get("url")
        elif self.download_type == "remote_banner":
            for game in data.get("data", {}).get("game_info_list", []):
                if game.get("game", {}).get("biz") != "nap_cn":
                    continue

                backgrounds = game.get("backgrounds", [])
                if backgrounds:
                    return backgrounds[0]["background"]["url"]
        return None

    def _save_image(self, content):
        """保存图片"""
        temp_path = self.save_path + '.tmp'
        with open(temp_path, "wb") as f:
            f.write(content)
        if os.path.exists(self.save_path):
            os.remove(self.save_path)
        os.rename(temp_path, self.save_path)

class HomeInterface(VerticalScrollInterface):
    """主页界面"""

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx
        self.main_window = parent

        self._banner_widget = Banner(self.choose_banner_image())
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
        button_group = ButtonGroup()
        button_group.setMaximumHeight(320)
        h1_layout.addWidget(button_group)

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

        # 根据配置设置启用状态
        self.notice_container.set_notice_enabled(self.ctx.custom_config.notice_card)

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

    def __del__(self):
        """析构时清理资源"""
        try:
            self._cleanup_threads()
            if hasattr(self, 'notice_container') and self.notice_container:
                self.notice_container.cleanup_resources()
        except Exception:
            # 析构时忽略清理错误
            pass

    def _init_check_runners(self):
        """初始化检查更新的线程"""
        self._check_code_runner = CheckCodeRunner(self.ctx)
        self._check_code_runner.need_update.connect(
            self._need_to_update_code,
            Qt.ConnectionType.UniqueConnection
        )
        self._check_model_runner = CheckModelRunner(self.ctx)
        self._check_model_runner.need_update.connect(
            self._need_to_update_model,
            Qt.ConnectionType.UniqueConnection
        )
        self._check_banner_runner = CheckBannerRunner(self.ctx)
        self._check_banner_runner.need_update.connect(
            self.reload_banner,
            Qt.ConnectionType.UniqueConnection
        )
        self._banner_downloader = BackgroundImageDownloader(self.ctx, "remote_banner")
        # 使用队列连接确保线程安全
        self._banner_downloader.image_downloaded.connect(
            self.reload_banner,
            Qt.ConnectionType.UniqueConnection
        )
        self._version_poster_downloader = BackgroundImageDownloader(self.ctx, "version_poster")
        # 使用队列连接确保线程安全
        self._version_poster_downloader.image_downloaded.connect(
            self.reload_banner,
            Qt.ConnectionType.UniqueConnection
        )

    def closeEvent(self, event):
        """界面关闭事件处理"""
        self._cleanup_threads()
        # 清理公告卡片资源
        if hasattr(self, 'notice_container') and self.notice_container:
            self.notice_container.cleanup_resources()
        super().closeEvent(event)

    def _cleanup_threads(self):
        """清理所有线程"""
        thread_names = ['_banner_downloader', '_version_poster_downloader',
                       '_check_code_runner', '_check_model_runner', '_check_banner_runner']
        
        for thread_name in thread_names:
            if hasattr(self, thread_name):
                thread = getattr(self, thread_name)
                if thread and hasattr(thread, 'stop'):
                    thread.stop()
                    
    def _ensure_threads_stopped(self):
        """确保所有线程完全停止"""
        thread_names = ['_banner_downloader', '_version_poster_downloader',
                       '_check_code_runner', '_check_model_runner', '_check_banner_runner']
        
        for thread_name in thread_names:
            if hasattr(self, thread_name):
                thread = getattr(self, thread_name)
                if thread and thread.isRunning():
                    thread.stop()
                    # 等待线程完全停止
                    if thread.isRunning():
                        thread.wait(1000)  # 等待最多1秒

    def on_interface_shown(self) -> None:
        """界面显示时启动检查更新的线程"""
        super().on_interface_shown()
        
        # 先确保所有线程完全停止
        self._ensure_threads_stopped()
        
        # 安全启动检查线程
        if hasattr(self, '_check_code_runner') and not self._check_code_runner.isRunning():
            self._check_code_runner.start()
        if hasattr(self, '_check_model_runner') and not self._check_model_runner.isRunning():
            self._check_model_runner.start()
        if hasattr(self, '_check_banner_runner') and not self._check_banner_runner.isRunning():
            self._check_banner_runner.start()
            
        # 根据配置安全启动相应的背景下载器
        if self.ctx.custom_config.version_poster:
            if hasattr(self, '_version_poster_downloader') and not self._version_poster_downloader.isRunning():
                self._version_poster_downloader.start()
        elif self.ctx.custom_config.remote_banner:
            if hasattr(self, '_banner_downloader') and not self._banner_downloader.isRunning():
                self._banner_downloader.start()

        # 检查公告卡片配置是否变化
        self._check_notice_config_change()

        # 检查背景是否需要刷新
        self._check_banner_reload_signal()

        # 初始化主题色，避免navbar颜色闪烁
        self._update_start_button_style_from_banner()

    def on_interface_hidden(self) -> None:
        """界面隐藏时清理资源"""
        super().on_interface_hidden()
        
        # 停止所有线程
        self._cleanup_threads()
        
        # 清理公告卡片资源
        if hasattr(self, 'notice_container') and self.notice_container:
            self.notice_container.cleanup_resources()

    def _need_to_update_code(self, with_new: bool):
        if not with_new:
            self._show_info_bar("代码已是最新版本", "Enjoy it & have fun!")
            return
        else:
            self._show_info_bar("有新版本啦", "稍安勿躁~")

    def _need_to_update_model(self, with_new: bool):
        if with_new:
            self._show_info_bar("有新模型啦", "到[设置-模型选择]更新吧~", 5000)

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
            self._banner_widget.set_banner_image(self.choose_banner_image())
            # 依据背景重新计算按钮配色
            self._update_start_button_style_from_banner()
            self.ctx.signal.reload_banner = False
            if show_notification:
                self._show_info_bar("背景已更新", "新的背景已成功应用", 3000)
        except Exception as e:
            log.error(f"刷新背景时出错: {e}")

    def choose_banner_image(self) -> str:
        # 获取背景图片路径
        custom_banner_path = os.path.join(os_utils.get_path_under_work_dir('custom', 'assets', 'ui'), 'banner')
        version_poster_path = os.path.join(os_utils.get_path_under_work_dir('assets', 'ui'), 'version_poster.webp')
        remote_banner_path = os.path.join(os_utils.get_path_under_work_dir('assets', 'ui'), 'remote_banner.webp')
        index_banner_path = os.path.join(os_utils.get_path_under_work_dir('assets', 'ui'), 'index.png')

        # 主页背景优先级：自定义 > 远端 > index.png
        if self.ctx.custom_config.custom_banner and os.path.exists(custom_banner_path):
            banner_path = custom_banner_path
        elif self.ctx.custom_config.version_poster and os.path.exists(version_poster_path):
            banner_path = version_poster_path
        elif self.ctx.custom_config.remote_banner and os.path.exists(remote_banner_path):
            banner_path = remote_banner_path
        else:
            banner_path = index_banner_path

        return banner_path

    def _check_notice_config_change(self):
        """检查公告卡片配置是否发生变化"""
        if self.ctx.signal.notice_card_config_changed:
            current_config = self.ctx.custom_config.notice_card
            self.notice_container.set_notice_enabled(current_config)
            # 重置信号状态
            self.ctx.signal.notice_card_config_changed = False

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
        current_banner_path = self.choose_banner_image()
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
        if self.ctx.custom_config.is_custom_theme_color:
            return self.ctx.custom_config.theme_color

        current_banner_path = self.choose_banner_image()

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
        """处理从图片提取的颜色，增强鲜艳度和亮度"""
        # 增强颜色鲜艳度
        lr, lg, lb = ColorUtils.enhance_color_vibrancy(r, g, b)

        # 如果太暗则适当提亮
        lr, lg, lb = ColorUtils.brighten_if_too_dark(lr, lg, lb)

        return lr, lg, lb

    def _apply_button_style(self, theme_color: tuple[int, int, int]) -> None:
        """应用样式到启动按钮"""
        lr, lg, lb = theme_color
        text_color = ColorUtils.get_text_color_for_background(lr, lg, lb)

        # 本按钮局部样式：圆角为高度一半（胶囊形），背景从图取色
        radius = 24  # 固定按钮高度48px的一半，确保胶囊形状

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
        if cached_path != current_banner_path or not os.path.exists(current_banner_path):
            return False

        # 检查文件修改时间是否改变
        try:
            current_mtime = os.path.getmtime(current_banner_path)
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
            self.ctx.custom_config.theme_color_banner_mtime = os.path.getmtime(banner_path)
        except OSError:
            self.ctx.custom_config.theme_color_banner_mtime = 0.0
