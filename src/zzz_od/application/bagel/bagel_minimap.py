"""离线匹配裁剪后的小地图与已核对的参考图。"""

from dataclasses import dataclass
from math import atan2, degrees, hypot, isfinite

import cv2
import numpy as np


@dataclass(frozen=True)
class MinimapMatch:
    """当前图到参考图的相似变换，以及玩家锚点投影。"""

    matrix: tuple[tuple[float, float, float], tuple[float, float, float]]
    player_position: tuple[float, float]
    mutual_matches: int
    inliers: int
    median_residual_px: float


def _features(image: np.ndarray, mask: np.ndarray) -> tuple[list[cv2.KeyPoint], np.ndarray | None]:
    """仅在调用方给定的静态区域提取 SIFT 特征。"""
    if image.ndim == 2:
        gray = image
    elif image.ndim == 3 and image.shape[2] == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        raise ValueError("小地图必须是灰度或 BGR 图像")
    if gray.dtype != np.uint8 or mask.shape != gray.shape or mask.dtype != np.uint8:
        raise ValueError("图像与遮罩必须是尺寸匹配的 uint8 数组")
    points, descriptors = cv2.SIFT_create(contrastThreshold=0.015, edgeThreshold=15).detectAndCompute(gray, mask)
    return list(points), descriptors


def _ratio_matches(first: np.ndarray, second: np.ndarray) -> list[cv2.DMatch]:
    """过滤没有两个近邻或描述子区别不明显的匹配。"""
    return [pair[0] for pair in cv2.BFMatcher().knnMatch(first, second, k=2)
            if len(pair) == 2 and pair[0].distance < 0.7 * pair[1].distance]


def register_minimap(
    current: np.ndarray,
    current_mask: np.ndarray,
    reference: np.ndarray,
    reference_mask: np.ndarray,
    player_anchor: tuple[float, float],
) -> MinimapMatch | None:
    """拟合当前图到参考图的变换，证据不足时返回 None。

    Args:
        current: 当前帧裁剪的小地图。
        current_mask: 当前帧有效静态几何遮罩。
        reference: 已审核的参考小地图。
        reference_mask: 参考图有效静态几何遮罩。
        player_anchor: 当前帧已标定的玩家锚点，单位为裁剪图像素。

    Returns:
        通过几何约束的变换与锚点投影，或者 None。
    """
    current_points, current_desc = _features(current, current_mask)
    reference_points, reference_desc = _features(reference, reference_mask)
    ax, ay = player_anchor
    height, width = current_mask.shape
    if not all(isfinite(v) for v in player_anchor) or not (0 <= ax < width and 0 <= ay < height):
        raise ValueError("玩家锚点必须位于当前小地图内")
    if current_desc is None or reference_desc is None or len(current_desc) < 2 or len(reference_desc) < 2:
        return None

    forward = _ratio_matches(current_desc, reference_desc)
    reverse = {(match.trainIdx, match.queryIdx) for match in _ratio_matches(reference_desc, current_desc)}
    mutual = [match for match in forward if (match.queryIdx, match.trainIdx) in reverse]
    if len(mutual) < 8:
        return None

    source = np.float32([current_points[match.queryIdx].pt for match in mutual])
    target = np.float32([reference_points[match.trainIdx].pt for match in mutual])
    matrix, inlier_mask = cv2.estimateAffinePartial2D(
        source, target, method=cv2.RANSAC, ransacReprojThreshold=2.0,
    )
    if matrix is None or inlier_mask is None or not np.isfinite(matrix).all():
        return None
    chosen = inlier_mask.ravel().astype(bool)
    count = int(chosen.sum())
    if count < 8 or count / len(mutual) < 0.55:
        return None
    for points in (source[chosen], target[chosen]):
        extent = np.ptp(points, axis=0)
        if min(extent) < 20 or cv2.contourArea(cv2.convexHull(points)) < 800:
            return None

    scale = hypot(float(matrix[0, 0]), float(matrix[1, 0]))
    angle = degrees(atan2(float(matrix[1, 0]), float(matrix[0, 0])))
    if not (0.98 <= scale <= 1.02) or abs(angle) > 2:
        return None
    errors = np.linalg.norm(source[chosen] @ matrix[:, :2].T + matrix[:, 2] - target[chosen], axis=1)
    median_error = float(np.median(errors))
    if median_error > 0.75 or float(np.percentile(errors, 90)) > 2.0:
        return None
    position = matrix[:, :2] @ np.array([ax, ay]) + matrix[:, 2]
    if not np.isfinite(position).all():
        return None
    return MinimapMatch(
        matrix=(tuple(float(v) for v in matrix[0]), tuple(float(v) for v in matrix[1])),
        player_position=(float(position[0]), float(position[1])),
        mutual_matches=len(mutual), inliers=count, median_residual_px=median_error,
    )
