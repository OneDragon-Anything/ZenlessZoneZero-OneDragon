from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QGraphicsDropShadowEffect,
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
        self.areaLayout.setContentsMargins(11, 32, 11, 0)
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

        # 首页模式下需要添加阴影的控件列表
        self._home_shadow_targets: list[QWidget] = [
            self.titleLabel,
            self.launcherVersionButton,
            self.codeVersionButton,
            self.questionButton,
            self.minBtn,
            self.maxBtn,
            self.closeBtn,
        ]
        self._is_home_mode: bool = False

        self.setProperty("homeMode", "false")

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

    def set_home_mode(self, enable: bool) -> None:
        """首页模式切换：通过动态属性 homeMode 选择 QSS 规则，配合阴影效果。"""
        if enable:
            if not self._is_home_mode:
                self._is_home_mode = True
            self.setProperty("homeMode", "true")
            self.setStyleSheet(self.styleSheet())
            self._apply_home_shadows()
        else:
            if not self._is_home_mode:
                return
            self._is_home_mode = False
            self._clear_home_shadows()
            self.setProperty("homeMode", "false")
            self.setStyleSheet(self.styleSheet())

    def _apply_home_shadows(self) -> None:
        """给首页标题栏的文字和按钮补硬阴影，提升海报背景上的可读性。"""
        for widget in self._home_shadow_targets:
            self._apply_widget_shadow(widget)

    def _clear_home_shadows(self) -> None:
        """清除首页标题栏的阴影效果。"""
        for widget in self._home_shadow_targets:
            widget.setGraphicsEffect(None)

    def _apply_widget_shadow(self, widget: QWidget) -> None:
        """给 widget 应用硬投影效果（blur=5, offset=1,1, alpha=255）。"""
        shadow = QGraphicsDropShadowEffect(widget)
        shadow.setBlurRadius(5)
        shadow.setOffset(1, 1)
        shadow.setColor(QColor(0, 0, 0, 255))
        widget.setGraphicsEffect(shadow)

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
    beforeCurrentChanged = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def setCurrentWidget(self, widget, popOut=True):
        if isinstance(widget, QAbstractScrollArea):
            widget.verticalScrollBar().setValue(0)
        old_idx = self.view.currentIndex()
        new_idx = self.view.indexOf(widget)
        if old_idx != new_idx:
            self.beforeCurrentChanged.emit(old_idx, new_idx)
        self.view.setCurrentWidget(widget, duration=0)
