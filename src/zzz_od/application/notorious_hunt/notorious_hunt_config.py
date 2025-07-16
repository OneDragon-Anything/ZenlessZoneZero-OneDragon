from enum import Enum
from typing import Optional, List

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_config import YamlConfig
from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem


class NotoriousHuntLevelEnum(Enum):

    DEFAULT = ConfigItem('默认等级')
    LEVEL_65 = ConfigItem('等级Lv.65')
    LEVEL_60 = ConfigItem('等级Lv.60')
    LEVEL_50 = ConfigItem('等级Lv.50')
    LEVEL_40 = ConfigItem('等级Lv.40')
    LEVEL_30 = ConfigItem('等级Lv.30')


class NotoriousHuntBuffEnum(Enum):

    BUFF_1 = ConfigItem('第一个BUFF', 1)
    BUFF_2 = ConfigItem('第二个BUFF', 2)
    BUFF_3 = ConfigItem('第三个BUFF', 3)


class NotoriousHuntConfig(YamlConfig):

    def __init__(self, instance_idx: Optional[int] = None):
        YamlConfig.__init__(
            self,
            module_name='notorious_hunt',
            instance_idx=instance_idx,
        )

        self.plan_list: List[ChargePlanItem] = []

        if 'plan_list' in self.data:
            for plan_item in self.data.get('plan_list', []):
                old_plan = ChargePlanItem(**plan_item)
                # 1.4版本 快捷手册中的TAB名称改动 在这里做检测兼容
                if old_plan.tab_name == '挑战':
                    old_plan.tab_name = '作战'
                self.plan_list.append(old_plan)

        existed_missions = [i.mission_type_name for i in self.plan_list]
        default_list = self._get_default_plan()
        if len(self.plan_list) < len(default_list):
            for plan in default_list:
                if plan.mission_type_name not in existed_missions:
                    self.plan_list.append(plan)

    def _get_default_plan(self) -> List[ChargePlanItem]:
        """
        默认的周本计划
        """
        return [
            ChargePlanItem('作战', '恶名狩猎', '初生死路屠夫', None),
            ChargePlanItem('作战', '恶名狩猎', '未知复合侵蚀体', None),
            ChargePlanItem('作战', '恶名狩猎', '冥宁芙·双子', None),
            ChargePlanItem('作战', '恶名狩猎', '「霸主侵蚀体·庞培」', None),
            ChargePlanItem('作战', '恶名狩猎', '牲鬼·布林格', None),
            ChargePlanItem('作战', '恶名狩猎', '秽息司祭', None)
        ]

    def save(self):
        self.data = {}
        plan_list = []
        self.data['plan_list'] = plan_list

        for plan_item in self.plan_list:
            plan_list.append({
                'tab_name': plan_item.tab_name,
                'category_name': plan_item.category_name,
                'mission_type_name': plan_item.mission_type_name,
                'mission_name': plan_item.mission_name,
                'level': plan_item.level,
                'predefined_team_idx': plan_item.predefined_team_idx,
                'auto_battle_config': plan_item.auto_battle_config,
                'run_times': plan_item.run_times,
                'plan_times': plan_item.plan_times,
                'notorious_hunt_buff_num': plan_item.notorious_hunt_buff_num,
            })

        YamlConfig.save(self)

    def update_plan(self, idx: int, plan: ChargePlanItem) -> None:
        if idx < 0 or idx >= len(self.plan_list):
            return
        self.plan_list[idx] = plan
        self.save()

    def move_up(self, idx: int) -> None:
        if idx <= 0 or idx >= len(self.plan_list):
            return

        tmp = self.plan_list[idx - 1]
        self.plan_list[idx - 1] = self.plan_list[idx]
        self.plan_list[idx] = tmp

        self.save()

    def reset_plans(self) -> None:
        if len(self.plan_list) == 0:
            return

        while True:
            all_finish: bool = True
            for plan in self.plan_list:
                if plan.run_times < plan.plan_times:
                    all_finish = False

            if not all_finish:
                break

            for plan in self.plan_list:
                plan.run_times -= plan.plan_times

            self.save()

    def get_next_plan(self) -> Optional[ChargePlanItem]:
        if len(self.plan_list) == 0:
            return None

        self.reset_plans()

        for plan in self.plan_list:
            if plan.run_times < plan.plan_times:
                return plan

        return None

    def add_plan_run_times(self, to_add: ChargePlanItem) -> None:
        """
        找到一个合适的计划 增加有一次运行次数
        """
        # 第一次 先找还没有完成的
        for plan in self.plan_list:
            if not self._is_same_plan(plan, to_add):
                continue
            if plan.run_times >= plan.plan_times:
                continue
            plan.run_times += 1
            self.save()
            return

        # 第二次 就随便加一个
        for plan in self.plan_list:
            if not self._is_same_plan(plan, to_add):
                continue
            plan.run_times += 1
            self.save()
            return

    def _is_same_plan(self, x: ChargePlanItem, y: ChargePlanItem) -> bool:
        if x is None or y is None:
            return False

        return (x.tab_name == y.tab_name
                and x.category_name == y.category_name
                and x.mission_type_name == y.mission_type_name
                and x.mission_name == y.mission_name)
