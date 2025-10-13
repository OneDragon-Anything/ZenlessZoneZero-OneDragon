from typing import Optional

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, PushSettingCard

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.operation.application import application_const
from one_dragon.utils.log_utils import log
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from zzz_od.application.battle_assistant.auto_battle_config import (
    get_auto_battle_op_config_list,
)
from zzz_od.application.world_patrol import world_patrol_const
from zzz_od.application.world_patrol.world_patrol_config import WorldPatrolConfig
from zzz_od.application.world_patrol.world_patrol_run_record import WorldPatrolRunRecord
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext


class WorldPatrolRunInterface(AppRunInterface):

    def __init__(self,
                 ctx: ZContext,
                 parent=None):
        self.ctx: ZContext = ctx
        self.app: Optional[ZApplication] = None

        AppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=world_patrol_const.APP_ID,
            object_name='world_patrol_run_interface',
            nav_text_cn='锄大地(测试)',
            parent=parent,
        )
        self.config: Optional[WorldPatrolConfig] = None
        self.run_record: Optional[WorldPatrolRunRecord] = None

    def get_widget_at_top(self) -> QWidget:
        # 创建一个容器 widget 用于水平排列
        col_widget = QWidget(self)
        col_layout = QHBoxLayout(col_widget)
        col_widget.setLayout(col_layout)

        # 将左侧和右侧的 widget 添加到主布局中，并均分空间
        col_layout.addWidget(self._get_left_opts(), stretch=1)
        col_layout.addWidget(self._get_right_opts(), stretch=1)

        return col_widget

    def _get_left_opts(self) -> QWidget:
        # 创建左侧的垂直布局容器
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        widget.setLayout(layout)

        self.help_opt = HelpCard(url='',
                                 content='使用此功能前请先到 [游戏助手]->[鼠标校准] 运行一次')
        layout.addWidget(self.help_opt)

        self.auto_battle_opt = ComboBoxSettingCard(icon=FluentIcon.SEARCH, title='自动战斗')
        layout.addWidget(self.auto_battle_opt)

        layout.addStretch(1)
        return widget

    def _get_right_opts(self) -> QWidget:
        # 创建右侧的垂直布局容器
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        widget.setLayout(layout)

        self.run_record_opt = PushSettingCard(
            icon=FluentIcon.SYNC,
            title='运行记录',
            text='重置记录'
        )
        self.run_record_opt.clicked.connect(self._on_reset_record_clicked)
        layout.addWidget(self.run_record_opt)

        self.route_list_opt = ComboBoxSettingCard(icon=FluentIcon.SEARCH, title='路线名单')
        layout.addWidget(self.route_list_opt)

        layout.addStretch(1)
        return widget

    def on_interface_shown(self) -> None:
        AppRunInterface.on_interface_shown(self)

        self.config = self.ctx.run_context.get_config(
            app_id=world_patrol_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )
        self.run_record = self.ctx.run_context.get_run_record(
            app_id=world_patrol_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
        )

        config_list = [
            ConfigItem(i.name)
            for i in self.ctx.world_patrol_service.get_world_patrol_route_lists()
        ]
        self.route_list_opt.set_options_by_list(
            [ConfigItem('全部', value='')]
            +
            config_list
        )
        self.route_list_opt.init_with_adapter(get_prop_adapter(self.config, 'route_list'))

        self.auto_battle_opt.set_options_by_list(get_auto_battle_op_config_list('auto_battle'))
        self.auto_battle_opt.init_with_adapter(get_prop_adapter(self.config, 'auto_battle'))

    def _on_reset_record_clicked(self) -> None:
        self.run_record.reset_record()
        log.info('已重置记录')