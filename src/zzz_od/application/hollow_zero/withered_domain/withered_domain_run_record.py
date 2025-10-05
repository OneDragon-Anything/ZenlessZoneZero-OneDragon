from typing import Optional

from one_dragon.base.operation.application_run_record import (
    AppRunRecord,
    AppRunRecordPeriod,
)
from one_dragon.utils import os_utils
from zzz_od.application.hollow_zero.withered_domain import withered_domain_const
from zzz_od.application.hollow_zero.withered_domain.withered_domain_config import (
    HollowZeroExtraTask,
    WitheredDomainConfig,
)


class WitheredDomainRunRecord(AppRunRecord):

    def __init__(self, config: WitheredDomainConfig, instance_idx: Optional[int] = None, game_refresh_hour_offset: int = 0):
        AppRunRecord.__init__(
            self,
            app_id=withered_domain_const.APP_ID,
            instance_idx=instance_idx,
            game_refresh_hour_offset=game_refresh_hour_offset,
            record_period=AppRunRecordPeriod.WEEKLY
        )
        self.config: WitheredDomainConfig = config

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
        self.no_eval_point = False
        self.period_reward_complete = False

    @property
    def weekly_run_times(self) -> int:
        return self.get('weekly_run_times', 0)

    @weekly_run_times.setter
    def weekly_run_times(self, new_value: int) -> None:
        self.update('weekly_run_times', new_value)

    @property
    def daily_run_times(self) -> int:
        return self.get('daily_run_times', 0)

    @daily_run_times.setter
    def daily_run_times(self, new_value: int) -> None:
        self.update('daily_run_times', new_value)

    def add_times(self) -> None:
        """
        增加通关次数
        :return:
        """
        self.weekly_run_times = self.weekly_run_times + 1

    def add_daily_times(self) -> None:
        """
        增加一次每日进入次数
        @return:
        """
        self.daily_run_times = self.daily_run_times + 1

    def is_finished_by_times(self) -> bool:
        """
        从运行次数看 是否已经完成了
        :return:
        """
        return (self.weekly_run_times >= self.config.weekly_plan_times
                or self.daily_run_times >= self.config.daily_plan_times)

    def is_finished_by_weekly_times(self) -> bool:
        """
        从每周运行次数看 是否已经完成了
        :return:
        """
        return self.weekly_run_times >= self.config.weekly_plan_times

    def is_finished_by_day(self) -> bool:
        """
        按天的角度看是否已经完成
        """
        if self.is_finished_by_week():
            return True
        return self.daily_run_times >= self.config.daily_plan_times

    def is_finished_by_week(self) -> bool:
        """
        按周的角度看是否已经完成
        """
        if self.weekly_run_times < self.config.weekly_plan_times:
            # 基础次数都还没有完成
            return False
        if self.config.extra_task == HollowZeroExtraTask.NONE.value.value:
            # 完成基础次数 不需要额外刷取
            return True
        elif self.config.extra_task == HollowZeroExtraTask.EVA_POINT.value.value:
            # 完成基础次数 需要刷业绩 就看空业绩点出来没有
            return self.no_eval_point
        elif self.config.extra_task == HollowZeroExtraTask.PERIOD_REWARD.value.value:
            return self.period_reward_complete
        else:
            return False

    @property
    def no_eval_point(self) -> bool:
        return self.get('no_eval_point', False)

    @no_eval_point.setter
    def no_eval_point(self, new_value: bool) -> None:
        self.update('no_eval_point', new_value)

    @property
    def period_reward_complete(self) -> bool:
        return self.get('period_reward_complete', False)

    @period_reward_complete.setter
    def period_reward_complete(self, new_value: bool) -> None:
        """
        在精英怪战斗结束后提示周期奖励满
        或者通关后 没有显示丁尼奖励
        @param new_value:
        @return:
        """
        self.update('period_reward_complete', new_value)

