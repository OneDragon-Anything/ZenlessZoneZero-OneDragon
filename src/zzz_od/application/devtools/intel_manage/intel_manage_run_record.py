from one_dragon.base.operation.application_run_record import AppRunRecord
from zzz_od.application.devtools.intel_manage import intel_manage_const


class IntelManageRunRecord(AppRunRecord):
    """
    信息管理应用的运行记录
    """

    def __init__(self, instance_idx: int | None = None, game_refresh_hour_offset: int = 0):
        AppRunRecord.__init__(
            self,
            intel_manage_const.APP_ID,
            instance_idx=instance_idx,
            game_refresh_hour_offset=game_refresh_hour_offset,
        )