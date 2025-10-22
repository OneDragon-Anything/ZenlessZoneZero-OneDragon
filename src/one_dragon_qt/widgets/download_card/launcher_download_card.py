import os

from PySide6.QtGui import QIcon
from qfluentwidgets import FluentIcon, FluentThemeColor

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.base.web.common_downloader import CommonDownloaderParam
from one_dragon.base.web.zip_downloader import ZipDownloader
from one_dragon.envs.env_config import DEFAULT_ENV_PATH
from one_dragon.utils import app_utils, os_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.widgets.setting_card.common_download_card import (
    ZipDownloaderSettingCard,
)


class LauncherDownloadCard(ZipDownloaderSettingCard):

    def __init__(self, ctx: OneDragonEnvContext):
        self.ctx: OneDragonEnvContext = ctx
        self.latest_version = "latest"

        # 使用父类的 ComboBox 和 download_btn
        ZipDownloaderSettingCard.__init__(
            self,
            ctx=ctx,
            icon=FluentIcon.INFO,
            title=gt('启动器'),
            content=gt('未安装'),
            parent=None
        )

        # 设置下拉框选项：稳定版和测试版
        self.set_options_by_list([
            ConfigItem('稳定版', 'stable'),
            ConfigItem('测试版', 'beta')
        ])

        # 默认选择稳定版
        self.combo_box.setCurrentIndex(0)

        # 初始化显示状态
        self.check_and_update_display()

    def on_index_changed(self, index: int) -> None:
        """
        重写父类方法，当版本通道改变时重新检查更新
        :param index: 选项索引
        :return:
        """
        if index == self.last_index:  # 没改变时 不发送信号
            return
        self.last_index = index

        # 重新检查并更新显示
        self.check_and_update_display()

    def _create_downloader_param(self) -> CommonDownloaderParam:
        """
        创建下载器参数
        :return: CommonDownloaderParam
        """
        zip_file_name = f'{self.ctx.project_config.project_name}-Launcher.zip'
        launcher_exe = 'OneDragon-Launcher.exe'
        launcher_path = os.path.join(os_utils.get_work_dir(), launcher_exe)

        base = (
            'latest/download'
            if self.latest_version == 'latest'
            else f'download/{self.latest_version}'
        )
        download_url = f'{self.ctx.project_config.github_homepage}/releases/{base}/{zip_file_name}'

        return CommonDownloaderParam(
            save_file_path=DEFAULT_ENV_PATH,
            save_file_name=zip_file_name,
            github_release_download_url=download_url,
            check_existed_list=[launcher_path],
            unzip_dir_path=os_utils.get_work_dir()
        )

    def check_launcher_exist(self) -> bool:
        """
        检查启动器是否存在
        :return: 是否存在
        """
        launcher_path = os.path.join(os_utils.get_work_dir(), 'OneDragon-Launcher.exe')
        return os.path.exists(launcher_path)

    def check_launcher_update(self) -> tuple[bool, str, str]:
        """
        检查启动器更新
        :return: (是否最新, 最新版本, 当前版本)
        """
        current_version = app_utils.get_launcher_version()
        latest_stable, latest_beta = self.ctx.git_service.get_latest_tag()

        # 根据下拉框选择的通道决定检查哪个版本
        selected_channel = self.combo_box.currentData()
        if selected_channel == 'beta':
            # 测试版通道：与最新测试版比较；若不存在测试版，则视为已最新
            target_latest = latest_beta or current_version
        else:
            # 稳定版通道：与最新稳定版比较；若不存在稳定版，则视为已最新
            target_latest = latest_stable or current_version

        if current_version == target_latest:
            return True, target_latest, current_version
        else:
            self.latest_version = target_latest
            return False, target_latest, current_version

    def check_and_update_display(self) -> None:
        """
        检查启动器状态并更新显示
        重写父类方法以实现启动器特有的逻辑
        :return:
        """
        if self.check_launcher_exist():
            if os_utils.run_in_exe():  # 安装器中不检查更新
                icon = FluentIcon.INFO.icon(color=FluentThemeColor.DEFAULT_BLUE.value)
                msg = gt('已安装')
                self.update_display(icon, msg)
                self.download_btn.setText(gt('已安装'))
                self.download_btn.setDisabled(True)
                return

            self.download_btn.setText(gt('检查中...'))
            is_latest, latest_version, current_version = self.check_launcher_update()

            # 更新下载器参数
            param = self._create_downloader_param()
            self.downloader = ZipDownloader(param=param)
            if self.download_runner is not None:
                self.download_runner.downloader = self.downloader

            if is_latest:
                icon = FluentIcon.INFO.icon(color=FluentThemeColor.DEFAULT_BLUE.value)
                msg = f"{gt('已安装')} {current_version}"
                self.download_btn.setText(gt('已安装'))
                self.download_btn.setDisabled(True)
            else:
                icon = FluentIcon.INFO.icon(color=FluentThemeColor.GOLD.value)
                msg = f"{gt('需更新')} {gt('当前版本')}: {current_version}; {gt('最新版本')}: {latest_version}"
                self.download_btn.setText(gt('更新'))
                self.download_btn.setDisabled(False)
        else:
            icon = FluentIcon.INFO.icon(color=FluentThemeColor.RED.value)
            msg = gt('需下载')
            self.download_btn.setText(gt('下载'))
            self.download_btn.setDisabled(False)

            # 更新下载器参数
            param = self._create_downloader_param()
            self.downloader = ZipDownloader(param=param)
            if self.download_runner is not None:
                self.download_runner.downloader = self.downloader

        self.update_display(icon, msg)

    def update_display(self, icon: QIcon, msg: str) -> None:
        """
        更新显示内容
        :param icon: 图标
        :param msg: 消息
        :return:
        """
        self.iconLabel.setIcon(icon)
        self.contentLabel.setText(msg)

    def _on_download_click(self) -> None:
        """
        重写父类的下载点击方法，添加删除旧启动器的逻辑
        :return:
        """
        if self.download_runner is None:
            log.warning('下载器未初始化')
            return
        if self.download_runner.isRunning():
            log.warning('我知道你很急 但你先别急 正在运行了')
            return

        # 删除旧的启动器
        old_launcher_path = os.path.join(os_utils.get_work_dir(), 'OneDragon-Launcher.exe')
        if os.path.exists(old_launcher_path):
            try:
                os.remove(old_launcher_path)
            except Exception as e:
                log.error(f'删除旧启动器失败: {e}')

        # 调用父类的下载逻辑
        self.download_btn.setText(gt('安装中'))
        self.download_btn.setDisabled(True)
        self.download_runner.start()

    def _on_download_finish(self, success: bool, message: str) -> None:
        """
        重写父类的下载完成方法，添加更新标题栏版本号的逻辑
        :param success: 是否成功
        :param message: 消息
        :return:
        """
        log.info(message)
        if success:
            # 更新标题栏版本号
            try:
                self.window().titleBar.setLauncherVersion(app_utils.get_launcher_version())
            except Exception as e:
                log.error(f'更新标题栏版本号失败: {e}')

            icon = FluentIcon.INFO.icon(color=FluentThemeColor.DEFAULT_BLUE.value)
            msg = gt('安装成功')
            self.update_display(icon, msg)
            self.download_btn.setText(gt('已安装'))
            self.download_btn.setDisabled(True)
        else:
            icon = FluentIcon.INFO.icon(color=FluentThemeColor.RED.value)
            self.update_display(icon, message)
            self.download_btn.setText(gt('重试'))
            self.download_btn.setDisabled(False)
