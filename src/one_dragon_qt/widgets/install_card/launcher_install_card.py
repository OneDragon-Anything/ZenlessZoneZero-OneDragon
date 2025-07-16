import os
from typing import Callable, Optional, Tuple
from PySide6.QtGui import QIcon
from qfluentwidgets import FluentIcon, FluentThemeColor

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.envs.env_config import DEFAULT_ENV_PATH
from one_dragon.utils import app_utils, os_utils, file_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.widgets.install_card.base_install_card import BaseInstallCard


class LauncherInstallCard(BaseInstallCard):

    def __init__(self, ctx: OneDragonEnvContext):
        BaseInstallCard.__init__(
            self,
            ctx=ctx,
            title_cn='启动器',
            install_method=self.install_launcher
        )

    def install_launcher(self, progress_callback: Optional[Callable[[float, str], None]]) -> Tuple[bool, str]:
        msg = gt('正在安装启动器...')
        if progress_callback is not None:
            progress_callback(-1, msg)
        log.info(msg)

        for _ in range(2):
            zip_file_name = f'{self.ctx.project_config.project_name}-Launcher.zip'
            zip_file_path = os.path.join(DEFAULT_ENV_PATH, zip_file_name)
            download_url = f'{self.ctx.project_config.github_homepage}/releases/latest/download/{zip_file_name}'
            if not os.path.exists(zip_file_path):
                success = self.ctx.download_service.download_file_from_url(download_url, zip_file_path, progress_callback=progress_callback)
                if not success:
                    return False, gt('下载启动器失败 请尝试到「设置」更改网络代理')

            msg = f"{gt('正在解压')} {zip_file_name} ..."
            log.info(msg)
            if progress_callback is not None:
                progress_callback(0, msg)

            old_launcher_path = os.path.join(os_utils.get_work_dir(), 'OneDragon-Launcher.exe')
            if os.path.exists(old_launcher_path):
                os.remove(old_launcher_path)

            success = file_utils.unzip_file(zip_file_path, os_utils.get_work_dir())

            msg = gt('解压成功') if success else gt('解压失败 准备重试')
            log.info(msg)
            if progress_callback is not None:
                progress_callback(1 if success else 0, msg)

            os.remove(zip_file_path)
            if not success:  # 解压失败的话 可能是之前下的zip包坏了 尝试删除重来
                continue
            else:
                return True, gt('安装启动器成功')

        # 重试之后还是失败了
        return False, gt('安装启动器失败')

    def check_launcher_exist(self) -> bool:
        """
        检查启动器是否存在
        :return: 是否存在
        """
        launcher_path = os.path.join(os_utils.get_work_dir(), 'OneDragon-Launcher.exe')
        return os.path.exists(launcher_path)

    def check_launcher_update(self) -> Tuple[bool, str, str]:
        current_version = app_utils.get_launcher_version()
        latest_version = self.ctx.git_service.get_latest_tag()
        if current_version == latest_version:
            return True, latest_version, current_version
        return False, latest_version, current_version

    def after_progress_done(self, success: bool, msg: str) -> None:
        """
        安装结束的回调，由子类自行实现
        :param success: 是否成功
        :param msg: 提示信息
        :return:
        """
        if success:
            self.check_and_update_display()
        else:
            self.update_display(FluentIcon.INFO.icon(color=FluentThemeColor.RED.value), gt(msg))

    def get_display_content(self) -> Tuple[QIcon, str]:
        """
        获取需要显示的状态，由子类自行实现
        :return: 显示的图标、文本
        """
        if self.check_launcher_exist():
            is_latest, latest_version, current_version = self.check_launcher_update()
            if is_latest or os_utils.run_in_exe():  # 安装器中不检查更新
                icon = FluentIcon.INFO.icon(color=FluentThemeColor.DEFAULT_BLUE.value)
                msg = f"{gt('已安装')} {current_version}"
            else:
                icon = FluentIcon.INFO.icon(color=FluentThemeColor.GOLD.value)
                msg = f"{gt('需更新')} {gt('当前版本')}: {current_version}; {gt('最新版本')}: {latest_version}"
        else:
            icon = FluentIcon.INFO.icon(color=FluentThemeColor.RED.value)
            msg = gt('需下载')

        return icon, msg