from typing import Optional

from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.application.world_patrol import world_patrol_const
from zzz_od.application.world_patrol.operation.world_patrol_run_route import (
    WorldPatrolRunRoute,
)
from zzz_od.application.world_patrol.world_patrol_config import WorldPatrolConfig
from zzz_od.application.world_patrol.world_patrol_route import WorldPatrolRoute
from zzz_od.application.world_patrol.world_patrol_route_list import RouteListType
from zzz_od.application.world_patrol.world_patrol_run_record import WorldPatrolRunRecord
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.goto.goto_menu import GotoMenu


class WorldPatrolApp(ZApplication):

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=world_patrol_const.APP_ID,
            op_name=world_patrol_const.APP_NAME,
            need_notify=False,
        )
        self.config: Optional[WorldPatrolConfig] = self.ctx.run_context.get_config(
            app_id=world_patrol_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )
        self.run_record: Optional[WorldPatrolRunRecord] = self.ctx.run_context.get_run_record(
            app_id=world_patrol_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
        )

        self.route_list: list[WorldPatrolRoute] = []
        self.route_idx: int = 0

    @operation_node(name='初始化', is_start_node=True)
    def init_world_patrol(self) -> OperationRoundResult:
        self.ctx.init_auto_op(self.config.auto_battle)

        self.ctx.world_patrol_service.load_data()
        for area in self.ctx.world_patrol_service.area_list:
            self.route_list.extend(self.ctx.world_patrol_service.get_world_patrol_routes_by_area(area))

        if self.config.route_list != '':
            route_list_configs = self.ctx.world_patrol_service.get_world_patrol_route_lists()
            config = None
            for route_list_config in route_list_configs:
                if route_list_config.name == self.config.route_list:
                    config = route_list_config
                    break

            if config is not None:
                route_id_list = config.route_items.copy()
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
    @operation_node(name='开始前返回大世界')
    def back_at_first(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='开始前返回大世界')
    @operation_node(name='打开菜单')
    def open_menu(self) -> OperationRoundResult:
        op = GotoMenu(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='打开菜单')
    @operation_node(name='前往绳网')
    def goto_inter_knot(self) -> OperationRoundResult:
        return self.round_by_goto_screen(screen_name='绳网', success_wait=1, retry_wait=1)

    @node_from(from_name='前往绳网')
    @operation_node(name='停止追踪')
    def stop_tracking(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(screen_name='绳网', area_name='按钮-停止追踪',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='停止追踪')
    @node_from(from_name='停止追踪', success=False)
    @operation_node(name='停止追踪后返回大世界')
    def back_after_stop_tracking(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='停止追踪后返回大世界')
    @operation_node(name='执行路线')
    def run_route(self) -> OperationRoundResult:
        if self.route_idx >= len(self.route_list):
            return self.round_success(status=f'路线已全部完成')

        route: WorldPatrolRoute = self.route_list[self.route_idx]
        if route.full_id in self.run_record.finished:
            self.route_idx += 1
            return self.round_wait(status=f'跳过已完成路线 {route.full_id}')

        op = WorldPatrolRunRoute(self.ctx, route)
        result = op.execute()
        if result.success:
            self.run_record.add_record(route.full_id)
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
    ctx.run_context.stop_running()


if __name__ == '__main__':
    __debug()
