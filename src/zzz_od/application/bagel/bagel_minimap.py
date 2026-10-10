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
    return match_features(
        extract_features(current, current_mask),
        extract_features(reference, reference_mask),
        player_anchor,
    )


@dataclass(frozen=True)
class MinimapFeatures:
    """可复用的特征坐标和描述子；数组不可修改。"""

    points: np.ndarray
    descriptors: np.ndarray | None
    shape: tuple[int, int]


def extract_features(image: np.ndarray, mask: np.ndarray) -> MinimapFeatures:
    """一次提取特征，供多个匹配目标复用。"""
    keypoints, descriptors = _features(image, mask)
    points = np.asarray([point.pt for point in keypoints], dtype=np.float32).reshape(-1, 2)
    points.setflags(write=False)
    if descriptors is not None:
        descriptors.setflags(write=False)
    return MinimapFeatures(points, descriptors, image.shape[:2])


def match_features(
    current: MinimapFeatures,
    reference: MinimapFeatures,
    player_anchor: tuple[float, float],
) -> MinimapMatch | None:
    """复用特征并沿用双向匹配、几何与残差校验。"""
    current_points, current_desc = current.points, current.descriptors
    reference_points, reference_desc = reference.points, reference.descriptors
    ax, ay = player_anchor
    height, width = current.shape
    if not all(isfinite(v) for v in player_anchor) or not (0 <= ax < width and 0 <= ay < height):
        raise ValueError("玩家锚点必须位于当前小地图内")
    if current_desc is None or reference_desc is None or len(current_desc) < 2 or len(reference_desc) < 2:
        return None

    forward = _ratio_matches(current_desc, reference_desc)
    reverse = {(match.trainIdx, match.queryIdx) for match in _ratio_matches(reference_desc, current_desc)}
    mutual = [match for match in forward if (match.queryIdx, match.trainIdx) in reverse]
    if len(mutual) < 8:
        return None

    source = np.float32([current_points[match.queryIdx] for match in mutual])
    target = np.float32([reference_points[match.trainIdx] for match in mutual])
    return _fit_match(source, target, len(mutual), player_anchor)


def _fit_match(
    source: np.ndarray,
    target: np.ndarray,
    mutual_count: int,
    player_anchor: tuple[float, float],
) -> MinimapMatch | None:
    """所有匹配入口共用同一组几何门槛。"""
    source = np.asarray(source, dtype=np.float32)
    target = np.asarray(target, dtype=np.float32)
    matrix, inlier_mask = cv2.estimateAffinePartial2D(
        source, target, method=cv2.RANSAC, ransacReprojThreshold=2.0,
    )
    if matrix is None or inlier_mask is None or not np.isfinite(matrix).all():
        return None
    chosen = inlier_mask.ravel().astype(bool)
    count = int(chosen.sum())
    if count < 8 or count / mutual_count < 0.55:
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
    position = matrix[:, :2] @ np.array(player_anchor) + matrix[:, 2]
    if not np.isfinite(position).all():
        return None
    return MinimapMatch(
        matrix=(tuple(float(v) for v in matrix[0]), tuple(float(v) for v in matrix[1])),
        player_position=(float(position[0]), float(position[1])),
        mutual_matches=mutual_count, inliers=count, median_residual_px=median_error,
    )


def match_feature_regions(
    current: MinimapFeatures,
    reference: MinimapFeatures,
    regions: tuple[np.ndarray, ...],
    player_anchor: tuple[float, float],
) -> tuple[MinimapMatch, ...]:
    """一次计算描述子距离，复用到覆盖全图的分区以发现竞争位置。"""
    ax, ay = player_anchor
    height, width = current.shape
    if not all(isfinite(v) for v in player_anchor) or not (0 <= ax < width and 0 <= ay < height):
        raise ValueError("玩家锚点必须位于当前小地图内")
    first, second = current.descriptors, reference.descriptors
    if first is None or second is None or min(len(first), len(second)) < 8:
        return ()
    # 平方欧氏距离的比例门槛为 0.7²；整图和分区均使用双向比例检验。
    distances = cv2.gemm(first, second, -2, None, 0, flags=cv2.GEMM_2_T)
    distances += np.sum(first * first, axis=1)[:, None]
    distances += np.sum(second * second, axis=1)[None, :]
    np.maximum(distances, 0, out=distances)
    matches = []
    all_indices = np.arange(len(second))
    source_rows = np.arange(len(first))
    # 分区只限制参考图范围，参考点到当前帧的反向最近邻不会变化。
    reverse = np.argmin(distances, axis=0)
    reverse_first = distances[reverse, all_indices].copy()
    distances[reverse, all_indices] = np.inf
    reverse_second = np.min(distances, axis=0)
    distances[reverse, all_indices] = reverse_first
    reverse_valid = reverse_first < .49 * reverse_second
    for indices in (all_indices, *regions):
        matrix = np.ascontiguousarray(distances[:, indices])
        forward = np.argmin(matrix, axis=1)
        nearest = matrix[source_rows, forward].copy()
        matrix[source_rows, forward] = np.inf
        second_nearest = np.min(matrix, axis=1)
        reference_indices = indices[forward]
        source_indices = np.flatnonzero(
            (nearest < .49 * second_nearest)
            & (reverse[reference_indices] == source_rows)
            & reverse_valid[reference_indices]
        )
        if len(source_indices) < 8:
            continue
        target_indices = reference_indices[source_indices]
        match = _fit_match(current.points[source_indices], reference.points[target_indices], len(source_indices), player_anchor)
        if match is not None:
            matches.append(match)
    return tuple(matches)
