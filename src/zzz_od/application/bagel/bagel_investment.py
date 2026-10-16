from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np

from one_dragon.utils import cv2_utils

if TYPE_CHECKING:
    from cv2.typing import MatLike

    from zzz_od.context.zzz_context import ZContext


def mask_investment_coin(crop: MatLike) -> MatLike | None:
    """定位唯一金币并遮挡其左侧区域，保持金额完整和 OCR 输入尺寸。"""
    if crop is None or crop.ndim != 3 or crop.shape[2] != 3 or crop.size == 0:
        return None
    hsv = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
    yellow = cv2.inRange(hsv, np.array([10, 100, 120]), np.array([40, 255, 255]))
    _, _, stats, _ = cv2.connectedComponentsWithStats(yellow)
    candidates: list[tuple[int, int]] = []
    for x, _y, width, height, area in stats[1:]:
        if area >= 100 and 18 <= width <= 45 and 18 <= height <= 45:
            candidates.append((int(x), int(x + width + 1)))
    if len(candidates) != 1:
        return None
    left, right = candidates[0]
    # 金币必须位于全部白色金额左侧；定位不明时不能遮掉高位后误读成零。
    if np.any(np.all(crop[:, :max(0, left - 2)] >= 180, axis=2)):
        return None
    masked = crop.copy()
    masked[:, :right] = 0
    return masked


def read_investment(ctx: ZContext, screen: MatLike) -> str:
    """先排除金币再读完整投资金额；定位失败保留为未知，不返回零。"""
    area = ctx.screen_loader.get_area('贝果-入场确认', '投资金额')
    if area is None:
        raise ValueError('缺少贝果画面区域：贝果-入场确认/投资金额')
    crop = cv2_utils.crop_image_only(screen, area.pc_rect)
    masked = mask_investment_coin(crop)
    if masked is None:
        return ''
    matches = ctx.ocr_service.get_ocr_result_list(masked, color_range=area.color_range)
    return ''.join(match.data for match in sorted(matches, key=lambda match: (match.y, match.x)))
