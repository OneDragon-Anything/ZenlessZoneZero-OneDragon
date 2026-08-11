from PySide6.QtCore import Qt
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, PrimaryPushButton, PushButton

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.utils import os_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.widgets.install_card.code_install_card import CodeInstallCard
from one_dragon_qt.widgets.install_card.launcher_install_card import LauncherInstallCard
from one_dragon_qt.widgets.install_card.python_install_card import PythonInstallCard
from one_dragon_qt.widgets.install_card.uv_install_card import UVInstallCard
from one_dragon_qt.widgets.install_card.venv_install_card import VenvInstallCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface


class InstallerInterface(VerticalScrollInterface):

    def __init__(self, ctx: OneDragonEnvContext, extra_install_cards: list | None = None, parent=None):
        VerticalScrollInterface.__init__(self, object_name='install_interface',
                                         parent=parent, content_widget=None,
                                         nav_text_cn='一键安装', nav_icon=FluentIcon.DOWNLOAD)
        self.ctx: OneDragonEnvContext = ctx
        # 额外安装卡（如手柄驱动、模型下载）直接收实例，工作目录在弹窗确认后已设置，可立即创建
        self.extra_install_cards: list = list(extra_install_cards or [])
        self._installing: bool = False
        self._installing_idx: int = -1

        self._init_install_cards()

    def _init_install_cards(self) -> None:
        """创建安装卡并连接信号。工作目录已在弹窗确认后设置，可直接创建。"""
        self.card_map: dict[str, object] = {
            'code': CodeInstallCard(self.ctx),
            'uv': UVInstallCard(self.ctx),
            'python': PythonInstallCard(self.ctx),
            'venv': VenvInstallCard(self.ctx),
            'launcher': LauncherInstallCard(self.ctx),
        }
        self.install_cards = [
            self.card_map[key] for key in ('code', 'uv', 'python', 'venv', 'launcher')
        ]
        self.all_install_cards = self.install_cards.copy()
        self.all_install_cards.extend(self.extra_install_cards)
        for card in self.install_cards:
            card.finished.connect(self.on_install_card_finished)
        for card in self.extra_install_cards:
            card.finished.connect(self.on_install_card_finished)
        for card in self.all_install_cards:
            card.progress_changed.connect(self.on_install_progress)
            card.check_and_update_display()

    def _one_click_cards(self) -> list:
        """一键安装要跑的卡片：排除 include_in_one_click=False 的可选卡（如虚拟手柄）。"""
        return [card for card in self.all_install_cards if card.include_in_one_click]

    def get_content_widget(self) -> QWidget:
        content_widget = QWidget()
        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 两页：安装 → 安装完成
        self.step_stack = QStackedWidget()
        self.step_stack.addWidget(self.create_install_widget())
        self.step_stack.addWidget(self.create_success_widget())
        main_layout.addWidget(self.step_stack, stretch=1)

        return content_widget

    def create_install_widget(self) -> QWidget:
        """安装页：全部安装卡（各自独立安装/重新安装）+ 底部一键安装。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 卡片容器（内部由 VerticalScrollInterface 提供滚动）
        cards_widget = QWidget()
        cards_layout = QVBoxLayout(cards_widget)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(4)
        for card in self.all_install_cards:
            cards_layout.addWidget(card)
        cards_layout.addStretch(1)
        layout.addWidget(cards_widget, stretch=1)

        # 底部：一键安装按钮（手动点击，不是自动）
        self.install_btn = PrimaryPushButton(gt('一键安装'))
        self.install_btn.setFixedSize(240, 48)
        self.install_btn.clicked.connect(self.on_install_btn_clicked)
        layout.addWidget(self.install_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        return widget

    def create_success_widget(self) -> QWidget:
        """安装完成页：启动一条龙 + 安装虚拟手柄。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)
        layout.addStretch(3)

        self.launch_btn = PrimaryPushButton(gt('启动一条龙'))
        self.launch_btn.setFixedSize(320, 72)
        self.launch_btn.setIcon(FluentIcon.PLAY)
        self.launch_btn.clicked.connect(self.launch_application)
        layout.addWidget(self.launch_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.gamepad_btn = PushButton(gt('安装虚拟手柄'))
        self.gamepad_btn.setFixedSize(200, 40)
        self.gamepad_btn.clicked.connect(self.on_gamepad_clicked)
        layout.addWidget(self.gamepad_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch(3)

        return widget

    # -------------------- 安装页逻辑 -------------------- #

    def on_install_btn_clicked(self) -> None:
        """一键安装：手动点击后按顺序安装所有卡片。"""
        if self._installing:
            return
        self.start_install()

    def start_install(self) -> None:
        """按顺序安装 代码 → uv → python → 依赖 → 模型 → 启动器（含额外卡），跳过已安装的。"""
        self._installing = True
        self.install_btn.setText(gt('安装中...'))
        self.install_btn.setDisabled(True)

        self._installing_idx = 0
        self._start_next_install_card()

    def _start_next_install_card(self) -> None:
        """从 _installing_idx 开始，跳过已安装的卡，启动第一张未安装的；全装完切成功页。"""
        cards = self._one_click_cards()
        while self._installing_idx < len(cards):
            card = cards[self._installing_idx]
            if getattr(card, '_installed', False):
                self._installing_idx += 1
                continue
            card.start_progress()
            return
        self._finish_install_all()

    def _finish_install_all(self) -> None:
        """全部安装完成：恢复按钮，切到成功页。"""
        self._installing = False
        self._installing_idx = -1
        self.install_btn.setText(gt('一键安装'))
        self.install_btn.setDisabled(False)
        self.step_stack.setCurrentIndex(1)  # 全部安装完成，切到成功页

    def on_install_card_finished(self, success: bool) -> None:
        """一张安装卡完成后的链式推进。"""
        if self._installing_idx == -1:  # 并非从这里开始的顺序安装
            return

        if not success:
            self._installing = False
            self._installing_idx = -1
            self.install_btn.setText(gt('一键安装'))
            self.install_btn.setDisabled(False)
            return

        self._installing_idx += 1
        self._start_next_install_card()

    def on_install_progress(self, progress: float, message: str) -> None:
        """安装进度回调（卡片内部已显示各自状态，这里仅记录日志）。"""
        if message:
            log.info(message)

    # -------------------- 成功页逻辑 -------------------- #

    def on_gamepad_clicked(self) -> None:
        """安装虚拟手柄（控制器），不进一键安装。"""
        for card in self.all_install_cards:
            if not card.include_in_one_click:
                card.start_progress()
                return

    def launch_application(self) -> None:
        """启动一条龙：打开安装目录下的启动器，然后退出安装器。"""
        import os
        from pathlib import Path

        from PySide6.QtWidgets import QApplication

        launcher_path = Path(os_utils.get_work_dir()) / 'OneDragon-Launcher.exe'
        if not launcher_path.exists():
            return
        # 用 os.startfile 而非 shell 拼接，避免安装路径含 & 等字符时被 cmd 解释
        os.startfile(launcher_path)
        QApplication.quit()
