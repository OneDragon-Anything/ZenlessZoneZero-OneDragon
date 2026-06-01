from enum import Enum

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_config import YamlConfig
from one_dragon.base.operation.application.application_config import ApplicationConfig
from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem
from zzz_od.application.notorious_hunt import notorious_hunt_const


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


class NotoriousHuntWeekdayEnum(Enum):

    MONDAY = ConfigItem('周一', 1)
    TUESDAY = ConfigItem('周二', 2)
    WEDNESDAY = ConfigItem('周三', 3)
    THURSDAY = ConfigItem('周四', 4)
    FRIDAY = ConfigItem('周五', 5)
    SATURDAY = ConfigItem('周六', 6)
    SUNDAY = ConfigItem('周日', 7)


class NotoriousHuntConfig(ApplicationConfig):

    def __init__(self, instance_idx: int, group_id: str):
        ApplicationConfig.__init__(
            self,
            app_id=notorious_hunt_const.APP_ID,
            instance_idx=instance_idx,
            group_id=group_id,
        )

        self.plan_list: list[ChargePlanItem] = []

        for plan_item in self.data.get('plan_list', []):
            self.plan_list.append(ChargePlanItem(**plan_item))

    @property
    def weekly_challenge_start_weekday(self) -> int:
        return self.data.get('weekly_challenge_start_weekday', 1)

    @weekly_challenge_start_weekday.setter
    def weekly_challenge_start_weekday(self, new_value: int) -> None:
        self.update('weekly_challenge_start_weekday', new_value)

    @property
    def loop(self) -> bool:
        return self.get('loop', True)

    @loop.setter
    def loop(self, new_value: bool) -> None:
        self.update('loop', new_value)

    def save(self) -> None:
        plan_list = []
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
                'plan_id': plan_item.plan_id,
            })
        self.data['plan_list'] = plan_list

        YamlConfig.save(self)

    def add_plan(self, plan: ChargePlanItem) -> None:
        self.plan_list.append(plan)
        self.save()

    def delete_plan(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.plan_list):
            return
        self.plan_list.pop(idx)
        self.save()

    def update_plan(self, idx: int, plan: ChargePlanItem) -> None:
        if idx < 0 or idx >= len(self.plan_list):
            return
        self.plan_list[idx] = plan
        self.save()

    def move_top(self, idx: int) -> None:
        """移动到顶部"""
        if idx <= 0 or idx >= len(self.plan_list):
            return

        plan = self.plan_list.pop(idx)
        self.plan_list.insert(0, plan)
        self.save()

    def reset_plans(self) -> None:
        """根据运行次数重置运行计划，仅未被 skipped 的计划项参与判定与扣减"""
        if len(self.plan_list) == 0:
            return

        eligible = [plan for plan in self.plan_list if not plan.skipped]
        if len(eligible) == 0:
            return

        modified: bool = False
        while True:
            all_finish: bool = True
            for plan in eligible:
                if plan.run_times < plan.plan_times:
                    all_finish = False

            if not all_finish:
                break

            for plan in eligible:
                plan.run_times -= plan.plan_times

            modified = True

        if modified:
            self.save()

    def get_next_plan(self, last_tried_plan: ChargePlanItem | None = None) -> ChargePlanItem | None:
        """
        获取下一个未完成且未被跳过的计划。

        Args:
            last_tried_plan: 上次尝试的计划。为 None 时从列表开头查找；
                否则从该计划之后的位置起查找，到列表末尾返回 None（不回卷）。
        """
        if len(self.plan_list) == 0:
            return None

        start_index = 0
        if last_tried_plan is not None:
            # 定位上次尝试的计划，从其后一位开始查找
            last_tried_index = -1
            for i, plan in enumerate(self.plan_list):
                if self._is_same_plan(plan, last_tried_plan):
                    last_tried_index = i
                    break

            if last_tried_index != -1:
                start_index = last_tried_index + 1
                if start_index >= len(self.plan_list):
                    return None
            # 失配时 start_index 保持 0，回退为从开头查找

        for i in range(start_index, len(self.plan_list)):
            plan = self.plan_list[i]
            if plan.skipped:
                continue
            if plan.run_times < plan.plan_times:
                return plan

        return None

    def all_plan_finished(self) -> bool:
        """全部计划是否均已完成（跳过 skipped 的计划）"""
        for plan in self.plan_list:
            if plan.skipped:
                continue
            if plan.run_times < plan.plan_times:
                return False
        return True

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

        # 优先按 plan_id 比较：恶名狩猎计划项 mission_name 多为 None，
        # 同副本类型的多条计划无法靠字段区分
        if x.plan_id and y.plan_id:
            return x.plan_id == y.plan_id

        # 缺少 plan_id 的旧数据回退到字段比较
        return (x.tab_name == y.tab_name
                and x.category_name == y.category_name
                and x.mission_type_name == y.mission_type_name
                and x.mission_name == y.mission_name)
