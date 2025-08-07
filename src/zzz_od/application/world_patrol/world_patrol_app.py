from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.application.world_patrol.operation.world_patrol_run_route import WorldPatrolRunRoute
from zzz_od.application.world_patrol.world_patrol_route import WorldPatrolRoute
from zzz_od.application.world_patrol.world_patrol_route_list import RouteListType
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext


class WorldPatrolApp(ZApplication):

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx, app_id='world_patrol',
            op_name='锄大地',
            run_record=ctx.lost_void_record,
            need_notify=False,
        )

        self.route_list: list[WorldPatrolRoute] = []
        self.route_idx: int = 0

    @operation_node(name='初始化', is_start_node=True)
    def init_world_patrol(self) -> OperationRoundResult:
        self.ctx.init_auto_op(self.ctx.world_patrol_config.auto_battle)

        self.ctx.world_patrol_service.load_data()
        for area in self.ctx.world_patrol_service.area_list:
            self.route_list.extend(self.ctx.world_patrol_service.get_world_patrol_routes_by_area(area))

        if self.ctx.world_patrol_config.route_list != '':
            route_list_configs = self.ctx.world_patrol_service.get_world_patrol_route_lists()
            config = None
            for route_list_config in route_list_configs:
                if route_list_config.name == self.ctx.world_patrol_config.route_list:
                    config = route_list_config
                    break

            if config is not None:
                route_id_list = [route.area_full_id + '_' + str(route.idx) for route in config.route_items]
                if config.list_type == RouteListType.BLACKLIST:
                    self.route_list = [
                        route
                        for route in self.route_list
                        if route.full_id not in route_id_list
                    ]
                elif config.list_type == RouteListType.WHITELIST:
                    self.route_list = [
                        route
                        for route in self.route_list
                        if route.full_id in route_id_list
                    ]
        return self.round_success(status=f'加载路线 {len(self.route_list)}')

    @node_from(from_name='初始化')
    @operation_node(name='执行路线')
    def run_route(self) -> OperationRoundResult:
        if self.route_idx >= len(self.route_list):
            return self.round_success(status=f'路线已全部完成')

        route: WorldPatrolRoute = self.route_list[self.route_idx]
        if route.full_id in self.ctx.world_patrol_run_record.finished:
            self.route_idx += 1
            return self.round_wait(status=f'跳过已完成路线 {route.full_id}')

        op = WorldPatrolRunRoute(self.ctx, route)
        result = op.execute()
        if result.success:
            self.ctx.world_patrol_run_record.add_record(route.full_id)
            self.route_idx += 1
            return self.round_wait(status=f'完成路线 {route.full_id}')
        else:
            self.route_idx += 1
            return self.round_wait(status=f'路线失败 {result.status} {route.full_id}')


def __debug():
    ctx = ZContext()
    ctx.init_by_config()

    app = WorldPatrolApp(ctx)
    app.execute()
    ctx.stop_running()


if __name__ == '__main__':
    __debug()