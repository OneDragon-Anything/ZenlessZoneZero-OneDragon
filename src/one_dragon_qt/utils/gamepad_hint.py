import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QWidget
from qfluentwidgets import InfoBar, InfoBarPosition, PushButton

from one_dragon.base.controller.pc_button import pc_button_utils
from one_dragon.base.web.common_downloader import (
    CommonDownloader,
    CommonDownloaderParam,
)
from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log
from one_dragon_qt.services.download_queue_service import (
    ResourceDownloadSpec,
    ResourceDownloadTaskState,
)

VIGEMBUS_RELEASES_URL = 'https://github.com/nefarius/ViGEmBus/releases/latest'


def _after_installer_download(save_path: str, success: bool) -> None:
    """下载成功后打开安装程序。"""
    if success and os.path.exists(save_path):
        os.startfile(save_path)  # noqa: S606


def enqueue_vigembus_installer(parent: QWidget) -> None:
    """
    把 ViGEmBus 安装包加入资源下载队列，下载完成后自动打开安装程序。
    找不到下载队列时退回到打开 GitHub 下载页。
    """
    window = parent.window()
    queue = getattr(window, 'download_queue', None)
    ctx = getattr(window, 'ctx', None)
    installer = (
        ctx.env_config.repo_config.get_driver_installer('vigembus')
        if ctx is not None else None
    )
    if queue is None or installer is None:
        QDesktopServices.openUrl(QUrl(VIGEMBUS_RELEASES_URL))
        return

    title, tag, file_name, download_urls = installer
    save_dir = os_utils.get_path_under_work_dir('.temp', 'vigembus')
    save_path = os.path.join(save_dir, file_name)
    spec = ResourceDownloadSpec(
        resource_id='vigembus',
        resource_type='driver',
        title=title,
        current_version='',
        target_version=tag,
        note='下载完成后会自动打开安装程序',
        downloader_factory=lambda: CommonDownloader(
            CommonDownloaderParam(
                save_file_path=save_dir,
                save_file_name=file_name,
                download_urls=download_urls,
            )
        ),
        after_download=lambda success: _after_installer_download(save_path, success),
    )
    log.info('ViGEmBus 安装包加入下载队列')
    existing = queue.get_task(spec.task_key)
    if existing is None:
        queue.enqueue(spec)
    elif existing.state in (
        ResourceDownloadTaskState.FAILED,
        ResourceDownloadTaskState.CANCELLED,
    ):
        queue.retry(spec.task_key)
    elif existing.state == ResourceDownloadTaskState.SUCCEEDED:
        if os.path.exists(save_path):
            _after_installer_download(save_path, True)
        else:
            # 安装包已被清理，成功任务没法再用，移除后重新下载
            queue.remove(spec.task_key)
            queue.enqueue(spec)
    # 等待或进行中的任务继续去重，不重复添加


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
            content='未检测到 ViGEmBus 驱动，请下载并安装，安装后重启一条龙',
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            parent=parent,
            duration=10000,
        )
        btn = PushButton('下载并安装')
        btn.clicked.connect(lambda: enqueue_vigembus_installer(parent))
        bar.addWidget(btn)
        return False

    return True
