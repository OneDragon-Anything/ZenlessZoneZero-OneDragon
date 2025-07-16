from enum import Enum
from typing import Optional, List
import uuid

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_config import YamlConfig


class CardNumEnum(Enum):

    DEFAULT = ConfigItem('默认数量')
    NUM_1 = ConfigItem('1张卡片', '1')
    NUM_2 = ConfigItem('2张卡片', '2')
    NUM_3 = ConfigItem('3张卡片', '3')
    NUM_4 = ConfigItem('4张卡片', '4')
    NUM_5 = ConfigItem('5张卡片', '5')


class ChargePlanItem:

    def __init__(
            self,
            tab_name: str = '训练',
            category_name: str = '实战模拟室',
            mission_type_name: str = '基础材料',
            mission_name: str = '调查专项',
            level: str = '默认等级',
            auto_battle_config: str = '全配队通用',
            run_times: int = 0,
            plan_times: int = 1,
            card_num: str = CardNumEnum.DEFAULT.value.value,
            predefined_team_idx: int = -1,
            notorious_hunt_buff_num: int = 1,
            plan_id: Optional[str] = None,
    ):
        self.tab_name: str = tab_name
        self.category_name: str = category_name
        self.mission_type_name: str = mission_type_name
        self.mission_name: str = mission_name
        self.level: str = level
        self.auto_battle_config: str = auto_battle_config
        self.run_times: int = run_times
        self.plan_times: int = plan_times
        self.card_num: str = card_num  # 实战模拟室的卡片数量

        self.predefined_team_idx: int = predefined_team_idx  # 预备配队下标 -1为使用当前配队
        self.notorious_hunt_buff_num: int = notorious_hunt_buff_num  # 恶名狩猎 选择的buff
        self.plan_id: str = plan_id if plan_id else str(uuid.uuid4())  # 计划的唯一标识符

    @property
    def uid(self) -> str:
        return '%s_%s_%s_%s' % (
            self.tab_name if self.tab_name is not None else '',
            self.category_name if self.category_name is not None else '',
            self.mission_type_name if self.mission_type_name is not None else '',
            self.mission_name if self.mission_name is not None else '',
        )



class ChargePlanConfig(YamlConfig):

    def __init__(self, instance_idx: Optional[int] = None):
        YamlConfig.__init__(
            self,
            module_name='charge_plan',
            instance_idx=instance_idx,
        )

        self.plan_list: List[ChargePlanItem] = []

        for plan_item in self.data.get('plan_list', []):
            self.plan_list.append(ChargePlanItem(**plan_item))
        self.loop = self.get('loop', True)
        self.skip_plan = self.get('skip_plan', False)
        self.use_coupon = self.get('use_coupon', False)

    def save(self):
        plan_list = []

        new_history_list = []

        for plan_item in self.plan_list:
            plan_data = {
                'tab_name': '作战' if plan_item.category_name == '恶名狩猎' else '训练',
                'category_name': plan_item.category_name,
                'mission_type_name': plan_item.mission_type_name,
                'mission_name': plan_item.mission_name,
                'auto_battle_config': plan_item.auto_battle_config,
                'run_times': plan_item.run_times,
                'plan_times': plan_item.plan_times,
                'card_num': plan_item.card_num,
                'predefined_team_idx': plan_item.predefined_team_idx,
                'notorious_hunt_buff_num': plan_item.notorious_hunt_buff_num,
                'plan_id': plan_item.plan_id,
            }

            new_history_list.append(plan_data.copy())
            plan_list.append(plan_data)

        old_history_list = self.history_list
        for old_history_data in old_history_list:
            old_history = ChargePlanItem(**old_history_data)
            with_new = False
            for plan in self.plan_list:
                if self._is_same_plan(plan, old_history):
                    with_new = True
                    break

            if not with_new:
                new_history_list.append(old_history_data)

        self.data = {
            'loop': self.loop,
            'skip_plan': self.skip_plan,
            'use_coupon': self.use_coupon,
            'plan_list': plan_list,
            'history_list': new_history_list
        }

        YamlConfig.save(self)

    def add_plan(self, properties: dict) -> None:
        plan = ChargePlanItem(
            tab_name=properties.get('tab_name', '训练'),
            category_name=properties.get('category_name', '实战模拟室'),
            mission_type_name=properties.get('mission_type_name', '基础材料'),
            mission_name=properties.get('mission_name', '调查专项'),
            level=properties.get('level', '默认等级'),
            auto_battle_config=properties.get('auto_battle_config', '全配队通用'),
            run_times=properties.get('run_times', 0),
            plan_times=properties.get('plan_times', 1),
            card_num=properties.get('card_num', str(CardNumEnum.DEFAULT.value.value)),
            predefined_team_idx=properties.get('predefined_team_idx', 0),
            notorious_hunt_buff_num=properties.get('notorious_hunt_buff_num', 1),
        )
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

    def move_up(self, idx: int) -> None:
        if idx <= 0 or idx >= len(self.plan_list):
            return

        tmp = self.plan_list[idx - 1]
        self.plan_list[idx - 1] = self.plan_list[idx]
        self.plan_list[idx] = tmp

        self.save()

    def move_top(self, idx: int) -> None:
        if idx <= 0 or idx >= len(self.plan_list):
            return

        tmp = self.plan_list[idx]
        self.plan_list.pop(idx)
        self.plan_list.insert(0, tmp)

        self.save()

    def reset_plans(self) -> None:
        """
        根据运行次数 重置运行计划
        :return:
        """
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

    def get_next_plan(self, last_tried_plan: Optional[ChargePlanItem] = None) -> Optional[ChargePlanItem]:
        """
        获取下一个未完成的计划任务。
        如果提供了 last_tried_plan，则从该任务之后开始查找。
        如果未提供，则从列表的开头查找第一个未完成任务。
        不再在此方法内调用 reset_plans，重置逻辑由调用方（ChargePlanApp）管理。
        """
        if len(self.plan_list) == 0:
            return None

        start_index = 0
        if last_tried_plan is not None:
            # 1. 从上次尝试的计划之后开始查找
            last_tried_index = -1
            for i, plan in enumerate(self.plan_list):
                if self._is_same_plan(plan, last_tried_plan):
                    last_tried_index = i
                    break

            if last_tried_index != -1:
                start_index = last_tried_index + 1
                # 如果已到达列表末尾，返回 None
                if start_index >= len(self.plan_list):
                    return None
            else:
                # 2. 找不到上次计划则从头开始
                start_index = 0

        # 3. 从指定位置开始遍历查找符合条件的计划
        for i in range(start_index, len(self.plan_list)):
            plan = self.plan_list[i]
            if plan.run_times < plan.plan_times:
                return plan

        # 4. 检查完一轮都没找到合适的计划
        return None

    def all_plan_finished(self) -> bool:
        """
        是否全部计划已完成
        :return:
        """
        if self.plan_list is None:
            return True

        for plan in self.plan_list:
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

        # 如果两个计划都有ID，直接比较ID
        if hasattr(x, 'plan_id') and hasattr(y, 'plan_id') and x.plan_id and y.plan_id:
            return x.plan_id == y.plan_id

        # 向后兼容：如果没有ID，使用原有的比较方式
        return (x.tab_name == y.tab_name
                and x.category_name == y.category_name
                and x.mission_type_name == y.mission_type_name
                and x.mission_name == y.mission_name)

    @property
    def history_list(self) -> dict:
        return self.get('history_list', [])

    def get_history_by_uid(self, plan: ChargePlanItem) -> Optional[ChargePlanItem]:
        history_list = self.history_list
        for history_data in history_list:
            history = ChargePlanItem(**history_data)
            if self._is_same_plan(history, plan):
                return history
