from PySide6.QtCore import Signal, QThread
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QAbstractButton
from qfluentwidgets import SettingCard, FluentIconBase, PrimaryPushButton
from typing import Union, Optional, List

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.base.web.common_downloader import CommonDownloaderParam, CommonDownloader
from one_dragon.base.web.zip_downloader import ZipDownloader
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import MultiPushSettingCard


class DownloadRunner(QThread):
    finished = Signal(bool, str)

    def __init__(
            self,
            ctx: OneDragonContext,
            downloader: CommonDownloader,
    ):
        super().__init__()
        self.ctx: OneDragonContext = ctx
        self.downloader: CommonDownloader = downloader

    def run(self):
        """
        运行 最后发送结束信号
        :return:
        """
        try:
            result = self.downloader.download(
                ghproxy_url=self.ctx.env_config.gh_proxy_url if self.ctx.env_config.is_gh_proxy else None,
                proxy_url=self.ctx.env_config.personal_proxy if self.ctx.env_config.is_personal_proxy else None,
                skip_if_existed=False,
            )
            if result:
                self.finished.emit(True, '下载资源成功')
            else:
                self.finished.emit(False, '下载资源失败 请尝试更换代理')
        except Exception:
            self.finished.emit(False, '下载资源失败 请尝试更换代理')


class CommonDownloaderSettingCard(MultiPushSettingCard):

    value_changed = Signal(int, object)

    def __init__(
            self,
            ctx: OneDragonContext,
            icon: Union[str, QIcon, FluentIconBase],
            title: str,
            content=None,
            extra_btn_list: List[QAbstractButton] = None,
            parent=None
    ):

        """
        :param ctx: 上下文
        :param icon: 左边显示的图标
        :param title: 左边的标题 中文
        :param content: 左侧的详细文本 中文
        :param extra_btn_list: 在最右边额外显示的组件
        :param parent: 组件的parent
        """
        self.combo_box = ComboBox()
        self.last_index: int = -1  # 上一次选择的下标

        self.combo_box.currentIndexChanged.connect(self.on_index_changed)

        self.download_btn = PrimaryPushButton(text=gt('下载'))
        self.download_btn.clicked.connect(self._on_download_click)

        btn_list = [self.combo_box, self.download_btn]
        if extra_btn_list is not None:
            btn_list.extend(extra_btn_list)

        MultiPushSettingCard.__init__(
            self,
            btn_list=btn_list,
            icon=icon,
            title=title,
            content=content,
            parent=parent
        )

        self.ctx: OneDragonContext = ctx
        self.downloader: Optional[CommonDownloader] = None
        self.download_runner: Optional[DownloadRunner] = None

    def set_options_by_list(self, options: List[ConfigItem]) -> None:
        """
        设置选项
        :param options:
        :return:
        """
        self.combo_box.setCurrentIndex(-1)
        self.combo_box.clear()
        for opt_item in options:
            self.combo_box.addItem(opt_item.ui_text, userData=opt_item.value)

    def _get_downloader_param(self, index: int | None = None) -> CommonDownloaderParam:
        """
        获取下载器参数
        :param index: 选择的下标，如果为 None 则使用当前选中的下标
        :return: 下载器参数
        """
        if index is None:
            index = self.combo_box.currentIndex()
        return self.combo_box.itemData(index)

    def _create_downloader(self) -> CommonDownloader:
        """
        创建下载器对象，子类可以重写此方法来创建不同类型的下载器
        :return: 下载器对象
        """
        param = self._get_downloader_param()
        return CommonDownloader(param=param)

    def _update_downloader_and_runner(self) -> None:
        """
        更新下载器和运行线程对象
        总是重新创建下载器以确保使用最新的参数和状态
        :return:
        """
        # 创建下载器
        self.downloader = self._create_downloader()

        # 如果已有线程对象，只替换 downloader；否则创建新线程
        if self.download_runner is not None:
            if self.download_runner.isRunning():
                # 避免阻塞 UI：在线程结束时再替换 downloader
                def _swap_downloader_on_finish(*_args):
                    try:
                        self.download_runner.downloader = self.downloader
                    finally:
                        try:
                            self.download_runner.finished.disconnect(_swap_downloader_on_finish)
                        except Exception:
                            pass
                self.download_runner.finished.connect(_swap_downloader_on_finish)
            else:
                self.download_runner.downloader = self.downloader
        else:
            # 首次创建线程对象
            self.download_runner = DownloadRunner(self.ctx, self.downloader)
            self.download_runner.finished.connect(self._on_download_finish)

    def on_index_changed(self, index: int) -> None:
        """
        值发生改变时 往外发送信号
        :param index:
        :return:
        """
        if index == self.last_index:  # 没改变时 不发送信号
            return
        self.last_index = index

        self._update_downloader_and_runner()
        self.check_and_update_display()

        param: CommonDownloaderParam = self._get_downloader_param(index)
        self.value_changed.emit(index, param)

    def setContent(self, content: str) -> None:
        """
        更新左侧详细文本
        :param content: 文本 中文
        :return:
        """
        SettingCard.setContent(self, gt(content))

    def set_value_by_save_file_name(self, save_file_name: str) -> None:
        """
        设置值
        :param save_file_name: 保存文件名称
        :return:
        """
        for idx, item in enumerate(self.combo_box.items):
            if item.userData.save_file_name == save_file_name:
                self.combo_box.setCurrentIndex(idx)
                return

    def getValue(self):
        return self.combo_box.itemData(self.combo_box.currentIndex())

    def check_and_update_display(self) -> None:
        if self.downloader is not None and self.downloader.is_file_existed():
            self.download_btn.setText(gt('已下载'))
            self.download_btn.setDisabled(True)
        else:
            self.download_btn.setText(gt('下载'))
            self.download_btn.setDisabled(False)

    def _on_download_click(self) -> None:
        if self.download_runner is None:
            log.warning('未选择资源')
            return
        if self.download_runner.isRunning():
            log.warning('我知道你很急 但你先别急 正在运行了')
            return
        self.download_btn.setText(gt('下载中'))
        self.download_btn.setDisabled(False)
        self.download_runner.start()

    def _on_download_finish(self, result, message):
        log.info(message)
        self.check_and_update_display()


class ZipDownloaderSettingCard(CommonDownloaderSettingCard):

    def __init__(
            self,
            ctx: OneDragonContext,
            icon: Union[str, QIcon, FluentIconBase],
            title: str,
            content=None,
            extra_btn_list: List[QAbstractButton] = None,
            parent=None
    ):
        CommonDownloaderSettingCard.__init__(
            self,
            ctx=ctx,
            icon=icon,
            title=title,
            content=content,
            extra_btn_list=extra_btn_list,
            parent=parent
        )

    def _create_downloader(self) -> ZipDownloader:
        """
        创建 Zip 下载器对象
        :param param: 下载器参数，如果为 None 则通过 _get_downloader_param 获取
        :return: Zip 下载器对象
        """
        param = self._get_downloader_param()
        return ZipDownloader(param=param)
