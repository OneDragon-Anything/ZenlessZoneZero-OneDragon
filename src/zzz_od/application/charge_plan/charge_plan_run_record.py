import time

from one_dragon.base.operation.application_run_record import AppRunRecord


class ChargePlanRunRecord(AppRunRecord):
    MAX_CHARGE_POWER = 240
    NATURAL_RECOVERY_SECONDS = 6 * 60

    def __init__(self, instance_idx: int | None = None, game_refresh_hour_offset: int = 0):
        AppRunRecord.__init__(
            self,
            'charge_plan',
            instance_idx=instance_idx,
            game_refresh_hour_offset=game_refresh_hour_offset
        )

    def check_and_update_status(self) -> None:  # 每次都运行
        self.reset_record()

    def reset_record(self) -> None:
        AppRunRecord.reset_record(self)
        self.current_charge_power = None
        self.current_charge_power_record_time = None

    @property
    def current_charge_power(self) -> int | None:
        return self.get('current_charge_power', None)

    @current_charge_power.setter
    def current_charge_power(self, new_value: int | None) -> None:
        self.update('current_charge_power', new_value)

    @property
    def current_charge_power_record_time(self) -> float | None:
        return self.get('current_charge_power_record_time', None)

    @current_charge_power_record_time.setter
    def current_charge_power_record_time(self, new_value: float | None) -> None:
        self.update('current_charge_power_record_time', new_value)

    def record_current_charge_power(
        self,
        charge_power: int,
        record_time: float | None = None,
    ) -> None:
        if record_time is None:
            record_time = time.time()

        self.update('current_charge_power', charge_power, False)
        self.update('current_charge_power_record_time', record_time, False)
        self.save()

    def get_estimated_charge_power(self, current_time: float | None = None) -> int | None:
        charge_power = self.current_charge_power
        if charge_power is None:
            return None

        if current_time is None:
            current_time = time.time()

        record_time = self.current_charge_power_record_time
        if record_time is None:
            return min(charge_power, ChargePlanRunRecord.MAX_CHARGE_POWER)

        elapsed_seconds = max(0.0, current_time - record_time)
        recovered = int(elapsed_seconds // ChargePlanRunRecord.NATURAL_RECOVERY_SECONDS)

        return min(
            charge_power + recovered,
            ChargePlanRunRecord.MAX_CHARGE_POWER,
        )
