from one_dragon.base.operation.application_run_record import AppRunRecord


class WorldPatrolRunRecord(AppRunRecord):

    def __init__(self, instance_idx: int | None = None, game_refresh_hour_offset: int = 0):
        self.finished: list[str] = []
        self.time_cost: dict[str, list[float]] = {}
        self.completed_rounds: int = 0
        self.routes_per_round: int = 0
        AppRunRecord.__init__(self, 'world_patrol', instance_idx=instance_idx,
                              game_refresh_hour_offset=game_refresh_hour_offset)
        self.finished = self.get('finished', [])
        self.completed_rounds = self.get('completed_rounds', 0)
        self.routes_per_round = self.get('routes_per_round', 0)

    def reset_record(self):
        AppRunRecord.reset_record(self)
        self.finished = []
        self.completed_rounds = 0
        self.update('finished', self.finished, False)
        self.update('completed_rounds', self.completed_rounds, False)
        self.save()

    def reset_finished(self) -> None:
        """清空当日已完成路线列表，不影响其他记录字段。"""
        self.finished = []
        self.update('finished', self.finished, False)
        self.save()

    def inc_completed_rounds(self) -> None:
        """当日已完成轮数 +1，下次启动据此决定从第几轮继续。"""
        self.completed_rounds += 1
        self.update('completed_rounds', self.completed_rounds, False)
        self.save()

    def set_routes_per_round(self, count: int) -> None:
        """记录本次任务执行的路线数。"""
        self.routes_per_round = count
        self.update('routes_per_round', self.routes_per_round, False)
        self.save()

    def add_record(self, route_id: str):
        self.finished.append(route_id)
        if route_id not in self.time_cost:
            self.time_cost[route_id] = []
        while len(self.time_cost[route_id]) > 3:
            self.time_cost[route_id].pop(0)

        self.update('dt', self.dt, False)
        self.update('finished', self.finished, False)
        self.save()
