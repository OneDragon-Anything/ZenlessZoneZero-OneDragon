
from collections.abc import Callable

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QAbstractButton
from qfluentwidgets import FluentIconBase, PrimaryPushButton, SettingCard

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.base.web.common_downloader import (
    CommonDownloader,
    CommonDownloaderParam,
)
from one_dragon.base.web.zip_downloader import ZipDownloader
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.services.download_queue_service import (
    DownloadQueueService,
    ResourceDownloadSpec,
    ResourceDownloadTask,
    ResourceDownloadTaskState,
)
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import (
    MultiPushSettingCard,
)


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
        self.progress_signal: dict[str, str | None] = {'signal': None}

    def run(self):
        """
        运行 最后发送结束信号
        :return:
        """
        try:
            env_config = self.ctx.env_config
            result = self.downloader.download(
                source_order=env_config.get_resource_source_order(),
                ghproxy_url=env_config.gh_proxy_url if env_config.is_gh_proxy else None,
                proxy_url=env_config.personal_proxy if env_config.is_personal_proxy else None,
                skip_if_existed=False,
                progress_signal=self.progress_signal,
                on_source_success=env_config.mark_resource_source_success,
                on_source_failure=env_config.mark_resource_source_failure,
                fallback_on_slow=env_config.is_resource_source_auto,
            )
        except Exception:
            result = False

        if result:
            message = '下载资源成功'
        else:
            if self.progress_signal.get('signal') == 'cancel':
                message = '下载已取消'
            else:
                message = '下载资源失败 请尝试更换代理'

        self.finished.emit(result, message)

    def cancel(self):
        """
        取消下载
        :return:
        """
        self.progress_signal['signal'] = 'cancel'


class CommonDownloaderSettingCard(MultiPushSettingCard):

    value_changed = Signal(int, object)

    def __init__(
            self,
            ctx: OneDragonContext,
            icon: str | QIcon | FluentIconBase,
            title: str,
            content=None,
            extra_btn_list: list[QAbstractButton] = None,
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

        self.cancel_btn = PrimaryPushButton(text=gt('取消'))
        self.cancel_btn.clicked.connect(self._on_cancel_click)
        self.cancel_btn.setVisible(False)  # 初始隐藏取消按钮

        btn_list = [self.combo_box, self.download_btn, self.cancel_btn]
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
        self.downloader: CommonDownloader | None = None
        self.download_runner: DownloadRunner | None = None
        self.download_queue: DownloadQueueService | None = None
        self.download_spec_factory: Callable[[], ResourceDownloadSpec] | None = None
        self.active_value_getter: Callable[[], str] | None = None

    def set_active_value_getter(self, getter: Callable[[], str]) -> None:
        """设置当前正在使用的资源版本读取方法。"""
        self.active_value_getter = getter

    def use_download_queue(
        self,
        service: DownloadQueueService,
        spec_factory: Callable[[], ResourceDownloadSpec],
    ) -> None:
        """让卡片点击后加入统一下载队列。

        Args:
            service: 下载队列服务。
            spec_factory: 根据当前卡片选项构造资源规格的方法。
        """
        self.download_queue = service
        self.download_spec_factory = spec_factory
        service.task_added.connect(self._on_queue_task_changed)
        service.task_updated.connect(self._on_queue_task_changed)
        service.task_removed.connect(lambda _task_key: self.check_and_update_display())
        self.check_and_update_display()

    def _get_queue_task(self) -> ResourceDownloadTask | None:
        """返回卡片当前选项对应的队列任务。"""
        if self.download_queue is None or self.download_spec_factory is None:
            return None
        spec = self.download_spec_factory()
        return self.download_queue.get_task(spec.task_key)

    def _on_queue_task_changed(self, _task: ResourceDownloadTask) -> None:
        """队列状态变化时刷新卡片。"""
        self.check_and_update_display()

    def _apply_queue_display_state(self) -> bool:
        """应用队列状态，返回是否已接管按钮显示。"""
        task = self._get_queue_task()
        if task is None:
            return False
        if task.state == ResourceDownloadTaskState.WAITING:
            self.download_btn.setText(gt('下载中'))
            self.download_btn.setEnabled(True)
            return True
        if task.state in (
            ResourceDownloadTaskState.DOWNLOADING,
            ResourceDownloadTaskState.EXTRACTING,
            ResourceDownloadTaskState.APPLYING,
            ResourceDownloadTaskState.CANCELLING,
        ):
            self.download_btn.setText(gt('下载中'))
            self.download_btn.setEnabled(True)
            return True
        if task.state == ResourceDownloadTaskState.FAILED:
            self.download_btn.setText(gt('查看失败'))
            self.download_btn.setEnabled(True)
            return True
        return False

    def set_options_by_list(self, options: list[ConfigItem]) -> None:
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

        # 如果已有线程对象，只替换 downloader；否则创建新的线程对象
        if self.download_runner is not None:
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
        """
        检查并更新显示状态
        根据下载器状态和下载任务运行状态来设置各个按钮的启用/禁用状态
        """
        if self.download_queue is not None and self._apply_queue_display_state():
            self.combo_box.setEnabled(True)
            self.cancel_btn.setVisible(False)
            return

        is_running = self.download_runner is not None and self.download_runner.isRunning()
        is_downloaded = self.downloader is not None and self.downloader.is_file_existed()

        # 下拉框：只有在非下载状态时才能切换
        self.combo_box.setDisabled(is_running)

        # 下载按钮：下载中或已下载时禁用
        self.download_btn.setDisabled(is_running or is_downloaded)
        if is_running:
            self.download_btn.setText(gt('下载中'))
        elif is_downloaded:
            param = self._get_downloader_param()
            selected_value = param.save_file_name.removesuffix('.zip')
            is_active = (
                self.active_value_getter is not None
                and self.active_value_getter() == selected_value
            )
            self.download_btn.setText(gt('使用中') if is_active else gt('已下载'))
        else:
            self.download_btn.setText(gt('下载'))

        # 取消按钮：下载中时显示
        self.cancel_btn.setVisible(is_running)
        self.cancel_btn.setEnabled(is_running)

    def _on_download_click(self) -> None:
        """
        处理下载按钮点击事件
        """
        if self.download_queue is not None and self.download_spec_factory is not None:
            spec = self.download_spec_factory()
            task = self.download_queue.get_task(spec.task_key)
            if task is not None and task.state in (
                ResourceDownloadTaskState.WAITING,
                ResourceDownloadTaskState.DOWNLOADING,
                ResourceDownloadTaskState.EXTRACTING,
                ResourceDownloadTaskState.APPLYING,
                ResourceDownloadTaskState.CANCELLING,
                ResourceDownloadTaskState.FAILED,
            ):
                window = self.window()
                if hasattr(window, 'show_download_queue'):
                    window.show_download_queue()
                return
            if task is not None and task.state == ResourceDownloadTaskState.CANCELLED:
                self.download_queue.retry(task.task_key)
            else:
                self.download_queue.enqueue(spec)
            window = self.window()
            if hasattr(window, 'show_download_queue_added_tip'):
                window.show_download_queue_added_tip(spec.title)
            self.check_and_update_display()
            return

        if self.download_runner is None:
            log.warning('未选择资源')
            return
        if self.download_runner.isRunning():
            log.warning('我知道你很急 但你先别急 正在运行了')
            return

        # 重置取消信号
        self.download_runner.progress_signal['signal'] = None

        # 启动下载并更新UI状态
        self.download_runner.start()
        self.check_and_update_display()

    def _on_cancel_click(self) -> None:
        """
        处理取消按钮点击事件
        """
        if self.download_runner is None:
            log.warning('未选择资源')
            return
        if not self.download_runner.isRunning():
            log.warning('当前没有下载任务在运行')
            return

        # 取消下载
        self.download_runner.cancel()
        log.info('正在取消下载...')

        # 更新UI状态：禁用取消按钮，显示取消中
        self.download_btn.setText(gt('取消中'))
        self.cancel_btn.setDisabled(True)

    def _on_download_finish(self, result, message):
        """
        处理下载完成事件
        :param result: 下载是否成功
        :param message: 结果消息
        """
        log.info(message)
        self.check_and_update_display()


class ZipDownloaderSettingCard(CommonDownloaderSettingCard):

    def __init__(
            self,
            ctx: OneDragonContext,
            icon: str | QIcon | FluentIconBase,
            title: str,
            content=None,
            extra_btn_list: list[QAbstractButton] = None,
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
        :return: Zip 下载器对象
        """
        param = self._get_downloader_param()
        return ZipDownloader(param=param)
