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
        self._isAeroEnabled = False
        self._isMicaEnabled = False

        self._lightBackgroundColor = QColor(240, 244, 249)
        self._darkBackgroundColor = QColor(32, 32, 32)

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

    # 设置 Aero 磨砂效果 (不启用,会导致性能消耗)
    def setAeroEffectEnabled(self, isEnabled: bool):
        self._isAeroEnabled = isEnabled
        if isEnabled:
            self.windowEffect.setAeroEffect(int(self.winId()))
        else:
            self.windowEffect.removeBackgroundEffect(self.winId())
        # 设置背景颜色
        self.setBackgroundColor(self._normalBackgroundColor())

    # 判断 Aero 效果是否启用
    def isAeroEffectEnabled(self):
        return self._isAeroEnabled

    # 根据主题获取对应的背景色
    def _normalBackgroundColor(self):
        # 若启用 Aero 效果则返回透明背景
        if self.isAeroEffectEnabled():
            return QColor(0, 0, 0, 0)
        elif isDarkTheme():
            return self._darkBackgroundColor
        else:
            return self._lightBackgroundColor

    # 主题切换
    def _onThemeChangedFinished(self):
        if self.isAeroEffectEnabled():
            # 切换主题时重载 Aero 效果
            self.windowEffect.setAeroEffect(self.winId(), isDarkTheme())

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


# 自定义导航按钮类


class PhosNavigationBarPushButton(NavigationBarPushButton):
    _theme_colors = {
        "dark_icon": "#b2b2b2",
        "light_icon": "#5c6e93",
        "selected_icon": "#ffffff",
        "background_dark": 255,
        "background_light": 0,
    }

    def __init__(self, icon, text, isSelectable, selectedIcon=None, parent=None):
        super().__init__(icon, text, isSelectable, parent)

        # 初始化几何参数
        self.icon_rect = QRectF(22, 13, 20, 20)
        self.text_rect = QRect(0, 32, 64, 26)

        # 图标配置
        self._selectedIcon = selectedIcon or icon
        self._isSelectedTextVisible = True

        # 固定控件尺寸
        self.setFixedSize(64, 56)
        setFont(self, 12, weight=QFont.Weight.ExtraBold)

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

        # 绘制图标
        icon_color = self._get_icon_color()
        self._selectedIcon.render(painter, self.icon_rect, fill=icon_color)

        # 绘制文本(选中时根据配置显隐)
        if self.isSelected and not self._isSelectedTextVisible:
            return

        text_color = self._get_text_color()
        painter.setPen(text_color)
        painter.setFont(self.font())
        painter.drawText(self.text_rect, Qt.AlignCenter, self.text())

    def _get_bg_color(self):
        """获取自适应主题的背景颜色"""
        if self.isSelected:
            return QColor(214, 75, 84, 255)

        base_color = self._theme_colors[
            "background_dark" if isDarkTheme() else "background_light"
        ]

        # 动态透明度处理
        alpha = 64 if self.isPressed else 32 if self.isEnter else 0
        return QColor(base_color, base_color, base_color, alpha)

    def _get_icon_color(self):
        """获取图标颜色(含选中状态处理)"""
        if not self.isSelected:
            return self._theme_colors["dark_icon" if isDarkTheme() else "light_icon"]

        icon_type_check = isinstance(self._selectedIcon, FluentIconBase)
        return self._theme_colors["selected_icon" if icon_type_check else "light_icon"]

    def _get_text_color(self):
        """获取文本颜色"""
        if self.isSelected:
            return QColor(255, 255, 255)

        # 根据主题返回对应颜色
        return QColor(178, 178, 178) if isDarkTheme() else QColor(92, 110, 147)

    def setSelected(self, isSelected):
        """更新选中状态"""
        if isSelected == self.isSelected:
            return
        self.isSelected = isSelected


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

    def setVersion(self, launcher_version: str, code_version: str) -> None:
        """
        设置版本号 会更新UI
        @param version: 版本号
        @return:
        """
        self.launcher_version = launcher_version
        self.code_version = code_version
        self.launcherVersionButton.setText(f"ⓘ 启动器版本 {launcher_version}")
        self.codeVersionButton.setText(f"ⓘ 代码版本 {code_version}")
        if launcher_version:
            self.launcherVersionButton.setVisible(True)
        self.codeVersionButton.setVisible(True)

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
