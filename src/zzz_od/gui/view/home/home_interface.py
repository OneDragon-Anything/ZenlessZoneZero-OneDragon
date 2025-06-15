import os
import requests
from datetime import datetime, timedelta
from PySide6.QtCore import Qt, QThread, Signal, QSize, QUrl
from PySide6.QtGui import (
    QFont,
    QDesktopServices, QColor
)
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QSpacerItem,
    QSizePolicy,
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
from one_dragon_qt.widgets.notice_card import NoticeCard
from one_dragon_qt.widgets.vertical_scroll_interface import (
    VerticalScrollInterface,
)
from zzz_od.context.zzz_context import ZContext


class ButtonGroup(SimpleCardWidget):
    """显示主页和 GitHub 按钮的竖直按钮组"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)

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
        QDesktopServices.openUrl(QUrl("https://onedragon-anything.github.io/zzz/zh/home.html"))

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
        h2_layout = QHBoxLayout()
        h2_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 左边留白区域
        h2_layout.addItem(QSpacerItem(20, 10, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum))

        # 公告卡片
        if self.ctx.custom_config.notice_card:
            noticeCard = NoticeCard()
            h2_layout.addWidget(noticeCard)

        h2_layout.addStretch()

        # 启动游戏按钮布局
        start_button = PrimaryPushButton(text="启动一条龙🚀")
        start_button.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        start_button.setFixedSize(160, 48)
        start_button.clicked.connect(self._on_start_game)

        v1_layout = QVBoxLayout()
        v1_layout.addWidget(start_button, alignment=Qt.AlignmentFlag.AlignBottom)

        h2_layout.addLayout(v1_layout)

        # 空白占位符
        h2_layout.addItem(QSpacerItem(25, 10, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum))

        # 将底部水平布局添加到垂直布局
        v_layout.addLayout(h2_layout)

        # 初始化父类
        super().__init__(
            parent=parent,
            content_widget=self._banner_widget,
            object_name="home_interface",
            nav_text_cn="仪表盘",
            nav_icon=FluentIcon.HOME,
        )

        # 应用样式
        OdQtStyleSheet.GAME_BUTTON.apply(start_button)
        if self.ctx.custom_config.notice_card:
            OdQtStyleSheet.NOTICE_CARD.apply(noticeCard)

        self.ctx = ctx
        self._init_check_runners()

    def _init_check_runners(self):
        """初始化检查更新的线程"""
        self._check_code_runner = CheckCodeRunner(self.ctx)
        self._check_code_runner.need_update.connect(self._need_to_update_code)
        self._check_model_runner = CheckModelRunner(self.ctx)
        self._check_model_runner.need_update.connect(self._need_to_update_model)
        self._check_banner_runner = CheckBannerRunner(self.ctx)
        self._check_banner_runner.need_update.connect(self.reload_banner)
        self._banner_downloader = BackgroundImageDownloader(self.ctx, "remote_banner")
        self._banner_downloader.image_downloaded.connect(self.reload_banner)
        self._version_poster_downloader = BackgroundImageDownloader(self.ctx, "version_poster")
        self._version_poster_downloader.image_downloaded.connect(self.reload_banner)

    def on_interface_shown(self) -> None:
        """界面显示时启动检查更新的线程"""
        super().on_interface_shown()
        self._check_code_runner.start()
        self._check_model_runner.start()
        self._check_banner_runner.start()
        # 根据配置启动相应的背景下载器
        if self.ctx.custom_config.version_poster:
            self._version_poster_downloader.start()
        elif self.ctx.custom_config.remote_banner:
            self._banner_downloader.start()

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
        # 更新背景图片
        self._banner_widget.set_banner_image(self.choose_banner_image())
        self.ctx.signal.reload_banner = False
        if show_notification:
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