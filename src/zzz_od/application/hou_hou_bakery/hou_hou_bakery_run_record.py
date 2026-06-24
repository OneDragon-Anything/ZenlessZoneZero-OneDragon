
from one_dragon.base.operation.application_run_record import AppRunRecord


class HouHouBakeryRunRecord(AppRunRecord):

    def __init__(self, instance_idx: int | None = None, game_refresh_hour_offset: int = 0):
        AppRunRecord.__init__(
            self,
            'hou_hou_bakery',
            instance_idx=instance_idx,
            game_refresh_hour_offset=game_refresh_hour_offset
        )
