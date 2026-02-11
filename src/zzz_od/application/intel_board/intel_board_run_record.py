from one_dragon.base.operation.application_run_record import (
    AppRunRecord,
    AppRunRecordPeriod,
)
from zzz_od.application.intel_board import intel_board_const

# 每次战斗获得的经验值
EXP_PER_NOTORIOUS_HUNT = 500
EXP_PER_EXPERT_CHALLENGE = 250
EXP_TARGET = 5000


class IntelBoardRunRecord(AppRunRecord):

    def __init__(self, instance_idx: int | None = None, game_refresh_hour_offset: int = 0):
        AppRunRecord.__init__(
            self,
            intel_board_const.APP_ID,
            instance_idx=instance_idx,
            game_refresh_hour_offset=game_refresh_hour_offset,
            record_period=AppRunRecordPeriod.WEEKLY
        )

    @property
    def progress_complete(self) -> bool:
        """本周期进度是否已满 (1000/1000)"""
        return self.get('progress_complete', False)

    @progress_complete.setter
    def progress_complete(self, value: bool) -> None:
        self.update('progress_complete', value)

    @property
    def notorious_hunt_count(self) -> int:
        """本周期恶名狩猎完成次数"""
        return self.get('notorious_hunt_count', 0)

    @notorious_hunt_count.setter
    def notorious_hunt_count(self, value: int) -> None:
        self.update('notorious_hunt_count', value)

    @property
    def expert_challenge_count(self) -> int:
        """本周期专业挑战室完成次数"""
        return self.get('expert_challenge_count', 0)

    @expert_challenge_count.setter
    def expert_challenge_count(self, value: int) -> None:
        self.update('expert_challenge_count', value)

    @property
    def base_exp(self) -> int:
        """根据OCR进度估算的基础经验值（计数为0时的历史经验）"""
        return self.get('base_exp', 0)

    @base_exp.setter
    def base_exp(self, value: int) -> None:
        self.update('base_exp', value)

    @property
    def total_exp(self) -> int:
        """本周期已累计经验值"""
        return (self.base_exp
                + self.notorious_hunt_count * EXP_PER_NOTORIOUS_HUNT
                + self.expert_challenge_count * EXP_PER_EXPERT_CHALLENGE)

    @property
    def exp_complete(self) -> bool:
        """经验值是否已刷满"""
        return self.total_exp >= EXP_TARGET

    def reset_record(self):
        AppRunRecord.reset_record(self)
        self.progress_complete = False
        self.notorious_hunt_count = 0
        self.expert_challenge_count = 0
        self.base_exp = 0

    @property
    def run_status_under_now(self) -> int:
        if self._should_reset_by_dt():
            return AppRunRecord.STATUS_WAIT
        if self.progress_complete or self.exp_complete:
            return AppRunRecord.STATUS_SUCCESS
        return self.run_status
