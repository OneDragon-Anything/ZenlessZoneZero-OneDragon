from __future__ import annotations

from typing import Optional

from one_dragon.base.operation.application_run_record import (
    AppRunRecord,
    AppRunRecordPeriod,
)
from one_dragon.utils import os_utils
from zzz_od.application.matrix_action import matrix_action_const
from zzz_od.application.matrix_action.matrix_action_config import MatrixActionConfig


class MatrixActionRunRecord(AppRunRecord):

    def __init__(
        self,
        config: MatrixActionConfig,
        instance_idx: Optional[int] = None,
        game_refresh_hour_offset: int = 0,
    ):
        AppRunRecord.__init__(
            self,
            app_id=matrix_action_const.APP_ID,
            instance_idx=instance_idx,
            game_refresh_hour_offset=game_refresh_hour_offset,
            record_period=AppRunRecordPeriod.WEEKLY,
        )
        self.config: MatrixActionConfig = config

    @property
    def run_status_under_now(self):
        current_dt = self.get_current_dt()
        if os_utils.get_sunday_dt(self.dt) != os_utils.get_sunday_dt(current_dt):
            return AppRunRecord.STATUS_WAIT
        elif self.dt != current_dt:
            if self.is_finished_by_week():
                return AppRunRecord.STATUS_SUCCESS
            return AppRunRecord.STATUS_WAIT
        else:
            if self.is_finished_by_day():
                return AppRunRecord.STATUS_SUCCESS
            return AppRunRecord.STATUS_WAIT

    def check_and_update_status(self) -> None:
        current_dt = self.get_current_dt()
        if os_utils.get_sunday_dt(self.dt) != os_utils.get_sunday_dt(current_dt):
            self.reset_record()
            self.reset_for_weekly()
        elif self.dt != current_dt:
            self.reset_record()
            self.daily_run_times = 0
        else:
            if self.is_finished_by_week() or self.is_finished_by_day():
                return
            self.reset_record()

    def reset_for_weekly(self) -> None:
        self.weekly_run_times = 0
        self.daily_run_times = 0

    @property
    def weekly_run_times(self) -> int:
        return self.get("weekly_run_times", 0)

    @weekly_run_times.setter
    def weekly_run_times(self, new_value: int) -> None:
        self.update("weekly_run_times", new_value)

    @property
    def daily_run_times(self) -> int:
        return self.get("daily_run_times", 0)

    @daily_run_times.setter
    def daily_run_times(self, new_value: int) -> None:
        self.update("daily_run_times", new_value)

    def add_times(self) -> None:
        self.weekly_run_times = self.weekly_run_times + 1
        self.daily_run_times = self.daily_run_times + 1

    def is_finished_by_day(self) -> bool:
        if self.is_finished_by_week():
            return True
        return self.daily_run_times >= self.config.daily_plan_times

    def is_finished_by_week(self) -> bool:
        return self.weekly_run_times >= self.config.weekly_plan_times

