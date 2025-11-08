from typing import Optional

from one_dragon.base.operation.application_run_record import AppRunRecord, AppRunRecordPeriod
from one_dragon.utils import os_utils
from zzz_od.application.hollow_zero.lost_void.lost_void_config import LostVoidConfig, LostVoidTaskEnum


class LostVoidRunRecord(AppRunRecord):

    def __init__(self, config: LostVoidConfig, instance_idx: Optional[int] = None, game_refresh_hour_offset: int = 0):
        AppRunRecord.__init__(
            self,
            'lost_void',
            instance_idx=instance_idx,
            game_refresh_hour_offset=game_refresh_hour_offset,
            record_period=AppRunRecordPeriod.WEEKLY
        )

        self.config: LostVoidConfig = config

    @property
    def daily_run_times(self) -> int:
        return self.get('daily_run_times', 0)

    @daily_run_times.setter
    def daily_run_times(self, new_value: int):
        self.update('daily_run_times', new_value)

    @property
    def weekly_run_times(self) -> int:
        return self.get('weekly_run_times', 0)

    @weekly_run_times.setter
    def weekly_run_times(self, new_value: int):
        self.update('weekly_run_times', new_value)

    def add_complete_times(self) -> None:
        """
        每周和每天都增加一次完成次数
        @return:
        """
        self.daily_run_times += 1
        self.weekly_run_times += 1

    @property
    def bounty_commission_complete(self) -> bool:
        """
        是否已经刷满悬赏委托
        """
        return self.get('bounty_commission_complete', False)

    @bounty_commission_complete.setter
    def bounty_commission_complete(self, new_value: bool) -> None:
        """
        是否已经刷满悬赏委托
        """
        self.update('bounty_commission_complete', new_value)

    @property
    def eval_point_complete(self) -> bool:
        """
        是否已经刷满业绩点
        """
        return self.get('eval_point_complete', False)

    @eval_point_complete.setter
    def eval_point_complete(self, new_value: bool) -> None:
        """
        是否已经刷满业绩点
        """
        self.update('eval_point_complete', new_value)

    @property
    def period_reward_complete(self) -> bool:
        """
        是否已经刷满周期奖励
        """
        return self.get('period_reward_complete', False)

    @period_reward_complete.setter
    def period_reward_complete(self, new_value: bool) -> None:
        """
        是否已经刷满周期奖励
        """
        self.update('period_reward_complete', new_value)

    @property
    def is_finished_by_week(self) -> bool:
        """
        按周的角度看是否已经完成
        """
        if self.config.extra_task == LostVoidTaskEnum.BOUNTY_COMMISSION.value.value:
            # 需要刷悬赏委托 就看8000积分奖励完成没有
            return self.bounty_commission_complete
        elif self.config.extra_task == LostVoidTaskEnum.EVAL_POINT.value.value:
            # 需要刷业绩 就看空业绩点出来没有
            return self.eval_point_complete
        elif self.config.extra_task == LostVoidTaskEnum.PERIOD_REWARD.value.value:
            return self.period_reward_complete
        elif self.config.extra_task == LostVoidTaskEnum.WEEKLY_PLAN_TIMES.value.value:
            return self.weekly_run_times >= self.config.weekly_plan_times
        else:
            return False

    @property
    def is_finished_by_day(self) -> bool:
        """
        按天的角度看是否已经完成
        """
        if self.is_finished_by_week:
            return True
        # 当周未完成的情况下，按照每天上限次数判断当天是否完成
        return self.daily_run_times >= self.config.daily_plan_times

    @property
    def run_status_under_now(self):
        """
        基于当前时间显示的运行状态
        :return:
        """
        current_dt = self.get_current_dt()
        if os_utils.get_sunday_dt(self.dt) != os_utils.get_sunday_dt(current_dt):  # 上一次运行已经是上一周
            # 必定是重置
            return AppRunRecord.STATUS_WAIT
        elif self.dt != current_dt:  # 上一次运行已经是一天前
            if self.is_finished_by_week:  # 看本周是否已经完成
                return AppRunRecord.STATUS_SUCCESS
            else:
                return AppRunRecord.STATUS_WAIT
        else:  # 当天的
            if self.is_finished_by_day:  # 看当天是否已经完成
                return AppRunRecord.STATUS_SUCCESS
            else:
                return AppRunRecord.STATUS_WAIT

    def check_and_update_status(self) -> None:
        """
        判断并更新状态
        """
        current_dt = self.get_current_dt()
        if os_utils.get_sunday_dt(self.dt) != os_utils.get_sunday_dt(current_dt):  # 上一次运行已经是上一周
            # 必定是重置
            self.reset_record()
            self.reset_for_weekly()
        elif self.dt != current_dt:  # 上一次运行已经是一天前
            self.reset_record()
            self.daily_run_times = 0
        else:  # 当天的
            if self.is_finished_by_week:
                pass
            elif self.is_finished_by_day:
                pass
            else:
                self.reset_record()

    def reset_for_weekly(self) -> None:
        self.weekly_run_times = 0
        self.daily_run_times = 0
        self.bounty_commission_complete = False
        self.eval_point_complete = False
        self.period_reward_complete = False
        self.complete_task_force_with_up = False

    @property
    def complete_task_force_with_up(self) -> bool:
        """
        是否使用了UP代理人完成特遣调查
        :return:
        """
        return self.get('complete_task_force_with_up', False)

    @complete_task_force_with_up.setter
    def complete_task_force_with_up(self, new_value: bool) -> None:
        self.update('complete_task_force_with_up', new_value)
