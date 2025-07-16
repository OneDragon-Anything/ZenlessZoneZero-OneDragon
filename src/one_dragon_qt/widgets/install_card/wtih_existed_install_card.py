import os
from PySide6.QtWidgets import QFileDialog
from qfluentwidgets import FluentIcon, PushButton
from typing import Callable, Optional, Tuple

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon_qt.widgets.install_card.base_install_card import BaseInstallCard
from one_dragon.utils import os_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log


class WithExistedInstallCard(BaseInstallCard):

    def __init__(self,
                 ctx: OneDragonEnvContext,
                 title_cn: str,
                 install_method: Callable[[Callable[[float, str], None]], Tuple[bool, str]],
                 install_btn_icon: FluentIcon = FluentIcon.DOWN,
                 install_btn_text_cn: str = '默认安装',
                 content_cn: str = '未安装'):
        self.existed_btn = PushButton(FluentIcon.FOLDER, gt('选择已有'))
        self.existed_btn.clicked.connect(self.choose_existed_file)

        BaseInstallCard.__init__(
            self,
            ctx=ctx,
            title_cn=title_cn,
            install_method=install_method,
            install_btn_icon=install_btn_icon,
            install_btn_text_cn=install_btn_text_cn,
            content_cn=content_cn,
            left_widgets=[self.existed_btn]
        )

    def choose_existed_file(self) -> None:
        """
        选择已有的环境
        :return:
        """
        default_dir = self.get_existed_os_path()
        if default_dir is None:
            default_dir = os_utils.get_work_dir()
        file_path, _ = QFileDialog.getOpenFileName(self,
                                                   gt('选择你的') + self.title,
                                                   dir=default_dir,
                                                   filter="Exe (*.exe)",
                                                   )
        if file_path is not None and file_path.endswith('.exe'):
            log.info('选择路径 %s', file_path)
            self.on_existed_chosen(os.path.normpath(file_path))

    def get_existed_os_path(self) -> Optional[str]:
        """
        获取系统环境变量中的路径，由子类自行实现
        :return:
        """
        pass

    def on_existed_chosen(self, file_path: str) -> None:
        """
        选择了本地文件之后的回调，由子类自行实现
        :param file_path: 本地文件的路径
        :return:
        """
        self.finished.emit(True)
