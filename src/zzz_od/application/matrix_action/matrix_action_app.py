from __future__ import annotations

import time
from typing import ClassVar, Optional

import cv2

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.matcher.match_result import MatchResult, MatchResultList
from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.base.screen import screen_utils
from one_dragon.base.screen.screen_utils import FindAreaResultEnum
from one_dragon.utils import cal_utils, cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidRegionType,
)
from zzz_od.application.hollow_zero.lost_void.operation.lost_void_run_level import (
    LostVoidRunLevel,
)
from zzz_od.application.matrix_action import matrix_action_const
from zzz_od.application.matrix_action.matrix_action_config import MatrixActionConfig
from zzz_od.application.matrix_action.matrix_action_run_record import (
    MatrixActionRunRecord,
)
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld


class MatrixActionApp(ZApplication):

    STATUS_TIMES_FINISHED: ClassVar[str] = "已完成进入次数"
    STATUS_AGAIN: ClassVar[str] = "继续挑战"
    STATUS_RELAY: ClassVar[str] = "接力运行"
    STATUS_ON_MATRIX_PAGE: ClassVar[str] = "矩阵行动页面"
    STATUS_NEED_BACK_WORLD: ClassVar[str] = "需返回大世界"

    def __init__(self, ctx: ZContext, use_internal_run_record: bool = True):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=matrix_action_const.APP_ID,
            op_name=matrix_action_const.APP_NAME,
        )
        self.config: MatrixActionConfig = self.ctx.run_context.get_config(
            app_id=matrix_action_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )
        self.run_record: MatrixActionRunRecord = self.ctx.run_context.get_run_record(
            instance_idx=self.ctx.current_instance_idx,
            app_id=matrix_action_const.APP_ID,
        )
        self.use_internal_run_record: bool = use_internal_run_record
        self._init_runtime_state()

    def _init_runtime_state(self) -> None:
        """初始化运行时状态"""
        self._support_agent_opened: bool = False
        self._support_up_clicked_once: bool = False
        self._preset_team_clicked_once: bool = False
        self._team_clicked_once: bool = False
        self._team_scroll_times: int = 0
        self._start_challenge_seen: bool = False
        self._last_click_at: float = 0.0
        self._click_cooldown_sec: float = 1.0
        self._next_step_last_click_at: float = 0.0
        self._next_step_click_cooldown_sec: float = 5.0
        self.next_region_type: LostVoidRegionType = LostVoidRegionType.ENTRY

    def handle_init(self) -> None:
        ZApplication.handle_init(self)
        self._init_runtime_state()
        self._reset_click_cooldown()

    @operation_node(name="初始化加载", is_start_node=True)
    def init_for_matrix_action(self) -> OperationRoundResult:
        if self.use_internal_run_record and self.run_record.is_finished_by_day():
            return self._round_success_with_click_reset(MatrixActionApp.STATUS_TIMES_FINISHED)
        try:
            # 复用迷失之地战斗流程所需的运行上下文（检测器/数据/策略）
            self.ctx.lost_void.init_before_run()
            # 覆盖为矩阵行动当前选择的挑战配置
            self.ctx.lost_void.challenge_config = self.config.challenge_config_instance
        except Exception:
            return self.round_fail("初始化失败")
        return self._round_success_with_click_reset(MatrixActionApp.STATUS_AGAIN)

    @node_from(from_name="初始化加载", status=STATUS_AGAIN)
    @operation_node(name="开始前接力检查")
    def check_initial_screen(self) -> OperationRoundResult:
        # 特殊兼容：在挑战确认弹窗处开始，先确认进入挑战
        result = self.round_by_find_and_click_area(
            self.last_screenshot,
            "迷失之地-大世界",
            "按钮-挑战-确认",
        )
        if result.is_success:
            self.next_region_type = LostVoidRegionType.CHANLLENGE_TIME_TRAIL
            return self.round_wait(result.status, wait=0.3)

        # 已在战斗画面，直接接力
        if self._check_in_battle():
            return self._round_success_with_click_reset(MatrixActionApp.STATUS_RELAY)

        # 已在矩阵行动页面，直接进入挑战流程
        if self._check_ocr_text("矩阵行动"):
            return self._round_success_with_click_reset(MatrixActionApp.STATUS_ON_MATRIX_PAGE)

        # 已在迷失之地流程画面，直接接力到层间移动
        screen_name = self.check_and_update_current_screen(
            self.last_screenshot,
            screen_name_list=[
                "迷失之地-大世界",
                "迷失之地-通用选择",
                "迷失之地-武备选择",
                "迷失之地-邦布商店",
                "迷失之地-路径迭换",
                "迷失之地-抽奖机",
            ],
        )
        if screen_name is not None:
            return self._round_success_with_click_reset(MatrixActionApp.STATUS_RELAY)

        return self._round_success_with_click_reset(MatrixActionApp.STATUS_NEED_BACK_WORLD)

    @node_from(from_name="开始前接力检查", status=STATUS_NEED_BACK_WORLD)
    @operation_node(name="返回大世界")
    def back_at_first(self) -> OperationRoundResult:
        """返回大世界"""
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name="返回大世界")
    @operation_node(name="前往快捷手册-作战", node_max_retry_times=300)
    def goto_compendium_combat(self) -> OperationRoundResult:
        result = self.round_by_goto_screen(
            screen_name="快捷手册-作战",
            retry_wait=0.3,
        )
        if result.is_success and self._check_ocr_text("零号空洞"):
            return self._round_success_with_click_reset("出现零号空洞")
        return self.round_retry(
            result.status if result.status is not None else "等待快捷手册-作战",
            wait=0.3,
        )

    @node_from(from_name="前往快捷手册-作战")
    @operation_node(name="点击零号空洞")
    def click_hollow_zero(self) -> OperationRoundResult:
        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
        if self._check_ocr_text(["迷失之地", "前往"], ocr_result_map=ocr_result_map):
            return self._round_success_with_click_reset("出现迷失之地")

        target = self._find_first_text("零号空洞", ocr_result_map=ocr_result_map)
        if target is not None:
            if self._is_click_on_cooldown():
                return self.round_wait("点击零号空洞", wait=0.1)
            if self._click_with_cooldown(target.center):
                return self.round_wait("点击零号空洞", wait=0.3)
            return self.round_retry("点击零号空洞失败", wait=0.1)

        return self.round_retry("未找到零号空洞", wait=0.3)

    @node_from(from_name="点击零号空洞")
    @operation_node(name="前往矩阵行动")
    def go_to_matrix_action(self) -> OperationRoundResult:
        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
        if self._check_ocr_text("矩阵行动", ocr_result_map=ocr_result_map):
            return self._round_success_with_click_reset("出现矩阵行动")

        confirm = self._find_first_text("确认", ocr_result_map=ocr_result_map)
        if confirm is not None:
            if self._is_click_on_cooldown():
                return self.round_wait("点击确认", wait=0.1)
            if self._click_with_cooldown(confirm.center):
                return self.round_wait("点击确认", wait=0.3)
            return self.round_retry("点击确认失败", wait=0.1)

        lost_void_pos = self._find_first_text("迷失之地", ocr_result_map=ocr_result_map)
        goto_list = self._find_all_text("前往", ocr_result_map=ocr_result_map)
        if lost_void_pos is not None and len(goto_list) > 0:
            valid_goto = [i for i in goto_list if i.center.y > lost_void_pos.center.y]
            if len(valid_goto) > 0:
                nearest_goto = min(
                    valid_goto,
                    key=lambda x: cal_utils.distance_between(x.center, lost_void_pos.center),
                )
                if self._is_click_on_cooldown():
                    return self.round_wait("点击前往", wait=0.1)
                if self._click_with_cooldown(nearest_goto.center):
                    return self.round_wait("点击前往", wait=0.3)
                return self.round_retry("点击前往失败", wait=0.1)

        return self.round_retry("未找到矩阵行动入口", wait=0.3)

    @node_from(from_name="前往矩阵行动")
    @node_from(from_name="开始前接力检查", status=STATUS_ON_MATRIX_PAGE)
    @operation_node(name="前往挑战")
    def goto_challenge(self) -> OperationRoundResult:
        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
        has_matrix_action = self._check_ocr_text("矩阵行动", ocr_result_map=ocr_result_map)
        has_goto_challenge = self._check_ocr_text(
            "前往挑战",
            ocr_result_map=ocr_result_map,
        )
        if has_matrix_action and not has_goto_challenge:
            return self._round_success_with_click_reset("已进入挑战界面")

        target = self._find_first_text("前往挑战", ocr_result_map=ocr_result_map)
        if target is not None:
            if self._is_click_on_cooldown():
                return self.round_wait("点击前往挑战", wait=0.1)
            if self._click_with_cooldown(target.center):
                return self.round_wait("点击前往挑战", wait=0.3)
            return self.round_retry("点击前往挑战失败", wait=0.1)

        return self.round_retry("未找到前往挑战", wait=0.3)

    @node_from(from_name="前往挑战")
    @operation_node(name="点击下一步")
    def click_next_step(self) -> OperationRoundResult:
        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
        if self._check_ocr_text("主战编队", ocr_result_map=ocr_result_map):
            return self._round_success_with_click_reset("出现主战编队")

        target = self._find_first_text("下一步", ocr_result_map=ocr_result_map)
        if target is not None:
            if time.monotonic() - self._next_step_last_click_at < self._next_step_click_cooldown_sec:
                return self.round_wait("点击下一步", wait=0.1)
            if self._is_click_on_cooldown():
                return self.round_wait("点击下一步", wait=0.1)
            if self._click_with_cooldown(target.center):
                self._next_step_last_click_at = time.monotonic()
                return self.round_wait("点击下一步", wait=0.1)
            return self.round_retry("点击下一步失败", wait=0.1)

        return self.round_retry("未找到下一步", wait=0.1)

    @node_from(from_name="点击下一步")
    @operation_node(name="点击主战编队")
    def click_main_team(self) -> OperationRoundResult:
        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
        if self._check_ocr_text("预备编队", ocr_result_map=ocr_result_map):
            return self._round_success_with_click_reset("出现预备编队")

        target = self._find_first_text("主战编队", ocr_result_map=ocr_result_map)
        if target is not None:
            if self._is_click_on_cooldown():
                return self.round_wait("点击主战编队", wait=0.1)
            if self._click_with_cooldown(target.center):
                return self.round_wait("点击主战编队", wait=0.3)
            return self.round_retry("点击主战编队失败", wait=0.1)

        return self.round_retry("未找到主战编队", wait=0.3)

    @node_from(from_name="点击主战编队")
    @operation_node(name="点击预备编队")
    def click_preset_team(self) -> OperationRoundResult:
        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
        target = self._find_first_text("预备编队", ocr_result_map=ocr_result_map, exact=True)
        if target is None:
            target = self._find_first_text("预备编队", ocr_result_map=ocr_result_map)
        if target is None:
            target = self._find_first_text("预设编队", ocr_result_map=ocr_result_map)

        # 必须先点过一次，再按文本块高亮判定是否进入预备编队
        if (
            self._preset_team_clicked_once
            and target is not None
            and self._is_text_block_highlighted(target)
        ):
            return self._round_success_with_click_reset("预备编队已高亮")

        if target is not None:
            if self._is_click_on_cooldown():
                return self.round_wait("点击预备编队", wait=0.1)
            if self._click_with_cooldown(target.center):
                self._preset_team_clicked_once = True
                return self.round_wait("点击预备编队", wait=0.3)
            return self.round_retry("点击预备编队失败", wait=0.1)

        return self.round_retry("未找到预备编队", wait=0.1)

    @node_from(from_name="点击预备编队")
    @operation_node(name="选择配队")
    def select_team(self) -> OperationRoundResult:
        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
        left_center = self._get_left_screen_center()
        target = self._find_first_text(
            self.config.team_name,
            ocr_result_map=ocr_result_map,
            exact=True,
        )
        if target is None:
            target = self._find_first_text(
                self.config.team_name,
                ocr_result_map=ocr_result_map,
            )

        # 必须至少点击命中一次目标队伍（找不到时最多滚动5次，之后左侧中点兜底点一次）
        if not self._team_clicked_once:
            if target is not None:
                if self._is_click_on_cooldown():
                    return self.round_wait(f"点击{self.config.team_name}", wait=0.1)
                if self._click_with_cooldown(target.center):
                    self._team_clicked_once = True
                    self._team_scroll_times = 0
                    return self.round_wait(f"点击{self.config.team_name}", wait=0.3)
                return self.round_retry(f"点击{self.config.team_name}失败", wait=0.1)

            if self._team_scroll_times < 5:
                start = left_center
                end = start + Point(0, -300)
                self.ctx.controller.drag_to(start=start, end=end)
                self._team_scroll_times += 1
                return self.round_wait(
                    f"未找到{self.config.team_name} 左侧上划{self._team_scroll_times}/5",
                    wait=0.3,
                )

            if self._is_click_on_cooldown():
                return self.round_wait("左侧中点兜底选队", wait=0.1)
            if self._click_with_cooldown(left_center):
                self._team_clicked_once = True
                self._team_scroll_times = 0
                return self.round_wait("未找到目标队伍 左侧中点兜底选队", wait=0.3)
            return self.round_retry("左侧中点兜底选队失败", wait=0.1)

        main_markers = self._find_all_text(
            "主战",
            ocr_result_map=ocr_result_map,
            exact=True,
        )
        title_marker = self._find_first_text(
            "主战编队",
            ocr_result_map=ocr_result_map,
        )
        if title_marker is not None and len(main_markers) > 0:
            overlap_main_markers = [
                marker
                for marker in main_markers
                if marker.x <= title_marker.x + title_marker.w
                and marker.x + marker.w >= title_marker.x
                and marker.center.y > title_marker.center.y
            ]
            if len(overlap_main_markers) > 0:
                return self._round_success_with_click_reset("主战与标题垂直重叠 已选择配队")

        if target is not None:
            if self._is_click_on_cooldown():
                return self.round_wait(f"点击{self.config.team_name}", wait=0.1)
            if self._click_with_cooldown(target.center):
                return self.round_wait(f"点击{self.config.team_name}", wait=0.3)
            return self.round_retry(f"点击{self.config.team_name}失败", wait=0.1)

        return self.round_retry(f"未找到{self.config.team_name}", wait=0.3)

    @node_from(from_name="选择配队")
    @operation_node(name="点击一次协助代理人")
    def click_support_agent_once(self) -> OperationRoundResult:
        if self._support_agent_opened:
            return self._round_success_with_click_reset("已点击协助代理人")

        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
        support = self._find_first_text("协助代理人", ocr_result_map=ocr_result_map)
        if support is not None:
            if self._is_click_on_cooldown():
                return self.round_wait("点击协助代理人", wait=0.1)
            if self._click_with_cooldown(support.center):
                self._support_agent_opened = True
                return self.round_wait("点击协助代理人", wait=0.1)
            return self.round_retry("点击协助代理人失败", wait=0.1)

        return self.round_retry("未找到协助代理人", wait=0.1)

    @node_from(from_name="点击一次协助代理人")
    @operation_node(name="等待代理人列表", node_max_retry_times=300)
    def wait_support_agent_panel(self) -> OperationRoundResult:
        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
        if self._check_ocr_text("代理人", ocr_result_map=ocr_result_map):
            return self._round_success_with_click_reset("已出现代理人列表")
        return self.round_retry("等待代理人列表", wait=0.1)

    @node_from(from_name="等待代理人列表")
    @operation_node(name="选择协助代理人")
    def select_support_agent(self) -> OperationRoundResult:
        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
        if (
            self._support_up_clicked_once
            and self._check_ocr_text("协战", ocr_result_map=ocr_result_map, exact=True)
        ):
            return self._round_success_with_click_reset("已选择协助代理人")

        up_markers = self._find_all_text("UP", ocr_result_map=ocr_result_map, exact=True)
        left_up_markers = [
            marker
            for marker in up_markers
            if marker.center.x < self.ctx.controller.standard_width // 2
        ]
        if len(left_up_markers) == 0:
            return self.round_retry("未找到左侧UP", wait=0.1)

        left_up_markers.sort(key=lambda x: (x.y, x.x))
        if self._is_click_on_cooldown():
            return self.round_wait("点击左侧UP", wait=0.1)
        if self._click_with_cooldown(left_up_markers[0].center):
            self._support_up_clicked_once = True
            return self.round_wait("点击左侧UP", wait=0.1)

        return self.round_retry("点击左侧UP失败", wait=0.1)

    @node_from(from_name="选择协助代理人")
    @operation_node(name="开始挑战")
    def start_challenge(self) -> OperationRoundResult:
        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
        start = self._find_first_text("开始挑战", ocr_result_map=ocr_result_map)
        if start is None:
            if self._start_challenge_seen or self._check_in_battle():
                if self.use_internal_run_record:
                    self.run_record.add_times()
                return self._round_success_with_click_reset("已进入空洞战斗")
            return self.round_retry("等待开始挑战按钮", wait=0.3)

        self._start_challenge_seen = True
        if self._is_click_on_cooldown():
            return self.round_wait("点击开始挑战", wait=0.1)
        if self._click_with_cooldown(start.center):
            return self.round_wait("点击开始挑战", wait=0.3)
        return self.round_retry("点击开始挑战失败", wait=0.3)

    @node_from(from_name="开始挑战", status="已进入空洞战斗")
    @node_from(from_name="开始前接力检查", status=STATUS_RELAY)
    @operation_node(name="加载自动战斗配置")
    def load_auto_op(self) -> OperationRoundResult:
        self.ctx.auto_battle_context.init_auto_op(
            sub_dir="auto_battle",
            op_name=self.config.challenge_config_instance.auto_battle,
        )
        return self._round_success_with_click_reset()

    @node_from(from_name="加载自动战斗配置")
    @node_from(from_name="层间移动")
    @operation_node(name="层间移动")
    def run_level(self) -> OperationRoundResult:
        log.info(f"推测楼层类型 {self.next_region_type.value.value}")
        op = LostVoidRunLevel(self.ctx, self.next_region_type)
        op_result = op.execute()
        if op_result.success and op_result.status == LostVoidRunLevel.STATUS_NEXT_LEVEL:
            if op_result.data is not None:
                self.next_region_type = LostVoidRegionType.from_value(op_result.data)
            else:
                self.next_region_type = LostVoidRegionType.ENTRY
        return self.round_by_op_result(op_result)

    @node_from(from_name="层间移动", status=LostVoidRunLevel.STATUS_COMPLETE)
    @operation_node(name="通关后处理")
    def after_complete(self) -> OperationRoundResult:
        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
        if self._check_ocr_text("矩阵行动", ocr_result_map=ocr_result_map):
            return self._round_success_with_click_reset("通关完成")
        return self.round_wait("等待矩阵行动文本", wait=0.3)

    def _round_success_with_click_reset(self, status: Optional[str] = None) -> OperationRoundResult:
        self._reset_click_cooldown()
        return self.round_success(status)

    def _reset_click_cooldown(self) -> None:
        self._last_click_at = 0.0

    def _is_click_on_cooldown(self) -> bool:
        return time.monotonic() - self._last_click_at < self._click_cooldown_sec

    def _click_with_cooldown(self, pos) -> bool:
        # 先记录点击尝试时间，避免底层点击返回失败时短时间内重复点击同一目标
        self._last_click_at = time.monotonic()
        return self.ctx.controller.click(pos)

    def _is_text_block_highlighted(self, text_mr: MatchResult) -> bool:
        if self.last_screenshot is None:
            return False

        pad_x = max(4, text_mr.w // 6)
        pad_y = max(2, text_mr.h // 4)
        rect = Rect(
            text_mr.x - pad_x,
            text_mr.y - pad_y,
            text_mr.x + text_mr.w + pad_x,
            text_mr.y + text_mr.h + pad_y,
        )
        part = cv2_utils.crop_image_only(self.last_screenshot, rect)
        if part is None or part.size == 0:
            return False

        hsv = cv2.cvtColor(part, cv2.COLOR_RGB2HSV)
        saturation = hsv[:, :, 1]
        value = hsv[:, :, 2]

        # 黑白文本饱和度低；高亮文本会有稳定的中高饱和像素
        colorful_ratio = ((saturation > 45) & (value > 70)).mean()
        mean_saturation = float(saturation.mean())
        return colorful_ratio >= 0.06 and mean_saturation >= 18.0

    def _get_left_screen_center(self) -> Point:
        return Point(
            self.ctx.controller.standard_width // 4,
            self.ctx.controller.standard_height // 2,
        )

    def _check_ocr_text(
        self,
        text_list: str | list[str],
        ocr_result_map: Optional[dict[str, MatchResultList]] = None,
        exact: bool = False,
    ) -> bool:
        if isinstance(text_list, str):
            text_list = [text_list]
        if ocr_result_map is None:
            ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)

        for text in text_list:
            if self._find_first_text(text, ocr_result_map=ocr_result_map, exact=exact) is None:
                return False
        return True

    def _find_first_text(
        self,
        text: str,
        ocr_result_map: Optional[dict[str, MatchResultList]] = None,
        exact: bool = False,
        cutoff: float = 0.6,
        lcs_percent: float = 0.7,
    ) -> Optional[MatchResult]:
        if ocr_result_map is None:
            ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)

        if exact:
            target = self._normalize_ocr_text(text)
            for ocr_text, mrl in ocr_result_map.items():
                if self._normalize_ocr_text(ocr_text) == target and mrl.max is not None:
                    return mrl.max
            return None

        target = gt(text, "game")
        word_list = list(ocr_result_map.keys())
        match_idx = str_utils.find_best_match_by_difflib(target, word_list, cutoff=cutoff)
        if match_idx is not None and match_idx >= 0:
            mrl = ocr_result_map[word_list[match_idx]]
            if mrl.max is not None:
                return mrl.max

        for ocr_text, mrl in ocr_result_map.items():
            if str_utils.find_by_lcs(target, ocr_text, percent=lcs_percent) and mrl.max is not None:
                return mrl.max

        return None

    def _find_all_text(
        self,
        text: str,
        ocr_result_map: Optional[dict[str, MatchResultList]] = None,
        exact: bool = False,
        lcs_percent: float = 0.7,
    ) -> list[MatchResult]:
        if ocr_result_map is None:
            ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)

        result: list[MatchResult] = []
        if exact:
            target = self._normalize_ocr_text(text)
            for ocr_text, mrl in ocr_result_map.items():
                if self._normalize_ocr_text(ocr_text) == target:
                    result.extend(mrl.arr)
            return result

        target = gt(text, "game")
        for ocr_text, mrl in ocr_result_map.items():
            if str_utils.find_by_lcs(target, ocr_text, percent=lcs_percent):
                result.extend(mrl.arr)
        return result

    def _check_in_battle(self) -> bool:
        if self.last_screenshot is None:
            return False

        result = screen_utils.find_area(self.ctx, self.last_screenshot, "战斗画面", "按键-普通攻击")
        if result == FindAreaResultEnum.TRUE:
            return True

        result = screen_utils.find_area(self.ctx, self.last_screenshot, "战斗画面", "按键-交互")
        return result == FindAreaResultEnum.TRUE

    @staticmethod
    def _normalize_ocr_text(text: str) -> str:
        return "".join(text.split()).upper()


def __debug():
    ctx = ZContext()
    ctx.init()
    op = MatrixActionApp(ctx)
    op.execute()


if __name__ == "__main__":
    __debug()
