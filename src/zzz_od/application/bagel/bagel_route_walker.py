"""贝果路线执行状态机：按打点顺序走到最后。

入场后先识别出生点：连续 2 次新截图命中同一个已登记出生点才确认，最多
观察 10 秒。正式运行执行该出生点当前开启的路线；试跑执行指定路线，但角色
也必须站在该路线绑定的出生点。确认后从路线第 1 点开始，游标顺序推进：

- 下一格是途径点：正常导航，进入 3px 到达半径即算路过。
- 下一格是箱类：按距离慢步或碎步靠近。当前目标是电子保险箱时，进入
  15px 后保持 0.08 秒短步；可信提示出现后松键，按类型交互。
- 路线走完：原地判断现场有无交互物，没有就结束；由应用层走既有退出结算链。

出生点不在已登记范围内、或出生点没有开启路线时，返回 ``STATUS_ANCHOR_MISS``，
由应用层退出重开。

导航与交互复用旧实现里与旧流程解耦的部分：分层定位、朝向识别、转向
补偿、光圈解锁、逐件入箱、关闭面板。旧流程（flow.yml 步骤、写死的
动作模板）不再参与。
"""

from __future__ import annotations

import time
from math import atan2, cos, degrees, floor, hypot, radians, sin
from typing import TYPE_CHECKING

import numpy as np

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.utils import cal_utils, cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.bagel import bagel_screen
from zzz_od.application.bagel.bagel_close_search import BagelCloseSearch
from zzz_od.application.bagel.bagel_input_worker import (
    TURN_DEADBAND,
    TURN_DEADBAND_FAST,
    BagelInputWorker,
)
from zzz_od.application.bagel.bagel_operation import BagelOperation
from zzz_od.application.bagel.bagel_route_model import (
    BEACON,
    ELEVATOR,
    ELEVATOR_EXIT_BACKWARD,
    BagelRoute,
    BagelRoutePoint,
    BagelRouteRef,
    BagelSpawnPoint,
    check_route_start,
)
from zzz_od.application.bagel.bagel_route_recorder import is_foreground
from zzz_od.application.bagel.bagel_route_store import (
    BagelRouteConfigError,
    BagelRouteStore,
)
from zzz_od.application.bagel.bagel_spawn import (
    SPAWN_AMBIGUOUS,
    SPAWN_HIT,
    SPAWN_MISS,
    BagelSpawnMatch,
    match_spawn,
)
from zzz_od.application.bagel.bagel_stats import BagelSafeLedger, parse_value
from zzz_od.application.bagel.bagel_store import BagelStoreSafe
from zzz_od.application.bagel.bagel_unlock_safe import BagelUnlockSafe
from zzz_od.game_data.map_locator.map_locator import (
    MultiMapLocator,
    load_map_locators,
)
from zzz_od.game_data.map_locator.minimap_angle import analyze

if TYPE_CHECKING:
    from cv2.typing import MatLike

    from one_dragon.base.matcher.ocr.ocr_match_result import OcrMatchResult
    from one_dragon.base.operation.operation_base import OperationResult
    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.context.zzz_context import ZContext

ELEVATOR_OPTION_TAP_SECONDS: float = 1.0
"""电梯选项还没出现时，点一次屏幕中间推进对话的间隔（用户给定每秒一次）。"""

ELEVATOR_ENTRY_TIMEOUT: float = 10.0
"""从电梯门口往前走多久还没进电梯就判失败（秒）。

只限制「门口走向电梯」这一段，此时还在场景里，失败后能正常退出。
进电梯之后的三段一律不设超时：卡在里面连游戏都退不出来。
"""

ELEVATOR_PHASE_ENTER: str = 'enter'
ELEVATOR_PHASE_WAIT_OPTION: str = 'wait_option'
ELEVATOR_PHASE_CLICK_OPTION: str = 'click_option'
ELEVATOR_PHASE_EXIT: str = 'exit'
"""电梯四个阶段的标识：进门、等选项、点选项、出电梯。"""

SPAWN_CONFIRM_FRAMES: int = 2
"""出生点识别需要连续几次新截图得出相同结论。"""

SPAWN_OBSERVE_SECONDS: float = 10.0
"""出生点识别的最长观察时间（秒）；期间不移动角色。"""

ARRIVE_RADIUS: float = 3.0
"""到达半径：3px 内算到点（用户给定）。"""

INTERACTION_TRUST_DISTANCE: float = 40.0
"""交互采信距离：提示出现时距目标点超过此值不采信。"""

SPRINT_DISTANCE: float = 30.0
"""多少像素外开冲刺（用户给定 30px）。

30px 外就冲刺，边跑边点闪避；30px 内不冲刺，松键改用走路逼近。
"""

BEACON_SLOW_RADIUS: float = 10.0
"""途径点慢步半径：进入它改用慢步走走停停，不再一路按住前进（用户给定）。"""

NEAR_STEP_TURN_RADIUS: float = 8.0
"""距离目标点小于它就不再按角度停车转。

这个距离上目标方位完全由 1~2px 的定位抖动决定：实测 5px 处相邻两轮算出的偏差
是 78° 和 59°，按它停车转只会原地打摆。改成像束角内那样边走边转，转向幅度受
CRUISE_TURN_CAP 限制。
"""

BOX_SMALL_STEP_RADIUS: float = 3.0
"""箱子碎步半径：进到它以内用碎步（用户给定 3px）。"""

ELECTRONIC_SMALL_STEP_RADIUS: float = 15.0
"""电子保险箱短步半径：进入后保持短步，直到当前目标结束。"""

BOX_WAIT_RADIUS: float = 1.9
"""箱子原地等待半径：距离小于 1.9px 就停步原地等提示（用户给定）。

用户要求「0px 才停」，但坐标不一定正好落在目标点上：
编辑器拖点会保留 1 位小数，定位又是整数像素，实际常停在 0.5px。
按 <= 0 判定永远进不去原地等待，只能一路碎步撞到 75 秒兜底超时。
所以用「小于 1.9」作判据，0.5px 这种就能正确进入等待。
"""

SMALL_STEP_TIMEOUT: float = 5.0
"""碎步超时（秒）：3px 内碎步前进超过它还没贴到目标就判超时（用户给定）。

碎步是不看角度硬迈的，方向偏了会一直贴着原地蹭。给一个短时限，
免得它在这个距离上耗到 75 秒的单点兜底。
"""

SLOW_STEP_PRESS: float = 0.5
"""慢步单次按压时长（秒）：比碎步长，一次走得多一点（用户给定 0.5）。"""

SLOW_STEP_WAIT: float = 0.1
"""慢步投递后重新观察的间隔（秒）；短按未结束时不叠发下一步。"""

TURN_SCALE_LESSON_SAMPLES: int = 10
"""至少攒到这么多个有效样本，才认为整局中位数可信。

一局十几个大转角实际只有 13~15 条有效样本，门槛取 20 等于永远不保存。
"""

TURN_SCALE_DRIFT_TOLERANCE: float = 0.15
"""前后半局中位数差超过它就认为还没稳定，不保存。"""

TURN_SCALE_MIN_CHANGE: float = 0.03
"""与本次初值差不到这么多就不写盘：实测每局的改进只有 0.03~0.06，门槛取大就永远写不进去。"""

TURN_SCALE_PEAK_BIN_WIDTH: float = 0.05
"""峰值箱的分箱宽度：箱以 1.0 为中心（如 0.975~1.025），取个数最多的箱的区间中点。"""

TURN_SCALE_BOUNDS: tuple[float, float] = (0.55, 1.95)
"""可信的补偿比例范围；超出说明样本被别的动作污染，存了也是错的。"""

ANGLE_FAIL_SECONDS: float = 10.0
"""连续读不到镜头朝向超过这个时长才判失败（用户给定 10 秒）。

单帧读不到是常事（转视角、贴墙、扇形被挡），不能立刻中断整条路线。
"""

WALK_TURN_ANGLE: float = 10.0
"""束角（用户术语）：朝向偏差在它以内不松前进键，边走边转微调。

转向线程 5 度内算对准不转，所以 5~10 度是边走边修，超过 10 度停车等转。
同时走和大角度转会互相干扰，表现为原地乱转，所以大偏差必须先松键。
"""

SMALL_STEP_PRESS: float = 0.08
"""碎步单次按压时长（秒）。"""

LOCATE_FAIL_SECONDS: float = 10.0
"""连续定位失败超过这个时长才判失败（用户给定 10 秒）。

给 MultiMapLocator 的最后一档降级留足时间：它要丢失满 1 秒
才开始搜索全部层，全层搜索本身也慢。
"""

STUCK_SECONDS: float = 3.0
STUCK_DISTANCE: float = 2.0
"""按住前进时判卡位：窗口内位移不足此值即视为走不动。"""

SIDE_STEP_SECONDS: float = 0.2
"""卡位时侧移一小步的按键时长（秒）。短按一下，不挪过头。"""

STUCK_STEP_LIMIT: int = 5
"""同一个点连续侧移的上限；挪这么多步还脱不了身，说明不是偏线而是真走不通。"""

POINT_TIMEOUT: dict[str, float] = {BEACON: 45.0, 'default': 75.0}
"""单点超时（秒）：途径点 45，箱类 75。"""

ACTION_LIMIT: int = 100
"""单个点允许的输入次数上限。"""

BOX_PROMPT_SECONDS: float = 1.0
"""箱子点贴到 0px 后原地等提示的上限（用户给定 1 秒）。

箱子一定会刷出交互提示，所以到 0px 还读不到，只可能是这个点本身
没东西，直接跳到下一个点，不判失败、也不原地死等。
"""

SURROUND_CHECK_SECONDS: float = 2.0
"""走完路线后原地观察交互物的时长。"""

MECHANICAL_HOLD_SECONDS: float = 5.0
"""机械保险箱长按 F 的最长时间（秒）。"""

INTERACT_TAP_SECONDS: float = 0.2
"""点按交互键 F 的按住时长（秒）。"""

ICON_THRESHOLD: float = 0.8
"""交互图标与刷卡图标的模板匹配阈值；实测同类 1.0、异类 0.33。"""

ENTRY_TEXT_MARGIN: int = 6
"""读取条目文字时，纵向向上下各留的像素。"""

PICKUP_WORDS: tuple[str, ...] = ('药粉', '拾取')
"""可拾取物而非容器的提示词；按 F 会捡起地上的东西，不能当箱子处理。"""


def _closest_on_segment(
    start: BagelRoutePoint, end: BagelRoutePoint, position: tuple[float, float],
) -> tuple[float, float]:
    """线段上离角色位置最近的点，夹在线段两端之间。

    Args:
        start: 线段起点，路径上的上一个点。
        end: 线段终点，当前目标点。
        position: 角色当前坐标。

    Returns:
        线段上的最近点坐标。
    """
    dx, dy = end.x - start.x, end.y - start.y
    length_sq = dx * dx + dy * dy
    if length_sq <= 0:
        return (float(start.x), float(start.y))
    t = ((position[0] - start.x) * dx + (position[1] - start.y) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    return (start.x + t * dx, start.y + t * dy)


def peak_bin_midpoint(samples: list[float], bin_width: float) -> tuple[float, int]:
    """全程补偿比例的峰值箱中点：箱以 1.0 为中心，取个数最多的箱的区间中点。

    Args:
        samples: 全程原始补偿比例样本。
        bin_width: 分箱宽度，必须大于零。

    Returns:
        峰值箱区间中点与该箱内样本数。
    """
    bins: dict[int, list[float]] = {}
    for value in samples:
        bins.setdefault(floor((value - 1.0) / bin_width + 0.5 + 1e-9), []).append(value)
    peak_key = max(bins, key=lambda key: len(bins[key]))
    return (1.0 + peak_key * bin_width, len(bins[peak_key]))


class BagelRouteWalker(BagelOperation):
    """按打点顺序执行路线，箱类按类型交互。"""

    STATUS_ANCHOR_MISS: str = '出生点没有可执行路线，退出重开'
    STATUS_SPAWN_FAILED: str = '出生点识别失败'
    STATUS_CONFIG_INVALID: str = '路线配置无效'
    STATUS_NOT_FOREGROUND: str = '游戏不在前台，已停止'
    STATUS_DONE: str = '路线走完'

    def __init__(
        self, ctx: ZContext, blueprint_priority: bool = True,
        route_ref: BagelRouteRef | None = None,
    ) -> None:
        """加载出生点清单并准备定位。

        Args:
            ctx: 运行上下文。
            blueprint_priority: 入箱时蓝图是否优先。
            route_ref: 试跑时指定的路线，关闭的路线也可以试跑；None 表示正式运行，
                识别出生点后执行该出生点当前开启的路线。

        Raises:
            ValueError: 出生点清单无法读取，或指定路线不存在、损坏、绑定的出生点未登记。
        """
        super().__init__(ctx, op_name='贝果-路线执行', timeout_seconds=-1)
        self.store: BagelRouteStore = BagelRouteStore()
        try:
            self.spawns: list[BagelSpawnPoint] = self.store.load_spawns()
            self.trial_route: BagelRoute | None = (
                None if route_ref is None else self.store.load_route(route_ref)
            )
        except BagelRouteConfigError as error:
            raise ValueError(str(error)) from error
        if self.trial_route is not None and not any(
            spawn.spawn_id == self.trial_route.spawn_id for spawn in self.spawns
        ):
            raise ValueError(f'路线绑定的出生点未登记：{self.trial_route.spawn_id}')
        self.routes: list[BagelRoute] = []
        """本局执行的路线快照；识别出生点后才确定，只含一条。"""
        self.spawn: BagelSpawnPoint | None = None
        """本局识别到的出生点。"""
        self.spawn_started_at: float | None = None
        """出生点识别的起始时刻。"""
        self.spawn_last_match: BagelSpawnMatch | None = None
        """上一帧的出生点匹配结论；定位失败时清空。"""
        self.spawn_streak: int = 0
        """连续得出相同出生点结论的新截图次数。"""
        self.blueprint_priority: bool = blueprint_priority
        self.locator: MultiMapLocator = MultiMapLocator(load_map_locators())
        self.route_index: int = 0
        self.cursor: int = 0
        self.current_kind: str | None = None
        self.f_pressed: bool = False
        self.mechanical_hold_until: float | None = None
        self.mechanical_retried: bool = False
        self.position: tuple[float, float] | None = None
        self.last_map_id: str | None = None
        self.locate_misses: int = 0
        self.locate_miss_since: float | None = None
        """连续定位失败的起始时刻，恢复定位后清空。"""
        self.angle_miss_since: float | None = None
        """连续读不到镜头朝向的起始时刻，读到朝向后清空。"""
        self.last_position: tuple[float, float] | None = None
        self.steps: int = 0
        self.stuck_since: tuple[tuple[float, float], float] | None = None
        self.stuck_steps: int = 0
        """当前点已经侧移了几次，进入新点时清零。"""
        self.target_wait_since: float | None = None
        self.electronic_small_steps: bool = False
        """当前电子保险箱已进入短步阶段，定位回到半径外时也不恢复长步。"""
        self.small_step_since: float | None = None
        """进入 3px 碎步段的起始时刻，用于碎步超时判定。"""
        self.point_started_at: float | None = None
        self.last_input_frame: float | None = None
        self.decision: str = '准备开始'
        """最近一轮的决策文字，供执行态悬浮窗显示。"""
        self.sprinting: bool = False
        """当前是否在冲刺。"""
        log.info(
            '贝果转向本局按 turn_dx=%.4f 起步，校准由转向线程自己学，局末写回同一字段',
            self.ctx.game_config.turn_dx,
        )
        self.elevator_phase: str | None = None
        """电梯当前阶段：进门 / 选楼层 / 出电梯；不在电梯里时为 None。"""
        self.elevator_since: float | None = None
        """当前电梯阶段的起始时刻，用于计时。"""
        self.elevator_last_tap: float = 0.0
        """上次为推进对话而点按的时刻，控制每秒一次。"""
        self.input_worker: BagelInputWorker = BagelInputWorker(ctx)
        """按键单独线程：主线投递即返回；同种操作不打断自己，不同操作打断旧的。"""
        self.ledger: BagelSafeLedger = BagelSafeLedger()
        """本局安全箱物品，只用于统计日志。"""
        self.survey_value: int | None = None
        """最近一次关闭搜查面板后从 HUD 读到的调查收益，只用于统计日志。"""

    def state_snapshot(self) -> dict[str, object]:
        """给悬浮窗用的执行状态快照。

        每次调用都按当前游标现算，不维护第二份真值，避免两边对不上。

        Returns:
            含决策、路线进度、点位与当前位置的字典。
        """
        route = self.routes[self.route_index] if self.routes else None
        point = self._current_point()
        distance: float | None = None
        if point is not None and self.position is not None:
            distance = hypot(point.x - self.position[0], point.y - self.position[1])
        return {
            'decision': self.decision,
            'route_id': route.route_id if route is not None else '',
            'route_name': route.name if route is not None else '',
            'spawn_name': self.spawn.name if self.spawn is not None else '',
            'route_index': self.route_index,
            'route_count': len(self.routes),
            'cursor': self.cursor,
            'total': len(route.points) if route is not None else 0,
            'points': [(point.kind, (point.x, point.y)) for point in route.points]
                      if route is not None else [],
            'layer': route.points[0].layer if route is not None and route.points else '',
            'position': self.position,
            'map_id': self.last_map_id,
            'distance': distance,
        }

    def _execute_one_round(self) -> OperationRoundResult:
        """每轮前先确认游戏在前台，结束后更新决策文字。

        用户切出游戏时，按键会打进别的窗口，必须先松键并停下，
        否则会在后台一直空转。
        """
        if not self._game_in_foreground():
            self._release_forward()
            self.decision = '游戏不在前台 · 已停止'
            return self.round_fail(self.STATUS_NOT_FOREGROUND)
        result = super()._execute_one_round()
        node_name = '未知' if self._current_node is None else self._current_node.cn
        status = result.status or result.status_display or ''
        self.decision = f'{node_name} · {status}' if status else node_name
        self._log_decision(node_name, status)
        return result

    def _log_decision(self, node_name: str, status: str) -> None:
        """每轮打一条决策日志，带点位、距离与角度，便于核对停在哪一步。

        同样的文字连续重复时也照打：卡住的表现正是同一条反复出现，
        静默掉就看不到「一直短步」「一直转圈」这类症状。

        到点那一轮不能把「当前游标」和「位置」直接配对：游标已经推进到
        下一个点，位置还是走到上一个点时的位置，两边一算就得到一个
        几十像素的假距离，看起来像「离老远就说到点」。所以到点这一轮
        只打位置，判定距离由 navigate 自己在到点时打一条独立的 log。
        """
        point = self._current_point()
        parts = [f'[{node_name}]']
        if status:
            parts.append(status)
        if point is not None:
            parts.append(f'第{self.cursor + 1}点 {point.kind}')
        arrived = node_name == '导航移动' and status.startswith('已到点')
        if point is not None and self.position is not None and not arrived:
            distance = hypot(point.x - self.position[0], point.y - self.position[1])
            parts.append(f'距 {distance:.1f}px')
        if self.position is not None:
            parts.append(f'位置 ({self.position[0]:.0f},{self.position[1]:.0f})')
        if self.current_kind is not None:
            parts.append(f'提示 {self.current_kind}')
        log.info('贝果执行 %s', ' · '.join(parts))

    def _game_in_foreground(self) -> bool:
        """游戏窗口是否在前台；拿不到窗口句柄时按前台处理，避免误停。"""
        game_win = self.ctx.controller.game_win
        hwnd = game_win.get_hwnd()
        if hwnd is None:
            return True
        return is_foreground(hwnd)

    # ---------- 定位 ----------

    def minimap(self) -> MatLike:
        """按原生区域裁出小地图；框架截图为 RGB，定位与朝向直接使用。"""
        area = self.ctx.screen_loader.get_area('贝果-局内', '定位小地图')
        if area is None:
            raise ValueError('缺少贝果定位小地图区域')
        crop = cv2_utils.crop_image_only(self.last_screenshot, area.pc_rect)
        if crop is None or crop.size == 0:
            raise ValueError('小地图裁剪为空')
        if crop.ndim == 2:
            crop = np.stack([crop] * 3, axis=-1)
        return crop

    def locate(self) -> tuple[float, float] | None:
        """定位一次并更新所在地图。"""
        result = self.locator.locate(self.minimap())
        if result is None:
            return None
        locator, _score, center = result
        self.last_map_id = locator.map_id
        self.position = (float(center[0]), float(center[1]))
        return self.position

    def player_angle(self) -> float | None:
        """识别镜头朝向角，正右为 0、逆时针增加。

        必须取 ``analyze`` 的第二个返回值（扇形方向 = 镜头朝向），
        不能用第一个（菱形尖端 = 角色朝向）。角色站着不动时，
        鼠标转动只改变镜头，角色朝向几乎不变，取错就会出现
        「不管怎么转，角度完全没更新」。
        """
        _marker_vertices, _marker_edges, sector, _radius, _center = analyze(self.minimap())
        return sector

    # ---------- 节点 ----------

    @operation_node(name='出生点识别', is_start_node=True)
    def anchor(self) -> OperationRoundResult:
        """识别出生点并确定本局路线，期间不移动角色。

        每轮使用新截图定位一次。连续 ``SPAWN_CONFIRM_FRAMES`` 次得出相同结论才采用；
        定位缺失或命中多个出生点时等下一帧，超过 ``SPAWN_OBSERVE_SECONDS`` 仍无结论则失败，
        不按路线顺序任取一条。
        """
        now = time.monotonic()
        if self.spawn_started_at is None:
            self.spawn_started_at = now
        if now - self.spawn_started_at > SPAWN_OBSERVE_SECONDS:
            reason = '定位失败' if self.spawn_last_match is None else self.spawn_last_match.describe()
            log.warning('贝果出生点识别：%.0f 秒内没有稳定结论（%s）', SPAWN_OBSERVE_SECONDS, reason)
            return self.round_fail(self.STATUS_SPAWN_FAILED, data=reason)
        position = self.locate()
        if position is None:
            self.spawn_last_match = None
            self.spawn_streak = 0
            return self.round_wait('定位失败，等下一帧', wait=0.2)
        match = match_spawn(self.spawns, self.last_map_id or '', position)
        self.spawn_streak = self.spawn_streak + 1 if match.same_as(self.spawn_last_match) else 1
        self.spawn_last_match = match
        if match.kind == SPAWN_AMBIGUOUS or self.spawn_streak < SPAWN_CONFIRM_FRAMES:
            return self.round_wait(match.describe(), wait=0.2)
        if match.kind == SPAWN_MISS:
            log.info(
                '贝果出生点识别：位置 (%.0f,%.0f) 不在任何已登记出生点范围内',
                position[0], position[1],
            )
            return self.round_fail(self.STATUS_ANCHOR_MISS)
        if match.kind != SPAWN_HIT or match.spawn is None:
            return self.round_fail(self.STATUS_SPAWN_FAILED, data=match.describe())
        return self._start_route_at(match.spawn)

    def _start_route_at(self, spawn: BagelSpawnPoint) -> OperationRoundResult:
        """按识别到的出生点确定路线快照，并从第 1 点开始。

        Args:
            spawn: 已确认的出生点。
        """
        self.spawn = spawn
        if self.trial_route is not None:
            route = self.trial_route
            if route.spawn_id != spawn.spawn_id:
                bound = next(
                    (item.name for item in self.spawns if item.spawn_id == route.spawn_id),
                    route.spawn_id,
                )
                return self.round_fail(
                    self.STATUS_SPAWN_FAILED,
                    data=f'角色在{spawn.name}，路线「{route.name}」绑定的是{bound}',
                )
        else:
            try:
                route = self.store.active_route(spawn.spawn_id)
            except BagelRouteConfigError as error:
                log.error('贝果出生点 %s 的路线配置无效：%s', spawn.name, error)
                return self.round_fail(self.STATUS_CONFIG_INVALID, data=str(error))
            if route is None:
                log.info('贝果出生点识别：%s 没有开启的路线', spawn.name)
                return self.round_fail(self.STATUS_ANCHOR_MISS)
        problem = check_route_start(route, spawn)
        if problem is not None:
            return self.round_fail(self.STATUS_CONFIG_INVALID, data=f'路线「{route.name}」{problem}')
        self.routes = [route]
        self._enter_point(0, 0)
        log.info(
            '贝果出生点识别：%s，执行路线「%s」（%s），共 %s 点',
            spawn.name, route.name, route.ref, len(route.points),
        )
        return self.round_success('已锚定')

    @node_from(from_name='游标推进', status='已推进')
    @node_from(from_name='导航移动', status='已到点')
    @node_from(from_name='导航移动', status='跳过此点')
    @node_from(from_name='碎步移动', status='跳过此点')
    @node_from(from_name='进出电梯', status='已离开电梯')
    @operation_node(name='点调度', mute=True)
    def dispatch(self) -> OperationRoundResult:
        """按游标当前点分派到导航、碎步或现场判断。"""
        point = self._current_point()
        if point is None:
            return self.round_success('路线走完')
        if point.kind == BEACON:
            return self.round_success('下一格是途径点')
        if point.kind == ELEVATOR:
            return self.round_success('下一格是电梯')
        return self.round_success('下一格是箱类')

    @node_from(from_name='点调度', status='路线走完')
    @node_from(from_name='导航移动', status='路线走完')
    @node_from(from_name='碎步移动', status='路线走完')
    @operation_node(name='现场交互判断')
    def check_surroundings(self) -> OperationRoundResult:
        """原地扫 2 秒：识别到已知提示就按提示交互，否则换路线。"""
        if self._nearby_kind() is not None:
            self.target_wait_since = None
            return self.round_success('现场有交互物')
        if self.target_wait_since is None:
            self.target_wait_since = time.monotonic()
        elif time.monotonic() - self.target_wait_since >= SURROUND_CHECK_SECONDS:
            self.target_wait_since = None
            return self.round_success('现场无交互物')
        return self.round_wait('原地观察交互提示', wait=0.25)

    def _nearby_kind(self) -> str | None:
        """右侧最上面一条交互提示的类型，识别不到时返回 None。

        先模板匹配交互图标或刷卡图标定位条目，再对该条右侧文字分类：
        含「保险箱」按电子/机械分，含「门」按门，其余都是可搜查容器。
        """
        entry = self._top_entry()
        if entry is None:
            return None
        return self._classify(entry[0], entry[1])

    def _top_entry(self) -> tuple[str, str] | None:
        """取最上面一条提示，返回（图标类型, 条目文字）。

        多条提示同时出现时，最上面那条才是按 F 生效的目标。
        只在提示区矩形内匹配，避免全屏误命中。
        """
        area = self.ctx.screen_loader.get_area('贝果-局内', '交互图标')
        if area is None:
            return None
        crop = cv2_utils.crop_image_only(self.last_screenshot, area.pc_rect)
        if crop is None or crop.size == 0:
            return None
        best: tuple[int, str, str] | None = None
        for icon, kind in (('interact_icon', 'interact'), ('card_key_icon', 'card')):
            result = self.ctx.tm.match_template(
                crop, 'bagel', icon, threshold=ICON_THRESHOLD, only_best=False,
            )
            for match in result:
                if best is None or match.center.y < best[0]:
                    best = (match.center.y, kind, self._entry_text(match, area.pc_rect.x1))
        if best is None:
            return None
        return best[1], best[2]

    def _entry_text(self, match, offset_x: int) -> str:
        """读取一条提示右侧的文字，去掉空白。

        只裁这一条的高度：整块提示区一起识别会漏读，按条裁剪才能稳定读出。

        Args:
            match: 提示区裁剪内的图标匹配结果。
            offset_x: 提示区裁剪相对整屏的左边距，用于换算回整屏坐标。
        """
        area = self.ctx.screen_loader.get_area('贝果-局内', '交互条目文字')
        if area is None:
            return ''
        left = max(area.pc_rect.x1, offset_x + match.x + match.w)
        right = area.pc_rect.x2
        top = area.pc_rect.y1 + match.y - ENTRY_TEXT_MARGIN
        bottom = area.pc_rect.y1 + match.y + match.h + ENTRY_TEXT_MARGIN
        if right <= left or bottom <= top:
            return ''
        texts = self.ctx.ocr_service.get_ocr_result_list(
            image=self.last_screenshot, rect=Rect(left, top, right, bottom),
        )
        return ''.join(str_utils.remove_whitespace(item.data) for item in texts)

    def _classify(self, icon_kind: str, text: str) -> str | None:
        """按图标与条目文字判断交互类型。

        特殊分支只有两类保险箱：电子保险箱要解锁，机械保险箱要长按。
        其余「箱 / 包 / 柜」都是按一下 F 开始搜宝；门和刷卡处按 F 直接开门。
        """
        if icon_kind == 'card':
            return 'card_reader'
        if gt('电子保险箱', 'game') in text:
            return 'electronic_safe'
        if gt('机械保险箱', 'game') in text:
            return 'mechanical_safe'
        if gt('门', 'game') in text:
            return 'door'
        if any(name in text for name in PICKUP_WORDS):
            return None
        if text:
            return 'box'
        return None

    @node_from(from_name='现场交互判断', status='现场有交互物')
    @operation_node(name='现场交互')
    def interact_nearby(self) -> OperationRoundResult:
        """首次按提示确定类型，之后检查本次交互结果，不要求场景提示仍可见。"""
        if self.current_kind is None:
            self.current_kind = self._nearby_kind()
        if self.current_kind is None:
            return self.round_retry('提示消失，再看一帧', wait=0.2)
        return self._interact_by_kind(self.current_kind)

    @node_from(from_name='现场交互判断', status='现场无交互物')
    @operation_node(name='路线结束')
    def finish_route(self) -> OperationRoundResult:
        """本局只执行一条路线，走完且现场没有交互物即结束。"""
        log.info('贝果路线执行：路线「%s」走完', self.routes[self.route_index].name)
        return self.round_success(self.STATUS_DONE)

    # ---------- 导航 ----------

    @node_from(from_name='出生点识别', status='已锚定')
    @node_from(from_name='点调度', status='下一格是途径点')
    @operation_node(name='导航移动', mute=True)
    def navigate(self) -> OperationRoundResult:
        """朝当前点移动；途径点 3px 到达，箱类见到提示就停。

        到点后必须回点调度重新分派，不能直接再进本节点：游标已经推进到
        下一个点，那个点可能是电梯或箱子，得由点调度按种类交给对应节点。
        直接自环会让电梯点落到箱类分支，被当成箱子慢步逼近。
        """
        return self._move_toward()

    @node_from(from_name='点调度', status='下一格是箱类')
    @operation_node(name='碎步移动', mute=True)
    def small_step(self) -> OperationRoundResult:
        """按距离逼近箱类点，统一检查到位、提示与单点超时。"""
        return self._move_toward()

    # ---------- 交互 ----------

    @node_from(from_name='点调度', status='下一格是电梯')
    @operation_node(name='进出电梯')
    def elevator(self) -> OperationRoundResult:
        """进出电梯：走向电梯，点楼层选项，再走出来。

        电梯点在进门前能正常定位，进电梯后小地图整块消失，所以不能按
        3px 判到达（用户定义：读不到朝向就是进了电梯）。进去之后分三段，
        每段只等它自己的信号，统一不设超时——卡在电梯里连游戏都退不出来。

        1. 进门：朝电梯点走，读不到朝向即进入电梯。
        2. 等选项：一直点屏幕中间推进对话，直到楼层选项出现。
        3. 点选项：一直点那个选项，直到它从画面上消失。
        4. 出梯：一直按住配置的方向，直到小地图回来。

        点上没有楼层文字（`elevator_option` 为空）的电梯没有第 2、3 段，
        进门后直接进出梯段。
        """
        point = self._current_point()
        if point is None:
            return self.round_success('路线走完')
        if self.elevator_phase is None:
            # 首次进入本节点必须从「进门」阶段开始。之前漏了这一步，
            # phase 一直是 None，直接落到出梯阶段，「朝电梯走」整个没执行过。
            self.elevator_phase = ELEVATOR_PHASE_ENTER
            self.elevator_since = None
        phase = self.elevator_phase
        if phase == ELEVATOR_PHASE_ENTER:
            return self._elevator_enter(point)
        if phase == ELEVATOR_PHASE_WAIT_OPTION:
            return self._elevator_wait_option(point)
        if phase == ELEVATOR_PHASE_CLICK_OPTION:
            return self._elevator_click_option(point)
        return self._elevator_exit(point)

    def _elevator_enter(self, point: BagelRoutePoint) -> OperationRoundResult:
        """朝电梯点走，途中读不到朝向就是进了电梯。

        电梯点没有「到达」这回事：小地图会整块消失，坐标和朝向都读不到，
        3px 这种判据在电梯口根本不成立。所以这里只朝点走，一旦
        `player_angle()` 读不到就当已进电梯（用户定义）。
        """
        if self.player_angle() is None:
            self._release_forward()
            self.elevator_since = None
            if point.elevator_option:
                self.elevator_phase = ELEVATOR_PHASE_WAIT_OPTION
                self.elevator_last_tap = 0.0
                return self.round_wait('小地图已消失，视为进入电梯', wait=0.2)
            self.elevator_phase = ELEVATOR_PHASE_EXIT
            return self.round_wait('小地图已消失，这电梯没有楼层选项', wait=0.2)
        if self.elevator_since is None:
            self.elevator_since = time.monotonic()
        if time.monotonic() - self.elevator_since >= ELEVATOR_ENTRY_TIMEOUT:
            self._release_forward()
            self.elevator_phase = None
            self.elevator_since = None
            return self.round_recoverable_fail('电梯门口走了 10 秒还没进入电梯')
        position = self.locate()
        if position is not None:
            angle = self.player_angle()
            if angle is not None:
                target_angle = self._target_angle(position, point)
                angle_diff = cal_utils.angle_delta(angle % 360, target_angle)
                self._submit_turn(target_angle, deadband=TURN_DEADBAND_FAST)
                if abs(angle_diff) > WALK_TURN_ANGLE:
                    # 方向偏太多先停下等转，不然会走到旁边去。
                    self._release_forward()
                    return self.round_wait(f'朝电梯转向 {angle_diff:.0f}度', wait=0.05)
                self.input_worker.hold_forward()
                return self.round_wait('走向电梯', wait=0.15)
        # 定位暂时丢失但朝向还在（贴墙等）：先不松前进，等下一帧。
        self.input_worker.hold_forward()
        return self.round_wait('走向电梯，定位暂缺', wait=0.15)

    def _elevator_wait_option(self, point: BagelRoutePoint) -> OperationRoundResult:
        """一直点屏幕中间推进对话，直到楼层选项出现。不设超时。"""
        found = self._find_elevator_option(point.elevator_option)
        if found is not None:
            self.elevator_phase = ELEVATOR_PHASE_CLICK_OPTION
            return self.round_wait(f'楼层选项已出现：{found.data}', wait=0.1)
        if time.monotonic() - self.elevator_last_tap >= ELEVATOR_OPTION_TAP_SECONDS:
            self.elevator_last_tap = time.monotonic()
            self.input_worker.tap_center()
        return self.round_wait('等待电梯楼层选项', wait=0.2)

    def _elevator_click_option(self, point: BagelRoutePoint) -> OperationRoundResult:
        """一直点那个选项，直到它从画面上消失。不设超时。

        选项点中后会收起，收起即表示楼层已选、电梯开始移动。
        中途某一帧识别不到也算收起，所以这里用「识别到才点、识别不到就
        进下一段」，不需要连续几帧确认。
        """
        found = self._find_elevator_option(point.elevator_option)
        if found is None:
            self.elevator_phase = ELEVATOR_PHASE_EXIT
            return self.round_wait('楼层选项已消失，准备出梯', wait=0.1)
        self.ctx.controller.click(found.rect.center)
        return self.round_wait(f'点选楼层：{found.data}', wait=0.2)

    def _find_elevator_option(self, option: str) -> OcrMatchResult | None:
        """在楼层列表里找配置的文字。

        Args:
            option: 要选的楼层文字，如「负二层」。

        Returns:
            匹配到的 OCR 结果；没有则返回 None。
        """
        area = self.ctx.screen_loader.get_area('贝果-局内', '电梯选项')
        if area is None:
            return None
        results = self.ctx.ocr_service.get_ocr_result_list(
            image=self.last_screenshot, rect=area.pc_rect,
        )
        target = gt(option, 'game')
        for item in results:
            if target in str_utils.remove_whitespace(item.data):
                return item
        return None

    def _elevator_exit(self, point: BagelRoutePoint) -> OperationRoundResult:
        """一直按住配置的方向往前走，直到小地图回来。不设超时。"""
        if self.player_angle() is not None:
            self._release_forward()
            self._release_backward()
            self.elevator_phase = None
            self.elevator_since = None
            self._enter_point(self.route_index, self.cursor + 1)
            return self.round_success('已离开电梯')
        if self.elevator_since is None:
            self.elevator_since = time.monotonic()
        if point.elevator_exit == ELEVATOR_EXIT_BACKWARD:
            self.input_worker.hold_backward()
        else:
            self.input_worker.hold_forward()
        elapsed = time.monotonic() - self.elevator_since
        return self.round_wait(f'出电梯 {elapsed:.1f}s', wait=0.15)

    def _release_backward(self) -> None:
        """松开后退键。"""
        self.input_worker.stop_backward()

    @node_from(from_name='碎步移动', status='提示已出现')
    @node_from(from_name='导航移动', status='提示已出现')
    @operation_node(name='按类型交互')
    def interact(self) -> OperationRoundResult:
        """按当前点类型执行交互。"""
        if self.current_kind is None:
            return self.round_retry('未知交互类型', wait=0.2)
        return self._interact_by_kind(self.current_kind)

    def _interact_by_kind(self, kind: str) -> OperationRoundResult:
        """分派交互动作。"""
        if kind == 'electronic_safe':
            return self._run_unlock_safe()
        if kind == 'mechanical_safe':
            return self._hold_mechanical()
        return self._press_f(kind)

    def _run_unlock_safe(self) -> OperationRoundResult:
        """电子保险箱：光圈解锁子操作。"""
        self._release_forward()
        op = BagelUnlockSafe(self.ctx, phase='full')
        result = op.execute()
        self._adopt_screenshot(op)
        if result.success:
            return self.round_success('电子保险箱已解锁')
        return self.round_recoverable_fail(f'电子保险箱解锁失败：{result.status}')

    def _hold_mechanical(self) -> OperationRoundResult:
        """机械保险箱：提示出现时长按 F，直到搜查面板出现。

        长按发生在提示出现时，不是面板打开后；面板一出就松手，
        后面与普通箱走同一套收集入箱。面板用底部共用的安全箱标记确认，
        不依赖专有标题。
        """
        if self.mechanical_hold_until is None:
            self._release_forward()
            self.mechanical_hold_until = time.monotonic() + MECHANICAL_HOLD_SECONDS
            self.input_worker.hold_interact()
            return self.round_wait('长按F中')
        if self._has('搜查安全箱'):
            self.input_worker.release_interact()
            self._reset_point_state()
            return self.round_success('机械保险箱已打开')
        if time.monotonic() >= self.mechanical_hold_until:
            self.input_worker.release_interact()
            if self.mechanical_retried:
                self._reset_point_state()
                return self.round_recoverable_fail('机械保险箱长按F超时')
            self.mechanical_retried = True
            self.mechanical_hold_until = None
            return self.round_wait('长按F超时，释放后重试', wait=0.3)
        return self.round_wait('长按F等待面板', wait=0.3)

    def _press_f(self, kind: str) -> OperationRoundResult:
        """点按 F：普通容器、门、刷卡处、电梯。

        容器类以搜查面板出现为完成；门、刷卡处、电梯以提示消失为完成。
        按 F 前先松前进键，避免按住前行漂移。
        """
        self._release_forward()
        if kind == 'box' and self._has('搜查容器标题'):
            # 容器面板已开：立刻交给收集入箱，不在这里判完成。
            # 用「提示消失」推断完成会漏掉收集和关闭面板，面板一直开着
            # 盖住小地图，后面整段导航都定位失败。
            self._reset_point_state()
            return self.round_success('面板已打开')
        if self.f_pressed and self._top_entry() is None:
            self._reset_point_state()
            return self.round_success('已完成')
        self.input_worker.tap_interact(INTERACT_TAP_SECONDS)
        self.f_pressed = True
        return self.round_wait('已点按F，等待结果', wait=0.4)

    @node_from(from_name='按类型交互', status='电子保险箱已解锁')
    @node_from(from_name='按类型交互', status='机械保险箱已打开')
    @node_from(from_name='按类型交互', status='面板已打开')
    @node_from(from_name='现场交互', status='电子保险箱已解锁')
    @node_from(from_name='现场交互', status='机械保险箱已打开')
    @node_from(from_name='现场交互', status='面板已打开')
    @operation_node(name='收集入箱')
    def collect(self) -> OperationRoundResult:
        """逐件装入安全箱。"""
        op = BagelStoreSafe(self.ctx, blueprint_priority=self.blueprint_priority, ledger=self.ledger)
        result = op.execute()
        self._adopt_screenshot(op)
        if result.success:
            return self.round_success('已入箱')
        return self.round_recoverable_fail(f'入箱失败：{result.status}')

    @node_from(from_name='收集入箱', status='已入箱')
    @operation_node(name='关闭面板')
    def close_panel(self) -> OperationRoundResult:
        """关闭搜查面板并确认回到局内。"""
        op = BagelCloseSearch(self.ctx)
        result = op.execute()
        self._adopt_screenshot(op)
        if result.success:
            self._read_survey_value()
            return self.round_success('已关闭面板')
        return self.round_recoverable_fail(f'关闭面板失败：{result.status}')

    @node_from(from_name='按类型交互', status='已完成')
    @node_from(from_name='现场交互', status='已完成')
    @node_from(from_name='关闭面板', status='已关闭面板')
    @operation_node(name='游标推进')
    def advance(self) -> OperationRoundResult:
        """游标加一并回点调度。"""
        self._enter_point(self.route_index, self.cursor + 1)
        return self.round_success('已推进')

    # ---------- 移动核心 ----------

    def _move_toward(self) -> OperationRoundResult:
        """朝当前游标点移动一轮。"""
        point = self._current_point()
        if point is None:
            return self.round_success('路线走完')
        timeout = self._check_timeout(point)
        if timeout is not None:
            return timeout
        hud = self._check_hud()
        if hud is not None:
            return hud
        position = self.locate()
        if position is None:
            # 定位丢失立刻停步：继续按着前进会走到不知道哪里去，
            # 恢复定位后再接着走。判失败要等满 10 秒，给降级搜索留时间。
            self._release_forward()
            if self.is_bagel_result():
                return self.round_fail(self.STATUS_DEFEATED)
            if self.last_position is None:
                return self.round_retry('起步定位失败，重试', wait=0.3)
            if self.locate_miss_since is None:
                self.locate_miss_since = time.monotonic()
            if time.monotonic() - self.locate_miss_since < LOCATE_FAIL_SECONDS:
                self.locate_misses += 1
                return self.round_wait('定位丢失，停下等待', wait=0.1)
            return self.round_recoverable_fail(
                f'连续 {LOCATE_FAIL_SECONDS:.0f}s 定位失败，停止移动',
            )
        self.locate_misses = 0
        self.locate_miss_since = None
        self.last_position = position
        distance = hypot(point.x - position[0], point.y - position[1])
        if (
            point.kind == 'electronic_safe'
            and distance <= ELECTRONIC_SMALL_STEP_RADIUS
            and not self.electronic_small_steps
        ):
            self.electronic_small_steps = True
            self._release_forward()
            log.info(
                '贝果电子保险箱进入短步阶段：距离 %.1fpx，半径 %.0fpx，按压 %.2fs',
                distance, ELECTRONIC_SMALL_STEP_RADIUS, SMALL_STEP_PRESS,
            )
        if self.last_input_frame is not None and self.last_screenshot_time <= self.last_input_frame:
            return self.round_wait('等待动作后的新截图', wait=0.05)
        if distance <= SPRINT_DISTANCE and self.sprinting:
            self._exit_sprint()
        if point.kind == BEACON:
            # 途径点是纯路点：3px 内算到点，10px 内慢步逼近。
            if distance <= ARRIVE_RADIUS:
                self._release_forward()
                log.info(
                    '贝果到点：第 %s 点判定距离 %.2fpx（判据 %.0fpx，位置 %s）',
                    self.cursor + 1, distance, ARRIVE_RADIUS, position,
                )
                self._enter_point(self.route_index, self.cursor + 1)
                # 状态文字必须正好是「已到点」：节点边按状态精确匹配，
                # 掺了距离就匹配不上，导航链会在这里断掉、整条路线直接判走完。
                return self.round_success('已到点')
            if distance <= BEACON_SLOW_RADIUS:
                return self._slow_step(point, position)
            return self._cruise(point, position)
        # 电子保险箱进入 15px 后保持短步；其他箱类仍在 3px 内使用碎步。
        # 可信提示出现就转入交互，不要求先走到原地等待半径。
        prompt = self._prompt_stop(distance)
        if prompt is not None:
            return prompt
        if distance < BOX_WAIT_RADIUS:
            self.small_step_since = None
            return self._wait_here(point)
        self.target_wait_since = None
        if distance <= BOX_SMALL_STEP_RADIUS:
            timeout = self._check_small_step_timeout()
            if timeout is not None:
                return timeout
            return self._short_step()
        self.small_step_since = None
        return self._slow_step(point, position, short_press=self.electronic_small_steps)

    def _wait_here(self, point: BagelRoutePoint) -> OperationRoundResult:
        """已站在箱子上：原地不动，等提示出现或超时跳到下一个点。

        箱子一定会刷出交互提示，所以到时间还没提示，只可能是这个点
        本身没有东西（或站位被挡住），直接跳过，不判失败、也不死等。

        Args:
            point: 当前游标点。
        """
        self._release_forward()
        if self.target_wait_since is None:
            self.target_wait_since = time.monotonic()
            return self.round_wait('原地等待交互提示', wait=0.2)
        if time.monotonic() - self.target_wait_since >= BOX_PROMPT_SECONDS:
            self.target_wait_since = None
            log.info(
                '贝果第 %s 点（%s）原地等 %ss 无提示，跳到下一个点',
                self.cursor + 1, point.kind, f'{BOX_PROMPT_SECONDS:.0f}',
            )
            self._enter_point(self.route_index, self.cursor + 1)
            return self.round_success('跳过此点')
        return self.round_wait('原地等待交互提示', wait=0.2)

    def _prompt_stop(self, distance: float) -> OperationRoundResult | None:
        """可信提示出现后松键并转入交互，不另做停稳复核。

        Args:
            distance: 当前可靠定位到目标点的距离。

        Returns:
            允许交互的结果；未识别到可信提示时返回 None。
        """
        kind = self._nearby_kind()
        if kind is None or distance > INTERACTION_TRUST_DISTANCE:
            return None
        self._release_forward()
        self.current_kind = kind
        self.target_wait_since = None
        return self.round_success('提示已出现')

    def _angle_miss_result(self, angle: float | None) -> OperationRoundResult | None:
        """读不到镜头朝向时停下等；连续读不到满 10 秒才判失败。

        单帧读不到是常事（转视角、贴墙、扇形被墙切掉），一帧失败就中断
        整条路线太脆。读不到时转向线程也转不了（没有当前角算偏差），
        这里只松键等画面回来，不下发任何转向。

        Args:
            angle: 本轮读到的镜头朝向；读到就不做处理。

        Returns:
            需要等待或失败时返回本轮结果；读到朝向后返回 None。
        """
        if angle is not None:
            self.angle_miss_since = None
            return None
        self._release_forward()
        if self.angle_miss_since is None:
            self.angle_miss_since = time.monotonic()
        missed = time.monotonic() - self.angle_miss_since
        if missed >= ANGLE_FAIL_SECONDS:
            return self.round_recoverable_fail(
                f'连续 {ANGLE_FAIL_SECONDS:.0f}s 识别不到镜头朝向，停止移动',
            )
        self.input_worker.submit_turn(None)
        return self.round_wait(f'未识别到朝向，停下等待（{missed:.1f}s）', wait=0.1)

    def _cruise(
        self, point: BagelRoutePoint, position: tuple[float, float],
    ) -> OperationRoundResult:
        """远距离移动：只提交目标方向，前进键自己管。

        转向全由转向线程负责（稳 3 帧、5 度以上才转）。这里只按本轮
        偏差管前进：超过 10 度松键停车等转，以内按住走。
        同时走和大角度转会互相干扰，表现为原地乱转。

        近距离不再按角度停车转：这个距离上的目标方位由定位抖动决定，
        停下车来按它转只会原地打摆，改成边走边转（线程内限幅 15 度）。
        """
        angle = self.player_angle()
        miss = self._angle_miss_result(angle)
        if miss is not None:
            return miss
        target_angle = self._target_angle(position, point)
        controller_angle = angle % 360
        angle_diff = cal_utils.angle_delta(controller_angle, target_angle)
        distance = hypot(point.x - position[0], point.y - position[1])
        near = distance <= NEAR_STEP_TURN_RADIUS
        self._submit_turn(target_angle, cruise_only=near, deadband=TURN_DEADBAND_FAST)
        if abs(angle_diff) > WALK_TURN_ANGLE and not near:
            # 大偏差：松键停车等转向线程转到位再走。
            self._release_forward()
            return self.round_wait(f'停车等转向 {angle_diff:.0f}度')
        stuck = self._check_stuck(position, point, controller_angle)
        if stuck is not None:
            return stuck
        if self.input_worker.hold_forward():
            self._record_input()
        self._set_sprint(distance)
        return self.round_wait('冲刺前进' if self.sprinting else '按住前进')

    def _submit_turn(self, target: float, cruise_only: bool = False, deadband: float = TURN_DEADBAND) -> None:
        """提交目标方向给转向线程；只存不定夺，不记输入。

        转不转、转多少、校准，全由转向线程自己采样、稳 3 帧后定。
        这里不调 _record_input：提交只是写内存，不是输入，
        记了会逼主线每轮多等一张新截图，把主循环限速。

        Args:
            target: 目标方向（度）。
            cruise_only: 近距离只做边走边转，线程内限幅 15 度。
            deadband: 本次目标的对准死区；快速移动传 2 度，其余用默认 5 度。
        """
        self.input_worker.submit_turn(target, cruise_only=cruise_only, deadband=deadband)

    def persist_turn_scale(self) -> None:
        """把本局学到的补偿比例写回现有灵敏度字段 turn_dx，供下一局直接用。

        全程原始样本按箱宽分箱，取个数最多的箱的区间中点；远离峰值的脏样本
        够不着峰值直接丢掉。超出可信范围、或与 1.0 几乎一样时不写盘。
        不再写 config/bagel/turn_scale.yml，直接改现有 turn_dx 字段。
        """
        samples = self.input_worker.turn_scale_samples
        if len(samples) < TURN_SCALE_LESSON_SAMPLES:
            return
        scale, peak_count = peak_bin_midpoint(samples, TURN_SCALE_PEAK_BIN_WIDTH)
        min_scale, max_scale = TURN_SCALE_BOUNDS
        if not min_scale <= scale <= max_scale:
            log.info('贝果转向校准值 %.3f 超出可信范围，不写回 turn_dx', scale)
            return
        if abs(scale - 1.0) < TURN_SCALE_MIN_CHANGE:
            return
        old_dx = self.ctx.game_config.turn_dx
        new_dx = round(float(old_dx) * float(scale), 6)
        try:
            self.ctx.game_config.turn_dx = new_dx
        except Exception:
            log.error('转向补偿写回 turn_dx 失败', exc_info=True)
            return
        log.info(
            '贝果转向补偿比例 %.3f 已写回 turn_dx（%.4f → %.4f，峰值 %s/%s 样本），下一局直接用',
            scale, old_dx, new_dx, peak_count, len(samples),
        )

    def _set_sprint(self, distance: float) -> None:
        """按距离决定是否冲刺。

        绝区零里冲刺是「按住方向键 + 连点闪避」，所以冲刺时持续点闪避，
        不需要按住闪避键。

        Args:
            distance: 距当前目标点的距离。
        """
        want = distance > SPRINT_DISTANCE
        if want:
            self.sprinting = True
            self._dodge_tap()
        elif self.sprinting:
            self._exit_sprint()

    def _dodge_tap(self) -> None:
        """点一下闪避：冲刺期间每轮都点，维持冲刺状态。"""
        self.input_worker.dodge()

    def _exit_sprint(self) -> None:
        """退出冲刺：松开方向键。"""
        self.sprinting = False
        self.input_worker.stop_forward()

    def _stop_sprint(self) -> None:
        """立刻松键。"""
        self.sprinting = False
        self.input_worker.stop_forward()

    def _prepare_forward_step(self) -> OperationRoundResult | None:
        """上一短按结束并取得松键后的截图，才允许发起下一步。"""
        if self.input_worker.forward_step_active():
            return self.round_wait('等待本次前进短按结束', wait=0.02)
        self._release_forward()
        released_at = self.input_worker.forward_released_at
        if released_at is None or self.last_screenshot_time <= released_at:
            return self.round_wait('等待松键后的新截图', wait=0.02)
        return None

    def _short_step(self) -> OperationRoundResult:
        """近距离移动：不停下来对准，直接短按前进。

        3px 内不再转向：这么近的距离，目标方向完全由 1px 级的坐标抖动
        决定，算出来的角度没有意义。一旦按角度判停，就会出现「每轮都在
        转向、一步也不走」的原地打摆。

        方向真的偏了也不怕：走一步后距离变大，自然回到慢步分支去对准。
        超时由调用方 _check_small_step_timeout 管，这里只负责迈步。
        """
        ready = self._prepare_forward_step()
        if ready is not None:
            return ready
        limited = self._fail_if_action_limit()
        if limited is not None:
            return limited
        if not self._step_forward(SMALL_STEP_PRESS):
            return self.round_wait('等待前进短按可用', wait=0.02)
        self._record_input()
        return self.round_wait('短步前进')

    def _check_small_step_timeout(self) -> OperationRoundResult | None:
        """碎步段超时检查：3px 内迈步超过 5 秒还没贴到就跳过这个点。

        碎步不看角度硬迈，方向偏了会一直原地蹭，靠单点 75 秒兜底太慢，
        所以这一小段单独计时。超时说明这个点贴不上（站位被挡、坐标偏），
        直接推进到下一个点，不判失败、也不死等。

        Returns:
            跳过结果；未超时返回 None。
        """
        if self.small_step_since is None:
            self.small_step_since = time.monotonic()
            return None
        if time.monotonic() - self.small_step_since < SMALL_STEP_TIMEOUT:
            return None
        self.small_step_since = None
        self._release_forward()
        log.info(
            '贝果第 %s 点（%s）碎步 %ss 没贴上，跳到下一个点',
            self.cursor + 1, self._current_kind_name(), f'{SMALL_STEP_TIMEOUT:.0f}',
        )
        self._enter_point(self.route_index, self.cursor + 1)
        return self.round_success('跳过此点')

    def _current_kind_name(self) -> str:
        """当前游标点的类型名，只用于日志。"""
        point = self._current_point()
        return point.kind if point is not None else '无'

    def _slow_step(
        self, point: BagelRoutePoint, position: tuple[float, float],
        short_press: bool = False,
    ) -> OperationRoundResult:
        """按目标方向步进，电子箱短步阶段使用更短的按压时间。

        只提交目标方向给转向线程；偏差超过 10 度时停车等转，
        其余情况短按前进。每步结束后使用新截图重新判断，
        避免多次短按相互覆盖。

        近距离不再按角度停车转：这个距离上的目标方位由定位抖动决定，
        改成边走边转（线程内限幅 15 度）。

        Args:
            point: 当前目标点。
            position: 当前可靠定位。
            short_press: 是否使用 0.08 秒短步；否则使用 0.5 秒慢步。
        """
        ready = self._prepare_forward_step()
        if ready is not None:
            return ready
        action = '短步' if short_press else '慢步'
        angle = self.player_angle()
        miss = self._angle_miss_result(angle)
        if miss is not None:
            return miss
        target_angle = self._target_angle(position, point)
        angle_diff = cal_utils.angle_delta(angle % 360, target_angle)
        distance = hypot(point.x - position[0], point.y - position[1])
        near = distance <= NEAR_STEP_TURN_RADIUS
        self._submit_turn(target_angle, cruise_only=near)
        if abs(angle_diff) > WALK_TURN_ANGLE and not near:
            # 大偏差：松键停车等转向线程转到位，不短按前进。
            self._release_forward()
            return self.round_wait(f'{action}停车等转向 {angle_diff:.0f}度')
        limited = self._fail_if_action_limit()
        if limited is not None:
            return limited
        duration = SMALL_STEP_PRESS if short_press else SLOW_STEP_PRESS
        if not self._step_forward(duration):
            return self.round_wait('等待前进短按可用', wait=0.02)
        self._record_input()
        wait = None if short_press else SLOW_STEP_WAIT
        return self.round_wait(f'{action}前进', wait=wait)

    @staticmethod
    def _target_angle(
        position: tuple[float, float], point: BagelRoutePoint,
    ) -> float:
        """当前位置指向目标点的角度。

        与朝向识别（analyze）同一套坐标系：屏幕上方为正、逆时针增加，
        所以纵向取负号；符号写反会让角色一直原地打转。
        """
        return degrees(atan2(-(point.y - position[1]), point.x - position[0])) % 360

    def _check_stuck(
        self, position: tuple[float, float], point: BagelRoutePoint, angle: float,
    ) -> OperationRoundResult | None:
        """按住前进却走不动时，往路径线那一侧侧移一小步。

        走不动一般不是被挡住，而是已经偏到路径线外，正顶着墙或箱子。
        这时继续判失败没意义。拿「上一个点 → 当前目标点」这条连线当路径线，
        朝线上的最近点挪一小步，让前进方向重新对上线。
        """
        if self.stuck_since is None:
            self.stuck_since = (position, time.monotonic())
            return None
        origin, started = self.stuck_since
        if hypot(position[0] - origin[0], position[1] - origin[1]) >= STUCK_DISTANCE:
            self.stuck_since = (position, time.monotonic())
            self.stuck_steps = 0
            return None
        if time.monotonic() - started < STUCK_SECONDS:
            return None
        if self.stuck_steps >= STUCK_STEP_LIMIT:
            self._release_forward()
            return self.round_recoverable_fail('持续前进但位置未变化，侧移多次仍无法脱离')
        direction = self._path_side(position, point, angle)
        self.stuck_steps += 1
        self.stuck_since = None
        if direction is None:
            # 没有上一个点，或已经站在线上，判断不出该往哪挪，不瞎动。
            return self.round_wait('前进受阻，等待重新判定路径线', wait=0.2)
        self.input_worker.side_step(direction, SIDE_STEP_SECONDS)
        self._record_input()
        return self.round_wait(
            f'前进受阻，往路径线{"右" if direction > 0 else "左"}侧移动一步',
            wait=SIDE_STEP_SECONDS + 0.1,
        )

    def _path_side(
        self, position: tuple[float, float], point: BagelRoutePoint, angle: float,
    ) -> int | None:
        """该往哪一侧挪：1 按 D（角色右手边），-1 按 A（角色左手边）。

        A/D 是相对角色朝向的左右，不是地图上的左右，所以要先把「指向路径线」
        的方向换算到角色局部坐标：角色朝向角 angle 下，右手方向是
        `(sin angle, cos angle)`（地图 y 轴向下），与它点乘为正就是往右挪。

        路径线取上一个点到当前目标点的连线；角色在线的哪一侧都不必先判，
        直接朝线上最近点走，偏多偏少都成立。
        """
        origin = self._previous_point()
        if origin is None:
            return None
        foot = _closest_on_segment(origin, point, position)
        to_line = (foot[0] - position[0], foot[1] - position[1])
        if hypot(to_line[0], to_line[1]) < 0.5:
            return None
        right_x, right_y = sin(radians(angle)), cos(radians(angle))
        return 1 if to_line[0] * right_x + to_line[1] * right_y >= 0 else -1

    def _previous_point(self) -> BagelRoutePoint | None:
        """上一个点；路线起点没有上一个点时返回 None。"""
        if not self.routes:
            return None
        route = self.routes[self.route_index]
        if self.cursor <= 0:
            return None
        return route.points[self.cursor - 1]

    def _check_timeout(self, point: BagelRoutePoint) -> OperationRoundResult | None:
        """单点超时检查。"""
        if self.point_started_at is None:
            self.point_started_at = time.monotonic()
            return None
        limit = POINT_TIMEOUT.get(point.kind, POINT_TIMEOUT['default'])
        if time.monotonic() - self.point_started_at >= limit:
            self._release_forward()
            return self.round_recoverable_fail(
                f'第 {self.cursor + 1} 点（{point.kind}）超时 {limit:.0f}s',
            )
        return None

    def _check_hud(self) -> OperationRoundResult | None:
        """局内 HUD 检查：暂停菜单直接失败。

        这里不能因为没识别到普通攻击按钮就松前进键。长距离行进时
        只要某一帧模板没命中，前进键就被松开，表现就是走两步停一下。
        只有确认打开了暂停菜单才停。
        """
        if self.round_by_find_area(
            self.last_screenshot, '战斗-菜单', '按钮-退出战斗',
        ).is_success:
            self._release_forward()
            return self.round_recoverable_fail('移动中打开了暂停菜单')
        return None

    def _fail_if_action_limit(self) -> OperationRoundResult | None:
        """单点输入次数上限。"""
        if self.steps < ACTION_LIMIT:
            return None
        self._release_forward()
        return self.round_recoverable_fail('单点输入达到上限')

    def _current_point(self) -> BagelRoutePoint | None:
        """当前路线游标处的点；还没确定路线时返回 None。"""
        if not self.routes:
            return None
        route = self.routes[self.route_index]
        if self.cursor >= len(route.points):
            return None
        return route.points[self.cursor]

    def _enter_point(self, route_index: int, point_index: int) -> None:
        """进入某个点：切换游标并清空单点状态。"""
        self.route_index = route_index
        self.cursor = point_index
        self.point_started_at = time.monotonic()
        self._reset_point_state()

    def _reset_point_state(self) -> None:
        """清空与单个点绑定的交互状态。

        转向比例不重置：它是整局共享的校准结果，换点后继续沿用。
        只清掉待学习样本，避免拿跨点的旧样本反推。
        """
        self.current_kind = None
        self.f_pressed = False
        self.mechanical_hold_until = None
        self.mechanical_retried = False
        self.target_wait_since = None
        self.electronic_small_steps = False
        self.small_step_since = None
        self.steps = 0
        self.stuck_since = None
        self.stuck_steps = 0
        self.elevator_phase = None
        self.elevator_since = None

    def _step_forward(self, duration: float) -> bool:
        """请求一次前进短按，返回输入线程是否接受。

        Args:
            duration: 这一次按住的时长（秒）。
        """
        return self.input_worker.step_forward(duration)

    def _record_input(self) -> None:
        """记录一次输入并拒绝复用旧截图。"""
        self.steps += 1
        self.last_input_frame = max(time.time(), self.last_screenshot_time)

    def _release_forward(self) -> None:
        """松开前进键与冲刺键，并清卡位计时与步进计时。"""
        self.stuck_since = None
        self._stop_sprint()
        self.input_worker.stop_forward()
        self.input_worker.stop_backward()

    def _read_survey_value(self) -> None:
        """关闭面板回到局内后读 HUD 调查收益；失败局用最后一次读数作为本局收益。"""
        try:
            value = parse_value(bagel_screen.read_area(
                self.ctx, self.last_screenshot, '贝果-局内', '调查收益',
            ))
        except Exception:
            log.error('读取调查收益失败，本次不计入统计', exc_info=True)
            return
        if value is None:
            return
        self.survey_value = value

    def _adopt_screenshot(self, op: BagelOperation) -> None:
        """子操作结束后同步其最后截图。"""
        if op.last_screenshot is not None:
            self.last_screenshot = op.last_screenshot
            self.last_screenshot_time = op.last_screenshot_time

    def handle_pause(self) -> None:
        """暂停时松键，并让转向线程立刻停手。

        暂停期间主线不再提交，靠提交新鲜度线程 1 秒后也会自己停；
        这里主动清一次，不等那 1 秒，避免暂停瞬间按旧目标转镜头。
        """
        self._release_forward()
        self.input_worker.submit_turn(None)
        super().handle_pause()

    def after_operation_done(self, result: OperationResult) -> None:
        """退出路径统一松键，含冲刺键，并停掉输入线程。"""
        self._stop_sprint()
        self.input_worker.shutdown()
        super().after_operation_done(result)
