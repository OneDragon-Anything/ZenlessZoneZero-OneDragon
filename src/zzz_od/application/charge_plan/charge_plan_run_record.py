import time

from one_dragon.base.operation.application_run_record import AppRunRecord


class ChargePlanRunRecord(AppRunRecord):
    MAX_CHARGE_POWER = 240
    NATURAL_RECOVERY_SECONDS = 360

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
        self.charge_power_snapshot = [0, -1]

    @property
    def charge_power_snapshot(self) -> list[int]:
        return self.get('current_charge_power_snapshot', [0, -1])

    @charge_power_snapshot.setter
    def charge_power_snapshot(self, new_value: list[int]) -> None:
        charge_power, record_time = new_value
        self.update('current_charge_power_snapshot', [charge_power, record_time])

    def record_current_charge_power(self, charge_power: int) -> None:
        self.charge_power_snapshot = [charge_power, int(time.time())]

    def get_estimated_charge_power(self) -> int:
        charge_power, record_time = self.charge_power_snapshot
        if record_time == -1:
            return -1

        current_time = int(time.time())
        elapsed_seconds = max(0, current_time - record_time)
        recovered = int(elapsed_seconds // ChargePlanRunRecord.NATURAL_RECOVERY_SECONDS)

        return min(
            charge_power + recovered,
            ChargePlanRunRecord.MAX_CHARGE_POWER,
        )
