from PySide6.QtCore import Qt, Signal, QRect, QRectF, QUrl
from PySide6.QtGui import QIcon, QPainter, QColor, QFont, QDesktopServices
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QSpacerItem,
    QSizePolicy,
    QHBoxLayout,
    QPushButton,
    QApplication,
    QAbstractScrollArea,
)
from qfluentwidgets import (
    FluentStyleSheet,
    isDarkTheme,
    setFont,
    SplitTitleBar,
    NavigationBarPushButton,
    MSFluentWindow,
    SingleDirectionScrollArea,
    NavigationBar,
    qrouter,
    FluentIconBase,
    NavigationItemPosition,
    InfoBar,
    InfoBarPosition,
)
from qfluentwidgets.common.animation import BackgroundAnimationWidget
from qfluentwidgets.common.config import qconfig
from qfluentwidgets.components.widgets.frameless_window import FramelessWindow
from qfluentwidgets.window.stacked_widget import StackedWidget
from typing import Union


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
        self.navigationInterface = PhosNavigationBar(self)
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


    # 覆盖父类的加载逻辑
    def resizeEvent(self, e):
        self.titleBar.move(self.navigationInterface.width() + 16, 0)
        self.titleBar.resize(
            self.width() - self.navigationInterface.width() - 16, self.titleBar.height()
        )


# 自定义导航栏类 (继承自 NavigationBar )
class PhosNavigationBar(NavigationBar):

    def __init__(self, parent=None):
        super(NavigationBar, self).__init__(parent)

        # 导航项
        self.items = {}
        # 路由历史管理
        self.history = qrouter

        # 变量
        self.scrollArea = SingleDirectionScrollArea(self)
        self.scrollWidget = QWidget()
        self.vBoxLayout = QVBoxLayout(self)
        self.topLayout = QVBoxLayout()
        self.bottomLayout = QVBoxLayout()
        self.scrollLayout = QVBoxLayout(self.scrollWidget)

        # 初始化
        self.__initWidget()
        self.__initLayout()

    # 组件
    def __initWidget(self):
        self.resize(48, self.height())
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)

        # 事件过滤器
        self.window().installEventFilter(self)

        # 滚动条样式
        self.scrollArea.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scrollArea.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scrollArea.setWidget(self.scrollWidget)
        self.scrollArea.setWidgetResizable(True)

        self.scrollWidget.setObjectName("scrollWidget")
        FluentStyleSheet.NAVIGATION_INTERFACE.apply(self)
        FluentStyleSheet.NAVIGATION_INTERFACE.apply(self.scrollWidget)

    # 布局
    def __initLayout(self):
        # 配置
        self.vBoxLayout.setContentsMargins(0, 5, 0, 5)
        self.topLayout.setContentsMargins(4, 0, 4, 0)
        self.bottomLayout.setContentsMargins(4, 0, 4, 0)
        self.scrollLayout.setContentsMargins(4, 0, 4, 0)
        self.vBoxLayout.setSpacing(4)
        self.topLayout.setSpacing(4)
        self.bottomLayout.setSpacing(4)
        self.scrollLayout.setSpacing(4)
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.topLayout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scrollLayout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.bottomLayout.setAlignment(Qt.AlignmentFlag.AlignBottom)

        # 关系
        self.vBoxLayout.addLayout(self.topLayout, 0)
        self.vBoxLayout.addWidget(self.scrollArea)
        self.vBoxLayout.addLayout(self.bottomLayout, 0)

    # 插入导航项
    def insertItem(
        self,
        index: int,
        routeKey: str,
        icon: Union[str, QIcon, FluentIconBase],
        text: str,
        onClick=None,
        selectable=True,
        selectedIcon=None,
        position=NavigationItemPosition.TOP,
    ):
        if routeKey in self.items:
            return

        # 自定义导航按钮
        widget = PhosNavigationBarPushButton(icon, text, selectable, selectedIcon, self)
        self.insertWidget(index, routeKey, widget, onClick, position)
        return widget

    def _onWidgetClicked(self):
        widget = self.sender()
        if widget.isSelectable:
            # 路由切换逻辑
            route_key = widget.property("routeKey")
            self.setCurrentItem(route_key)

    def update_all_buttons_theme_color(self, color_rgb: tuple):
        """更新所有导航按钮的主题色"""
        for widget in self.items.values():
            if isinstance(widget, PhosNavigationBarPushButton):
                widget.update_global_theme_color(color_rgb)


# 自定义导航按钮类


class PhosNavigationBarPushButton(NavigationBarPushButton):
    _theme_colors = {
        "dark_icon": "#8b8b8b",
        "light_icon": "#818181",
        "selected_icon": "#0067c0",
        "background_dark": 255,
        "background_light": 0,
    }

    def __init__(self, icon, text, isSelectable, selectedIcon=None, parent=None):
        super().__init__(icon, text, isSelectable, parent)

        # 初始化几何参数
        self.icon_rect = QRectF(22, 13, 20, 20)
        self.icon_rect_centered = QRectF(22, 18, 20, 20)
        self.text_rect = QRect(0, 32, 64, 26)

        # 图标配置
        self._icon = icon
        self._selectedIcon = selectedIcon or icon
        # 是否在选中状态下仍显示文字（默认显示）
        self._isSelectedTextVisible = True

        # 固定控件尺寸
        self.setFixedSize(64, 56)
        setFont(self, 12)

        # 全局主题色
        self._global_theme_color = (0, 120, 215)  # 默认蓝色

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.Antialiasing
            | QPainter.TextAntialiasing
            | QPainter.SmoothPixmapTransform
        )
        painter.setPen(Qt.NoPen)

        # 绘制背景
        bg_color = self._get_bg_color()
        painter.setBrush(bg_color)
        painter.drawRoundedRect(self.rect().adjusted(4, 0, -4, 0), 10, 10)

        # 绘制蓝色短线（选中状态）
        if self.isSelected:
            r, g, b = self._global_theme_color
            painter.setBrush(QColor(r, g, b))  # 使用全局主题色
            line_rect = QRect(2, 18, 4, 20)  # 左侧短线
            painter.drawRoundedRect(line_rect, 2, 2)

        # 绘制图标
        icon_color = self._get_icon_color()
        current_icon = self._selectedIcon if self.isSelected else self._icon
        # 选中且隐藏文字时居中；否则使用普通位置以便显示文字
        icon_position = self.icon_rect_centered if (self.isSelected and not self._isSelectedTextVisible) else self.icon_rect
        current_icon.render(painter, icon_position, fill=icon_color)

        # 选中时是否隐藏文字由 _isSelectedTextVisible 决定
        if self.isSelected and not self._isSelectedTextVisible:
            return

        text_color = self._get_text_color()
        painter.setPen(text_color)
        painter.setFont(self.font())
        painter.drawText(self.text_rect, Qt.AlignCenter, self.text())

    def _get_bg_color(self):
        """获取自适应主题的背景颜色"""
        if self.isSelected:
            return QColor(0, 0, 0, 0)

        # 悬停
        if self.isEnter:
            return QColor(128, 128, 128, 25)  # 淡灰色悬停效果

        return QColor(0, 0, 0, 0)  # 默认透明背景

    def _get_icon_color(self):
        """获取图标颜色(含选中状态处理)"""
        if not self.isSelected:
            return self._theme_colors["dark_icon" if isDarkTheme() else "light_icon"]

        icon_type_check = isinstance(self._selectedIcon, FluentIconBase)
        if icon_type_check:
            # 使用全局主题色
            r, g, b = self._global_theme_color
            return f"rgb({r}, {g}, {b})"
        else:
            return self._theme_colors["light_icon"]

    def _get_text_color(self):
        """获取文本颜色"""
        if self.isSelected:
            if isDarkTheme():
                return QColor(255, 255, 255)
            else:
                # 使用全局主题色
                r, g, b = self._global_theme_color
                return QColor(r, g, b)

        # 根据主题返回对应颜色
        return QColor(178, 178, 178) if isDarkTheme() else QColor(92, 110, 147)

    def setSelected(self, isSelected):
        """更新选中状态"""
        if isSelected == self.isSelected:
            return
        self.isSelected = isSelected

    def update_global_theme_color(self, color_rgb: tuple):
        """更新全局主题色"""
        self._global_theme_color = color_rgb
        self.update()  # 触发重绘


class PhosTitleBar(SplitTitleBar):
    """One Dragon 自定义标题栏"""

    def __init__(self, parent=None):
        # 调用父类的初始化方法
        super(SplitTitleBar, self).__init__(parent)

        # 设置标题栏的固定高度
        self.setFixedHeight(32)

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 10, 0, 0)

        # 添加窗口图标
        self.iconLabel = QLabel(self)
        self.iconLabel.setFixedSize(18, 18)
        layout.addWidget(
            self.iconLabel, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )

        self.window().windowIconChanged.connect(self.setIcon)

        # 空白项
        layout.addSpacerItem(
            QSpacerItem(8, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        )

        # 添加窗口标题
        self.titleLabel = QLabel(self)
        layout.addWidget(
            self.titleLabel, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.titleLabel.setObjectName("titleLabel")

        self.window().windowTitleChanged.connect(self.setTitle)

        # 扩展空白项
        layout.addSpacerItem(
            QSpacerItem(
                40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
            )
        )

        # 将新创建的布局插入到标题栏的主布局中
        self.hBoxLayout.insertLayout(0, layout)

        Qlayout = QHBoxLayout()
        Qlayout.setContentsMargins(8, 10, 0, 0)

        self.launcherVersionButton = QPushButton("ⓘ 启动器版本 未知")
        self.launcherVersionButton.setObjectName("launcherVersionButton")
        self.launcherVersionButton.clicked.connect(lambda: self.copy_version(self.launcher_version))
        self.launcherVersionButton.setVisible(False)
        Qlayout.addWidget(
            self.launcherVersionButton,
            0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
        )

        self.codeVersionButton = QPushButton("ⓘ 代码版本 未知")
        self.codeVersionButton.setObjectName("codeVersionButton")
        self.codeVersionButton.clicked.connect(lambda: self.copy_version(self.code_version))
        self.codeVersionButton.setVisible(False)
        Qlayout.addWidget(
            self.codeVersionButton,
            0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
        )

        self.questionButton = QPushButton("ⓘ 问题反馈")
        self.questionButton.setObjectName("questionButton")
        self.questionButton.clicked.connect(self.open_github)
        Qlayout.addWidget(
            self.questionButton,
            0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
        )

        # 将新创建的布局插入到标题栏的主布局中
        self.hBoxLayout.insertLayout(2, Qlayout)

        self.issue_url: str = ""
        self.launcher_version: str = ""
        self.code_version: str = ""

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
