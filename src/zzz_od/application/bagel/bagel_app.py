from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.config.notify_config import NotifyDetailMode
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.bagel import (
    bagel_const,
    bagel_route_stats,
    bagel_screen,
    bagel_stats,
    bagel_usage,
)
from zzz_od.application.bagel.bagel_deposit import BagelDeposit
from zzz_od.application.bagel.bagel_enter import BagelEnter
from zzz_od.application.bagel.bagel_exit import BagelExit
from zzz_od.application.bagel.bagel_log import BagelRoundLog
from zzz_od.application.bagel.bagel_operation import (
    BagelOperation,
    BagelRecoverableFailure,
    bagel_run_events,
    execute_bagel_round,
    is_bagel_result,
)
from zzz_od.application.bagel.bagel_return import BagelReturn
from zzz_od.application.bagel.bagel_route_model import now_iso
from zzz_od.application.bagel.bagel_route_stats import (
    BagelRouteRecord,
    BagelRouteRecorder,
)
from zzz_od.application.bagel.bagel_route_store import (
    BagelRouteConfigError,
    BagelRouteStore,
)
from zzz_od.application.bagel.bagel_route_walker import BagelRouteWalker
from zzz_od.application.bagel.bagel_run_flow import release_flow_inputs
from zzz_od.application.bagel.bagel_settle import BagelSettleWarehouse
from zzz_od.application.bagel.bagel_slots import safe_occupied_indices
from zzz_od.application.bagel.bagel_stats import BagelRunStats, BagelSafeLedger
from zzz_od.application.zzz_application import ZApplication

if TYPE_CHECKING:
    from one_dragon.base.operation.operation_base import OperationResult
    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.application.bagel.bagel_config import BagelConfig
    from zzz_od.application.bagel.bagel_route_model import BagelRoute, BagelSpawnPoint
    from zzz_od.application.bagel.bagel_run_record import BagelRunRecord
    from zzz_od.application.bagel.bagel_stats import BagelRound
    from zzz_od.context.zzz_context import ZContext


class BagelApp(ZApplication):
    """支持出生点收集并按成功入仓局数循环。"""

    STATUS_SKIP: str = '非支持出生点，退出重开'
    STATUS_ANCHOR_SKIP: str = '出生点没有可执行路线，退出重开'
    STATUS_A: str = '已进入局内，开始识别出生点'

    def __init__(
        self, ctx: ZContext, config: BagelConfig, record: BagelRunRecord,
    ) -> None:
        """注入工厂对应账号、分组的配置。"""
        super().__init__(
            ctx,
            app_id=bagel_const.APP_ID,
            op_name=bagel_const.APP_NAME,
            need_check_game_win=True,
            run_record=record,
        )
        self.config: BagelConfig = config
        self.matched_map_id: str | None = None
        self.attempts: int = 0
        self.success_rounds: int = 0
        self.rounds_since_sell: int = 0
        self.empty_rounds: int = 0
        self.defeat_rounds: int = 0
        self.failure_retries_used: int = 0
        self.failure_retry_pending: bool = False
        self.failure_reason: str | None = None
        self.failure_history: list[dict[str, object]] = []
        self._spawn_hud_misses: int = 0
        self.initial_clear_pending: bool = True
        self.last_return_status: str | None = None
        self._round_log: BagelRoundLog = BagelRoundLog(self.display_name)
        self._stats: BagelRunStats = BagelRunStats()
        """每局收益、红色物品与用时统计；写日志，任务结束推送摘要。"""
        self._round_ledger: BagelSafeLedger | None = None
        """本局路线执行器的安全箱账本；本局没跑路线时为 None。"""
        self._round_survey: int = 0
        """本局调查收益的最后一次读数；零携带入场后为 0，路线执行器读到后更新。"""
        self._route_recorder: BagelRouteRecorder = BagelRouteRecorder()
        """路线数据记录：每局写一行，任务结束输出按出生点的汇总表。"""
        self._round_map_id: str | None = None
        self._round_spawn: BagelSpawnPoint | None = None
        self._round_route: BagelRoute | None = None
        """本局的地图、出生点和执行的路线；没定位或没跑路线时为 None。"""
        self._route_rounds: int = 0
        """本次任务写入的路线数据记录局数；为 0 时不输出汇总表。"""
        self._route_reported: bool = False

    def _log_round_result(
        self,
        from_node_name: str,
        node_name: str,
        status_text: str,
        result: OperationRoundResult | None,
    ) -> None:
        """正式应用与子操作使用相同的等待汇总规则。"""
        if result is None:
            self._round_log.flush()
            super()._log_round_result(from_node_name, node_name, status_text, result)
            return
        self._round_log.record(
            from_node_name, node_name, status_text, result,
            self.node_retry_times, self.node_max_retry_times,
        )

    def execute(self) -> OperationResult:
        """正式应用返回前完成本次运行的事件收尾。"""
        self._round_log = BagelRoundLog(self.display_name)
        with bagel_run_events(self):
            try:
                result = super().execute()
                if self.run_record is not None:
                    self.run_record.update('retry_summary', {
                        'used': self.failure_retries_used,
                        'limit': self.config.max_failure_retries,
                        'failures': self.failure_history,
                        'success_rounds': self.success_rounds,
                        'stop_reason': result.status,
                        'stop_detail': str(result.data) if result.data is not None else None,
                    })
                log.info(
                    '贝果任务结束：%s；入场=%s，成功=%s，失败结算=%s，连续空箱=%s；'
                    '整体重试=%s/%s；最近正常结算返回=%s；耗时=%.1f秒',
                    result.status, self.attempts, self.success_rounds, self.defeat_rounds,
                    self.empty_rounds, self.failure_retries_used, self.config.max_failure_retries,
                    self.last_return_status or '未记录', self.operation_usage_time,
                )
                return result
            finally:
                self._round_log.flush()
                release_flow_inputs(self.ctx)
                try:
                    self._stats.finish_task()
                except Exception:
                    log.error('输出贝果统计总表失败', exc_info=True)
                self._report_routes()

    def after_operation_done(self, result: OperationResult) -> None:
        """正式任务停止也保存现场，程序错误或收尾失败不能只留下旧的局内截图。"""
        self._round_log.flush()
        try:
            if not result.success and self.last_screenshot is not None:
                self.screenshot()
                path = self.save_screenshot()
                bagel_usage.log_screenshot(path)
            elif not result.success:
                log.warning('没有可保存的现场截图。请查看相关日志。')
        except Exception:
            log.error('保存贝果任务停止截图时发生异常', exc_info=True)
            log.warning('本次未确认保存现场截图。请查看相关日志。')
        finally:
            if not result.success:
                log.error('停止原因：%s；详情：%s', result.status, result.data)
                log.info(bagel_usage.stop_guidance(result.status))
                bagel_usage.log_feedback()
            self._finish_stats(result)
            super().after_operation_done(result)

    def _finish_stats(self, result: OperationResult) -> None:
        """输出统计总表并推送摘要；只写统计，出错不影响停止流程。"""
        try:
            self._stats.finish_task()
        except Exception:
            log.error('输出贝果统计总表失败', exc_info=True)
        self._report_routes()
        try:
            self._push_summary(result)
        except Exception:
            log.error('推送贝果收益摘要失败', exc_info=True)

    def _record_route(self, finished: BagelRound | None) -> None:
        """把收尾的这一局写入路线数据记录；未完成的局不写。只写记录，出错不影响流程。

        Args:
            finished: ``BagelRunStats.finish_round`` 返回的这一局。
        """
        if finished is None or finished.outcome == bagel_stats.OUTCOME_UNFINISHED:
            return
        try:
            route = self._round_route
            self._route_recorder.append(BagelRouteRecord(
                ended_at=now_iso(),
                instance=self.ctx.current_instance_idx,
                map_id=self._round_map_id,
                spawn_id=self._round_spawn.spawn_id if self._round_spawn is not None else None,
                route_source=route.source if route is not None else None,
                route_id=route.route_id if route is not None else None,
                route_name=route.name if route is not None else None,
                route_version=bagel_route_stats.route_version(route) if route is not None else None,
                outcome=finished.outcome,
                seconds=round(finished.seconds, 1),
                income=finished.income,
                red=bagel_stats.red_counts(finished.items),
            ))
            self._route_rounds += 1
        except Exception:
            log.error('记录贝果路线数据失败', exc_info=True)

    def _report_routes(self) -> None:
        """任务结束输出路线数据汇总表；本次任务没写入记录时不输出，重复调用只输出一次。"""
        if self._route_reported or self._route_rounds == 0:
            return
        self._route_reported = True
        try:
            catalog = BagelRouteStore().load_catalog()
            for line in bagel_route_stats.report_lines(self._route_recorder.load(), catalog):
                log.info('贝果路线数据：%s', line)
        except Exception:
            log.error('输出贝果路线数据汇总失败', exc_info=True)

    def _push_summary(self, result: OperationResult) -> None:
        """任务结束推送收益摘要，按本应用的节点通知设置发送；用户手动停止不推送。

        正常结束和异常停止都可能发生在任一节点，不能只靠单个节点的 ``@node_notify``，
        所以在这里按节点通知的同一套规则发送：关闭不发，仅失败时只在异常停止时发，
        合并时放进通知池，由框架在应用结束时一起发出。
        """
        if self.ctx.run_context.is_context_stop:
            return
        if not self.ctx.notify_config.enable_notify or not self.ctx.run_context.is_app_need_notify(self.app_id):
            return
        mode = self.ctx.notify_config.get_app_detail_mode(self.app_id)
        if mode == NotifyDetailMode.OFF.value.value:
            return
        if mode == NotifyDetailMode.ERROR_ONLY.value.value and result.success:
            return
        # 失败原因常带「；」后的细节，推送只取第一段。
        stop_reason = None if result.success else str(result.status).split('；')[0]
        summary = self._stats.summary(stop_reason)
        if summary is None:
            return
        title = f'{gt("任务")}「{gt(bagel_const.APP_NAME)}」{gt("收益统计")}'
        content = f'{title}\n{summary}'
        if mode == NotifyDetailMode.MERGE.value.value:
            self.ctx.run_context.notify_pool.add(content=content)
        else:
            self.ctx.push_service.push_async(title=self.ctx.notify_config.title, content=content)

    def _execute_one_round(self) -> OperationRoundResult:
        """初始化以外的程序异常也直接停止，不获得业务重开额度。"""
        return execute_bagel_round(self)

    def handle_pause(self) -> None:
        """暂停释放按键，不打断当前拖拽，也不重置累计状态；暂停时长不计入统计用时。"""
        release_flow_inputs(self.ctx, release_mouse=False)
        self._stats.pause()
        super().handle_pause()

    def handle_resume(self) -> None:
        """恢复后统计继续计时。"""
        self._stats.resume()
        super().handle_resume()

    def handle_init(self) -> None:
        """新任务重置计数；子操作切换和暂停恢复不调用此初始化。"""
        super().handle_init()
        self.attempts = 0
        self.success_rounds = 0
        self.rounds_since_sell = 0
        self.empty_rounds = 0
        self.defeat_rounds = 0
        self.failure_retries_used = 0
        self.failure_retry_pending = False
        self.failure_reason = None
        self.failure_history = []
        self.matched_map_id = None
        self._spawn_hud_misses = 0
        self.initial_clear_pending = True
        self.last_return_status = None
        self._stats = BagelRunStats()
        self._round_ledger = None
        self._round_survey = 0
        self._reset_round_route()
        self._route_rounds = 0
        self._route_reported = False
        self._route_recorder.prune()

    def _reset_round_route(self) -> None:
        """新的一局开始前清空地图、出生点和路线。"""
        self._round_map_id = None
        self._round_spawn = None
        self._round_route = None

    def _record_round_income(self, read_hud: bool) -> None:
        """把本局调查收益和带出物品记入统计；只写统计，出错不影响流程。

        Args:
            read_hud: 是否先截一张新图读 HUD。失败局已在结算画面，HUD 不可见。
        """
        try:
            value: int | None = None
            if read_hud:
                self.screenshot()
                value = bagel_stats.parse_value(bagel_screen.read_area(
                    self.ctx, self.last_screenshot, '贝果-局内', '调查收益',
                ))
            if self._round_ledger is not None:
                self._stats.set_items(self._round_ledger.report())
            self._stats.set_income(value if value is not None else self._round_survey)
        except Exception:
            log.error('记录贝果本局收益失败', exc_info=True)

    @operation_node(
        name='检查贝果运行条件', is_start_node=True, screenshot_before_round=False,
    )
    def check_ready(self) -> OperationRoundResult:
        """校验配置和路线选择；是否零携带由入场时的当前画面确认。

        路线选择无效时拒绝开始，不自动换成其他路线。
        """
        try:
            self.config.validate()
            catalog = BagelRouteStore().load_catalog()
            problems = catalog.selection_problems()
            if problems:
                raise ValueError('；'.join(problems))
            if catalog.active_count() == 0:
                raise ValueError('没有开启的贝果路线，先在路线编辑器里为出生点开启路线')
        except (OSError, ValueError, BagelRouteConfigError) as error:
            return self.round_fail(f'贝果配置无效：{error}')
        for spawn in catalog.spawns:
            ref = catalog.active_ref(spawn.spawn_id)
            route = catalog.route(ref) if ref is not None else None
            log.info('贝果出生点 %s：%s', spawn.name, f'开启「{route.name}」' if route is not None else '未开启路线')
        bagel_usage.log_start(self.config)
        return self.round_success()

    @node_from(from_name='检查贝果运行条件')
    @node_from(from_name='返回入口')
    @node_from(from_name='判断成功局数', status='继续入场')
    @operation_node(name='零携带入场', screenshot_before_round=False)
    def enter(self) -> OperationRoundResult:
        """非支持出生点可继续重开，不受尝试次数限制。"""
        self.screenshot()
        allow_clear_loadout = self.initial_clear_pending
        # 资格在调用入场前消耗，不能等出生识别增加 attempts 才关闭。
        self.initial_clear_pending = False
        if not allow_clear_loadout and all(
            self.round_by_find_area(self.last_screenshot, '贝果-仓库', name).is_success
            for name in ('放入仓库', '返回研究站')
        ):
            occupied = safe_occupied_indices(self.last_screenshot)
            if occupied is None:
                return self.round_fail('结算仓库安全箱格子状态不明，禁止开始新局')
            if occupied:
                return self.round_fail('结算仓库安全箱仍有物资，先核对去向，禁止开始新局')
        self._spawn_hud_misses = 0
        retrying_failure = self.failure_retry_pending
        if retrying_failure:
            self.failure_retry_pending = False
            self.failure_retries_used += 1
            log.warning('贝果失败重开：%s；整体重试已用 %s/%s',
                        self.failure_reason, self.failure_retries_used, self.config.max_failure_retries)
        log.info('贝果收集：准备第 %s 次入场', self.attempts + 1)
        self._stats.start_round(self.attempts + 1)
        self._round_ledger = None
        self._round_survey = 0
        self._reset_round_route()
        result = BagelEnter(
            self.ctx, allow_clear_loadout=allow_clear_loadout, allow_world_recovery=True,
            prepare_shortcut_entry=allow_clear_loadout,
            recovery_auto_clean=self.config.auto_clean_warehouse,
            recovery_filter_groups=self.config.clean_filter_groups(),
        ).execute()
        if retrying_failure and not result.success:
            return self._finish_failed_round(result, '额外入场')
        return self.round_by_op_result(result, wait=1)

    @node_from(from_name='零携带入场')
    @operation_node(name='识别出生点', timeout_seconds=10)
    def check_spawn(self) -> OperationRoundResult:
        """支持点进入短线收集；其余正常退出重开。"""
        if is_bagel_result(self):
            return self.round_fail(BagelOperation.STATUS_DEFEATED)
        if not self.round_by_find_area(
            self.last_screenshot, '战斗画面', '按键-普通攻击',
        ).is_success:
            self._spawn_hud_misses += 1
            if self._spawn_hud_misses < 4:
                return self.round_wait('局内 HUD 暂未识别，再看一帧', wait=0.3)
            return self.round_fail(BagelOperation.STATUS_ROUND_FAILED, data='未识别贝果局内画面')
        self._spawn_hud_misses = 0
        area = self.ctx.screen_loader.get_area('贝果-局内', '定位小地图')
        if area is None:
            return self.round_fail('缺少贝果定位小地图区域')
        self.attempts += 1
        # 出生点识别由路线执行器完成：这里只确认画面是贝果局内并可以开始。
        self.matched_map_id = 'route_walker'
        log.info('第 %s 次入场成功，交给路线执行器识别出生点', self.attempts)
        return self.round_success(self.STATUS_A)

    @node_from(from_name='识别出生点', status=STATUS_SKIP)
    @node_from(from_name='执行局内流程', status=STATUS_ANCHOR_SKIP)
    @operation_node(name='退出非支持局', screenshot_before_round=False)
    def exit_unsupported(self) -> OperationRoundResult:
        """出生点没有可执行路线：空跑退出，失败时留图。

        路线执行器识别到的出生点不在已登记范围内，或该出生点没有开启路线时也走这里，
        退出去重开，不计成功、不消耗整体重试次数。
        """
        self._stats.set_outcome(bagel_stats.OUTCOME_UNSUPPORTED)
        self._stats.set_income(0)
        return self.round_by_op_result(BagelExit(self.ctx).execute())

    @node_from(from_name='退出非支持局')
    @node_from(from_name='判断整体重试次数', status='继续入场')
    @operation_node(name='返回入口', screenshot_before_round=False)
    def return_entry(self) -> OperationRoundResult:
        """返回贝果主界面后开下一局；大世界落点由入场操作重建入口。"""
        result = BagelReturn(self.ctx).execute()
        self._record_route(self._stats.finish_round())
        return (
            self._finish_failed_round(result, '返回入口') if self.failure_retry_pending
            else self.round_by_op_result(result)
        )

    @node_from(from_name='识别出生点', status=STATUS_A)
    @operation_node(name='执行局内流程', screenshot_before_round=False)
    def run_flow(self) -> OperationRoundResult:
        """按出生点开启的路线执行；出生点识别与推进由路线执行器负责。"""
        try:
            walker = BagelRouteWalker(
                self.ctx, blueprint_priority=self.config.blueprint_priority,
            )
        except ValueError as error:
            return self.round_fail(f'路线执行器初始化失败：{error}')
        outcome = walker.execute()
        walker.persist_turn_scale()
        self._round_ledger = walker.ledger
        self._round_survey = walker.survey_value
        self._round_spawn = walker.spawn
        self._round_route = walker.routes[0] if walker.routes else None
        self._round_map_id = walker.spawn.map_id if walker.spawn is not None else walker.last_map_id
        if walker.last_screenshot is not None:
            self.last_screenshot = walker.last_screenshot
            self.last_screenshot_time = walker.last_screenshot_time
        if outcome.success:
            if outcome.status == BagelRouteWalker.STATUS_DONE:
                return self.round_success(BagelRouteWalker.STATUS_DONE)
            return self.round_fail('路线执行提前结束，未确认全部路线完成', data=outcome.status)
        if not outcome.success and outcome.status == BagelRouteWalker.STATUS_ANCHOR_MISS:
            # 出生点不在已登记范围内或没有开启路线，属于换一局重开，
            # 不是整体失败；走非支持出生点那条退出重开的路。
            return self.round_success(self.STATUS_ANCHOR_SKIP)
        if not outcome.success and outcome.status == BagelRouteWalker.STATUS_SPAWN_FAILED:
            # 出生点识别没有稳定结论：按失败局退出，消耗一次整体重试。
            reason = f'{outcome.status}：{outcome.data}' if outcome.data else outcome.status
            return self.round_fail(BagelOperation.STATUS_ROUND_FAILED, data=reason)
        if not outcome.success and outcome.status == BagelRouteWalker.STATUS_CONFIG_INVALID:
            return self.round_fail(f'贝果路线配置无效：{outcome.data}')
        if not outcome.success and (
            isinstance(outcome.data, BagelRecoverableFailure)
            or outcome.status == self.STATUS_TIMEOUT
        ):
            reason = outcome.data.reason if isinstance(outcome.data, BagelRecoverableFailure) else outcome.status
            return self.round_fail(BagelOperation.STATUS_ROUND_FAILED, data=reason)
        return self.round_by_op_result(outcome)

    @node_from(from_name='执行局内流程', status=BagelRouteWalker.STATUS_DONE)
    @operation_node(name='正常局退出', screenshot_before_round=False)
    def exit_after_success(self) -> OperationRoundResult:
        """路线完整结束后退出到仓库；退出失败时不入仓或计成功。"""
        release_flow_inputs(self.ctx)
        self._record_round_income(read_hud=True)
        operation = BagelExit(self.ctx)
        result = operation.execute()
        self.last_screenshot = operation.last_screenshot
        self.last_screenshot_time = operation.last_screenshot_time
        return self.round_by_op_result(result)

    @node_from(from_name='正常局退出')
    @operation_node(name='结算仓库', screenshot_before_round=False)
    def settle(self) -> OperationRoundResult:
        """只有安全箱有物且确实入仓才计成功；空箱局仍要返回入口。"""
        finishing = (self.config.max_success_rounds > 0
                     and self.success_rounds + 1 >= self.config.max_success_rounds)
        result = self._settle_warehouse(finishing=finishing)
        if result.success:
            if result.status == BagelDeposit.STATUS_DONE:
                self.success_rounds += 1
                self.empty_rounds = 0
                self._stats.set_outcome(bagel_stats.OUTCOME_SUCCESS)
            elif result.status == BagelDeposit.STATUS_EMPTY:
                self.empty_rounds += 1
                self._stats.set_outcome(bagel_stats.OUTCOME_EMPTY)
            log.info('贝果单局结算：第 %s 次入场，出生点=%s，结果=%s；成功=%s，连续空箱=%s，出售累计=%s/%s',
                     self.attempts, self.matched_map_id, result.status,
                     self.success_rounds, self.empty_rounds, self.rounds_since_sell, self.config.sell_interval)
        return self.round_by_op_result(result)

    def _settle_warehouse(self, finishing: bool = False) -> OperationResult:
        """应用持有本任务出售计数，结算成功后再更新；失败局也复用。"""
        due = self.rounds_since_sell + 1 >= self.config.sell_interval
        log.info('贝果出售计划：自动清理=%s，累计入仓=%s/%s，本局非空入仓后到期=%s，正常结束补卖=%s',
                 self.config.auto_clean_warehouse, self.rounds_since_sell,
                 self.config.sell_interval, due, finishing)
        result = BagelSettleWarehouse(
            self.ctx, self.config.auto_clean_warehouse,
            filter_groups=self.config.clean_filter_groups(),
            sell_due=due or finishing,
        ).execute()
        if result.success:
            if isinstance(result.data, dict) and result.data.get('sale_completed'):
                self.rounds_since_sell = 0
                self._stats.record_sale(result.data.get('sale_coins'))
            elif result.status == BagelDeposit.STATUS_DONE:
                self.rounds_since_sell += 1
        return result

    @node_from(from_name='结算仓库')
    @operation_node(name='成功局返回入口', screenshot_before_round=False)
    def return_after_success(self) -> OperationRoundResult:
        """最后一局也返回，并记录实际到达的页面。"""
        result = BagelReturn(self.ctx).execute()
        self._record_route(self._stats.finish_round())
        self.last_return_status = result.status if result.success else None
        return self.round_by_op_result(result)

    @node_from(from_name='成功局返回入口')
    @operation_node(name='判断成功局数', screenshot_before_round=False)
    def decide_success_rounds(self) -> OperationRoundResult:
        """只有正常入仓的局数计入上限。"""
        if self.config.max_success_rounds > 0 and self.success_rounds >= self.config.max_success_rounds:
            location = {'已返回贝果入口': '贝果入口', '已返回大世界': '大世界'}.get(self.last_return_status)
            if location is not None:
                log.info('已达到成功次数上限。已成功入仓 %s 局。程序已完成结算检查，并返回%s。本次任务已结束。', self.success_rounds, location)
            else:
                log.info('已达到成功次数上限。已成功入仓 %s 局。返回结果：%s。本次任务已结束。', self.success_rounds, self.last_return_status or '位置未确认')
            return self.round_success(f'已成功入仓 {self.success_rounds} 局')
        if self.empty_rounds >= 3:
            return self.round_fail('连续 3 局安全箱为空，未计成功，停止自动重开')
        return self.round_success('继续入场')

    @node_from(from_name='识别出生点', success=False, status=BagelOperation.STATUS_DEFEATED)
    @node_from(from_name='识别出生点', success=False, status=BagelOperation.STATUS_ROUND_FAILED)
    @node_from(from_name='识别出生点', success=False, status=ZApplication.STATUS_TIMEOUT)
    @node_from(from_name='执行局内流程', success=False, status=BagelOperation.STATUS_ROUND_FAILED)
    @node_from(from_name='执行局内流程', success=False, status=ZApplication.STATUS_TIMEOUT)
    @node_from(from_name='执行局内流程', success=False, status=BagelOperation.STATUS_CONTAINER_FAILED)
    @node_from(from_name='执行局内流程', success=False, status=BagelOperation.STATUS_DEFEATED)
    @node_from(from_name='执行局内流程', success=False, status=BagelOperation.STATUS_INTERRUPTED)
    @operation_node(name='失败局退出', screenshot_before_round=False)
    def exit_after_defeat(self) -> OperationRoundResult:
        """记住原始失败，释放输入并从新画面选择退出和结算路径。"""
        previous = self._previous_round_result
        self.failure_reason = (
            f'{previous.status}：{previous.data}' if previous is not None and previous.data
            else previous.status if previous is not None else '局内失败'
        )
        release_flow_inputs(self.ctx)
        self._stats.set_outcome(bagel_stats.OUTCOME_FAILED)
        self._record_round_income(read_hud=False)
        path = self.save_screenshot()
        self.failure_history.append({'reason': self.failure_reason, 'screenshot': path,
                                     'used': self.failure_retries_used})
        log.error('本局失败：%s。程序正在退出并处理仓库结算。本局不计成功。整体重试次数已用 %s/%s。',
                  self.failure_reason, self.failure_retries_used, self.config.max_failure_retries)
        bagel_usage.log_screenshot(path)
        return self._finish_failed_round(BagelExit(self.ctx).execute(), '退出')

    def _finish_failed_round(self, result: OperationResult, phase: str) -> OperationRoundResult:
        """收尾失败同时报告原始原因，不能继续返回或开局。"""
        if not result.success:
            return self.round_fail(
                f'本局失败：{self.failure_reason}；{phase}失败：{result.status}',
                data=result.data,
            )
        return self.round_by_op_result(result)

    @node_from(from_name='失败局退出')
    @operation_node(name='失败局结算仓库', screenshot_before_round=False)
    def settle_after_defeat(self) -> OperationRoundResult:
        """失败局同样入仓清理；清理失败则保留其错误，不改口成撤离失败。"""
        if self.config.auto_clean_warehouse:
            log.info('失败局有物入仓计入出售间隔，不补卖；满仓或残留允许提前出售并重试一次入仓。')
        else:
            log.info('清理仓库已关闭。失败局只入仓，不出售物品。')
        result = self._settle_warehouse()
        if result.success:
            self.defeat_rounds += 1
            log.info('贝果失败局结算：第 %s 次入场，结果=%s；累计失败结算=%s，不计成功；出售累计=%s/%s',
                     self.attempts, result.status, self.defeat_rounds,
                     self.rounds_since_sell, self.config.sell_interval)
        return self._finish_failed_round(result, '入仓或清理')

    @node_from(from_name='失败局结算仓库')
    @operation_node(name='判断整体重试次数', screenshot_before_round=False)
    def decide_defeat_rounds(self) -> OperationRoundResult:
        """结算后决定是否再开；额度在实际调用额外入场时才消耗。"""
        if self.failure_retries_used >= self.config.max_failure_retries:
            return self.round_fail(
                f'整体重试已用 {self.failure_retries_used}/{self.config.max_failure_retries}，'
                f'已完成仓库结算，停止自动重开；本局失败：{self.failure_reason}',
            )
        self.failure_retry_pending = True
        return self.round_success('继续入场')
