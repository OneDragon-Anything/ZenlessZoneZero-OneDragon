from one_dragon.base.operation.application_run_record import (
    AppRunRecord,
    AppRunRecordPeriod,
)
from zzz_od.application.intel_board import intel_board_const


class IntelBoardRunRecord(AppRunRecord):

    def __init__(self, instance_idx: int | None = None, game_refresh_hour_offset: int = 0):
        AppRunRecord.__init__(
            self,
            intel_board_const.APP_ID,
            instance_idx=instance_idx,
            game_refresh_hour_offset=game_refresh_hour_offset,
            record_period=AppRunRecordPeriod.WEEKLY
        )
