from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QWidget
from qfluentwidgets import InfoBar, InfoBarPosition, PushButton

from one_dragon.base.controller.pc_button import pc_button_utils

VIGEMBUS_RELEASES_URL = 'https://github.com/nefarius/ViGEmBus/releases/latest'


def check_background_mode_available(parent: QWidget) -> bool:
    """
    检查后台模式所需的虚拟手柄环境，不可用时弹出提示。
    缺 ViGEmBus 驱动时，提示里带按钮打开 GitHub 最新版下载页。

    :return: 是否可用
    """
    if not pc_button_utils.is_vgamepad_installed():
        InfoBar.warning(
            title='后台模式不可用',
            content='未安装虚拟手柄依赖组件（vgamepad），请在「扩展安装」页安装',
            parent=parent,
            duration=5000,
        )
        return False

    if not pc_button_utils.is_vigembus_driver_installed():
        bar = InfoBar.warning(
            title='后台模式不可用',
            content='未检测到 ViGEmBus 驱动，请从 GitHub 下载并安装最新版，安装后重启一条龙',
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            parent=parent,
            duration=10000,
        )
        btn = PushButton('打开下载页')
        btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(VIGEMBUS_RELEASES_URL)))
        bar.addWidget(btn)
        return False

    return True
