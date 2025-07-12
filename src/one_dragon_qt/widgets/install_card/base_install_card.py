from PySide6.QtCore import Signal, QThread
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, PrimaryPushButton
from typing import Optional, Callable, Tuple, List

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import MultiPushSettingCard
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log


class InstallRunner(QThread):
    progress_changed = Signal(float, str)
    finished = Signal(bool, str)

    def __init__(self, method: Callable[[Callable[[float, str], None]], Tuple[bool, str]]):
        super().__init__()
        self.method: Callable[[Callable[[float, str], None]], Tuple[bool, str]] = method

    def run(self):
        """
        运行 最后发送结束信号
        :return:
        """
        result = self.method(self.progress_callback)
        self.finished.emit(result[0], result[1])

    def progress_callback(self, progress: float, message: str) -> None:
        """
        进度回调
        :param progress: 当前进度 0~1 的小数
        :param message: 当前信息
        :return:
        """
        self.progress_changed.emit(progress, message)


class DisplayChecker(QThread):

    finished = Signal(QIcon, str)

    def __init__(self, method: Callable[[], Tuple[QIcon, str]]):
        super().__init__()

        self.method: Callable[[], Tuple[QIcon, str]] = method

    def run(self):
        """
        运行 最后发送结束信号
        :return:
        """
        result = self.method()
        if result is not None:
            self.finished.emit(result[0], result[1])


class BaseInstallCard(MultiPushSettingCard):

    progress_changed = Signal(float, str)
    finished = Signal(bool)

    def __init__(self,
                 ctx: OneDragonEnvContext,
                 title_cn: str,
                 install_method: Callable[[Callable[[float, str], None]], Tuple[bool, str]],
                 install_btn_icon: FluentIcon = FluentIcon.DOWN,
                 install_btn_text_cn: str = '默认安装',
                 content_cn: str = '未安装',
                 left_widgets: List[QWidget] = None,
                 parent=None
                 ):
        self.ctx: OneDragonEnvContext = ctx
        self.title: str = gt(title_cn)

        btn_list = []
        if left_widgets is not None:
            for left_widget in left_widgets:
                btn_list.append(left_widget)

        self.install_btn = PrimaryPushButton(install_btn_icon, gt(install_btn_text_cn))
        self.install_btn.clicked.connect(self.start_progress)
        btn_list.append(self.install_btn)

        self.install_runner = InstallRunner(install_method)
        self.install_runner.progress_changed.connect(self.update_progress)
        self.install_runner.finished.connect(self.on_progress_done)

        self.display_checker = DisplayChecker(self.get_display_content)
        self.display_checker.finished.connect(self.update_display)

        MultiPushSettingCard.__init__(
            self,
            btn_list=btn_list,
            icon=FluentIcon.INFO,
            title=self.title,
            content=gt(content_cn),
            parent=parent
        )

    def start_progress(self) -> None:
        """
        开始运行
        :return:
        """
        if self.install_runner.isRunning():
            log.warning('我知道你很急 但你先别急 正在运行了')
            return
        self.install_runner.start()

    def update_progress(self, progress: float, message: str) -> None:
        """
        安装过程中的进度回调
        :param progress: 当前进度
        :param message: 进度信息
        :return:
        """
        self.progress_changed.emit(progress, message)
        self.setContent(message)

    def on_progress_done(self, success: bool, msg: str) -> None:
        """
        安装结束的回调 发送结束信号
        :return:
        """
        if success:
            self.progress_changed.emit(100, None)
        else:
            self.progress_changed.emit(0, None)
        self.finished.emit(success)
        self.after_progress_done(success, msg)

    def after_progress_done(self, success: bool, msg: str) -> None:
        """
        安装结束的回调，由子类自行实现
        :param success: 是否成功
        :param msg: 提示信息
        :return:
        """
        pass

    def check_and_update_display(self) -> None:
        """
        检查状态并更新显示
        :return:
        """
        if self.display_checker.isRunning():
            log.warning('我知道你很急 但你先别急 正在运行了')
            return
        self.setContent(gt('检查中'))
        self.display_checker.start()

    def get_display_content(self) -> Tuple[QIcon, str]:
        """
        获取需要显示的状态，由子类自行实现
        :return: 显示的图标、文本
        """
        pass

    def update_display(self, icon: Optional[QIcon], message: str):
        """
        更新显示
        :param icon: 图标
        :param message: 文本
        :return:
        """
        if message is not None:
            self.setContent(message)
        if icon is not None:
            self.iconLabel.setIcon(icon)
