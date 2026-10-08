from __future__ import annotations

from typing import TYPE_CHECKING

import cv2

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.utils import cv2_utils
from one_dragon.utils.log_utils import log
from zzz_od.application.bagel import bagel_const, bagel_usage
from zzz_od.application.bagel.bagel_deposit import BagelDeposit
from zzz_od.application.bagel.bagel_enter import BagelEnter
from zzz_od.application.bagel.bagel_exit import BagelExit
from zzz_od.application.bagel.bagel_flow import BagelFlow, load_published_flow
from zzz_od.application.bagel.bagel_operation import (
    BagelOperation,
    BagelRecoverableFailure,
    bagel_run_events,
    execute_bagel_round,
    is_bagel_result,
)
from zzz_od.application.bagel.bagel_return import BagelReturn
from zzz_od.application.bagel.bagel_route import SUPPORTED_MAP_IDS
from zzz_od.application.bagel.bagel_route_vision import BagelSpawnMatcher
from zzz_od.application.bagel.bagel_run_flow import BagelRunFlow, release_flow_inputs
from zzz_od.application.bagel.bagel_settle import BagelSettleWarehouse
from zzz_od.application.bagel.bagel_slots import safe_occupied_indices
from zzz_od.application.zzz_application import ZApplication

if TYPE_CHECKING:
    from one_dragon.base.operation.operation_base import OperationResult
    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.application.bagel.bagel_config import BagelConfig
    from zzz_od.application.bagel.bagel_run_record import BagelRunRecord
    from zzz_od.context.zzz_context import ZContext


class BagelApp(ZApplication):
    """支持出生点收集并按成功入仓局数循环。"""

    STATUS_SKIP: str = '非支持出生点，退出重开'
    STATUS_A: str = '录像店复活点，开始收集'
    STATUS_B: str = '白鸽工地地铁站复活点，开始收集'

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
        self.spawn_matcher: BagelSpawnMatcher | None = None
        self.matched_map_id: str | None = None
        self.attempts: int = 0
        self.success_rounds: int = 0
        self.empty_rounds: int = 0
        self.defeat_rounds: int = 0
        self.failure_retries_used: int = 0
        self.failure_retry_pending: bool = False
        self.failure_reason: str | None = None
        self.failure_history: list[dict[str, object]] = []
        self._spawn_hud_misses: int = 0
        self.flow_snapshot: dict[str, BagelFlow] = {}
        self.initial_clear_pending: bool = True
        self.last_return_status: str | None = None

    def execute(self) -> OperationResult:
        """正式应用返回前完成本次运行的事件收尾。"""
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
                log.info('贝果任务结束：%s；整体重试已用 %s/%s',
                         result.status, self.failure_retries_used, self.config.max_failure_retries)
                return result
            finally:
                release_flow_inputs(self.ctx)

    def after_operation_done(self, result: OperationResult) -> None:
        """正式任务停止也保存现场，程序错误或收尾失败不能只留下旧的局内截图。"""
        try:
            if not result.success and self.last_screenshot is not None:
                self.screenshot()
                path = self.save_screenshot()
                log.error('贝果任务停止：%s；原因：%s', result.status, result.data)
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
            super().after_operation_done(result)

    def _execute_one_round(self) -> OperationRoundResult:
        """初始化以外的程序异常也直接停止，不获得业务重开额度。"""
        return execute_bagel_round(self)

    def handle_pause(self) -> None:
        """暂停只释放输入，累计重试和首次清空资格保持不变。"""
        release_flow_inputs(self.ctx)
        super().handle_pause()

    def handle_init(self) -> None:
        """新任务重置计数；子操作切换和暂停恢复不调用此初始化。"""
        super().handle_init()
        self.attempts = 0
        self.success_rounds = 0
        self.empty_rounds = 0
        self.defeat_rounds = 0
        self.failure_retries_used = 0
        self.failure_retry_pending = False
        self.failure_reason = None
        self.failure_history = []
        self.matched_map_id = None
        self._spawn_hud_misses = 0
        self.spawn_matcher = None
        self.flow_snapshot = {}
        self.initial_clear_pending = True
        self.last_return_status = None

    def _spawn_matcher(self) -> BagelSpawnMatcher:
        """延迟加载出生匹配，避免无资源环境构造失败。"""
        if self.spawn_matcher is None:
            self.spawn_matcher = BagelSpawnMatcher()
        return self.spawn_matcher

    @operation_node(
        name='检查贝果运行条件', is_start_node=True, screenshot_before_round=False,
    )
    def check_ready(self) -> OperationRoundResult:
        """校验配置和路线；是否零携带由入场时的当前画面确认。"""
        try:
            self.config.validate()
            self.flow_snapshot = {map_id: load_published_flow(map_id) for map_id in SUPPORTED_MAP_IDS}
            self._spawn_matcher()  # 入场前验证固定地图资源，避免进入局内才发现文件损坏。
        except (OSError, ValueError) as error:
            return self.round_fail(f'贝果配置无效：{error}')
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
        result = BagelEnter(
            self.ctx, allow_clear_loadout=allow_clear_loadout, allow_world_recovery=True,
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
        crop = cv2_utils.crop_image_only(self.last_screenshot, area.pc_rect)
        crop = cv2.cvtColor(crop, cv2.COLOR_RGB2BGR)
        self.attempts += 1
        map_id = self._spawn_matcher().match(crop)
        self.matched_map_id = map_id
        if map_id == 'janus_high_a':
            log.info('第 %s 次抽到录像店复活点，开始收集', self.attempts)
            return self.round_success(self.STATUS_A)
        if map_id == 'janus_high_b':
            log.info('第 %s 次抽到白鸽工地地铁站复活点，开始收集', self.attempts)
            return self.round_success(self.STATUS_B)
        log.info('第 %s 次非支持出生点，退出重开', self.attempts)
        log.info('当前出生点不支持收集，正在退出重开。本次不计成功，不清理仓库，也不消耗整体重试次数。出生点重选没有次数上限。')
        log.info('抽到录像店或白鸽工地地铁站出生点后，程序开始收集。如需结束任务，请使用程序的停止操作。')
        return self.round_success(self.STATUS_SKIP)

    @node_from(from_name='识别出生点', status=STATUS_SKIP)
    @operation_node(name='退出非支持局', screenshot_before_round=False)
    def exit_unsupported(self) -> OperationRoundResult:
        """空跑退出；失败时留图。"""
        return self.round_by_op_result(BagelExit(self.ctx).execute())

    @node_from(from_name='退出非支持局')
    @node_from(from_name='判断整体重试次数', status='继续入场')
    @operation_node(name='返回入口', screenshot_before_round=False)
    def return_entry(self) -> OperationRoundResult:
        """回研究站入口后再开下一局。"""
        result = BagelReturn(self.ctx).execute()
        return (
            self._finish_failed_round(result, '返回入口') if self.failure_retry_pending
            else self.round_by_op_result(result)
        )

    @node_from(from_name='识别出生点', status=STATUS_A)
    @node_from(from_name='识别出生点', status=STATUS_B)
    @operation_node(name='执行局内流程', screenshot_before_round=False)
    def run_flow(self) -> OperationRoundResult:
        """按出生地执行发布流程；与开发工具共用同一执行器。"""
        if self.matched_map_id not in self.flow_snapshot:
            return self.round_fail('缺少已识别出生地的发布流程')
        result = BagelRunFlow(
            self.ctx, self.flow_snapshot[self.matched_map_id],
            map_snapshot=self._spawn_matcher().vision(self.matched_map_id).map,
            continuous_safe_unlock=True,
            on_location_wait=lambda: log.info(bagel_usage.LOCATION_WAIT_HINT),
        )
        outcome = result.execute()
        if result.last_screenshot is not None:
            self.last_screenshot = result.last_screenshot
            self.last_screenshot_time = result.last_screenshot_time
        if not outcome.success and (
            isinstance(outcome.data, BagelRecoverableFailure)
            or outcome.status == self.STATUS_TIMEOUT
        ):
            reason = outcome.data.reason if isinstance(outcome.data, BagelRecoverableFailure) else outcome.status
            return self.round_fail(BagelOperation.STATUS_ROUND_FAILED, data=reason)
        return self.round_by_op_result(outcome)

    @node_from(from_name='执行局内流程')
    @operation_node(name='结算仓库', screenshot_before_round=False)
    def settle(self) -> OperationRoundResult:
        """只有安全箱有物且确实入仓才计成功；空箱局仍要返回入口。"""
        result = BagelSettleWarehouse(
            self.ctx, self.config.auto_clean_warehouse, self.config.clean_filter_areas(),
        ).execute()
        if result.success:
            if result.status == BagelDeposit.STATUS_DONE:
                self.success_rounds += 1
                self.empty_rounds = 0
            elif result.status == BagelDeposit.STATUS_EMPTY:
                self.empty_rounds += 1
            log.info('贝果单局结算：%s；已入仓 %s 局，连续空箱 %s 局',
                     result.status, self.success_rounds, self.empty_rounds)
        return self.round_by_op_result(result)

    @node_from(from_name='结算仓库')
    @operation_node(name='成功局返回入口', screenshot_before_round=False)
    def return_after_success(self) -> OperationRoundResult:
        """最后一局也回到研究站入口。"""
        result = BagelReturn(self.ctx).execute()
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
            log.info('失败局入仓后仍按出售方案清理仓库。出售范围包含已有库存。')
        else:
            log.info('清理仓库已关闭。失败局只入仓，不出售物品。')
        result = BagelSettleWarehouse(
            self.ctx, self.config.auto_clean_warehouse, self.config.clean_filter_areas(),
        ).execute()
        if result.success:
            self.defeat_rounds += 1
            log.info('贝果失败局结算：%s；累计失败 %s 局，未计成功',
                     result.status, self.defeat_rounds)
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
