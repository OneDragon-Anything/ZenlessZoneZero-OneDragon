from typing import Optional

from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon

from one_dragon.base.operation.application import application_const
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.key_setting_card import KeySettingCard
from one_dragon_qt.widgets.setting_card.spin_box_setting_card import (
    DoubleSpinBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from zzz_od.application.devtools.screenshot_helper import screenshot_helper_const
from zzz_od.application.devtools.screenshot_helper.screenshot_helper_config import (
    ScreenshotHelperConfig,
)
from zzz_od.context.zzz_context import ZContext


class DevtoolsScreenshotHelperInterface(AppRunInterface):

    def __init__(self,
                 ctx: ZContext,
                 parent=None):
        self.ctx: ZContext = ctx

        AppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=screenshot_helper_const.APP_ID,
            object_name='devtools_screenshot_helper_interface',
            nav_text_cn='截图助手',
            parent=parent,
        )
        self.config: Optional[ScreenshotHelperConfig] = None

    def get_widget_at_top(self) -> QWidget:
        top_widget = Column()

        self.frequency_opt = DoubleSpinBoxSettingCard(icon=FluentIcon.GAME, title='截图间隔(秒)')
        top_widget.add_widget(self.frequency_opt)

        self.length_opt = DoubleSpinBoxSettingCard(icon=FluentIcon.GAME, title='持续时间(秒)')
        top_widget.add_widget(self.length_opt)

        self.key_save_opt = KeySettingCard(icon=FluentIcon.GAME, title='保存截图按键',
                                           content='按下后，保存 持续时间(秒) 内的截图，用于捕捉漏判')
        top_widget.add_widget(self.key_save_opt)

        self.dodge_detect_opt = SwitchSettingCard(icon=FluentIcon.GAME, title='闪避检测',
                                                  content='脚本识别黄光红光时，自动截图，用于捕捉误判')
        top_widget.add_widget(self.dodge_detect_opt)

        self.screenshot_before_key_opt = SwitchSettingCard(icon=FluentIcon.GAME, title='按键前截图',
                                                          content='开启时截图按键之前的画面，关闭时截图按键之后的画面')
        top_widget.add_widget(self.screenshot_before_key_opt)

        self.mini_map_angle_detect_opt = SwitchSettingCard(icon=FluentIcon.GAME, title='小地图朝向检测',
                                                           content='无法计算朝向时截图')
        top_widget.add_widget(self.mini_map_angle_detect_opt)

        return top_widget

    def on_interface_shown(self) -> None:
        """
        子界面显示时 进行初始化
        :return:
        """
        AppRunInterface.on_interface_shown(self)
        self.config = self.ctx.run_context.get_config(
            app_id=screenshot_helper_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )
        self.frequency_opt.init_with_adapter(get_prop_adapter(self.config, 'frequency_second'))
        self.length_opt.init_with_adapter(get_prop_adapter(self.config, 'length_second'))
        self.key_save_opt.init_with_adapter(get_prop_adapter(self.config, 'key_save'))
        self.dodge_detect_opt.init_with_adapter(get_prop_adapter(self.config, 'dodge_detect'))
        self.screenshot_before_key_opt.init_with_adapter(get_prop_adapter(self.config, 'screenshot_before_key'))
        self.mini_map_angle_detect_opt.init_with_adapter(get_prop_adapter(self.config, 'mini_map_angle_detect'))
