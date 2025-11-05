from enum import Enum

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.operation.application.application_config import ApplicationConfig


class LostVoidTaskEnum(Enum):

    BOUNTY_COMMISSION = ConfigItem('完成悬赏委托', desc='完成每周8000积分奖励')
    EVAL_POINT = ConfigItem('刷满业绩点', desc='刷满每周业绩点')
    PERIOD_REWARD = ConfigItem('刷满周期奖励', desc='刷满每周丁尼')
    WEEKLY_PLAN_TIMES = ConfigItem('完成周计划次数', desc='完成配置的每周计划次数')


class LostVoidConfig(ApplicationConfig):

    def __init__(self, instance_idx: int, group_id: str):
        ApplicationConfig.__init__(
            self,
            app_id='lost_void',
            instance_idx=instance_idx,
            group_id=group_id,
        )

    @property
    def daily_plan_times(self) -> int:
        return self.get('daily_plan_times', 5)

    @daily_plan_times.setter
    def daily_plan_times(self, new_value: int):
        self.update('daily_plan_times', new_value)

    @property
    def weekly_plan_times(self) -> int:
        return self.get('weekly_plan_times', 2)

    @weekly_plan_times.setter
    def weekly_plan_times(self, new_value: int):
        self.update('weekly_plan_times', new_value)

    @property
    def extra_task(self) -> str:
        return self.get('extra_task', LostVoidTaskEnum.BOUNTY_COMMISSION.value.value)

    @extra_task.setter
    def extra_task(self, new_value: str):
        self.update('extra_task', new_value)

    @property
    def is_bounty_commission_mode(self) -> bool:
        return self.extra_task == LostVoidTaskEnum.BOUNTY_COMMISSION.value.value

    @property
    def mission_name(self) -> str:
        return self.get('mission_name', '战线肃清')

    @mission_name.setter
    def mission_name(self, new_value: str):
        self.update('mission_name', new_value)

    @property
    def challenge_config(self) -> str:
        return self.get('challenge_config', '默认-终结')

    @challenge_config.setter
    def challenge_config(self, new_value: str):
        self.update('challenge_config', new_value)