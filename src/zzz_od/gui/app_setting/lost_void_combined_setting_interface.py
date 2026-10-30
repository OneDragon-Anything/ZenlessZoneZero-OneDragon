from one_dragon_qt.widgets.segmented_setting_interface import SegmentedSettingInterface
from zzz_od.context.zzz_context import ZContext


class LostVoidCombinedSettingInterface(SegmentedSettingInterface):

    def __init__(self, ctx: ZContext, parent=None):
        from zzz_od.gui.view.hollow_zero.lost_void_challenge_config_interface import (
            LostVoidChallengeConfigInterface,
        )
        from zzz_od.gui.view.hollow_zero.lost_void_setting_interface import (
            LostVoidSettingInterface,
        )

        SegmentedSettingInterface.__init__(
            self,
            object_name='lost_void_combined_setting',
            nav_text_cn='迷失之地配置',
            sub_interfaces=[
                LostVoidSettingInterface(ctx),
                LostVoidChallengeConfigInterface(ctx),
            ],
            parent=parent,
        )
