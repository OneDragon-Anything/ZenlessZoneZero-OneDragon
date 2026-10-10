"""固定地图的校验、不可变快照与进程内特征缓存。"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import count
from math import isfinite
from types import MappingProxyType
from typing import TYPE_CHECKING

import cv2
import numpy as np
import yaml

from zzz_od.application.bagel.bagel_minimap import (
    extract_features,
)
from zzz_od.application.bagel.bagel_route import resource_root

if TYPE_CHECKING:
    from collections.abc import Mapping

    from zzz_od.application.bagel.bagel_minimap import MinimapFeatures


def registration_image(image: np.ndarray, representation: str, blur_size: int) -> np.ndarray:
    """对实时图和底图使用同一表示；大图与局部图的效果由历史样本回归。"""
    gray = np.min(image[:, :, :3], axis=2) if image.ndim == 3 else image
    blurred = cv2.GaussianBlur(gray, (blur_size, blur_size), 0)
    if representation == 'clahe_min_channel':
        return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(blurred)
    if representation == 'highpass_min_channel':
        background = cv2.GaussianBlur(blurred, (0, 0), 5)
        return np.clip(blurred.astype(np.float32) - background + 64, 0, 255).astype(np.uint8)
    raise ValueError(f'未知地图图像表示：{representation}')


def _pair(value: object, label: str) -> tuple[float, float]:
    """解析坐标并拒绝非有限值和布尔。"""
    if not isinstance(value, list) or len(value) != 2 or any(
        type(v) not in (int, float) or not isfinite(v) for v in value
    ):
        raise ValueError(f'地图{label}必须是两个有限数值')
    return float(value[0]), float(value[1])


def _freeze_settings(value: object) -> Mapping[str, object]:
    """参数字典与其中的列表均不可修改，避免执行中改变快照。"""
    if not isinstance(value, dict):
        raise ValueError('地图识别参数必须是字典')
    return MappingProxyType({key: tuple(item) if isinstance(item, list) else item for key, item in value.items()})


_SNAPSHOT_IDS = count(1)


@dataclass(frozen=True)
class MapFeatureBank:
    """整图特征与覆盖全图的重叠分区，分区只选特征，不重新提取。"""

    representation: str
    features: MinimapFeatures
    regions: tuple[np.ndarray, ...]


@dataclass(frozen=True)
class BagelFixedMap:
    """一次执行共用的地图资源和特征，编号仅在当前进程内标识快照。"""

    map_id: str
    snapshot_id: int
    image: np.ndarray
    mask: np.ndarray
    position_mask: np.ndarray
    origin: tuple[int, int]
    anchor: tuple[float, float]
    spawn: tuple[float, float]
    mask_settings: Mapping[str, object]
    arrow_settings: Mapping[str, object]
    blur_size: int
    banks: tuple[MapFeatureBank, ...]
    reference_centers: tuple[tuple[str, tuple[float, float]], ...]
    landmarks: tuple[tuple[str, tuple[float, float]], ...]

    def supports_position(self, position: tuple[float, float]) -> bool:
        """拒绝观测范围外的锚点，容许观测范围内的箭头及图标空洞。"""
        # position 是底图像素坐标（未加 origin），position_mask 是像素数组。
        x, y = (round(v) for v in position)
        return 0 <= y < self.position_mask.shape[0] and 0 <= x < self.position_mask.shape[1] and bool(self.position_mask[y, x])


def load_fixed_map(map_id: str) -> BagelFixedMap:
    """读取完整一组资源并校验；新执行使用新版本，旧快照不受影响。"""
    root = resource_root(map_id)
    metadata = (root / 'map.yml').read_bytes()
    image = (root / 'map.png').read_bytes()
    mask = (root / 'map_mask.png').read_bytes()
    if (root / 'map.yml').read_bytes() != metadata:
        raise ValueError('地图资源正在更新，请完成整组安装后重试')
    return _load_snapshot(map_id, metadata, image, mask)


@lru_cache(maxsize=4)
def _load_snapshot(map_id: str, metadata: bytes, image_data: bytes, mask_data: bytes) -> BagelFixedMap:
    """相同内容只提取一次特征；缓存键包含图片、遮罩及预处理元数据。"""
    data = yaml.safe_load(metadata)
    if not isinstance(data, dict) or data.get('map_id') != map_id:
        raise ValueError('固定地图标识不匹配')
    if type(data.get('format_version')) is not int or data['format_version'] != 1:
        raise ValueError('未知固定地图格式版本')
    if type(data.get('coordinate_version')) is not int or data['coordinate_version'] != 1 or data.get('coordinate_unit') != 'reference_spawn_pixel':
        raise ValueError('未知固定地图坐标版本或单位')
    size = _pair(data.get('size_wh'), '尺寸')
    origin = _pair(data.get('origin_xy'), '原点')
    if any(int(v) != v for v in (*size, *origin)) or min(size) <= 0 or max(size) > 4096:
        raise ValueError('地图尺寸或原点无效')
    image = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_UNCHANGED)
    mask = cv2.imdecode(np.frombuffer(mask_data, np.uint8), cv2.IMREAD_UNCHANGED)
    shape = (int(size[1]), int(size[0]))
    if image is None or image.shape != (*shape, 4) or image.dtype != np.uint8:
        raise ValueError('固定地图必须是与尺寸一致的 RGBA 图片')
    if mask is None or mask.shape != shape or mask.dtype != np.uint8 or not np.isin(mask, (0, 255)).all() or not np.any(mask):
        raise ValueError('固定地图有效像素遮罩无效')
    if not np.array_equal(image[:, :, 3], mask):
        raise ValueError('地图透明通道与有效遮罩不一致')
    anchor = _pair(data.get('anchor_xy'), '玩家锚点')
    spawn = _pair(data.get('spawn_xy'), '出生坐标')
    if not all(0 <= v < 201 for v in anchor) or spawn != (100, 100):
        raise ValueError('地图锚点或既有出生坐标无效')
    blur_size = data.get('registration_blur_size')
    edge = data.get('feature_edge_margin')
    window, stride = data.get('match_window_size'), data.get('match_window_stride')
    if type(blur_size) is not int or blur_size not in (1, 3, 5) or type(edge) is not int or not 0 <= edge <= 16:
        raise ValueError('地图预处理参数无效')
    if type(window) is not int or type(stride) is not int or not 80 <= window <= 401 or not 1 <= stride <= window // 2:
        raise ValueError('地图特征分区参数无效')
    representations = data.get('representations')
    if not isinstance(representations, list) or not representations or any(not isinstance(item, str) for item in representations) or len(set(representations)) != len(representations) or any(
        item not in ('clahe_min_channel', 'highpass_min_channel') for item in representations
    ):
        raise ValueError('地图图像表示参数无效')
    settings, arrows = _freeze_settings(data.get('mask')), _freeze_settings(data.get('player_arrow'))
    _validate_settings(settings, arrows)
    # 只填补被观测区域包围的孔洞，不向外围扩张；这不是可通行图。
    padded = np.pad(mask, 1)
    outside = padded.copy()
    cv2.floodFill(outside, None, (0, 0), 255)
    position_mask = cv2.bitwise_or(padded, cv2.bitwise_not(outside))[1:-1, 1:-1].copy()
    feature_mask = cv2.erode(mask, np.ones((edge * 2 + 1, edge * 2 + 1), np.uint8))
    banks = []
    for representation in representations:
        features = extract_features(registration_image(image, representation, blur_size), feature_mask)
        if features.descriptors is None or len(features.points) < 8:
            raise ValueError('固定地图没有足够的静态特征')
        regions = []
        for y in range(0, max(1, shape[0] - stride), stride):
            for x in range(0, max(1, shape[1] - stride), stride):
                selected = np.flatnonzero(
                    (features.points[:, 0] >= x) & (features.points[:, 0] <= x + window)
                    & (features.points[:, 1] >= y) & (features.points[:, 1] <= y + window)
                )
                if len(selected) >= 8:
                    selected.setflags(write=False)
                    regions.append(selected)
        banks.append(MapFeatureBank(representation, features, tuple(regions)))
    for array in (image, mask, position_mask):
        array.setflags(write=False)
    return BagelFixedMap(
        map_id, next(_SNAPSHOT_IDS),
        image, mask, position_mask, (int(origin[0]), int(origin[1])), anchor, spawn,
        settings, arrows, blur_size, tuple(banks),
        _named_points(data.get('reference_centers', [])), _named_points(data.get('landmarks', [])),
    )


def _named_points(value: object) -> tuple[tuple[str, tuple[float, float]], ...]:
    """解析只用于展示的参考中心与地标。"""
    if not isinstance(value, list) or any(not isinstance(item, dict) or not isinstance(item.get('name'), str) for item in value):
        raise ValueError('地图地标无效')
    return tuple((item['name'], _pair(item.get('xy'), '地标')) for item in value)


def _validate_settings(mask: Mapping[str, object], arrow: Mapping[str, object]) -> None:
    """移动前核对运行必需字段及其数值范围。"""
    try:
        valid = (
            mask['center_xy'] == (100, 100)
            and 0 < mask['inner_radius'] < mask['outer_radius'] < 101
            and 0 <= mask['maximum_saturation'] <= 255
            and 0 <= mask['minimum_brightness'] <= 255
            and 0 <= mask.get('edge_margin', 0) <= 10
            and 1 <= arrow['crop_radius'] <= 50
            and len(arrow['hsv_lower']) == len(arrow['hsv_upper']) == 3
            and all(0 <= low <= high <= 255 for low, high in zip(arrow['hsv_lower'], arrow['hsv_upper'], strict=True))
            and len(arrow['area_range']) == 2
            and 0 < arrow['area_range'][0] < arrow['area_range'][1]
            and 0 < arrow['maximum_center_offset'] <= 20
            and 0 <= arrow['minimum_green_spread'] <= 255
            and 0 < arrow['tip_percentile'] < 100
            and 0 < arrow['minimum_tip_offset'] <= 20
        )
        integers = ('inner_radius', 'outer_radius', 'edge_margin')
        valid = valid and all(type(mask.get(key, 0)) is int for key in integers) and type(arrow['crop_radius']) is int
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError('地图遮罩或角色箭头参数缺失或格式无效') from error
    if not valid:
        raise ValueError('地图遮罩或角色箭头参数越界')
