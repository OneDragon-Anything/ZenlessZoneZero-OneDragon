"""一次性定位：切到游戏、截一帧、定位一次，然后立刻交回编辑器。

给路线编辑器里的「定位」按钮用，只为了确认角色此刻在哪，不移动、不打点，
所以不做任何输入，也不进运行上下文。
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QThread, Signal

from one_dragon.utils import cv2_utils
from one_dragon.utils.log_utils import log
from zzz_od.application.bagel.bagel_route_recorder import MINIMAP_AREA, is_foreground
from zzz_od.game_data.map_locator.map_locator import MultiMapLocator, load_map_locators

if TYPE_CHECKING:
    from cv2.typing import MatLike
    from PySide6.QtWidgets import QWidget

    from one_dragon.base.geometry.rectangle import Rect
    from zzz_od.context.zzz_context import ZContext

GAME_FOREGROUND_TIMEOUT: float = 5.0
"""切到游戏前台的最长等待秒数。"""


class BagelLocateThread(QThread):
    """在后台线程里做一次定位，避免切窗口时卡住界面。"""

    status_changed = Signal(str)
    """当前阶段文案。"""

    done = Signal(bool, str, str, object)
    """(是否成功, 结论文案, 分层名, 层内坐标)；失败时分层名为空、坐标为 None。"""

    def __init__(self, ctx: ZContext, parent: QWidget | None = None) -> None:
        """
        Args:
            ctx: 运行上下文。
            parent: Qt 父对象。
        """
        super().__init__(parent)
        self.ctx: ZContext = ctx

    def run(self) -> None:
        """切到游戏定位一次并立刻返回结论。"""
        try:
            self._locate_once()
        except Exception as error:
            log.error('贝果单次定位异常', exc_info=True)
            self.done.emit(False, f'定位异常：{error}', '', None)

    def _locate_once(self) -> None:
        """截一帧小地图，定位一次，把层名与层内坐标交回去。"""
        controller = self.ctx.controller
        if controller is None or not controller.init_game_win():
            self.done.emit(False, '游戏窗口未就绪，请先启动游戏', '', None)
            return
        hwnd = controller.game_win.get_hwnd()
        if hwnd is None or not controller.is_game_window_ready:
            self.done.emit(False, '未找到游戏窗口，请先启动游戏', '', None)
            return
        area = self.ctx.screen_loader.get_area(*MINIMAP_AREA)
        if area is None:
            self.done.emit(False, f'缺少画面区域：{MINIMAP_AREA[0]}/{MINIMAP_AREA[1]}', '', None)
            return

        self.status_changed.emit('正在切到游戏定位')
        controller.active_window()
        if not self._wait_for_foreground(hwnd):
            self.done.emit(False, '游戏窗口未切到前台，未定位', '', None)
            return

        screenshot = controller.get_screenshot()
        if screenshot is None:
            self.done.emit(False, '截图失败，未定位', '', None)
            return
        crop = self._crop(screenshot, area.pc_rect)
        if crop is None:
            self.done.emit(False, '小地图裁剪为空，未定位', '', None)
            return

        locators = load_map_locators()
        result = MultiMapLocator(locators).locate(crop)
        if result is None:
            self.done.emit(False, '这一帧没定位到，可能不在贝果局内', '', None)
            return
        locator, score, center = result
        # 路线里的点存的是全局坐标（打点时写的就是 center），所以这里也回全局坐标。
        global_xy = (float(center[0]), float(center[1]))
        message = (
            f'{locator.name} · 坐标 ({global_xy[0]:.0f}, {global_xy[1]:.0f})'
            f' · 匹配 {score:.2f}'
        )
        log.info('贝果单次定位：%s', message)
        self.done.emit(True, message, locator.name, global_xy)

    def _wait_for_foreground(self, hwnd: int) -> bool:
        """等游戏真的切到前台，超时返回 False。

        Args:
            hwnd: 游戏窗口句柄。

        Returns:
            游戏在前台时返回 True。
        """
        deadline = time.monotonic() + GAME_FOREGROUND_TIMEOUT
        while time.monotonic() < deadline:
            if is_foreground(hwnd):
                return True
            time.sleep(0.2)
        return False

    @staticmethod
    def _crop(screenshot: MatLike, rect: Rect) -> MatLike | None:
        """裁出小地图并统一成三通道，与录制、导航用同一套裁剪。

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
