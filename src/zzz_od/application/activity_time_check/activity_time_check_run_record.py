from one_dragon.base.operation.application_run_record import AppRunRecord


class ActivityTimeCheckRunRecord(AppRunRecord):

    def __init__(self, instance_idx: int | None = None, game_refresh_hour_offset: int = 0):
        AppRunRecord.__init__(
            self,
            'activity_time_check',
            instance_idx=instance_idx,
            game_refresh_hour_offset=game_refresh_hour_offset
        )

    def check_and_update_status(self):
        """每次都运行"""
        self.reset_record()
