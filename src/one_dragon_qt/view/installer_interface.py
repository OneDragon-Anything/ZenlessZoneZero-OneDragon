from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    FluentIcon,
    PrimaryPushButton,
    PushButton,
)

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.utils import os_utils
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.install_card.code_install_card import CodeInstallCard
from one_dragon_qt.widgets.install_card.launcher_install_card import LauncherInstallCard
from one_dragon_qt.widgets.install_card.python_install_card import PythonInstallCard
from one_dragon_qt.widgets.install_card.uv_install_card import UVInstallCard
from one_dragon_qt.widgets.install_card.venv_install_card import VenvInstallCard
from one_dragon_qt.widgets.log_display_card import LogDisplayCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface


class StageBar(QWidget):
    """安装阶段条：完成变绿打勾、当前高亮、未到达置灰。"""

    def __init__(self, stages: list[str], parent=None):
        super().__init__(parent)
        self._stage_names = stages
        self._labels: list[BodyLabel] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addStretch(1)
        for idx, name in enumerate(stages):
            label = BodyLabel(f'{idx + 1}. {name}')
            self._labels.append(label)
            layout.addWidget(label)
            if idx < len(stages) - 1:
                line = QFrame()
                line.setFrameShape(QFrame.Shape.HLine)
                line.setFixedSize(24, 2)
                line.setStyleSheet('background: #d0d0d0; border: none;')
                layout.addWidget(line)
        layout.addStretch(1)

        self.set_current(-1)

    def set_current(self, idx: int) -> None:
        """更新阶段状态：idx 之前的为完成，idx 为当前，之后为未到达。"""
        for i, (label, name) in enumerate(zip(self._labels, self._stage_names, strict=True)):
            if i < idx:
                label.setText(f'✓ {name}')
                label.setStyleSheet('color: #00a854;')
            elif i == idx:
                label.setText(f'● {name}')
                label.setStyleSheet('color: #009faa; font-weight: 600;')
            else:
                label.setText(f'{i + 1}. {name}')
                label.setStyleSheet('color: #a0a0a0;')


class InstallerInterface(VerticalScrollInterface):

    # 安装阶段名称和对应卡片，顺序即安装顺序
    STAGE_CARDS = [
        ('code', '同步代码'),
        ('uv', '安装 uv'),
        ('python', '安装 python'),
        ('venv', '安装依赖'),
        ('launcher', '安装启动器'),
    ]

    def __init__(self, ctx: OneDragonEnvContext, extra_install_cards: list | None = None, parent=None):
        VerticalScrollInterface.__init__(self, object_name='install_interface',
                                         parent=parent, content_widget=None,
                                         nav_text_cn='一键安装', nav_icon=FluentIcon.DOWNLOAD)
        self.ctx: OneDragonEnvContext = ctx
        # 额外安装卡（如手柄驱动）直接收实例，工作目录在弹窗确认后已设置，可立即创建
        self.extra_install_cards: list = list(extra_install_cards or [])
        self._installing: bool = False
        self._installing_idx: int = -1
        self._auto_started: bool = False  # 是否已自动开始安装，避免重复触发

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
        self.install_cards = [self.card_map[key] for key, _ in self.STAGE_CARDS]
        self.all_install_cards = self.install_cards.copy()
        self.all_install_cards.extend(self.extra_install_cards)
        for card in self.install_cards:
            card.finished.connect(self.on_install_card_finished)
        for card in self.all_install_cards:
            card.progress_changed.connect(self.on_install_progress)

    def get_content_widget(self) -> QWidget:
        content_widget = QWidget()
        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # 两页：安装 → 安装完成（无面包屑，页内直接切换）
        self.step_stack = QStackedWidget()
        self.step_stack.addWidget(self.create_install_widget())
        self.step_stack.addWidget(self.create_success_widget())
        main_layout.addWidget(self.step_stack, stretch=1)

        return content_widget

    def create_install_widget(self) -> QWidget:
        """第 1 页：阶段条 + 状态栏（可展开完整日志）+ 安装状态按钮。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        layout.addStretch(1)

        # 顶部：阶段条，完成/当前/未到达一目了然
        self.stage_bar = StageBar([gt(name) for _, name in self.STAGE_CARDS])
        layout.addWidget(self.stage_bar)

        # 中间：状态栏（当前阶段与尝试的源）
        self.progress_message_label = BodyLabel('')
        self.progress_message_label.setWordWrap(True)
        self.progress_message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.progress_message_label)

        # 完整日志：默认收起，失败时自动展开
        self.log_display = LogDisplayCard()
        self.log_display.setVisible(False)
        layout.addWidget(self.log_display, stretch=1)

        # 查看日志按钮
        self.log_toggle_btn = PushButton(gt('查看日志'))
        self.log_toggle_btn.setFixedSize(88, 30)
        self.log_toggle_btn.clicked.connect(self.on_log_toggle_clicked)
        layout.addWidget(self.log_toggle_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        # 底部：安装状态按钮；安装中「安装中...」禁用，失败变「安装失败，点击重试」，空闲可手动开始
        self.install_btn = PrimaryPushButton(gt('一键安装'))
        self.install_btn.setFixedSize(200, 44)
        self.install_btn.clicked.connect(self.on_install_btn_clicked)
        layout.addWidget(self.install_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch(1)

        return widget

    def create_success_widget(self) -> QWidget:
        """第 2 页：巨大的「启动一条龙」+ 额外的「安装虚拟手柄」。"""
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

    def on_interface_shown(self) -> None:
        """界面显示时自动开始安装（只触发一次）。"""
        super().on_interface_shown()
        if not self._auto_started:
            self._auto_started = True
            self.start_install()

    def on_install_btn_clicked(self) -> None:
        """安装页底部按钮：未在安装中时开始（失败后可重试）。"""
        if self._installing:
            return
        self.start_install()

    def start_install(self) -> None:
        """按顺序安装 同步代码 → uv → python → 依赖 → 启动器。"""
        self._installing = True
        self.install_btn.setText(gt('安装中...'))
        self.install_btn.setDisabled(True)
        self.progress_message_label.setText('')
        self.progress_message_label.setStyleSheet('')  # 清除上次失败/重试残留的红色样式
        self.log_display.start(clear_log=True)
        self.log_display.setVisible(False)
        self.log_toggle_btn.setText(gt('查看日志'))

        self._installing_idx = 0
        self.stage_bar.set_current(0)
        self.install_cards[0].start_progress()

    def on_log_toggle_clicked(self) -> None:
        """展开/收起完整日志。"""
        if self.log_display.isHidden():
            self.log_display.setVisible(True)
            self.log_toggle_btn.setText(gt('收起日志'))
        else:
            self.log_display.setVisible(False)
            self.log_toggle_btn.setText(gt('查看日志'))

    def on_install_card_finished(self, success: bool) -> None:
        """一张安装卡完成后的链式推进。"""
        if self._installing_idx == -1:  # 并非从这里开始的顺序安装
            return

        if not success:
            self._installing = False
            self._installing_idx = -1
            self.progress_message_label.setText(gt('安装失败，请查看日志'))
            self.progress_message_label.setStyleSheet('color: #d13438;')
            self.log_display.stop()
            self.log_display.setVisible(True)
            self.log_toggle_btn.setText(gt('收起日志'))
            self.install_btn.setText(gt('安装失败，点击重试'))
            self.install_btn.setDisabled(False)
            return

        self._installing_idx += 1
        if self._installing_idx < len(self.install_cards):
            self.stage_bar.set_current(self._installing_idx)
            self.install_cards[self._installing_idx].start_progress()
        else:
            self._installing = False
            self._installing_idx = -1
            self.log_display.stop()
            self.install_btn.setText(gt('一键安装'))
            self.install_btn.setDisabled(False)
            self.step_stack.setCurrentIndex(1)  # 全部安装完成，切到成功页

    def on_install_progress(self, progress: float, message: str) -> None:
        """安装进度回调：更新阶段条与状态文字。"""
        if self._installing_idx == -1:
            return
        self.stage_bar.set_current(self._installing_idx)
        if message:
            self.progress_message_label.setText(message)

    # -------------------- 成功页逻辑 -------------------- #

    def on_gamepad_clicked(self) -> None:
        """安装虚拟手柄（控制器）。"""
        if self.extra_install_cards:
            self.extra_install_cards[0].start_progress()

    def launch_application(self) -> None:
        """启动一条龙：打开安装目录下的启动器，然后退出安装器。"""
        import subprocess
        from pathlib import Path

        from PySide6.QtWidgets import QApplication

        launcher_path = Path(os_utils.get_work_dir()) / 'OneDragon-Launcher.exe'
        if not launcher_path.exists():
            # 错误提示写在安装页的状态栏，切回安装页让用户看到
            self.progress_message_label.setText(gt('启动器不存在，请重新安装'))
            self.progress_message_label.setStyleSheet('color: #d13438;')
            self.step_stack.setCurrentIndex(0)
            return
        subprocess.Popen(f'cmd /c "start "" "{launcher_path}""', shell=True)
        QApplication.quit()
