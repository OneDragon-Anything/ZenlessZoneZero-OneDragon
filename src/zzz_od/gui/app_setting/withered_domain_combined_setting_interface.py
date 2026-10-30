from one_dragon_qt.widgets.segmented_setting_interface import SegmentedSettingInterface
from zzz_od.context.zzz_context import ZContext


class WitheredDomainCombinedSettingInterface(SegmentedSettingInterface):

    def __init__(self, ctx: ZContext, parent=None):
        from zzz_od.gui.view.hollow_zero.withered_domain_challenge_config_interface import (
            WitheredDomainChallengeConfigInterface,
        )
        from zzz_od.gui.view.hollow_zero.withered_domain_setting_interface import (
            WitheredDomainSettingInterface,
        )

        SegmentedSettingInterface.__init__(
            self,
            object_name='withered_domain_combined_setting',
            nav_text_cn='枯萎之都配置',
            sub_interfaces=[
                WitheredDomainSettingInterface(ctx),
                WitheredDomainChallengeConfigInterface(ctx),
            ],
            parent=parent,
        )
