"""贝果路线执行的输入线程：按键放到单独线程做，互不打断。

原来「按下并保持一段时间」是在主线里 time.sleep 阻塞的，
阻塞期间既不截图也不决策，走路就不跟手。搬到单独线程后主线投递即返回。

三条独立通道，各自有线程，互不打断、可并发：
- 前进（状态）：只记「该不该按着」，线程把真实键位对齐到意图，重复调用无副作用。
- 转向（独立判稳）：主线只提交目标方向，这里自己采样朝向、数连续 3 帧稳定、
  1 度防抖、偏离 5 度才转一次，转稳后自己算校准样本。转向是相对位移，
  不排队不叠加，上一笔没校准完不开下一笔。
- 即时动作（队列）：点按 F、长按 F、松开 F、闪避，按顺序执行。

三条通道互不占用，所以转向永远不会把前进顶掉（曾因此原地不动）。
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from typing import TYPE_CHECKING

import numpy as np

from one_dragon.base.geometry.point import Point
from one_dragon.utils import cal_utils, cv2_utils
from one_dragon.utils.log_utils import log
from zzz_od.game_data.map_locator.minimap_angle import analyze

if TYPE_CHECKING:
    from collections.abc import Callable

    from zzz_od.context.zzz_context import ZContext

TAP_INTERACT: str = 'tap_interact'
"""点按交互键（F），按满 duration 后松开。"""

TAP_CENTER: str = 'tap_center'
"""点一下屏幕中间，用于推进对话、让选项弹出。"""

HOLD_INTERACT: str = 'hold_interact'
"""按住交互键（F）不松，直到收到松开指令。"""

RELEASE_INTERACT: str = 'release_interact'
"""松开交互键。"""

DODGE: str = 'dodge'
"""点一下闪避，用于维持冲刺。"""

SIDE_STEP: str = 'side_step'
"""点一下侧移（A 或 D）；方向记在 angle 上，-1 向左、1 向右。"""

SLEEP_SLICE: float = 0.01
"""等待轮询的切片时长（秒）。"""

SCREEN_CENTER: Point = Point(960, 540)
"""画面中心，点它推进对话。按 1080p 基准。"""

TURN_STABLE_FRAMES: int = 3
"""连续这么多帧朝向不动，才认为画面稳定、可以开始下一次转向。"""

TURN_STABLE_JITTER: float = 1.0
"""防抖：相邻两帧朝向差在它以内算没动。静止实测抖动 0.2 度，取 1 度是识别精度。"""

TURN_SAMPLE_INTERVAL: float = 0.03
"""转向线程自己采截图的间隔（秒）。独立于主线循环，首转不再等主线攒 3 轮。"""

TURN_DEADBAND: float = 5.0
"""对准死区：与目标差在它以内不转。1 度内是识别精度，1~5 度是被打偏后的容忍带。"""

TURN_DEADBAND_FAST: float = 2.0
"""快速移动时的对准死区：巡航与进电梯按住走，偏一点就会走偏，压到 2 度。"""

TURN_TARGET_FRESH_SECONDS: float = 1.0
"""提交新鲜度：目标超过这么久没更新就视为过期，暂停转向。

主线只在移动分支提交；开箱、等提示、暂停时不提交，靠这个超时让线程
自己停手，不用每个分支都调一次暂停。正常移动时约 0.1 秒提交一次，
远小于这个值，不影响。"""

TURN_RATIO_MIN: float = 0.2
TURN_RATIO_MAX: float = 20.0
"""可信校准值范围；超出说明样本被别的动作污染，直接丢弃。"""

STOP_TURN_CAP: float = 180.0
"""停车转的单次上限（度）：偏差多大就一把转到位，最大 180 度（掉头）。"""

STOP_TURN_CAP_WARMUP: float = 45.0
"""比例未知时用的保守上限（度）：一次别甩太大。"""

TURN_CAP_TRUST_SAMPLES: int = 3
"""攒够这么多个样本才放宽到 STOP_TURN_CAP。"""

CRUISE_TURN_CAP: float = 15.0
"""边走边转的单次上限（度）：只做小幅修正，剩下的下一轮再补。"""

TURN_CRUISE_LIMIT: float = 10.0
"""偏差在它以内是边走边转，对应主线束角；超过它才停车转。"""

TURN_RATIO_PEAK_BIN_WIDTH: float = 0.05
"""实时校准分箱宽度：箱以 1.0 为中心（如 0.975~1.025），每样本只做一次槽计数加一与峰值比较。"""

TURN_RATIO_CLAMP_WARN_STREAK: int = 5
"""校准值连续这么多个样本贴着可信区间的边界，就提示可能需要重做灵敏度检测。"""

TURN_SCALE_SAMPLE_MIN_COMMAND: float = 8.0
"""下发角小于它就不参与校准：这个幅度以下量化误差与上一把转向的余摆占比过大。"""

TURN_SETTLE_GRACE: float = 0.4
"""下发转向后这么久内画面没变化不计数：实测转稳中位 0.24 秒、最大 0.31 秒。"""

TURN_POST_TURN_QUIET: float = 0.3
"""下发转向后这么久内不截图：宽限内的样本本来就直接丢掉，不采省截图开销。
转稳最大 0.31 秒，0.3 停采后补 3 帧判稳，首个样本约 0.39 秒落地，不丢精度。"""

TURN_STILL_TIMEOUT: float = 1.0
"""宽限过后，画面持续没变化超过这么久就放行下一笔，不重置校准。

下发后 0.4 + 1.0 秒还没动静，继续等只会饿死后续转向，所以消费掉
这一笔让下一笔能转。校准值本身任何时候都不重置，只靠正常样本平滑收敛。"""

TURN_RATIO_MIN_ANGLE: float = 3.0
"""实际转角小于它就不采样：角度太小，量化误差占比过大。"""

TURN_RATIO_MIN_DELTA: float = 0.5
"""实际转角小于它视为画面还没跟上，样本留到下一轮再算。"""


class _Command:
    """一条待执行的按键指令。"""

    def __init__(
        self, kind: str, duration: float | None = None, angle: float = 0.0,
    ) -> None:
        """
        Args:
            kind: 指令类型，取本模块的常量。
            duration: 短按时长（秒），其它类型忽略。
            angle: 转向角度（度），仅转向使用。
        """
        self.kind: str = kind
        self.duration: float | None = duration
        self.angle: float = angle


class _InstantChannel:
    """即时动作通道：独立线程按顺序执行队列，互不打断。

    用于点按 F、长按 F、松开 F、闪避。这些动作很快，排队不会堆积，
    顺序执行更安全（比如先长按再松开）。
    """

    def __init__(self, name: str, handler: Callable[[_Command], None]) -> None:
        """
        Args:
            name: 线程名，便于排查。
            handler: 单条指令的执行函数。
        """
        self._handler: Callable[[_Command], None] = handler
        self._queue: deque[_Command] = deque()
        self._lock: threading.Lock = threading.Lock()
        self._wake: threading.Event = threading.Event()
        self._stopping: bool = False
        self._running: bool = False
        """正在执行一条指令；执行完才置回 False。"""
        self._thread: threading.Thread = threading.Thread(
            target=self._loop, name=name, daemon=True,
        )
        self._thread.start()

    def put(self, command: _Command) -> None:
        """入队一条指令。"""
        with self._lock:
            if self._stopping:
                return
            self._queue.append(command)
        self._wake.set()

    def busy(self) -> bool:
        """是否还有指令在排队或执行中。"""
        with self._lock:
            return self._running or bool(self._queue)

    def stop(self) -> None:
        """停止线程，丢掉未执行的指令。"""
        with self._lock:
            self._stopping = True
            self._queue.clear()
        self._wake.set()
        self._thread.join(timeout=1.0)

    def _loop(self) -> None:
        """依次执行队列里的指令。"""
        while True:
            self._wake.wait(SLEEP_SLICE)
            self._wake.clear()
            while True:
                with self._lock:
                    if self._stopping:
                        return
                    if not self._queue:
                        break
                    command = self._queue.popleft()
                    self._running = True
                try:
                    self._handler(command)
                except Exception:
                    log.error('贝果即时动作执行失败', exc_info=True)
                finally:
                    with self._lock:
                        self._running = False


class _TurnWorker:
    """转向独立线程：主线只给目标方向，这里自己采样、自己判稳、自己转、自己校准。

    主线只提交目标角，不提交朝向；这里按固定间隔自己截小地图读朝向，
    不等主线循环。连续 3 帧朝向差都在 1 度内才算稳，稳了且与目标差
    超过 5 度才转一次。转完清空历史，等新的 3 帧稳了再算校准样本，
    样本干净了才更新比例。被敌人打转方向时画面一直不稳，这里就一直
    不动手，等稳了再一次性转回去。
    """

    def __init__(
        self, handler: Callable[[float], None],
        sampler: Callable[[], float | None],
    ) -> None:
        """
        Args:
            handler: 执行一次转向的函数，参数是换算后的实际下发角。
            sampler: 采一帧当前镜头朝向；读不到返回 None。
        """
        self._handler: Callable[[float], None] = handler
        self._sampler: Callable[[], float | None] = sampler
        self._target: float | None = None
        """主线给的最新目标方向；None 表示暂停转向。"""
        self._target_at: float = 0.0
        """最新目标的提交时刻；超过新鲜度没更新就当过期。"""
        self._target_cruise_only: bool = False
        """主线近距离只做边走边转时为 True，单次转向 amplitude 受 CRUISE_TURN_CAP 限制。"""
        self._target_deadband: float = TURN_DEADBAND
        """本次目标用的对准死区；快速移动时主线会传 2 度，默认 5 度。"""
        self._history: deque[float] = deque(maxlen=TURN_STABLE_FRAMES)
        """最近几帧的当前朝向，读不到时清空。"""
        self._anchor: float | None = None
        """上次转向前的稳定朝向，用来和转稳后的朝向求实际转角。"""
        self._pending: float | None = None
        """上次真正下发的转角，等转稳后用来算校准样本。"""
        self._pending_at: float = 0.0
        """上次下发的时刻；宽限内画面没变化不计数。"""
        self._still_since: float | None = None
        """宽限过后首次看到画面没动的时刻；超时只放行下一笔，不碰校准。"""
        self.turn_ratio: float = 1.0
        """转向校准值：名义转角乘它就是实际转角，1.0 表示还没校准过。任何时候都不重置。"""
        self.turn_samples: int = 0
        """已累积的校准样本数，用于日志观察。"""
        self._peak_bins: dict[int, int] = {}
        """实时峰值槽计数：槽号到样本数，每样本只加一并与最高比较。"""
        self._peak_key: int | None = None
        """当前最高的槽号；不如它就保持不变。"""
        self._peak_count: int = 0
        """最高槽的样本数。"""
        self._clamp_streak: int = 0
        """校准值连续几次贴到夹取边界的计数，用于提示重做灵敏度检测。"""
        self._scale_samples: list[float] = []
        """本局按有效样本算出的补偿比例（1/校准值），局末取中位数写回现有灵敏度字段。"""
        self._busy: bool = False
        """正在执行鼠标转向的极短瞬间；平时都是 False，主线不用等它。"""
        self._lock: threading.Lock = threading.Lock()
        self._wake: threading.Event = threading.Event()
        self._stopping: bool = False
        self._thread: threading.Thread = threading.Thread(
            target=self._loop, name='bagel-turn', daemon=True,
        )
        self._thread.start()

    def submit(self, target: float | None, cruise_only: bool = False, deadband: float = TURN_DEADBAND) -> None:
        """提交最新目标方向；只存不定夺，转不转由线程自己采样再看。

        只写内存，不记输入、不碰截图，调完立刻返回，不会限速主循环。
        朝向由线程自己按固定间隔采样，暂停时目标置空，历史不清，
        恢复提交后不用重数 3 帧。

        Args:
            target: 目标方向（度），None 表示暂停转向。
            cruise_only: 近距离只做边走边转，单次幅度受 CRUISE_TURN_CAP 限制。
            deadband: 本次目标的对准死区；快速移动传 2 度，其余用默认 5 度。
        """
        with self._lock:
            if self._stopping:
                return
            if target is None:
                self._target = None
            else:
                self._target = target % 360
                self._target_at = time.monotonic()
                self._target_cruise_only = cruise_only
                self._target_deadband = deadband
        self._wake.set()

    def busy(self) -> bool:
        """是否正在执行鼠标转向；只有下发的那一瞬间是 True。"""
        with self._lock:
            return self._busy

    def stop(self) -> None:
        """停止线程。"""
        with self._lock:
            self._stopping = True
            self._pending = None
            self._anchor = None
            self._history.clear()
            self._target = None
            self._still_since = None
            self._peak_bins.clear()
            self._peak_key = None
            self._peak_count = 0
            self._clamp_streak = 0
        self._wake.set()
        self._thread.join(timeout=1.0)

    @staticmethod
    def _stable(history: list[float]) -> bool:
        """连续几帧的朝向差是否都在防抖内；处理 0/360 跨界。"""
        if len(history) < TURN_STABLE_FRAMES:
            return False
        recent = history[-TURN_STABLE_FRAMES:]
        return all(
            abs(cal_utils.angle_delta(a, b)) <= TURN_STABLE_JITTER
            for a, b in zip(recent, recent[1:], strict=False)
        )

    def _loop(self) -> None:
        """按固定间隔自己采样：稳了、有偏差、上一笔已校准，才转。"""
        while True:
            self._wake.wait(TURN_SAMPLE_INTERVAL)
            self._wake.clear()
            with self._lock:
                if self._stopping:
                    return
                in_quiet = (
                    self._pending is not None
                    and time.monotonic() - self._pending_at < TURN_POST_TURN_QUIET
                )
            if in_quiet:
                # 下发后静默期内不截图：这段的样本本来就丢掉，采了也是浪费。
                continue
            try:
                current = self._sampler()
            except Exception:
                log.error('贝果转向采样朝向失败', exc_info=True)
                current = None
            with self._lock:
                if self._stopping:
                    return
                if current is None:
                    self._history.clear()
                    # 读不到时不计时：重现后重新计时，避免缺数据也算静止。
                    self._still_since = None
                else:
                    self._history.append(current % 360)
                history = list(self._history)
                pending = self._pending
                anchor = self._anchor
            if not history:
                continue
            # 目标过期先处理：即使上一笔卡住没学完，暂停/开箱后也不留旧目标。
            # 否则学样本返回等待会跳过后边的过期分支，旧目标一直留着。
            with self._lock:
                if (
                    self._target is not None
                    and time.monotonic() - self._target_at > TURN_TARGET_FRESH_SECONDS
                ):
                    self._target = None
            if not self._stable(history):
                # 画面在动：不是静止，计时清掉重来。
                with self._lock:
                    self._still_since = None
                continue
            stable_angle = history[-1]
            if pending is not None and anchor is not None:
                # 上一笔转完又有 3 帧稳了，拿稳态差算样本，不拿转一半的中间帧。
                if not self._learn(anchor, pending, stable_angle):
                    continue
            with self._lock:
                if self._stopping:
                    return
                if self._pending is not None:
                    continue
                if self._target is None:
                    continue
                if time.monotonic() - self._target_at > TURN_TARGET_FRESH_SECONDS:
                    # 主线超过 1 秒没提交（开箱、等提示、暂停），目标过期不清历史：
                    # 画面朝向帧还接着用，恢复提交后不用重数 3 帧。
                    self._target = None
                    continue
                deviation = cal_utils.angle_delta(stable_angle, self._target)
                deadband = self._target_deadband
                if abs(deviation) <= deadband:
                    continue
                cruise_only = self._target_cruise_only
                magnitude = abs(deviation)
                if cruise_only or magnitude <= TURN_CRUISE_LIMIT:
                    cap = CRUISE_TURN_CAP
                elif self.turn_samples >= TURN_CAP_TRUST_SAMPLES:
                    cap = STOP_TURN_CAP
                else:
                    cap = STOP_TURN_CAP_WARMUP
                nominal = float(max(int(min(magnitude, cap)), 1))
                signed = nominal if deviation > 0 else -nominal
                ratio = self.turn_ratio
                actual = signed / ratio if ratio else signed
                # 上限按真正拖拽的角度算：比例小于 1 时下发角会被放大，只夹名义角等于没夹。
                actual = max(-cap, min(actual, cap))
                self._pending = actual
                self._pending_at = time.monotonic()
                self._anchor = stable_angle
                self._history.clear()
                self._busy = True
            try:
                self._handler(actual)
            except Exception:
                log.error('贝果转向执行失败', exc_info=True)
            finally:
                with self._lock:
                    self._busy = False

    def _learn(self, anchor: float, pending: float, stable: float) -> bool:
        """用转稳后的角度反推上一笔的真实比例；画面还没跟上时返回 False 等下一轮。

        Args:
            anchor: 转向前的稳定朝向。
            pending: 上次真正下发的转角。
            stable: 转稳后的当前朝向。

        Returns:
            样本已消费（不管有效无效）时返回 True，还要继续等时返回 False。
        """
        delta = cal_utils.angle_delta(anchor, stable)
        if abs(delta) < TURN_RATIO_MIN_DELTA:
            now = time.monotonic()
            if now - self._pending_at < TURN_SETTLE_GRACE:
                # 画面还在路上，等，不计时。
                return False
            with self._lock:
                if self._still_since is None:
                    # 宽限过后第一次看到没动，开始计时。
                    self._still_since = now
                    return False
                if now - self._still_since < TURN_STILL_TIMEOUT:
                    return False
                # 超时只放行下一笔，不碰校准值：任何时候都不重置。
                self._pending = None
                self._anchor = None
                self._still_since = None
            log.info(
                '贝果转向校准画面 %.1fs 没变化，放行下一笔（校准保持 %.3f）',
                TURN_SETTLE_GRACE + TURN_STILL_TIMEOUT, self.turn_ratio,
            )
            return True
        with self._lock:
            self._pending = None
            self._anchor = None
            self._still_since = None
        if abs(delta) < TURN_RATIO_MIN_ANGLE:
            # 小样本直接丢弃，不计数、不重置。
            return True
        if delta * pending <= 0:
            return True
        if abs(pending) < TURN_SCALE_SAMPLE_MIN_COMMAND:
            # 小幅度微调不参与校准：余摆与量化误差会把倍数抬到 2~15 倍。
            return True
        sample = abs(delta) / abs(pending)
        with self._lock:
            if not (TURN_RATIO_MIN <= sample <= TURN_RATIO_MAX):
                log.info(
                    '贝果转向校准样本异常，忽略：%.2f（名义 %.1f 实际 %.1f）',
                    sample, pending, delta,
                )
                return True
            key = math.floor((sample - 1.0) / TURN_RATIO_PEAK_BIN_WIDTH + 0.5 + 1e-9)
            slot_count = self._peak_bins.get(key, 0) + 1
            self._peak_bins[key] = slot_count
            if self._peak_key is None or slot_count > self._peak_count:
                self._peak_key = key
                self._peak_count = slot_count
                self.turn_ratio = 1.0 + key * TURN_RATIO_PEAK_BIN_WIDTH
            self.turn_samples += 1
            self._scale_samples.append(abs(pending) / abs(delta) if delta else 1.0)
            ratio, total = self.turn_ratio, self.turn_samples
        log.info(
            '贝果转向校准 %.3f（样本 %.2f，峰值槽 %s 个，名义 %.1f 实际 %.1f，共 %s 次）',
            ratio, sample, self._peak_count, pending, delta, total,
        )
        if TURN_RATIO_MIN * 1.2 <= ratio <= TURN_RATIO_MAX / 1.2:
            with self._lock:
                self._clamp_streak = 0
        else:
            with self._lock:
                self._clamp_streak += 1
                streak = self._clamp_streak
            if streak == TURN_RATIO_CLAMP_WARN_STREAK:
                log.warning(
                    '转向校准值 %.2f 已贴近可补偿边界（%.2f~%.2f），偏差可能超出范围，'
                    '建议跑一次鼠标灵敏度检测再继续',
                    ratio, TURN_RATIO_MIN, TURN_RATIO_MAX,
                )
        return True


class BagelInputWorker:
    """路线执行的全部按键都经由这里下发，主线只投递不等待。"""

    def __init__(self, ctx: ZContext) -> None:
        """
        Args:
            ctx: 运行上下文，提供控制器。
        """
        self.ctx: ZContext = ctx
        self._forward_want: bool = False
        """主线意图：是否该一直按住前进。"""
        self._forward_down: bool = False
        """实际状态：W 键现在是否真的按着。两者不一致时才发键。"""
        self._forward_step_duration: float | None = None
        """当前短按的时长；从请求被接收到实际松键期间保留。"""
        self._forward_step_until: float | None = None
        """从实际按下开始计算的短按截止时刻，使用单调时钟。"""
        self._forward_released_at: float = 0.0
        """最近一次实际松键的系统时间，用于判断截图是否晚于动作。"""
        self._forward_lock: threading.Lock = threading.Lock()
        self._backward_want: bool = False
        """主线意图：是否该一直按住后退（S）。电梯进出要用。"""
        self._backward_down: bool = False
        """实际状态：S 键现在是否真的按着。"""
        self._backward_lock: threading.Lock = threading.Lock()
        self._stopping: bool = False

        self._turn_worker: _TurnWorker = _TurnWorker(self._run_turn, self._sample_angle)
        self._instant_channel: _InstantChannel = _InstantChannel(
            'bagel-instant', self._run_instant,
        )
        self._forward_thread: threading.Thread = threading.Thread(
            target=self._forward_loop, name='bagel-forward', daemon=True,
        )
        self._forward_thread.start()
        self._backward_thread: threading.Thread = threading.Thread(
            target=self._backward_loop, name='bagel-backward', daemon=True,
        )
        self._backward_thread.start()

    # ---------- 主线投递 ----------

    def hold_forward(self) -> bool:
        """持续前进并取消旧短按；返回是否改变了前进意图。"""
        with self._forward_lock:
            if self._stopping:
                return False
            changed = not self._forward_want or self._forward_step_duration is not None
            self._forward_step_duration = None
            self._forward_step_until = None
            self._forward_want = True
            return changed

    def stop_forward(self) -> None:
        """请求松开前进，并取消尚未结束的短按。"""
        with self._forward_lock:
            self._forward_want = False
            self._forward_step_duration = None
            self._forward_step_until = None

    def step_forward(self, duration: float) -> bool:
        """请求一次短按；已有短按时拒绝新请求，不排队或延长。

        前进线程从实际按下开始计时，到期后松键。切换到持续前进或停止
        会取消该截止时刻，不创建可能影响后续输入的独立定时器。

        Args:
            duration: 按住时长（秒），必须大于零。

        Returns:
            是否接受本次请求。
        """
        if duration <= 0:
            raise ValueError('前进短按时长必须大于零')
        with self._forward_lock:
            if self._stopping or self._forward_step_duration is not None:
                return False
            self._forward_step_duration = duration
            self._forward_step_until = None
            self._forward_want = True
            return True

    def forward_step_active(self) -> bool:
        """是否还有尚未完成的前进短按，包含等待实际按下的请求。"""
        with self._forward_lock:
            return self._forward_step_duration is not None

    @property
    def forward_released_at(self) -> float | None:
        """前进已停止时返回最近松键时间；仍持键或有待执行请求时返回 None。"""
        with self._forward_lock:
            if self._forward_want or self._forward_down:
                return None
            return self._forward_released_at

    def hold_backward(self) -> None:
        """希望一直按住后退（S）；线程会把它对齐到真实按键状态。"""
        with self._backward_lock:
            self._backward_want = True

    def stop_backward(self) -> None:
        """松开后退。"""
        with self._backward_lock:
            self._backward_want = False

    def submit_turn(self, target: float | None, cruise_only: bool = False, deadband: float = TURN_DEADBAND) -> None:
        """提交最新目标方向；只存不定夺，朝向由转向线程自己采样。

        只写内存，不记输入，调完立刻返回，不会限速主循环。

        Args:
            target: 目标方向（度），None 表示暂停转向。
            cruise_only: 近距离只做边走边转，单次幅度受 CRUISE_TURN_CAP 限制。
            deadband: 本次目标的对准死区；快速移动传 2 度，其余用默认 5 度。
        """
        self._turn_worker.submit(target, cruise_only=cruise_only, deadband=deadband)

    @property
    def turn_ratio(self) -> float:
        """转向校准值，供主线日志观察。"""
        return self._turn_worker.turn_ratio

    @property
    def turn_samples(self) -> int:
        """已累积的校准样本数，供局末持久化判断。"""
        return self._turn_worker.turn_samples

    @property
    def turn_scale_samples(self) -> list[float]:
        """本局补偿比例原始样本，供局末峰值平均写回现有灵敏度字段。"""
        return list(self._turn_worker._scale_samples)

    def idle(self) -> bool:
        """即时动作是否空闲；前进短按状态需单独检查。

        转向不再阻塞主线：它只在稳了 3 帧后才转，稳不稳由它自己数，
        主线不等它。截到的画面是不是转稳后的，由转向线程的稳定判断保证。
        """
        return not self._instant_channel.busy()

    def tap_interact(self, duration: float = 0.2) -> None:
        """点按交互键。

        Args:
            duration: 按住时长（秒）。
        """
        self._instant_channel.put(_Command(TAP_INTERACT, duration=duration))

    def tap_center(self, duration: float = 0.08) -> None:
        """点一下屏幕中间，推进对话。

        电梯、门这类要按对话推进才会弹选项的地方，按 F 没用，必须点屏幕。

        Args:
            duration: 按住时长（秒）。
        """
        self._instant_channel.put(_Command(TAP_CENTER, duration=duration))

    def hold_interact(self) -> None:
        """按住交互键不松，用于机械保险箱长按。"""
        self._instant_channel.put(_Command(HOLD_INTERACT))

    def release_interact(self) -> None:
        """松开交互键。"""
        self._instant_channel.put(_Command(RELEASE_INTERACT))

    def dodge(self) -> None:
        """点一下闪避，用于维持冲刺。"""
        self._instant_channel.put(_Command(DODGE))

    def side_step(self, direction: int, duration: float = 0.2) -> None:
        """点一下侧移，用来从卡住的位置挪回路径线。

        Args:
            direction: -1 向左（A），1 向右（D）。
            duration: 按住时长（秒）。
        """
        self._instant_channel.put(
            _Command(SIDE_STEP, duration=duration, angle=1.0 if direction > 0 else -1.0),
        )

    def shutdown(self) -> None:
        """停止全部通道并松开前进；退出路径必须调用。"""
        self._stopping = True
        self.stop_forward()
        self._forward_thread.join(timeout=1.0)
        self._backward_thread.join(timeout=1.0)
        self._turn_worker.stop()
        self._instant_channel.stop()
        try:
            self.ctx.controller.move_w(release=True)
            self.ctx.controller.move_s(release=True)
            self.ctx.controller.interact(release=True)
        except Exception:
            log.error('贝果输入线程退出时松开按键失败', exc_info=True)

    # ---------- 前进通道 ----------

    def _forward_loop(self) -> None:
        """对齐前进键，并在实际按下后计时完成短按。

        状态检查、发键和时间记录共用一把锁。持续前进改为短按时，先
        实际松键再重新按下；停止或新移动方式会取消旧截止时刻。
        """
        while not self._stopping:
            with self._forward_lock:
                try:
                    if (
                        self._forward_step_until is not None
                        and time.monotonic() >= self._forward_step_until
                    ):
                        self._forward_want = False
                        self._forward_step_until = None
                    starting_step = (
                        self._forward_step_duration is not None
                        and self._forward_step_until is None
                        and self._forward_want
                    )
                    if starting_step and self._forward_down:
                        self.ctx.controller.move_w(release=True)
                        self._forward_down = False
                        self._forward_released_at = time.time()
                    want = self._forward_want
                    if want != self._forward_down:
                        if want:
                            self.ctx.controller.move_w(press=True)
                        else:
                            self.ctx.controller.move_w(release=True)
                            self._forward_released_at = time.time()
                        self._forward_down = want
                    if (
                        starting_step and self._forward_down
                        and self._forward_step_duration is not None
                    ):
                        self._forward_step_until = time.monotonic() + self._forward_step_duration
                    if not self._forward_want and not self._forward_down:
                        self._forward_step_duration = None
                except Exception:
                    log.error('贝果输入线程切换前进键失败', exc_info=True)
            time.sleep(SLEEP_SLICE)

    def _backward_loop(self) -> None:
        """每周期把后退键（S）对齐到意图状态；与前进通道同一套写法。

        电梯进门后可能要走出来，方向不一定是前进，所以需要单独一路按键。
        """
        while not self._stopping:
            with self._backward_lock:
                want = self._backward_want
                if want != self._backward_down:
                    try:
                        if want:
                            self.ctx.controller.move_s(press=True)
                        else:
                            self.ctx.controller.move_s(release=True)
                        self._backward_down = want
                    except Exception:
                        log.error('贝果输入线程切换后退键失败', exc_info=True)
            time.sleep(SLEEP_SLICE)

    # ---------- 转向通道 ----------

    def _sample_angle(self) -> float | None:
        """转向线程自己采一帧当前镜头朝向；读不到返回 None。

        用独立截图，不干扰主线截图策略；裁剪与识别与主线同区域同函数。
        异常只返回 None，由调用方清空历史，不抛出去杀线程。
        """
        try:
            screen = self.ctx.controller.get_screenshot(independent=True)
        except Exception:
            return None
        if screen is None:
            return None
        try:
            area = self.ctx.screen_loader.get_area('贝果-局内', '定位小地图')
        except Exception:
            return None
        if area is None:
            return None
        try:
            crop = cv2_utils.crop_image_only(screen, area.pc_rect)
        except Exception:
            return None
        if crop is None or crop.size == 0:
            return None
        if crop.ndim == 2:
            crop = np.stack([crop] * 3, axis=-1)
        try:
            _marker_vertices, _marker_edges, sector, _radius, _center = analyze(crop)
        except Exception:
            return None
        return sector

    def _run_turn(self, angle: float) -> None:
        """执行一次转向。

        Args:
            angle: 转向角度（度）。
        """
        self.ctx.controller.turn_by_angle_diff(angle)

    # ---------- 即时通道 ----------

    def _ensure_forward_down(self) -> None:
        """要走就先把前进键真的按下去，再让即时动作发出去。

        前进键是由 _forward_loop 每 10ms 对齐一次意图的，hold_forward()
        返回时键还没按下。此时立刻点闪避，游戏会先执行静止闪避（后跳或
        侧翻），再按前进就表现为「先退一下再走」，看起来像在按 S。
        所以发闪避这类动作之前，先把键位补齐。

        这里直接改 _forward_down，让账本和真实键位一致；否则 _forward_loop
        会以为已经按着，再也不补这一下。
        """
        with self._forward_lock:
            if not self._forward_want or self._forward_down:
                return
            try:
                self.ctx.controller.move_w(press=True)
                self._forward_down = True
                if self._forward_step_duration is not None:
                    self._forward_step_until = time.monotonic() + self._forward_step_duration
            except Exception:
                log.error('贝果冲刺前补按前进键失败', exc_info=True)

    def _run_instant(self, command: _Command) -> None:
        """执行一条即时动作。

        Args:
            command: 要执行的指令。
        """
        controller = self.ctx.controller
        if command.kind == TAP_INTERACT:
            controller.interact(press=True)
            time.sleep(command.duration or 0.0)
            controller.interact(release=True)
            return
        if command.kind == TAP_CENTER:
            # 电梯、门的选项靠点击对话推进才弹出，按 F 没用。
            controller.click(SCREEN_CENTER, press_time=command.duration or 0.08)
            return
        if command.kind == HOLD_INTERACT:
            controller.interact(press=True)
            return
        if command.kind == RELEASE_INTERACT:
            controller.interact(release=True)
            return
        if command.kind == DODGE:
            # 冲刺是「按住前进再连点闪避」，顺序反了会变成静止闪避。
            self._ensure_forward_down()
            controller.dodge()
            return
        if command.kind == SIDE_STEP:
            # 侧移方向由 angle 给出：-1 向左（A），1 向右（D）。
            # 前进键保持按住，侧移变成斜向，能顺着墙滑出卡位。
            key = controller.move_a if command.angle < 0 else controller.move_d
            key(press=True)
            time.sleep(command.duration or 0.0)
            key(release=True)
