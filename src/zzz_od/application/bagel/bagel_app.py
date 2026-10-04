from __future__ import annotations

from typing import TYPE_CHECKING

import cv2

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.utils import cv2_utils
from one_dragon.utils.log_utils import log
from zzz_od.application.bagel import bagel_const
from zzz_od.application.bagel.bagel_deposit import BagelDeposit
from zzz_od.application.bagel.bagel_enter import BagelEnter
from zzz_od.application.bagel.bagel_exit import BagelExit
from zzz_od.application.bagel.bagel_flow import BagelFlow, load_published_flow
from zzz_od.application.bagel.bagel_operation import BagelOperation, bagel_run_events
from zzz_od.application.bagel.bagel_return import BagelReturn
from zzz_od.application.bagel.bagel_route import SUPPORTED_MAP_IDS
from zzz_od.application.bagel.bagel_route_vision import BagelSpawnMatcher
from zzz_od.application.bagel.bagel_run_flow import BagelRunFlow
from zzz_od.application.bagel.bagel_settle import BagelSettleWarehouse
from zzz_od.application.bagel.bagel_slots import SAFE_SLOT_CENTERS, occupied_indices
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
        self._spawn_hud_misses: int = 0
        self.flow_snapshot: dict[str, BagelFlow] = {}
        self.initial_clear_pending: bool = True

    def execute(self) -> OperationResult:
        """正式应用返回前完成本次运行的事件收尾。"""
        with bagel_run_events(self):
            return super().execute()

    def handle_init(self) -> None:
        """每次运行重置出生检查、成功入仓及连续空箱、失败次数。"""
        super().handle_init()
        self.attempts = 0
        self.success_rounds = 0
        self.empty_rounds = 0
        self.defeat_rounds = 0
        self.matched_map_id = None
        self._spawn_hud_misses = 0
        self.spawn_matcher = None
        self.flow_snapshot = {}
        self.initial_clear_pending = True

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
        ) and occupied_indices(self.last_screenshot, SAFE_SLOT_CENTERS):
            return self.round_fail('结算仓库安全箱仍有物资，先核对去向，禁止开始新局')
        self._spawn_hud_misses = 0
        log.info('贝果收集：准备第 %s 次入场', self.attempts + 1)
        return self.round_by_op_result(
            BagelEnter(self.ctx, allow_clear_loadout=allow_clear_loadout).execute(), wait=1,
        )

    @node_from(from_name='零携带入场')
    @operation_node(name='识别出生点', timeout_seconds=10)
    def check_spawn(self) -> OperationRoundResult:
        """支持点进入短线收集；其余正常退出重开。"""
        if not self.round_by_find_area(
            self.last_screenshot, '战斗画面', '按键-普通攻击',
        ).is_success:
            self._spawn_hud_misses += 1
            if self._spawn_hud_misses < 4:
                return self.round_wait('局内 HUD 暂未识别，再看一帧', wait=0.3)
            return self.round_fail('未识别贝果局内画面')
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
        return self.round_success(self.STATUS_SKIP)

    @node_from(from_name='识别出生点', status=STATUS_SKIP)
    @operation_node(name='退出非支持局', screenshot_before_round=False)
    def exit_unsupported(self) -> OperationRoundResult:
        """空跑退出；失败时留图。"""
        return self.round_by_op_result(BagelExit(self.ctx).execute())

    @node_from(from_name='退出非支持局')
    @node_from(from_name='判断连续失败次数', status='继续入场')
    @operation_node(name='返回入口', screenshot_before_round=False)
    def return_entry(self) -> OperationRoundResult:
        """回研究站入口后再开下一局。"""
        return self.round_by_op_result(BagelReturn(self.ctx).execute())

    @node_from(from_name='识别出生点', status=STATUS_A)
    @node_from(from_name='识别出生点', status=STATUS_B)
    @operation_node(name='执行局内流程', screenshot_before_round=False)
    def run_flow(self) -> OperationRoundResult:
        """按出生地执行发布流程；与开发工具共用同一执行器。"""
        if self.matched_map_id not in self.flow_snapshot:
            return self.round_fail('缺少已识别出生地的发布流程')
        return self.round_by_op_result(BagelRunFlow(
            self.ctx, self.flow_snapshot[self.matched_map_id],
            map_snapshot=self._spawn_matcher().vision(self.matched_map_id).map,
        ).execute())

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
                self.defeat_rounds = 0
            elif result.status == BagelDeposit.STATUS_EMPTY:
                self.empty_rounds += 1
            log.info('贝果单局结算：%s；已入仓 %s 局，连续空箱 %s 局',
                     result.status, self.success_rounds, self.empty_rounds)
        return self.round_by_op_result(result)

    @node_from(from_name='结算仓库')
    @operation_node(name='成功局返回入口', screenshot_before_round=False)
    def return_after_success(self) -> OperationRoundResult:
        """最后一局也回到研究站入口。"""
        return self.round_by_op_result(BagelReturn(self.ctx).execute())

    @node_from(from_name='成功局返回入口')
    @operation_node(name='判断成功局数', screenshot_before_round=False)
    def decide_success_rounds(self) -> OperationRoundResult:
        """只有正常入仓的局数计入上限。"""
        if self.config.max_success_rounds > 0 and self.success_rounds >= self.config.max_success_rounds:
            return self.round_success(f'已成功入仓 {self.success_rounds} 局')
        if self.empty_rounds >= 3:
            return self.round_fail('连续 3 局安全箱为空，未计成功，停止自动重开')
        return self.round_success('继续入场')

    @node_from(from_name='执行局内流程', success=False, status=BagelOperation.STATUS_DEFEATED)
    @node_from(from_name='执行局内流程', success=False, status=BagelOperation.STATUS_INTERRUPTED)
    @operation_node(name='失败局退出', screenshot_before_round=False)
    def exit_after_defeat(self) -> OperationRoundResult:
        """撤离失败或搜查中断后收尾；退出失败原样上报，不丢弃安全箱物资。"""
        return self.round_by_op_result(BagelExit(self.ctx).execute())

    @node_from(from_name='失败局退出')
    @operation_node(name='失败局结算仓库', screenshot_before_round=False)
    def settle_after_defeat(self) -> OperationRoundResult:
        """失败局同样入仓清理；清理失败则保留其错误，不改口成撤离失败。"""
        result = BagelSettleWarehouse(
            self.ctx, self.config.auto_clean_warehouse, self.config.clean_filter_areas(),
        ).execute()
        if result.success:
            self.defeat_rounds += 1
            log.info('贝果失败局结算：%s；连续失败 %s 局，未计成功',
                     result.status, self.defeat_rounds)
        return self.round_by_op_result(result)

    @node_from(from_name='失败局结算仓库')
    @operation_node(name='判断连续失败次数', screenshot_before_round=False)
    def decide_defeat_rounds(self) -> OperationRoundResult:
        """失败局处理完仓库后允许重开，连续三次失败则停在仓库。"""
        if self.defeat_rounds >= 3:
            return self.round_fail('连续 3 局失败，已完成仓库结算，停止自动重开')
        return self.round_success('继续入场')
