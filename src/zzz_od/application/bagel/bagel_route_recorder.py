"""贝果路线打点录制：按数字键打不同类型的点，按退格删掉上一个点。

打点只记坐标与所在分层，不记动作。走到点上该做什么，等回放到那个点再识别交互物决定，
所以旧机制里「先 interact 再 unlock 再 store」这套写死的顺序不再存在。

按键沿用插件那套：
- 1 途径点、2 电子保险箱、3 机械保险箱、4 普通箱子、5 门、6 电梯，按下即在当前位置打一个点。
- 退格删掉上一个点。

录制前必须选定出生点：首个点只接受该出生点识别半径内的途径点。
停止后保存为绑定该出生点的自定义路线，路线数据定义与写盘见
``bagel_route_model`` 与 ``bagel_route_store``。
"""

from __future__ import annotations

import ctypes
import time
from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING, Any

import numpy as np
from pynput import keyboard

from one_dragon.utils import cv2_utils
from one_dragon.utils.log_utils import log
from zzz_od.application.bagel.bagel_route_model import (
    BEACON,
    KIND_LABELS,
    POINT_KINDS,
    BagelRoute,
    BagelRoutePoint,
    BagelSpawnPoint,
    now_iso,
)
from zzz_od.application.bagel.bagel_route_store import (
    BagelRouteConfigError,
    BagelRouteStore,
)
from zzz_od.game_data.map_locator.map_locator import MultiMapLocator, load_map_locators
from zzz_od.game_data.map_locator.minimap_angle import analyze

if TYPE_CHECKING:
    from collections.abc import Callable

    from cv2.typing import MatLike

    from one_dragon.base.geometry.rectangle import Rect
    from zzz_od.context.zzz_context import ZContext

MINIMAP_AREA = ('贝果-局内', '定位小地图')
"""小地图裁剪区域，与导航共用同一份建档。"""

FOREGROUND_CHECK_INTERVAL = 0.2
"""检查游戏是否仍在前台的间隔（秒）。"""

SPEED_WINDOW_SECONDS = 1.0
"""单帧最大偏移的统计窗口（秒）。"""

SHAKE_TOLERANCE = 1
"""与上一帧坐标差在这个像素内视为原地抖动，沿用上一帧坐标。"""

FOREGROUND_WAIT_SECONDS = 3.0
"""切到游戏前台的最长等待秒数。"""

UNDO_KEY = 'backspace'
"""删除上一个点的按键。"""


def is_foreground(hwnd: int) -> bool:
    """判断窗口是否为当前前台窗口。

    Args:
        hwnd: 窗口句柄。

    Returns:
        前台时为 True。
    """
    return int(ctypes.windll.user32.GetForegroundWindow()) == int(hwnd)


class BagelPointRecorder:
    """打点录制器；调用方在后台线程里跑 ``run``，用回调拿状态与点。

    逐帧定位持续运行，只有按下数字键才打点，退格删掉上一个点。
    """

    def __init__(
        self,
        ctx: ZContext,
        name: str,
        spawn: BagelSpawnPoint,
        activate: bool = False,
        on_point: Callable[[BagelRoutePoint], None] | None = None,
        on_undo: Callable[[], None] | None = None,
        on_status: Callable[[str], None] | None = None,
        on_layer: Callable[[str, Path], None] | None = None,
        on_position: Callable[[tuple[float, float] | None], None] | None = None,
        on_angles: Callable[[float | None, float | None], None] | None = None,
        on_stats: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """
        Args:
            ctx: 已初始化的上下文。
            name: 保存时使用的路线显示名称。
            spawn: 路线绑定的出生点，首个点必须在它的识别半径内。
            activate: 保存后是否开启这条路线。
            on_point: 每打下一个点回调一次。
            on_undo: 每删掉一个点回调一次。
            on_status: 阶段变化回调。
            on_layer: 命中层变化时回调，参数为分层名与底图路径。
            on_position: 每帧回调层内坐标，定位失败时为 None。
            on_angles: 每帧回调（镜头朝向, 角色朝向），识别不出时为 None。
            on_stats: 每帧回调定位统计，字段见 ``_build_stats``。
        """
        self.ctx: ZContext = ctx
        self.name: str = name
        self.spawn: BagelSpawnPoint = spawn
        self.activate: bool = activate
        self.on_point: Callable[[BagelRoutePoint], None] = on_point or (lambda _p: None)
        self.on_undo: Callable[[], None] = on_undo or (lambda: None)
        self.on_status: Callable[[str], None] = on_status or (lambda _t: None)
        self.on_layer: Callable[[str, Path], None] = on_layer or (lambda _n, _p: None)
        self.on_position: Callable[[tuple[float, float] | None], None] = (
            on_position or (lambda _c: None)
        )
        self.on_angles: Callable[[float | None, float | None], None] = (
            on_angles or (lambda _s, _m: None)
        )
        self.on_stats: Callable[[dict[str, Any]], None] = on_stats or (lambda _s: None)
        self.stop_requested: Event = Event()
        self.route: BagelRoute = self._new_route()
        self.saved_route: BagelRoute | None = None
        self.failure: str | None = None
        self.stop_reason: str = ''

        self._pending: list[str] = []
        self._listener: keyboard.Listener | None = None
        self._locator: MultiMapLocator | None = None
        self._layer_paths: dict[str, Path] = {}
        self._shown_layer: str | None = None
        self._shown_center: tuple[int, int] | None = None
        self._track: list[tuple[float, tuple[int, int]]] = []
        self._frame_count: int = 0
        self._fps: float = 0.0
        self._fps_start: float = 0.0

    def request_stop(self) -> None:
        """请求停止，收尾由 ``run`` 自己完成。"""
        self.stop_requested.set()

    def run(self) -> None:
        """持续定位，按数字键打点、按退格删掉上一个点。"""
        controller = self.ctx.controller
        if controller is None or not controller.init_game_win():
            self.failure = '游戏窗口未就绪，请先启动游戏'
            return
        game_win = controller.game_win
        hwnd = game_win.get_hwnd()
        if hwnd is None or not controller.is_game_window_ready:
            self.failure = '未找到游戏窗口，请先启动游戏'
            return
        area = self.ctx.screen_loader.get_area(*MINIMAP_AREA)
        if area is None:
            self.failure = f'缺少画面区域：{MINIMAP_AREA[0]}/{MINIMAP_AREA[1]}'
            return

        self.route = self._new_route()
        try:
            self.on_status('正在载入底图')
            locators = load_map_locators()
            self._locator = MultiMapLocator(locators)
            self._layer_paths = {locator.name: locator.image_path for locator in locators}
            self.on_status('准备切到游戏')
            controller.active_window()
            if not self._wait_for_foreground(hwnd):
                self.failure = '游戏窗口未切到前台，录制未开始'
                return
            self._start_key_listener()
            self.on_status(f'录制中，先在{self.spawn.name}按 1 打首个途径点')
            self.stop_reason = self._sample_loop(hwnd, area.pc_rect)
        except Exception as error:
            log.error('贝果路线打点异常', exc_info=True)
            self.failure = f'录制异常：{error}'
            return
        finally:
            self._stop_key_listener()

        if not self.route.points:
            self.failure = '没有打下任何点，未生成文件'
            return
        try:
            self.saved_route = BagelRouteStore().create_custom_route(
                self.name, self.spawn.spawn_id, points=list(self.route.points),
                activate=self.activate, started_at=self.route.started_at,
            )
        except (BagelRouteConfigError, ValueError) as error:
            log.error('贝果路线打点保存失败', exc_info=True)
            self.failure = f'保存失败：{error}'
            return
        self.on_status(self.stop_reason)

    def _new_route(self) -> BagelRoute:
        """录制中的内存路线；标识在保存时由存储模块生成。"""
        return BagelRoute(
            route_id='', name=self.name, spawn_id=self.spawn.spawn_id, started_at=now_iso(),
        )

    def _first_point_problem(self, point: BagelRoutePoint) -> str | None:
        """首个点的限制：必须是出生点识别半径内、同一分层的途径点。"""
        if point.kind != BEACON:
            return f'首个点必须是途径点（按 1），当前是{KIND_LABELS.get(point.kind, point.kind)}'
        if point.layer != self.spawn.layer:
            return f'首个点不在{self.spawn.name}所在分层'
        distance = self.spawn.distance_to(point.x, point.y)
        if distance > self.spawn.radius:
            return f'首个点距{self.spawn.name} {distance:.0f}px，需在 {self.spawn.radius:.0f}px 内'
        return None

    def _sample_loop(self, hwnd: int, rect: Rect) -> str:
        """定位循环，只在手动停止时结束；切出游戏时暂停定位但不停止录制。

        Args:
            hwnd: 游戏窗口句柄。
            rect: 小地图区域。

        Returns:
            停止原因文字。
        """
        controller = self.ctx.controller
        last_foreground_check = 0.0
        foreground = True
        while not self.stop_requested.is_set():
            now = time.monotonic()
            if now - last_foreground_check >= FOREGROUND_CHECK_INTERVAL:
                last_foreground_check = now
                foreground = is_foreground(hwnd)
                if not foreground:
                    # 切出游戏时游戏画面可能被遮挡，暂停采样，回到游戏继续。
                    self.on_position(None)
            if not foreground:
                time.sleep(FOREGROUND_CHECK_INTERVAL)
                continue
            screenshot_at = time.time()
            screenshot = controller.get_screenshot()
            if screenshot is None:
                continue
            crop = self._crop(screenshot, rect)
            if crop is None:
                continue
            angle_start = time.perf_counter()
            marker, _marker_edges, sector, _radius, _origin = analyze(crop)
            angle_ms = (time.perf_counter() - angle_start) * 1000
            self.on_angles(sector, marker)
            locate_start = time.perf_counter()
            located = self._locate(crop)
            locate_ms = (time.perf_counter() - locate_start) * 1000
            if located is None:
                self.on_position(None)
                self.on_stats(self._build_stats(None, None, None, angle_ms, locate_ms, 0.0))
                continue
            locator, score, center = located
            center = self._debounce(locator.name, center)
            total_ms = (time.time() - screenshot_at) * 1000
            local = (
                float(center[0] - locator.origin[0]),
                float(center[1] - locator.origin[1]),
            )
            if locator.name != self._shown_layer:
                image_path = self._layer_paths.get(locator.name)
                if image_path is None:
                    self.on_position(None)
                    continue
                self._shown_layer = locator.name
                self.on_layer(locator.name, image_path)
            self.on_position(local)
            step_max, window_span = self._track_step(center)
            self.on_stats(
                self._build_stats(
                    locator.name, center, score, angle_ms, locate_ms, total_ms,
                    step_max, window_span,
                ),
            )
            self._drain_presses(locator.name, center)
        return '录制已停止'

    def _build_stats(
        self,
        layer: str | None,
        center: tuple[int, int] | None,
        score: float | None,
        angle_ms: float,
        locate_ms: float,
        total_ms: float,
        step_max: float = 0.0,
        window_span: float = 0.0,
    ) -> dict[str, Any]:
        """汇总这一帧的定位统计，供悬浮窗显示。

        Args:
            layer: 命中分层名，未定位到时为 None。
            center: 全局坐标，未定位到时为 None。
            score: 匹配分，未定位到时为 None。
            angle_ms: 朝向识别耗时（毫秒）。
            locate_ms: 定位耗时（毫秒）。
            total_ms: 从截图到出结果的端到端耗时（毫秒）。
            step_max: 统计窗口内单帧最大偏移。
            window_span: 统计窗口的实际时长。

        Returns:
            统计字典，键为 layer/center/score/fps/angle_ms/locate_ms/total_ms/step_max/window_span。
        """
        self._update_fps()
        return {
            'layer': layer,
            'center': center,
            'score': score,
            'fps': self._fps,
            'angle_ms': angle_ms,
            'locate_ms': locate_ms,
            'total_ms': total_ms,
            'step_max': step_max,
            'window_span': window_span,
        }

    def _debounce(self, layer: str, center: tuple[int, int]) -> tuple[int, int]:
        """与上一帧坐标差在容差内就沿用上一帧，避免原地抖动。

        Args:
            layer: 本帧命中的分层名。
            center: 本帧定位出的全局坐标。

        Returns:
            实际采用的坐标。
        """
        previous = self._shown_center
        if (
            previous is not None
            and layer == self._shown_layer
            and abs(previous[0] - center[0]) <= SHAKE_TOLERANCE
            and abs(previous[1] - center[1]) <= SHAKE_TOLERANCE
        ):
            return previous
        self._shown_center = center
        return center

    def _track_step(self, center: tuple[int, int]) -> tuple[float, float]:
        """记录本帧坐标，返回窗口内单帧最大偏移与窗口实际时长。

        Args:
            center: 本帧全局坐标。

        Returns:
            (单帧最大偏移像素, 窗口内最早与最新样本的时间差)。
        """
        now = time.perf_counter()
        self._track.append((now, center))
        while len(self._track) >= 2 and now - self._track[1][0] > SPEED_WINDOW_SECONDS:
            self._track.pop(0)
        step_max = 0.0
        for prev, cur in zip(self._track, self._track[1:], strict=False):
            step = float(np.hypot(cur[1][0] - prev[1][0], cur[1][1] - prev[1][1]))
            if step > step_max:
                step_max = step
        span = self._track[-1][0] - self._track[0][0] if len(self._track) >= 2 else 0.0
        return step_max, span

    def _update_fps(self) -> None:
        """累计帧数并每秒刷新一次帧率。"""
        self._frame_count += 1
        now = time.perf_counter()
        if self._fps_start == 0:
            self._fps_start = now
            return
        elapsed = now - self._fps_start
        if elapsed >= 1.0:
            self._fps = self._frame_count / elapsed
            self._frame_count = 0
            self._fps_start = now

    def _drain_presses(self, layer: str, center: tuple[int, int]) -> None:
        """处理这一轮攒下的按键，按下的顺序依次生效。

        Args:
            layer: 当前命中分层名。
            center: 全局坐标。
        """
        while self._pending:
            key = self._pending.pop(0)
            if key == UNDO_KEY:
                removed = self.route.pop_point()
                if removed is not None:
                    self.on_undo()
                    self.on_status(f'已删上一个点 · 剩 {len(self.route.points)} 点')
                continue
            kind = POINT_KINDS.get(key)
            if kind is None:
                continue
            point = BagelRoutePoint(float(center[0]), float(center[1]), layer, kind[0])
            if not self.route.points:
                problem = self._first_point_problem(point)
                if problem is not None:
                    self.on_status(problem)
                    continue
            if self.route.append_point(point):
                self.on_point(point)
                self.on_status(f'已打 {len(self.route.points)} 点 · {kind[1]}')

    @staticmethod
    def _crop(screenshot: MatLike, rect: Rect) -> MatLike | None:
        """裁出小地图并统一成三通道，定位与朝向共用同一份裁剪。

        Args:
            screenshot: 整屏截图。
            rect: 小地图区域。

        Returns:
            小地图裁剪；裁剪失败时返回 None。
        """
        crop = cv2_utils.crop_image_only(screenshot, rect)
        if crop is None or crop.size == 0:
            return None
        if crop.ndim == 2:
            crop = np.stack([crop] * 3, axis=-1)
        return crop

    def _locate(self, crop: MatLike) -> tuple[Any, float, tuple[int, int]] | None:
        """在裁剪出的小地图上定位，失败返回 None。

        Args:
            crop: 小地图裁剪。

        Returns:
            (命中层, 匹配分, 全局坐标)。
        """
        if self._locator is None:
            return None
        result = self._locator.locate(crop)
        if result is None:
            return None
        locator, score, center = result
        return locator, score, center

    def _start_key_listener(self) -> None:
        """只监听打点键与退格键的按下。"""

        def on_press(key: keyboard.Key | keyboard.KeyCode) -> None:
            name = _key_name(key)
            if name is None:
                return
            if name in POINT_KINDS or name == UNDO_KEY:
                self._pending.append(name)

        self._listener = keyboard.Listener(on_press=on_press)
        self._listener.start()

    def _stop_key_listener(self) -> None:
        """关闭按键监听。"""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        self._pending.clear()

    def _wait_for_foreground(self, hwnd: int) -> bool:
        """等游戏窗口变成前台。

        Args:
            hwnd: 游戏窗口句柄。

        Returns:
            成为前台时为 True。
        """
        deadline = time.monotonic() + FOREGROUND_WAIT_SECONDS
        while time.monotonic() < deadline:
            if is_foreground(hwnd):
                return True
            if self.stop_requested.is_set():
                return False
            time.sleep(0.05)
        return is_foreground(hwnd)


def _key_name(key: keyboard.Key | keyboard.KeyCode) -> str | None:
    """把 pynput 按键统一成小写名字，非字符键返回 None。"""
    char = getattr(key, 'char', None)
    if isinstance(char, str) and char:
        return char.lower()
    name = getattr(key, 'name', None)
    return name.lower() if isinstance(name, str) else None
