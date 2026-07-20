import time

from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_notify import NotifyTiming, node_notify
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.log_utils import log
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
        self.run_record.total_rounds = self.config.daily_loop_count
        self.run_record.set_routes_per_round(len(self.route_list))
        # 基于当日已完成轮数计算起始轮次，使重启任务能从下一轮继续
        self.run_record.current_round = self.run_record.completed_rounds + 1
        # 仅清本轮的计时字段，保留 finished 以支持任务中途停止后的续跑
        self.run_record.reset_round_timing()
        if self.run_record.current_round > self.run_record.total_rounds:
            log.info(f'锄大地当日已完成 {self.run_record.completed_rounds}/{self.run_record.total_rounds} 轮，无需再跑')
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
        return self.round_by_goto_screen(screen_name='绳网', retry_wait=1)

    @node_from(from_name='前往绳网')
    @operation_node(name='停止追踪')
    def stop_tracking(self) -> OperationRoundResult:
        # 找到"停止追踪" → 点击 → 成功 → 返回大世界
        click_result = self.round_by_find_and_click_area(self.last_screenshot, '绳网', '按钮-停止追踪')
        if click_result.is_success:
            return click_result
        # 没找到"停止追踪"但找到"追踪" → 直接成功跳过 → 返回大世界
        find_result = self.round_by_find_area(self.last_screenshot, '绳网', '按钮-追踪')
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
    @node_from(from_name='准备下一轮', status='进入下一轮')
    @node_notify(when=NotifyTiming.CURRENT_DONE, detail=True)
    @operation_node(name='执行路线')
    def run_route(self) -> OperationRoundResult:
        # 当日已完成的轮数已达上限，直接走「全部完成」分支
        if self.run_record.current_round > self.run_record.total_rounds:
            return self.round_success(status='路线已全部完成')

        # 轮次首次进入：记录起始时间并打印开场日志
        if self.run_record.round_start_time is None:
            self.run_record.round_start_time = time.monotonic()
            log.info(f'开始第 {self.run_record.current_round}/{self.run_record.total_rounds} 轮锄大地')

        if self.route_idx >= len(self.route_list):
            return self.round_success(status='路线已全部完成')

        route: WorldPatrolRoute = self.route_list[self.route_idx]
        if route.full_id in self.run_record.finished:
            self.route_idx += 1
            return self.round_wait(status=f'跳过已完成路线 {route.full_id}')

        def _is_stuck_over_limit_status(status: object) -> bool:
            return isinstance(status, str) and '重启当前路线' in status

        route_finished = False
        fail_status = None
        retry_times = self.config.route_retry_times  # 同一条路线允许传送回当前路线起点重跑的最大次数
        attempt_idx = 0  # 当前是第几次尝试，0 表示首次执行，大于 0 表示已进入重试态

        while True:
            # 首次执行始终正常脱困；进入重试态后，是否仍尝试脱困由「路线重试处理方式」决定
            is_restarted = attempt_idx > 0 and self.config.route_retry_action == WorldPatrolConfig.ROUTE_RETRY_ACTION_SKIP
            op = WorldPatrolRunRoute(self.ctx, route, is_restarted=is_restarted)
            result = op.execute()

            if result.success:
                route_finished = True
                break

            if result.status == WorldPatrolRunRoute.STATUS_UI_DISAPPEARED:
                action = self.config.ui_disappear_action
                if action == WorldPatrolConfig.UI_DISAPPEAR_SILENT_FAIL:
                    log.warning(
                        f'第 {self.run_record.current_round}/{self.run_record.total_rounds} 轮因界面消失静默失败终止任务 '
                        f'路线 {route.full_id}'
                    )
                    self._stop_route_actions()
                    return self.round_fail(status=f'{WorldPatrolRunRoute.STATUS_UI_DISAPPEARED} {route.full_id}')

                restart_result = self._restart_game_for_ui_disappeared()
                if restart_result.is_fail:
                    return restart_result

                if action == WorldPatrolConfig.UI_DISAPPEAR_RESTART_RETRY and attempt_idx < retry_times:
                    attempt_idx += 1
                    continue

                self.route_idx += 1
                if action == WorldPatrolConfig.UI_DISAPPEAR_RESTART_RETRY:
                    return self.round_wait(status=f'界面消失重试耗尽，已重开游戏并跳过路线 {route.full_id}')
                return self.round_wait(status=f'界面消失已重开游戏并跳过路线 {route.full_id}')

            if _is_stuck_over_limit_status(result.status):
                # 「单条路线重试上限」是硬上限：还有额度就传送回当前路线起点重跑，额度用完则跳过该路线
                if attempt_idx < retry_times:
                    attempt_idx += 1
                    continue

                route_finished = False
                if attempt_idx > 0:
                    fail_status = f'重试 {attempt_idx} 次后仍卡住: {result.status}'
                else:
                    fail_status = result.status
                break

            fail_status = result.status
            break

        if route_finished:
            self.run_record.add_record(route.full_id)
            self.route_idx += 1
            return self.round_wait(status=f'完成路线 {route.full_id}')
        else:
            self.route_idx += 1
            return self.round_wait(status=f'路线失败 {fail_status} {route.full_id}')

    @node_from(from_name='执行路线', status='路线已全部完成')
    @operation_node(name='轮次结束判定')
    def decide_next_round(self) -> OperationRoundResult:
        """一轮路线跑完后的分流：

        - 当日已完成轮数已满 → 直接结束，本次不计入完成数
        - 本轮是最后一轮 → 计入当日已完成轮数后结束
        - 还有下一轮 → 计入当日已完成轮数后按配置间隔算出还要等多久
        """
        if self.run_record.current_round > self.run_record.total_rounds:
            log.info(f'锄大地当日已完成 {self.run_record.completed_rounds}/{self.run_record.total_rounds} 轮，无需再跑')
            return self.round_success(status='全部完成')

        # 本轮真实跑完，加入当日已完成轮数
        self.run_record.inc_completed_rounds()

        if self.run_record.current_round >= self.run_record.total_rounds:
            log.info(f'锄大地全部循环已完成 共 {self.run_record.total_rounds} 轮')
            return self.round_success(status='全部完成')

        loop_interval_seconds = self.config.loop_interval_seconds
        round_duration = time.monotonic() - self.run_record.round_start_time
        self.run_record.round_wait_seconds = max(0.0, loop_interval_seconds - round_duration)

        if self.run_record.round_wait_seconds > 0:
            log.info(
                f'第 {self.run_record.current_round}/{self.run_record.total_rounds} 轮耗时 {round_duration:.0f}s '
                f'最少占用 {loop_interval_seconds}s 将等待 {self.run_record.round_wait_seconds:.0f}s'
            )
        return self.round_success(status='进入轮间等待')

    @node_from(from_name='轮次结束判定', status='进入轮间等待')
    @operation_node(name='传送回录像店')
    def goto_video_shop(self) -> OperationRoundResult:
        """轮间等待前先离开野怪刷新点，离开勘域以避免怪物刷新后攻击我们。"""
        op = BackToNormalWorld(self.ctx, ensure_normal_world=True)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='传送回录像店')
    @operation_node(name='轮间等待')
    def wait_between_rounds(self) -> OperationRoundResult:
        """以 1 秒为粒度轮询等待，借助 round_wait 让暂停/停止信号能及时响应。"""
        if self.run_record.round_wait_start_time is None:
            self.run_record.round_wait_start_time = time.monotonic()

        elapsed = time.monotonic() - self.run_record.round_wait_start_time
        if elapsed >= self.run_record.round_wait_seconds:
            return self.round_success(status='等待完成')

        return self.round_wait(
            status=f'轮间等待中 {elapsed:.0f}/{self.run_record.round_wait_seconds:.0f}s',
            wait=min(1.0, self.run_record.round_wait_seconds - elapsed),
        )

    @node_from(from_name='轮间等待', status='等待完成')
    @operation_node(name='准备下一轮')
    def prepare_next_round(self) -> OperationRoundResult:
        """跨轮重置：清空 finished 让下一轮所有路线重新执行，并重置本轮的时间字段。"""
        self.run_record.current_round += 1
        self.route_idx = 0
        self.run_record.reset_finished()
        self.run_record.reset_round_timing()
        return self.round_success(status='进入下一轮')

    def _stop_route_actions(self) -> None:
        self.ctx.auto_battle_context.stop_auto_battle()
        self.ctx.controller.stop_moving_forward()

    def _restart_game_for_ui_disappeared(self) -> OperationRoundResult:
        if self.op_to_enter_game is None:
            return self.round_fail(status='未提供打开游戏方式')

        self._stop_route_actions()
        self.ctx.controller.close_game()
        time.sleep(5)

        enter_result = self.op_to_enter_game.execute()
        if not enter_result.success:
            return self.round_fail(status=f'重开游戏失败 {enter_result.status}')

        return self.round_success(status='重开游戏成功')


def __debug():
    ctx = ZContext()
    ctx.init()

    app = WorldPatrolApp(ctx)
    app.execute()
    ctx.run_context.stop_running()


if __name__ == '__main__':
    __debug()
