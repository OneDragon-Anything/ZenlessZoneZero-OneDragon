from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    FluentIcon,
    HyperlinkButton,
    MessageBox,
    PushButton,
    SegmentedWidget,
    ToolButton,
)

from one_dragon.base.operation.context_event_bus import ContextEventItem
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.base_interface import BaseInterface
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import (
    MultiPushSettingCard,
)
from one_dragon_qt.widgets.setting_card.spin_box_setting_card import (
    DoubleSpinBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from zzz_od.application.battle_assistant.auto_battle import auto_battle_const
from zzz_od.application.battle_assistant.auto_battle.auto_battle_app import (
    AutoBattleApp,
)
from zzz_od.application.battle_assistant.auto_battle_config import (
    get_auto_battle_config_file_path,
    get_auto_battle_op_config_list,
)
from zzz_od.application.battle_assistant.dodge_assitant import dodge_assistant_const
from zzz_od.config.game_config import ControlMethodEnum
from zzz_od.context.zzz_context import ZContext
from zzz_od.gui.view.battle_assistant.battle_state_display import (
    BattleStateDisplay,
    TaskDisplay,
)


class BattleAssistantInterface(AppRunInterface):
    """战斗助手界面，合并自动战斗和闪避助手，整个配置区域使用 QStackedWidget"""

    auto_op_loaded_signal = Signal()

    MODE_AUTO_BATTLE = '自动战斗'
    MODE_DODGE_ASSISTANT = '闪避助手'

    def __init__(self, ctx: ZContext, parent=None):
        # 只调 BaseInterface.__init__，跳过 VerticalScrollInterface / AppRunInterface 的 init
        BaseInterface.__init__(
            self,
            object_name='battle_assistant_interface',
            nav_text_cn='战斗助手',
            nav_icon=FluentIcon.GAME,
            parent=parent,
        )
        self.ctx: ZContext = ctx
        self.app_id: str = auto_battle_const.APP_ID
        self._init = False  # VerticalScrollInterface 的 guard
        self.auto_op_loaded_signal.connect(self._on_auto_op_loaded_signal)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _init_layout(self) -> None:
        if self._init:
            return
        self._init = True

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(11, 11, 11, 11)

        # 内层左右分栏
        content_hbox = QHBoxLayout()
        content_hbox.setContentsMargins(0, 0, 0, 0)
        content_hbox.setSpacing(12)
        outer_layout.addLayout(content_hbox, stretch=1)

        # ---- 左侧 ----
        left_content = self.get_content_widget()
        content_hbox.addWidget(left_content, stretch=1)

        # ---- 右侧：状态面板 ----
        right_widget = QWidget()
        right_widget.setMinimumWidth(350)
        right_widget.setMaximumWidth(400)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.task_display = TaskDisplay(self.ctx)
        right_layout.addWidget(self.task_display)
        self.battle_state_display = BattleStateDisplay(self.ctx)
        right_layout.addWidget(self.battle_state_display)
        content_hbox.addWidget(right_widget, stretch=0)

    # ------------------------------------------------------------------
    # 页面构建
    # ------------------------------------------------------------------

    def get_widget_at_top(self) -> QWidget:
        top = Column()

        # SegmentedWidget 模式切换
        self.mode_segment = SegmentedWidget()
        self.mode_segment.addItem(
            routeKey=self.MODE_AUTO_BATTLE, text=self.MODE_AUTO_BATTLE,
            onClick=lambda: self._apply_mode(self.MODE_AUTO_BATTLE),
        )
        self.mode_segment.addItem(
            routeKey=self.MODE_DODGE_ASSISTANT, text=self.MODE_DODGE_ASSISTANT,
            onClick=lambda: self._apply_mode(self.MODE_DODGE_ASSISTANT),
        )
        top.add_widget(self.mode_segment)

        # 整个配置区域 QStackedWidget（高度跟随当前页面）
        self.mode_stacked = QStackedWidget()
        self.auto_battle_page = self._build_auto_battle_page()
        self.dodge_page = self._build_dodge_page()
        self.mode_stacked.addWidget(self.auto_battle_page)
        self.mode_stacked.addWidget(self.dodge_page)
        self.mode_stacked.currentChanged.connect(self._on_stacked_page_changed)
        top.add_widget(self.mode_stacked)

        # 共用设置（两种模式共享）
        self.gpu_opt = SwitchSettingCard(
            icon=FluentIcon.GAME, title='GPU运算', content='游戏画面掉帧的话 可以不启用',
        )
        top.add_widget(self.gpu_opt)

        self.screenshot_opt = DoubleSpinBoxSettingCard(
            icon=FluentIcon.GAME, title='截图间隔 (秒)',
            content='一般默认0.02，除非电脑很卡。优先通过设置游戏30帧和低画质给AI留算力',
            minimum=0.02, maximum=0.1,
        )
        top.add_widget(self.screenshot_opt)

        self.gamepad_opt = ComboBoxSettingCard(
            icon=FluentIcon.GAME, title='操作方式',
            content='仅影响自动战斗。如需使用手柄，请先安装虚拟手柄依赖。',
            options_enum=ControlMethodEnum,
        )
        top.add_widget(self.gamepad_opt)

        self.mode_segment.setCurrentItem(self.MODE_AUTO_BATTLE)

        return top

    def _build_auto_battle_page(self) -> QWidget:
        page = Column()

        # 使用说明
        desc_btn = PushButton(gt('如何让AI打得更好？'))
        desc_btn.clicked.connect(self._on_desc_clicked)

        guide_btn = HyperlinkButton(
            text=gt('查看指南'),
            url='https://one-dragon.com/zzz/zh/feat_battle_assistant.html'
        )

        shared_btn = HyperlinkButton(
            text=gt('前往社区'),
            url='https://pd.qq.com/g/onedrag00n'
        )

        help_card = MultiPushSettingCard(
            icon=FluentIcon.HELP,
            title='使用说明',
            content='先看说明 再使用与提问',
            btn_list=[desc_btn, guide_btn, shared_btn]
        )
        page.add_widget(help_card)

        # 战斗配置
        self.config_opt = ComboBoxSettingCard(
            icon=FluentIcon.GAME, title='战斗配置',
            content='全配队通用会自动为您的队伍匹配专属配队，遇到问题请反馈。',
        )
        self.config_del_btn = ToolButton(FluentIcon.DELETE)
        self.config_del_btn.clicked.connect(self._on_auto_battle_del_clicked)
        self.config_opt.hBoxLayout.addWidget(self.config_del_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.config_opt.hBoxLayout.addSpacing(16)
        page.add_widget(self.config_opt)

        # 自动战斗独有
        self.auto_ultimate_opt = SwitchSettingCard(
            icon=FluentIcon.GAME, title='终结技一好就放', content='终结技无视时机立刻释放',
        )
        page.add_widget(self.auto_ultimate_opt)

        self.merged_opt = SwitchSettingCard(
            icon=FluentIcon.GAME, title='使用合并配置文件', content='关闭用于调试模板文件 正常开启即可',
        )
        page.add_widget(self.merged_opt)

        return page

    def _build_dodge_page(self) -> QWidget:
        page = Column()

        # 闪避方式
        self.dodge_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='闪避方式')
        self.dodge_del_btn = ToolButton(FluentIcon.DELETE)
        self.dodge_opt.hBoxLayout.addWidget(self.dodge_del_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.dodge_opt.hBoxLayout.addSpacing(16)
        self.dodge_del_btn.clicked.connect(self._on_dodge_del_clicked)
        page.add_widget(self.dodge_opt)

        return page

    # ------------------------------------------------------------------
    # Mode switching
    # ------------------------------------------------------------------

    def _on_stacked_page_changed(self, index: int) -> None:
        """切换页面时，让 QStackedWidget 高度跟随当前页面"""
        for i in range(self.mode_stacked.count()):
            w = self.mode_stacked.widget(i)
            if i == index:
                w.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
            else:
                w.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        self.mode_stacked.adjustSize()

    def _apply_mode(self, mode: str) -> None:
        is_auto = mode == self.MODE_AUTO_BATTLE
        self.app_id = auto_battle_const.APP_ID if is_auto else dodge_assistant_const.APP_ID

        self.mode_stacked.setCurrentWidget(
            self.auto_battle_page if is_auto else self.dodge_page
        )
        self.task_display.setVisible(is_auto)
        self.task_display.set_update_display(is_auto)

    # ------------------------------------------------------------------
    # Config initialisation
    # ------------------------------------------------------------------

    def _init_config_cards(self) -> None:
        # auto battle
        self._update_auto_battle_config_opts()
        self.config_opt.init_with_adapter(
            get_prop_adapter(self.ctx.battle_assistant_config, 'auto_battle_config')
        )
        self.auto_ultimate_opt.init_with_adapter(
            get_prop_adapter(self.ctx.battle_assistant_config, 'auto_ultimate_enabled')
        )
        self.merged_opt.init_with_adapter(
            get_prop_adapter(self.ctx.battle_assistant_config, 'use_merged_file')
        )

        # dodge
        self._update_dodge_way_opts()
        self.dodge_opt.init_with_adapter(
            get_prop_adapter(self.ctx.battle_assistant_config, 'dodge_assistant_config')
        )

        # shared
        self.gpu_opt.init_with_adapter(
            get_prop_adapter(self.ctx.model_config, 'flash_classifier_gpu')
        )
        self.screenshot_opt.init_with_adapter(
            get_prop_adapter(self.ctx.battle_assistant_config, 'screenshot_interval')
        )
        self.gamepad_opt.init_with_adapter(
            get_prop_adapter(self.ctx.battle_assistant_config, 'control_method')
        )

    # ------------------------------------------------------------------
    # Auto battle config
    # ------------------------------------------------------------------

    def _update_auto_battle_config_opts(self) -> None:
        self.config_opt.set_options_by_list(get_auto_battle_op_config_list('auto_battle'))

    def _on_auto_battle_del_clicked(self) -> None:
        item = self.config_opt.getValue()
        if item is None:
            return
        path = Path(get_auto_battle_config_file_path('auto_battle', str(item)))
        path.unlink(missing_ok=True)
        self._update_auto_battle_config_opts()

    # ------------------------------------------------------------------
    # Dodge config
    # ------------------------------------------------------------------

    def _update_dodge_way_opts(self) -> None:
        self.dodge_opt.set_options_by_list(get_auto_battle_op_config_list('dodge'))

    def _on_dodge_del_clicked(self) -> None:
        item= self.dodge_opt.getValue()
        if item is None:
            return
        path = Path(get_auto_battle_config_file_path('dodge', str(item)))
        path.unlink(missing_ok=True)
        self._update_dodge_way_opts()

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_desc_clicked(self) -> None:
        content = (
            '为了让您的自动战斗体验更加顺畅，这里有一些温馨的小建议给到您：\n\n'
            '1. 关于画面设置：建议您将游戏帧数限制在 30 帧，并适当降低画质设置。'
            '如果您的电脑配置非常强大，尝试 60 帧也是可以的，但请务必不要开启「无限帧率」哦。\n\n'
            '2. 释放电脑性能：自动战斗功能依托于 AI 视觉识别技术，需要消耗一定的计算资源。'
            '建议您在使用时尽量关闭不必要的后台程序，电脑运行越流畅，AI 的表现也会越出色。\n\n'
            '3. 截图间隔设置：为了不让 AI 错过每一个精彩瞬间，请确保截图频率至少达到每秒 20 次。'
            '毕竟，我们不能强求 AI 在 1 帧的画面里完成电竞级的操作呀。\n\n'
            '4. 按键设置建议：强烈建议您将连携技的「左」、「右」和「取消」设置为独立的按键，'
            '避免与普攻、闪避或终结技共用键位。特别需要强调的是，几乎所有的连携技释放错误都源自于使用了同一个按键。'
            '默认键位下，连携技出现时很容易被普攻误触，导致操作失误，分开设置会让战斗更精准。\n\n'
            '比如把连携左设置为1，连携右设置为3，取消设置为2\n\n'
            '5. 应对特殊情况：目前的 AI 还在学习中，暂时无法完美应对 BOSS 的转阶段或特殊状态攻击。'
            '遇到这种情况时，可能需要您稍微费心，暂停自动战斗并手动应对一下。\n\n'
            '6. 最佳显示环境：为了保证识别准确，请将游戏分辨率设置为 1920x1080，并关闭 HDR 功能。'
            '同时，请确保游戏画面没有被其他窗口遮挡，让 AI 能看清全局。\n\n'
            '祝您游戏愉快！'
        )
        w = MessageBox(gt("使用说明"), content, self.window())
        w.cancelButton.hide()
        w.yesButton.setText(gt("确认"))
        w.exec()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_interface_shown(self) -> None:
        AppRunInterface.on_interface_shown(self)
        self._init_config_cards()
        self.ctx.listen_event(AutoBattleApp.EVENT_OP_LOADED, self._on_auto_op_loaded_event)

    def on_interface_hidden(self) -> None:
        AppRunInterface.on_interface_hidden(self)
        self.battle_state_display.set_update_display(False)
        self.task_display.set_update_display(False)

    def _on_auto_op_loaded_event(self, event: ContextEventItem) -> None:
        self.auto_op_loaded_signal.emit()

    def _on_auto_op_loaded_signal(self) -> None:
        self.battle_state_display.set_update_display(True)
        is_auto = self.mode_stacked.currentWidget() is self.auto_battle_page
        self.task_display.set_update_display(is_auto)
