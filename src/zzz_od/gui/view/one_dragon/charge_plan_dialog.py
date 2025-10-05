from qfluentwidgets import MessageBoxBase, SubtitleLabel

from one_dragon.utils.i18_utils import gt
from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem, CardNumEnum, ChargePlanConfig
from zzz_od.context.zzz_context import ZContext
from zzz_od.gui.view.one_dragon.charge_plan_interface import ChargePlanCard


class ChargePlanDialog(MessageBoxBase):

    def __init__(self, ctx: ZContext, config: ChargePlanConfig, parent=None):
        self.ctx = ctx
        self.config = config

        super().__init__(parent)

        self.yesButton.setText(gt('确定'))
        self.cancelButton.setText(gt('取消'))

        self.titleLabel = SubtitleLabel(gt('新增体力计划'))
        self.viewLayout.addWidget(self.titleLabel)

        self._setup_card()

    def _setup_card(self):
        """设置体力计划卡片"""
        self.plan = ChargePlanItem(
            tab_name='训练',
            category_name='实战模拟室',
            mission_type_name='基础材料',
            mission_name='调查专项',
            level='默认等级',
            auto_battle_config='全配队通用',
            run_times=0,
            plan_times=1,
            card_num=str(CardNumEnum.DEFAULT.value.value),
            predefined_team_idx=0,
            notorious_hunt_buff_num=1,
        )
        card = ChargePlanCard(self.ctx, idx=-1, plan=self.plan, config=self.config)
        card.move_up_btn.hide()
        card.move_top_btn.hide()
        card.del_btn.hide()
        self.viewLayout.addWidget(card)
        self.viewLayout.addStretch(1)
