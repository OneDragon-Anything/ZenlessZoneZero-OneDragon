import time

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from qfluentwidgets import PrimaryPushButton, FluentIcon, PushButton, SubtitleLabel, PushSettingCard
from typing import Optional

from one_dragon.base.operation.context_event_bus import ContextEventItem
from one_dragon_qt.widgets.log_display_card import LogDisplayCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.action_recorder.monitor import RecordContext
from zzz_od.action_recorder.template_generator import PreProcessor, SelfAdaptiveGenerator
from zzz_od.context.zzz_context import ZContext

from one_dragon_qt.widgets.column import Column

class AppRunner(QThread):

    state_changed = Signal()

    def __init__(self, ctx: ZContext, app: RecordContext = None):
        super().__init__()
        self.ctx: ZContext = ctx
        self.app: RecordContext = app

    def run(self):
        """
        运行 最后发送结束信号
        :return:
        """

        self.app.records_status_and_action()
        self.app.output_records()


class TemplateGenerationInterface(AppRunInterface):

    def __init__(self,
                 ctx: ZContext,
                 parent=None):
        self.ctx: ZContext = ctx

        AppRunInterface.__init__(
            self,
            ctx=ctx,
            object_name='template_generation_interface',
            nav_text_cn='模板生成Beta',
            nav_icon=FluentIcon.GAME,
            parent=parent,
        )

        self.app: Optional[RecordContext] = None

        # 默认设置
        self._use_existing_tpl = True  # 使用预设模板
        self._add_switch_op = False  # 增加切换代理人操作

    def get_widget_at_top(self) -> QWidget:
        top_widget = Column()

        self.gen_opt = PushSettingCard(
            icon=FluentIcon.DOWN,
            title='生成模板',
            content='录制后，根据临时储存在 .log 文件夹的动作和状态文件，在 .log 文件夹中生成名为"配队动作模板.yml"的YAML模板',
            text='生成'
        )
        self.gen_opt.clicked.connect(self._template_generation)
        top_widget.add_widget(self.gen_opt)

        self.use_existing_opt = SwitchSettingCard(
            icon=FluentIcon.GAME, title='载入预设模板',
            content='从 auto_battle_state_handler 文件夹中检索已存在的代理人动作模板, 并替换模型生成的模板'
        )
        self.use_existing_opt.value_changed.connect(self._use_existing_changed)
        top_widget.add_widget(self.use_existing_opt)

        self.add_switch_opt = SwitchSettingCard(
            icon=FluentIcon.GAME, title='添加切换操作',
            content='生成动作模板时, 在代理人驻场动作最后自动添加切换下一位代理人操作'
        )
        self.add_switch_opt.value_changed.connect(self._add_switch_changed)
        top_widget.add_widget(self.add_switch_opt)

        return top_widget

    def on_interface_shown(self) -> None:
        """
        界面显示时 进行初始化
        :return:
        """
        AppRunInterface.on_interface_shown(self)
        self.use_existing_opt.setValue(self._use_existing_tpl)
        self.add_switch_opt.setValue(self._add_switch_op)

    def get_content_widget(self) -> QWidget:
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        widget_at_top = self.get_widget_at_top()
        if widget_at_top is not None:
            content_layout.addWidget(widget_at_top)

        self.state_text = SubtitleLabel()
        self.state_text.setText('先录制再生成动作模板')
        self.state_text.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        content_layout.addWidget(self.state_text)

        # 按钮行
        btn_row_widget = QWidget()
        btn_row_layout = QHBoxLayout(btn_row_widget)
        content_layout.addWidget(btn_row_widget)

        self.start_btn = PrimaryPushButton(
            text='%s %s' % (gt('开始录制'), self.ctx.key_start_running.upper()),
            icon=FluentIcon.PLAY,
        )
        self.start_btn.clicked.connect(self._on_start_clicked)
        btn_row_layout.addWidget(self.start_btn)

        self.stop_btn = PushButton(
            text='%s %s' % (gt('停止录制'), self.ctx.key_stop_running.upper()),
            icon=FluentIcon.CLOSE
        )
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        btn_row_layout.addWidget(self.stop_btn)

        self.log_card = LogDisplayCard()
        content_layout.addWidget(self.log_card)

        self.app_runner = AppRunner(self.ctx)
        self.app_runner.state_changed.connect(self.on_context_state_changed)

        widget_at_bottom = self.get_widget_at_bottom()
        if widget_at_bottom is not None:
            content_layout.addWidget(widget_at_bottom)

        content_layout.setStretch(content_layout.count() - 1, 1)

        return content_widget

    def _template_generation(self) -> None:
        """
        根据记录生成模板
        :return:
        """
        pp = PreProcessor()  # 预处理
        merged_status_ops = pp.pre_process()

        sag = SelfAdaptiveGenerator(merged_status_ops, pp.agent_names,
                                    self._use_existing_tpl, self.add_switch_opt)  # 模板生成
        agent_templates, special_status = sag.get_templates()
        sag.output_yaml(agent_templates, special_status)

        msg = '模板生成成功, 请在.log文件夹内查看'
        log.info(msg)

    def _on_key_press(self, event: ContextEventItem) -> None:
        """
        按键监听
        """
        key: str = event.data
        if key == self.ctx.key_start_running and self.ctx.is_context_stop:
            self._on_start_clicked()
        if key == self.ctx.key_stop_running:
            self._on_stop_clicked()

    def _on_start_clicked(self) -> None:
        # 开始录制
        self.ctx.init_by_config()
        self.ctx.init_ocr()

        self.app = RecordContext(self.ctx)
        AppRunInterface._on_start_clicked(self)

    def _on_stop_clicked(self) -> None:
        self.app.in_battle = True
        time.sleep(0.5)
        self.app.in_battle = False  # 打断循环

        self.app.battle.last_check_end_result = True

        self.app.button_listener.stop()
        self.app.battle.stop_context()

        self.ctx.stop_running()

    def get_app(self) -> RecordContext:
        return self.app

    def _use_existing_changed(self, value: bool) -> None:
        self._use_existing_tpl = value

    def _add_switch_changed(self, value: bool) -> None:
        self._add_switch_op = value
