from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)
from qfluentwidgets import (
    FluentStyleSheet,
    InfoBar,
    InfoBarPosition,
    MSFluentWindow,
    NavigationBar,
    SplitTitleBar,
    isDarkTheme,
    qconfig,
)
from qfluentwidgets.common.animation import BackgroundAnimationWidget
from qfluentwidgets.components.widgets.frameless_window import FramelessWindow
from qfluentwidgets.window.stacked_widget import StackedWidget


# 伪装父类 (替换 FluentWindowBase 初始化)
class PhosFluentWindowBase(BackgroundAnimationWidget, FramelessWindow):
    """Fluent window base class"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)


# 主窗口类 (继承自 MSFluentWindow )
class PhosWindow(MSFluentWindow, PhosFluentWindowBase):

    def __init__(self, parent=None):

        # 预配置
        self._isMicaEnabled = False

        self._lightBackgroundColor = QColor(248, 249, 252)
        self._darkBackgroundColor = QColor(39, 39, 39)

        # 父类初始化
        PhosFluentWindowBase.__init__(self, parent=parent)

        # 变量
        self.hBoxLayout = QHBoxLayout(self)
        self.stackedWidget = PhosStackedWidget(self)
        self.navigationInterface = NavigationBar(self)
        self.areaWidget = QWidget()
        self.areaWidget.setObjectName("areaWidget")
        self.areaLayout = QHBoxLayout(self.areaWidget)

        # 关系
        self.hBoxLayout.addWidget(self.navigationInterface)
        self.hBoxLayout.addWidget(self.areaWidget)
        self.areaLayout.addWidget(self.stackedWidget)
        self.setTitleBar(PhosTitleBar(self))

        # 配置
        self.hBoxLayout.setSpacing(0)
        self.hBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.hBoxLayout.setStretchFactor(self.areaWidget, 1)
        self.areaLayout.setContentsMargins(0, 32, 0, 0)
        self.titleBar.raise_()
        self.titleBar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)

        # 样式
        FluentStyleSheet.FLUENT_WINDOW.apply(self.stackedWidget)

        # 函数
        qconfig.themeChangedFinished.connect(self._onThemeChangedFinished)

    # 根据主题获取对应的背景色
    def _normalBackgroundColor(self):
        if isDarkTheme():
            return self._darkBackgroundColor
        else:
            return self._lightBackgroundColor

    # 调整标题栏位置
    def resizeEvent(self, e):
        self.titleBar.move(88, 0)
        self.titleBar.resize(self.width() - 88, self.titleBar.height())


class PhosTitleBar(SplitTitleBar):
    """One Dragon 自定义标题栏

    跳过 SplitTitleBar.__init__ 以完全自定义布局（图标、标题、版本号、问题反馈按钮）。
    注意: 若 SplitTitleBar/TitleBar 新增属性，需在此处手动同步。
    """

    def __init__(self, parent=None):
        # 跳过 SplitTitleBar.__init__，直接调用 TitleBar.__init__
        super(SplitTitleBar, self).__init__(parent)

        # 设置标题栏的固定高度
        self.setFixedHeight(32)

        # 窗口图标
        self.iconLabel = QLabel(self)
        self.iconLabel.setFixedSize(18, 18)
        self.hBoxLayout.insertSpacing(0, 0)
        self.hBoxLayout.insertWidget(
            1, self.iconLabel, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom
        )
        self.window().windowIconChanged.connect(self.setIcon)

        # 窗口标题
        self.titleLabel = QLabel(self)
        self.titleLabel.setObjectName("titleLabel")
        self.hBoxLayout.insertWidget(
            2, self.titleLabel, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom
        )
        self.window().windowTitleChanged.connect(self.setTitle)

        # 版本号与问题反馈按钮
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)

        self.launcherVersionButton = QPushButton("ⓘ 启动器版本 未知")
        self.launcherVersionButton.setObjectName("launcherVersionButton")
        self.launcherVersionButton.clicked.connect(lambda: self.copy_version(self.launcher_version))
        self.launcherVersionButton.setVisible(False)
        btn_layout.addWidget(
            self.launcherVersionButton,
            0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
        )

        self.codeVersionButton = QPushButton("ⓘ 代码版本 未知")
        self.codeVersionButton.setObjectName("codeVersionButton")
        self.codeVersionButton.clicked.connect(lambda: self.copy_version(self.code_version))
        self.codeVersionButton.setVisible(False)
        btn_layout.addWidget(
            self.codeVersionButton,
            0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
        )

        self.questionButton = QPushButton("ⓘ 问题反馈")
        self.questionButton.setObjectName("questionButton")
        self.questionButton.clicked.connect(self.open_github)
        btn_layout.addWidget(
            self.questionButton,
            0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
        )

        self.hBoxLayout.insertLayout(4, btn_layout)

        self.issue_url: str = ""
        self.launcher_version: str = ""
        self.code_version: str = ""

        self._updateButtonStyle()
        qconfig.themeChangedFinished.connect(self._updateButtonStyle)
        FluentStyleSheet.FLUENT_WINDOW.apply(self)

    def _updateButtonStyle(self):
        """
        圆角悬停样式，与 NavigationBarPushButton._drawBackground 一致
        hover: c=255/0(dark/light), alpha=9; pressed: alpha=6; radius=5
        """
        _is_dark = isDarkTheme()
        _c = 255 if _is_dark else 0
        _title_btn_qss = (
            "QPushButton { background: transparent; border: none;"
            " border-radius: 5px; padding: 4px 8px; }"
            f"QPushButton:hover {{ background-color: rgba({_c}, {_c}, {_c}, 9); }}"
            f"QPushButton:pressed {{ background-color: rgba({_c}, {_c}, {_c}, 6); }}"
        )
        self.launcherVersionButton.setStyleSheet(_title_btn_qss)
        self.codeVersionButton.setStyleSheet(_title_btn_qss)
        self.questionButton.setStyleSheet(_title_btn_qss)

    def setIcon(self, icon: QIcon):
        self.iconLabel.setPixmap(icon.pixmap(18, 18))

    def setTitle(self, title: str):
        self.titleLabel.setText(title)

    def setLauncherVersion(self, version: str) -> None:
        """
        设置启动器版本号 会更新UI
        @param version: 版本号
        @return:
        """
        self.launcher_version = version
        self.launcherVersionButton.setText(f"ⓘ 启动器版本 {version}")
        if version:
            self.launcherVersionButton.setVisible(True)

    def setCodeVersion(self, version: str) -> None:
        """
        设置代码版本号 会更新UI
        @param version: 版本号
        @return:
        """
        self.code_version = version
        self.codeVersionButton.setText(f"ⓘ 代码版本 {version}")
        if version:
            self.codeVersionButton.setVisible(True)

    def setInstallerVersion(self, version: str) -> None:
        """
        设置安装器版本号 会更新UI
        @param version: 版本号
        @return:
        """
        self.launcher_version = version
        self.launcherVersionButton.setText(f"ⓘ 安装器版本 {version}")
        if version:
            self.launcherVersionButton.setVisible(True)

    def setVersion(self, version: str) -> None:
        """
        设置程序版本号 会更新UI
        @param version: 版本号
        @return:
        """
        self.launcher_version = version
        self.launcherVersionButton.setText(f"ⓘ 程序版本 {version}")
        if version:
            self.launcherVersionButton.setVisible(True)

    # 定义打开GitHub网页的函数
    def open_github(self):
        url = QUrl(self.issue_url)
        QDesktopServices.openUrl(url)

    def copy_version(self, text: str):
        """
        将版本号复制到粘贴板
        @return:
        """
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        InfoBar.success(
            title="已复制版本号",
            content="",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=2000,
            parent=self.window(),
        ).setCustomBackgroundColor("white", "#202020")


class PhosStackedWidget(StackedWidget):
    """Stacked widget"""

    currentChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def setCurrentWidget(self, widget, popOut=True):
        if isinstance(widget, QAbstractScrollArea):
            widget.verticalScrollBar().setValue(0)
        self.view.setCurrentWidget(widget, duration=0)
