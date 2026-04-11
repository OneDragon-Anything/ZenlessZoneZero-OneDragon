import contextlib
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

import requests
from PySide6.QtCore import QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont
from PySide6.QtWidgets import (
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
    PillPushButton,
    setCustomStyleSheet,
)

from one_dragon.base.config.custom_config import BackgroundTypeEnum
from one_dragon.utils import app_utils, os_utils
from one_dragon.utils.log_utils import log
from one_dragon_qt.services.theme_manager import ThemeManager
from one_dragon_qt.utils.color_utils import get_foreground_color
from one_dragon_qt.utils.layout_utils import apply_shadow
from one_dragon_qt.widgets.banner import Banner
from one_dragon_qt.widgets.base_interface import BaseInterface
from one_dragon_qt.widgets.icon_button import IconButton
from one_dragon_qt.widgets.notice_card import NoticeCard
from zzz_od.context.zzz_context import ZContext


class ButtonGroup(QWidget):
    """显示主页和 GitHub 按钮的竖直按钮组"""

    def __init__(self, ctx: ZContext, parent=None):
        QWidget.__init__(self, parent=parent)
        self.ctx = ctx

        self.setFixedSize(70, 250)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(24)
        layout.setContentsMargins(8, 8, 8, 8)

        # 右侧按钮列表
        self.buttons = []

        # 创建主页按钮
        home_button = IconButton(
            FluentIcon.HOME.icon(color=QColor("#fff")),
            tip_title="官网",
            tip_content="使用说明 · 功能介绍",
            isTooltip=True,
        )
        home_button.setIconSize(QSize(30, 30))
        home_button.clicked.connect(self.open_home)
        layout.addWidget(home_button)
        self.buttons.append(home_button)

        # 创建 GitHub 按钮
        github_button = IconButton(
            FluentIcon.GITHUB.icon(color=QColor("#fff")),
            tip_title="GitHub",
            tip_content="源码 · 反馈 · Star⭐",
            isTooltip=True,
        )
        github_button.setIconSize(QSize(30, 30))
        github_button.clicked.connect(self.open_github)
        layout.addWidget(github_button)
        self.buttons.append(github_button)

        # 创建 文档 按钮
        doc_button = IconButton(
            FluentIcon.LIBRARY.icon(color=QColor("#fff")),
            tip_title="帮助文档",
            tip_content="遇到问题？点这里找答案",
            isTooltip=True,
        )
        doc_button.setIconSize(QSize(30, 30))
        doc_button.clicked.connect(self.open_doc)
        layout.addWidget(doc_button)
        self.buttons.append(doc_button)

        # 创建 频道 按钮
        chat_button = IconButton(
            FluentIcon.CHAT.icon(color=QColor("#fff")),
            tip_title="官方频道",
            tip_content="加入官方交流频道",
            isTooltip=True,
        )
        chat_button.setIconSize(QSize(30, 30))
        chat_button.clicked.connect(self.open_chat)
        layout.addWidget(chat_button)
        self.buttons.append(chat_button)


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

class HomeInterface(BaseInterface):
    """主页界面"""

    def __init__(self, ctx: ZContext, parent=None):
        # 初始化父类
        BaseInterface.__init__(
            self,
            object_name="home_interface",
            nav_text_cn="仪表盘",
            nav_icon=FluentIcon.HOME,
            parent=parent,
        )
        self.ctx: ZContext = ctx
        self.main_window = parent
        self._saved_area_margins = None

        # 监听背景刷新信号，确保主题色在背景变化时更新
        self._last_reload_banner_signal = False
        self._last_applied_theme_color: tuple[int, int, int] | None = None

        # 记录上次自动检查更新的时间
        self._last_auto_check_time = 0
        self._auto_check_interval = 300  # 5分钟冷却时间

        self._init_check_runners()
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self._banner_widget = Banner(self.choose_banner_media())
        main_layout.addWidget(self._banner_widget)

        v_layout = QVBoxLayout(self._banner_widget)
        # 边缘距离由子布局控制，避免与子布局叠加导致超过 16px
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(5)
        v_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignJustify)

        # 顶部留白 64px
        v_layout.addItem(QSpacerItem(10, 64, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum))

        # 底部区域 (公告卡片 + 启动按钮 + 按钮组)
        bottom_bar = QWidget()
        bottom_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        h2_layout = QHBoxLayout(bottom_bar)

        h2_layout.setContentsMargins(32, 32, 0, 32)

        # 公告卡片
        self.notice_container = NoticeCard(self.ctx.project_config.notice_url)
        apply_shadow(self.notice_container, blur=28, offset_x=0, offset_y=8, alpha=150)
        h2_layout.addWidget(self.notice_container, alignment=Qt.AlignmentFlag.AlignBottom)

        h2_layout.addStretch()

        # 启动游戏按钮布局
        self.start_button = PillPushButton(FluentIcon.PLAY_SOLID, '启动一条龙')
        self.start_button.setObjectName("start_button")
        self.start_button.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        self.start_button.setFixedHeight(48)
        self.start_button.setMinimumWidth(int(self.start_button.sizeHint().width() * 1.1))  # 加宽10%
        self.start_button.clicked.connect(self._on_start_game)
        apply_shadow(self.start_button, blur=24, offset_x=0, offset_y=6, alpha=140)

        # 设置图标和文本之间的间距
        if self.start_button.layout():
            self.start_button.layout().setSpacing(12)

        # 保存黑色和黄色图标
        self._black_icon = FluentIcon.PLAY_SOLID.icon(color=QColor("#000000"))
        self._yellow_icon = FluentIcon.PLAY_SOLID.icon(color=QColor("#FFDB29"))

        # 连接悬停事件
        self.start_button.enterEvent = self._on_button_enter
        self.start_button.leaveEvent = self._on_button_leave

        # 添加启动按钮到布局
        h2_layout.addWidget(self.start_button, alignment=Qt.AlignmentFlag.AlignBottom)

        # 按钮组
        self.button_group = ButtonGroup(self.ctx)
        self.button_group.setMaximumHeight(320)
        self._apply_button_group_shadows()
        h2_layout.addWidget(self.button_group, alignment=Qt.AlignmentFlag.AlignVCenter)

        # 将底部容器添加到主垂直布局
        v_layout.addWidget(bottom_bar)

        QTimer.singleShot(0, self._update_start_button_style_from_banner)

    def _apply_button_group_shadows(self) -> None:
        """给首页右侧悬浮图标加硬阴影，增强在复杂背景上的辨识度。"""
        for button in self.button_group.buttons:
            apply_shadow(button)

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

    def showEvent(self, event) -> None:
        """首次显示首页时立即应用标题栏样式，避免需要切页后才生效。"""
        QWidget.showEvent(self, event)
        self._set_title_bar_home_mode(True)

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

        # 设置顶部边距为0，让海报覆盖标题栏；同时切换标题栏首页模式
        if self.main_window:
            if self._saved_area_margins is None:
                self._saved_area_margins = self.main_window.areaLayout.contentsMargins()
            self.main_window.areaLayout.setContentsMargins(0, 0, 0, 0)
            self._set_title_bar_home_mode(True)

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

    def on_interface_leave(self) -> None:
        """视觉切换前恢复 margin 和标题栏，避免新页面闪烁旧样式。"""
        if self.main_window and self._saved_area_margins is not None:
            self.main_window.areaLayout.setContentsMargins(self._saved_area_margins)
            self._saved_area_margins = None
            self._set_title_bar_home_mode(False)

    def on_interface_hidden(self) -> None:
        """界面隐藏时的清理工作"""
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
        """显示信息条（手动定位，避免标题栏遮挡）"""
        bar = InfoBar.success(
            title=title,
            content=content,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.NONE,
            duration=duration,
            parent=self,
        )
        bar.setCustomBackgroundColor("white", "#202020")
        bar.move(self.width() - bar.width() - 24, 48)
        bar.show()

    def _on_start_game(self):
        """启动一条龙按钮点击事件处理"""
        # app.py中一条龙界面为第三个添加的
        self.ctx.signal.start_onedragon = True
        one_dragon_interface = self.main_window.stackedWidget.widget(2)
        self.main_window.switchTo(one_dragon_interface)

    def _on_button_enter(self, event):
        """按钮悬停事件"""
        self.start_button.setIcon(self._yellow_icon)
        # 调用父类的 enterEvent
        PillPushButton.enterEvent(self.start_button, event)

    def _on_button_leave(self, event):
        """按钮离开悬停事件"""
        self.start_button.setIcon(self._black_icon)
        # 调用父类的 leaveEvent
        PillPushButton.leaveEvent(self.start_button, event)

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
            # 更新背景图片（Banner.set_media 会自动重新提取主题色）
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
        if not hasattr(self, 'start_button'):
            return

        theme_color = self._get_theme_color()

        # 跳过未变化的主题色
        if theme_color == self._last_applied_theme_color:
            return
        self._last_applied_theme_color = theme_color

        self.ctx.custom_config.theme_color = theme_color
        ThemeManager.set_theme_color(theme_color)
        self._apply_button_style(theme_color)

    def _set_title_bar_home_mode(self, enable: bool) -> None:
        """切换标题栏首页模式。启用时额外检查当前页是否为首页，避免误伤其他页面。"""
        if not self.main_window or not hasattr(self.main_window, "titleBar"):
            return
        if enable:
            if not hasattr(self.main_window, "stackedWidget"):
                return
            if self.main_window.stackedWidget.currentWidget() is not self:
                return
        self.main_window.titleBar.set_home_mode(enable)

    def _get_theme_color(self) -> tuple[int, int, int]:
        """获取主题色，优先使用自定义颜色，否则从 Banner 读取"""
        if self.ctx.custom_config.custom_theme_color:
            return self.ctx.custom_config.theme_color

        return self._banner_widget.theme_color

    def _apply_button_style(self, theme_color: tuple[int, int, int]) -> None:
        """应用样式到启动按钮"""
        r, g, b = theme_color
        foreground = get_foreground_color(r, g, b)
        theme_bg = f"rgb({r}, {g}, {b})"
        hover_bg = foreground

        self._black_icon = FluentIcon.PLAY_SOLID.icon(color=QColor(foreground))
        self._yellow_icon = FluentIcon.PLAY_SOLID.icon(color=QColor(r, g, b))
        self.start_button.setIcon(self._black_icon)

        # 使用 setCustomStyleSheet 而不是 setStyleSheet，避免破坏按钮的内部布局
        qss = f"""
        PillPushButton#start_button {{
            background-color: {theme_bg};
            color: {foreground};
            border-radius: 28px;
            height: 48px;
            min-height: 48px;
        }}
        PillPushButton#start_button:hover {{
            background-color: {hover_bg};
            color: {theme_bg};
        }}
        """
        setCustomStyleSheet(self.start_button, qss, qss)
