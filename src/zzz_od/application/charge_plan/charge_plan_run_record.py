import time

from one_dragon.base.operation.application_run_record import AppRunRecord

ChargePowerSnapshot = tuple[int, float]

class ChargePlanRunRecord(AppRunRecord):
    MAX_CHARGE_POWER = 240
    NATURAL_RECOVERY_SECONDS = 6 * 60
    SNAPSHOT_KEY = 'current_charge_power_snapshot'

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
        self.charge_power_snapshot = None

    @property
    def charge_power_snapshot(self) -> ChargePowerSnapshot | None:
        snapshot = self.get(ChargePlanRunRecord.SNAPSHOT_KEY, None)
        if not isinstance(snapshot, (list, tuple)) or len(snapshot) != 2:
            return None

        charge_power, record_time = snapshot
        if not isinstance(charge_power, int) or not isinstance(record_time, (int, float)):
            return None

        return charge_power, float(record_time)

    @charge_power_snapshot.setter
    def charge_power_snapshot(self, new_value: ChargePowerSnapshot | None) -> None:
        if new_value is None:
            self.update(ChargePlanRunRecord.SNAPSHOT_KEY, None)
            return
        self.update(
            ChargePlanRunRecord.SNAPSHOT_KEY,
            [new_value[0], new_value[1]],
        )

    def record_current_charge_power(
        self,
        charge_power: int,
        record_time: float | None = None,
    ) -> None:
        if record_time is None:
            record_time = time.time()

        self.charge_power_snapshot = (charge_power, record_time)

    def get_estimated_charge_power(self, current_time: float | None = None) -> int | None:
        snapshot = self.charge_power_snapshot
        if snapshot is None:
            return None

        if current_time is None:
            current_time = time.time()

        elapsed_seconds = max(0.0, current_time - snapshot[1])
        recovered = int(elapsed_seconds // ChargePlanRunRecord.NATURAL_RECOVERY_SECONDS)

        return min(
            snapshot[0] + recovered,
            ChargePlanRunRecord.MAX_CHARGE_POWER,
        )
