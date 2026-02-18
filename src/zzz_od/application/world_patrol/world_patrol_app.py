from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_notify import node_notify, NotifyTiming
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


class WorldPatrolApp(ZApplication):

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=world_patrol_const.APP_ID,
            op_name=world_patrol_const.APP_NAME,
        )

        self.config: WorldPatrolConfig = self.ctx.run_context.get_config(
            app_id=world_patrol_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )
        self.run_record: WorldPatrolRunRecord = self.ctx.run_context.get_run_record(
            app_id=world_patrol_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
        )

        self.route_list: list[WorldPatrolRoute] = []
        self.route_idx: int = 0

    @operation_node(name='初始化', is_start_node=True)
    def init_world_patrol(self) -> OperationRoundResult:
        self.ctx.auto_battle_context.init_auto_op(self.config.auto_battle)

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
    @operation_node(name='前往绳网')
    def goto_inter_knot(self) -> OperationRoundResult:
        # 无任务追踪 → 跳过
        result = self.round_by_find_area(self.last_screenshot, '大世界', '任务追踪')
        if result.is_success:
            return self.round_success(status='无任务追踪')

        # 有任务追踪
        return self.round_by_goto_screen(screen_name='绳网', success_wait=1, retry_wait=1)

    @node_from(from_name='前往绳网')
    @operation_node(name='停止追踪')
    def stop_tracking(self) -> OperationRoundResult:
        # 找到"停止追踪" → 点击 → 成功 → 返回大世界
        click_result = self.round_by_find_and_click_area(screen=self.last_screenshot, screen_name='绳网', area_name='按钮-停止追踪',
                                                         success_wait=1)
        if click_result.is_success:
            return click_result
        # 没找到"停止追踪"但找到"追踪" → 直接成功跳过 → 返回大世界
        find_result = self.round_by_find_area(self.last_screenshot, screen_name='绳网', area_name='按钮-追踪')
        if find_result.is_success:
            return self.round_success(status='无需停止追踪')
        # 都没找到（不可能） → retry 几次 → 失败 → 仍然返回大世界
        return self.round_retry(status='未找到追踪按钮', wait=1)

    @node_from(from_name='停止追踪')
    @node_from(from_name='停止追踪', success=False)
    @operation_node(name='停止追踪后返回大世界')
    def back_after_stop_tracking(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='前往绳网', status='无任务追踪')
    @node_from(from_name='停止追踪后返回大世界')
    @node_notify(when=NotifyTiming.CURRENT_DONE, detail=True)
    @operation_node(name='执行路线')
    def run_route(self) -> OperationRoundResult:
        if self.route_idx >= len(self.route_list):
            return self.round_success(status='路线已全部完成')

        route: WorldPatrolRoute = self.route_list[self.route_idx]
        if route.full_id in self.run_record.finished:
            self.route_idx += 1
            return self.round_wait(status=f'跳过已完成路线 {route.full_id}')

        op = WorldPatrolRunRoute(self.ctx, route)
        result = op.execute()

        def _is_stuck_over_limit_status(status: object) -> bool:
            return isinstance(status, str) and '重启当前路线' in status

        route_finished = False
        fail_status = None

        if result.success:
            route_finished = True
        elif _is_stuck_over_limit_status(result.status):
            # 二次尝试（从头）
            retry_op = WorldPatrolRunRoute(self.ctx, route, is_restarted=True)
            retry_result = retry_op.execute()
            if retry_result.success:
                route_finished = True
            elif _is_stuck_over_limit_status(retry_result.status):
                route_finished = False
                fail_status = '重启后再次卡住'
            else:
                fail_status = retry_result.status
        else:
            fail_status = result.status

        if route_finished:
            self.run_record.add_record(route.full_id)
            self.route_idx += 1
            return self.round_wait(status=f'完成路线 {route.full_id}')
        else:
            self.route_idx += 1
            return self.round_wait(status=f'路线失败 {fail_status} {route.full_id}')


def __debug():
    ctx = ZContext()
    ctx.init()

    app = WorldPatrolApp(ctx)
    app.execute()
    ctx.run_context.stop_running()


if __name__ == '__main__':
    __debug()
