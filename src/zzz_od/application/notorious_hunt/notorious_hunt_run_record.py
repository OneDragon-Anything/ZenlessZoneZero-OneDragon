from __future__ import annotations

from one_dragon.base.operation.application_run_record import (
    AppRunRecord,
    AppRunRecordPeriod,
)
from one_dragon.utils import os_utils
from zzz_od.application.notorious_hunt.notorious_hunt_config import NotoriousHuntConfig


class NotoriousHuntRunRecord(AppRunRecord):

    def __init__(
        self,
        config: NotoriousHuntConfig | None = None,
        instance_idx: int | None = None,
        game_refresh_hour_offset: int = 0,
    ):
        AppRunRecord.__init__(
            self,
            'notorious_hunt',
            instance_idx=instance_idx,
            game_refresh_hour_offset=game_refresh_hour_offset,
            record_period=AppRunRecordPeriod.WEEKLY,
        )
        self.config: NotoriousHuntConfig | None = config

    def reset_record(self) -> None:
        AppRunRecord.reset_record(self)
        self.left_times = 3

    def get_current_weekday(self) -> int:
        return os_utils.get_current_day_of_week(self.game_refresh_hour_offset)

    @property
    def is_finished_by_week(self) -> bool:
        if self._should_reset_by_dt():
            return False

        return (self.left_times <= 0
                or self.run_status == AppRunRecord.STATUS_SUCCESS)

    @property
    def is_auto_run_allowed_today(self) -> bool:
        if self.config is None:
            return True

        return self.get_current_weekday() >= self.config.weekly_challenge_start_weekday

    @property
    def is_done(self) -> bool:
        if self.is_finished_by_week:
            return True

        return not self.is_auto_run_allowed_today

    @property
    def run_status_under_now(self):
        """
        基于当前时间显示的运行状态
        :return:
        """
        if self._should_reset_by_dt():
            return AppRunRecord.STATUS_WAIT
        elif self.left_times > 0:
            return self.run_status
        else:
            return AppRunRecord.STATUS_SUCCESS

    @property
    def left_times(self) -> int:
        return self.get('left_times', 3)

    @left_times.setter
    def left_times(self, new_value: int) -> None:
        self.update('left_times', new_value)
