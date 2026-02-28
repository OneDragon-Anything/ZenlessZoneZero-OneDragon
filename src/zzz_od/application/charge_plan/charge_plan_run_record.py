from one_dragon.base.operation.application_run_record import AppRunRecord


class ChargePlanRunRecord(AppRunRecord):

    def __init__(self, instance_idx: int | None = None, game_refresh_hour_offset: int = 0):
        AppRunRecord.__init__(
            self,
            'charge_plan',
            instance_idx=instance_idx,
            game_refresh_hour_offset=game_refresh_hour_offset
        )

    def check_and_update_status(self):  # 每次都运行
        self.reset_record()

    def reset_record(self) -> None:
        AppRunRecord.reset_record(self)
        self.current_charge_power = None

    @property
    def current_charge_power(self) -> int | None:
        return self.get('current_charge_power', None)

    @current_charge_power.setter
    def current_charge_power(self, new_value: int | None) -> None:
        self.update('current_charge_power', new_value)
