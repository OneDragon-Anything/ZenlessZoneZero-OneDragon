from typing import Optional

from one_dragon.base.operation.application_run_record import AppRunRecord, AppRunRecordPeriod
from one_dragon.utils import os_utils
from zzz_od.application.hollow_zero.lost_void.lost_void_config import LostVoidConfig, LostVoidExtraTask


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

    def is_finished_by_week(self) -> bool:
        """
        按周的角度看是否已经完成
        """
        if self.weekly_run_times < self.config.weekly_plan_times:
            # 基础次数都还没有完成
            return False
        if self.config.extra_task == LostVoidExtraTask.NONE.value.value:
            # 完成基础次数 不需要额外刷取
            return True
        elif self.config.extra_task == LostVoidExtraTask.EVAL_POINT.value.value:
            # 完成基础次数 需要刷业绩 就看空业绩点出来没有
            return self.eval_point_complete
        elif self.config.extra_task == LostVoidExtraTask.PERIOD_REWARD.value.value:
            return self.period_reward_complete
        else:
            return False

    def is_finished_by_day(self) -> bool:
        """
        按天角度看是否已经完成
        """
        if self.is_finished_by_week():
            return True
        elif self.daily_run_times < self.config.daily_plan_times:
            # 基础次数都还没有完成
            return False
        else:
            return True

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
            if self.is_finished_by_week():  # 看本周是否已经完成
                return AppRunRecord.STATUS_SUCCESS
            else:
                return AppRunRecord.STATUS_WAIT
        else:  # 当天的
            if self.is_finished_by_day():  # 看当天是否已经完成
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
            if self.is_finished_by_week():
                pass
            elif self.is_finished_by_day():
                pass
            else:
                self.reset_record()

    def reset_for_weekly(self) -> None:
        self.weekly_run_times = 0
        self.daily_run_times = 0
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