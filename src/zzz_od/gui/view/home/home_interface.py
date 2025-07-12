import os
import requests
from datetime import datetime, timedelta
from PySide6.QtCore import Qt, QThread, Signal, QSize, QUrl
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
    QApplication,
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
from one_dragon_qt.services.styles_manager import OdQtStyleSheet
from one_dragon_qt.widgets.banner import Banner
from one_dragon_qt.widgets.icon_button import IconButton
from one_dragon_qt.widgets.notice_card import NoticeCardContainer
from one_dragon_qt.widgets.vertical_scroll_interface import (
    VerticalScrollInterface,
)
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
            tip_content="加入官方群聊【绝区零&一条龙交流群】",
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
        """打开 Q群 链接"""
        QDesktopServices.openUrl(QUrl("https://qm.qq.com/q/N5iEy8sTu0"))

    def open_doc(self):
        """打开 巡夜的金山文档 链接"""
        QDesktopServices.openUrl(QUrl("https://kdocs.cn/l/cbSJUUNotJ3Z"))

    def open_sales(self):
        """其实还是打开 Q群 链接"""
        QDesktopServices.openUrl(QUrl("https://qm.qq.com/q/N5iEy8sTu0"))

class CheckRunnerBase(QThread):
    """检查更新的基础线程类"""

    need_update = Signal(bool)

    def __init__(self, ctx: ZContext):
        super().__init__()
        self.ctx = ctx

class CheckCodeRunner(CheckRunnerBase):
    def run(self):
        is_latest, msg = self.ctx.git_service.is_current_branch_latest()
        if msg == "与远程分支不一致":
            self.need_update.emit(True)
        elif msg != "获取远程代码失败":
            self.need_update.emit(not is_latest)

class CheckModelRunner(CheckRunnerBase):
    def run(self):
        self.need_update.emit(self.ctx.model_config.using_old_model())

class CheckBannerRunner(CheckRunnerBase):
    def run(self):
        if self.ctx.signal.reload_banner:
            self.need_update.emit(True)

class BackgroundImageDownloader(QThread):
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

    def run(self):
        if not os.path.exists(self.save_path):
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
        try:
            resp = requests.get(self.url, timeout=5)
            data = resp.json()

            img_url = self._extract_image_url(data)
            if not img_url:
                return

            img_resp = requests.get(img_url, timeout=5)
            if img_resp.status_code != 200:
                return

            self._save_image(img_resp.content)
            setattr(self.ctx.custom_config, self.config_key, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
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

        # 添加标志位，防止重复运行检查线程
        self._first_time_shown = True
        # 标记是否已经检查过更新（启动时检查一次即可）
        self._has_checked_updates = False

        self._banner_widget = Banner(self.choose_banner_image())
        self._banner_widget.set_percentage_size(0.8, 0.5)

        v_layout = QVBoxLayout(self._banner_widget)
        v_layout.setContentsMargins(0, 0, 0, 15)
        v_layout.setSpacing(5)
        v_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

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
        h2_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        h2_layout.setContentsMargins(20, 0, 20, 0)

        # 公告卡片
        self.notice_container = NoticeCardContainer()
        h2_layout.addWidget(self.notice_container)

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

        v1_layout = QVBoxLayout()
        v1_layout.setContentsMargins(0, 0, 0, 0)
        v1_layout.addWidget(self.start_button, alignment=Qt.AlignmentFlag.AlignBottom)

        h2_layout.addLayout(v1_layout)

        # 底部保持约 1cm 间距
        screen = QApplication.primaryScreen()
        dpi = screen.logicalDotsPerInch() if screen else 96
        one_cm_px = max(0, int(dpi / 2.54))
        v_layout.setContentsMargins(0, 0, 0, one_cm_px)

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

        # 应用样式
        OdQtStyleSheet.GAME_BUTTON.apply(self.start_button)
        self._update_start_button_style_from_banner()

        self.ctx = ctx
        self._init_check_runners()

        # 监听背景刷新信号，确保主题色在背景变化时更新
        self._last_reload_banner_signal = False

    def _init_check_runners(self):
        """初始化检查更新的线程"""
        self._check_code_runner = CheckCodeRunner(self.ctx)
        self._check_code_runner.need_update.connect(self._need_to_update_code)
        self._check_model_runner = CheckModelRunner(self.ctx)
        self._check_model_runner.need_update.connect(self._need_to_update_model)
        self._check_banner_runner = CheckBannerRunner(self.ctx)
        self._check_banner_runner.need_update.connect(self._reload_banner_silent)
        self._banner_downloader = BackgroundImageDownloader(self.ctx, "remote_banner")
        self._banner_downloader.image_downloaded.connect(self._reload_banner_silent)
        self._version_poster_downloader = BackgroundImageDownloader(self.ctx, "version_poster")
        self._version_poster_downloader.image_downloaded.connect(self._reload_banner_silent)

    def _reload_banner_silent(self, *args):
        """静默重新加载背景，不显示通知（自动更新）"""
        self.reload_banner(user_triggered=False)

    def on_interface_shown(self) -> None:
        """界面显示时启动检查更新的线程"""
        super().on_interface_shown()

        # 检查更新：首次显示时或者还没检查过更新时
        if not self._has_checked_updates:
            self._check_code_runner.start()
            self._check_model_runner.start()
            self._has_checked_updates = True

        # 背景相关检查：只在首次显示时运行
        if self._first_time_shown:
            self._check_banner_runner.start()
            # 根据配置启动相应的背景下载器
            if self.ctx.custom_config.version_poster:
                self._version_poster_downloader.start()
            elif self.ctx.custom_config.remote_banner:
                self._banner_downloader.start()
            self._first_time_shown = False

        # 检查公告卡片配置是否变化
        self._check_notice_config_change()

        # 检查背景是否需要刷新
        self._check_banner_reload_signal()

        # 初始化主题色，避免navbar颜色闪烁
        self._update_start_button_style_from_banner()

    def _need_to_update_code(self, with_new: bool):
        if not with_new:
            self._show_info_bar("代码已是最新版本", "Enjoy it & have fun!")
            return
        else:
            self._show_info_bar("有新版本啦", "稍安勿躁~")

    def _need_to_update_model(self, with_new: bool):
        if with_new:
            self._show_info_bar("有新模型啦", "到[设置-资源下载]更新吧~", 5000)

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
        self.ctx.signal.start_onedragon = True

        for i in range(self.main_window.stackedWidget.count()):
            widget = self.main_window.stackedWidget.widget(i)
            if widget.objectName() == "one_dragon_interface":
                self.main_window.switchTo(widget)
                break

    def reload_banner(self, user_triggered: bool = False) -> None:
        """
        刷新主页背景显示
        :param user_triggered: 是否为用户主动触发的更新
        :return:
        """
        # 更新背景图片
        self._banner_widget.set_banner_image(self.choose_banner_image())
        # 依据背景重新计算按钮配色
        self._update_start_button_style_from_banner()
        self.ctx.signal.reload_banner = False
        # 只有用户主动触发时才显示通知
        if user_triggered:
            self._show_info_bar("背景已更新", "新的背景已成功应用", 3000)

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
        image = self._banner_widget.banner_image
        if image is None or image.isNull() or not hasattr(self, 'start_button'):
            return

        # 取右下角区域的平均色，代表按钮附近背景
        w, h = image.width(), image.height()
        x0 = int(w * 0.65)
        y0 = int(h * 0.65)
        x1 = w
        y1 = h

        r_sum = g_sum = b_sum = count = 0
        for y in range(y0, y1, max(1, (y1 - y0) // 64)):
            for x in range(x0, x1, max(1, (x1 - x0) // 64)):
                c = image.pixelColor(x, y)
                r_sum += c.red()
                g_sum += c.green()
                b_sum += c.blue()
                count += 1
        if count == 0:
            return

        r = int(r_sum / count)
        g = int(g_sum / count)
        b = int(b_sum / count)

        base_color = QColor(r, g, b)
        h, s, v, a = base_color.getHsvF()
        if h < 0:  # 灰阶时 hue 可能为 -1
            h = 0.0
        s = min(1.0, s * 2.0 + 0.25)
        v = min(1.0, v * 1.08 + 0.06)
        vivid = QColor.fromHsvF(h, s, v, 1.0)
        lr, lg, lb = vivid.red(), vivid.green(), vivid.blue()

        # 若整体仍偏暗，小幅增加明度，避免洗白
        def luminance_of(rr: int, gg: int, bb: int) -> float:
            return 0.2126 * rr + 0.7152 * gg + 0.0722 * bb

        for _ in range(2):
            if luminance_of(lr, lg, lb) >= 160:
                break
            tmp = QColor(lr, lg, lb)
            th, ts, tv, ta = tmp.getHsvF()
            if th < 0:
                th = 0.0
            tv = min(1.0, tv + 0.10)
            tmp2 = QColor.fromHsvF(th, ts, tv, 1.0)
            lr, lg, lb = tmp2.red(), tmp2.green(), tmp2.blue()

        # 基于相对亮度选择文本色（黑/白）
        luminance = luminance_of(lr, lg, lb)
        text_color = "black" if luminance > 145 else "white"

        # 将提取的颜色存储到全局 context 中
        self.ctx.signal.global_theme_color = (lr, lg, lb)
        self.ctx.signal.theme_color_changed = True

        # 本按钮局部样式：圆角为高度一半（胶囊形），背景从图取色
        radius = max(1, self.start_button.height() // 2)
        self.start_button.setStyleSheet(
            f"background-color: rgb({lr}, {lg}, {lb}); color: {text_color}; border-radius: {radius}px;"
        )
