"""空洞类玩法局内 HUD 的识别。

在空洞类玩法（贝果计划、零号空洞等）局内直接退出游戏后再次登录，游戏会
直接回到局内画面。登录流程原来只认大世界，遇到这种画面会一直按「未知画面」
重试到超时，导致后面的应用根本不会被加载。

这里只判断「当前是否处在这种玩法的局内 HUD」，不区分具体是哪个玩法，也不负责
把角色带出去——退出玩法由各玩法自己的逻辑决定。

判据由两部分组成，都要命中才算：
  1. 右上角有一个金黄色的圆环计时图标；
  2. 右下角有战斗的普通攻击按钮。
单独的计时或单独的按钮都可能出现在别处（结算、地图、其它 HUD），两者同时出现
才代表「角色正处在可操作的局内」。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils import cv2_utils

if TYPE_CHECKING:
    from cv2.typing import MatLike

    from zzz_od.context.zzz_context import ZContext

SCREEN_NAME: str = '空洞-局内HUD'
AREA_CLOCK: str = '右上计时'
AREA_ATTACK: str = '普通攻击'
""""画面与区域名称；区域坐标见 assets/game_data/screen_info/hollow_zero_inside.yml。"""

# 金黄色圆环：H 25~42、S/V 都要足够高，排除淡黄背景与白色数字。
CLOCK_LOWER: tuple[int, int, int] = (25, 180, 120)
CLOCK_UPPER: tuple[int, int, int] = (42, 255, 255)
# 圆环的最小外接框与面积，过滤数字描边和细小高光。
CLOCK_MIN_WIDTH: int = 10
CLOCK_MIN_HEIGHT: int = 20
CLOCK_MIN_AREA: float = 60.0
# 普攻按钮区域里要有足够多的亮像素，避免纯黑/被面板遮住时误判。
ATTACK_MIN_BRIGHT_RATIO: float = 0.08


def _area_rect(ctx: ZContext, area_name: str) -> Rect | None:
    """读取本画面区域；画面或区域缺失时返回 None，由调用方决定降级。"""
    area = ctx.screen_loader.get_area(SCREEN_NAME, area_name)
    return None if area is None else area.rect


def has_clock_icon(screen: MatLike, rect: Rect) -> bool:
    """右上角区域里是否存在金黄色圆环计时图标。"""
    crop = cv2_utils.crop_image_only(screen, rect)
    if crop is None or crop.size == 0 or len(crop.shape) != 3:
        return False
    hsv = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
    mask = cv2.inRange(hsv, np.array(CLOCK_LOWER, dtype=np.uint8),
                       np.array(CLOCK_UPPER, dtype=np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        _x, _y, width, height = cv2.boundingRect(contour)
        if (width >= CLOCK_MIN_WIDTH and height >= CLOCK_MIN_HEIGHT
                and cv2.contourArea(contour) >= CLOCK_MIN_AREA):
            return True
    return False


def has_attack_button(screen: MatLike, rect: Rect) -> bool:
    """右下角区域里是否有足够亮的普攻按钮，用来排除被面板遮住的画面。"""
    crop = cv2_utils.crop_image_only(screen, rect)
    if crop is None or crop.size == 0 or len(crop.shape) != 3:
        return False
    bright = np.all(crop >= 90, axis=2)
    return float(np.count_nonzero(bright)) / float(bright.size) >= ATTACK_MIN_BRIGHT_RATIO


def is_in_hollow_inside(ctx: ZContext, screen: MatLike) -> bool:
    """当前画面是否是空洞类玩法的局内 HUD。

    Args:
        ctx: 运行上下文，用来读取画面区域配置。
        screen: 1920x1080 的 RGB 截图。

    Returns:
        同时命中计时圆环和普攻按钮时返回 True。画面区域缺失时返回 False，
        让登录流程保持原有行为，不因为少一份配置就卡住。
    """
    if screen is None or len(screen.shape) != 3 or screen.shape[:2] != (1080, 1920):
        return False
    clock_rect = _area_rect(ctx, AREA_CLOCK)
    attack_rect = _area_rect(ctx, AREA_ATTACK)
    if clock_rect is None or attack_rect is None:
        return False
    return has_clock_icon(screen, clock_rect) and has_attack_button(screen, attack_rect)
