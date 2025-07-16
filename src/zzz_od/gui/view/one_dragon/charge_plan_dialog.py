from qfluentwidgets import MessageBoxBase, SubtitleLabel

from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem, CardNumEnum
from zzz_od.context.zzz_context import ZContext
from zzz_od.gui.view.one_dragon.charge_plan_interface import ChargePlanCard


class ChargePlanDialog(MessageBoxBase):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx

        super().__init__(parent)

        self.yesButton.setText("确定")
        self.cancelButton.setText("取消")

        self.titleLabel = SubtitleLabel("新增体力计划")
        self.viewLayout.addWidget(self.titleLabel)

        self._setup_card()

    def _setup_card(self):
        """设置体力计划卡片"""
        plan = ChargePlanItem(
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
        self.card = ChargePlanCard(self.ctx, idx=None, plan=plan)
        self.card.move_up_btn.hide()
        self.card.move_top_btn.hide()
        self.card.del_btn.hide()
        self.viewLayout.addWidget(self.card)
        self.viewLayout.addStretch(1)

    def get_card_properties(self):
        properties = {}
        if hasattr(self, 'card'):
            properties = {
                'category_name': self.card.plan.category_name,
                'mission_type_name': self.card.plan.mission_type_name,
                'mission_name': self.card.plan.mission_name,
                'level': self.card.plan.level,
                'auto_battle_config': self.card.plan.auto_battle_config,
                'run_times': self.card.plan.run_times,
                'plan_times': self.card.plan.plan_times,
                'card_num': self.card.plan.card_num,
                'predefined_team_idx': self.card.plan.predefined_team_idx,
                'notorious_hunt_buff_num': self.card.plan.notorious_hunt_buff_num,
            }
        return properties