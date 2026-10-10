"""从新录像配准小地图并生成独立底图，不录制或控制游戏。"""

from __future__ import annotations

import math
import tempfile
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np
import yaml

from one_dragon.base.screen.screen_loader import ScreenContext
from zzz_od.application.bagel.bagel_fixed_map import _load_snapshot
from zzz_od.application.bagel.bagel_minimap import extract_features, match_features
from zzz_od.application.bagel.bagel_route import resource_root

if TYPE_CHECKING:
    from collections.abc import Iterator

    from zzz_od.application.bagel.bagel_minimap import MinimapFeatures


@dataclass(frozen=True)
class RegisteredFrame:
    """已接收的小地图、静态遮罩及到出生坐标系的完整变换。"""

    image: np.ndarray
    mask: np.ndarray
    features: MinimapFeatures
    transform: np.ndarray
    time: float

    @property
    def xy(self) -> tuple[float, float]:
        """玩家中心相对出生中心的位移。"""
        point = self.transform @ np.array([100., 100., 1.])
        return float(point[0] - 100), float(point[1] - 100)


def video_frames(video: Path, sampling_fps: float) -> Iterator[tuple[float, np.ndarray]]:
    """按解码帧时基采样原生 1080p 视频，拒绝未知帧率及不完整解码。"""
    screens = ScreenContext()
    screens.reload()
    area = screens.get_area('贝果-局内', '定位小地图')
    if area is None or area.pc_rect.width != 201 or area.pc_rect.height != 201:
        raise ValueError('缺少有效的贝果定位小地图区域')
    rect = area.pc_rect
    if not (0 <= rect.x1 < rect.x2 <= 1920 and 0 <= rect.y1 < rect.y2 <= 1080):
        raise ValueError('定位小地图区域超出原生画面')
    capture = cv2.VideoCapture(str(video.resolve()))
    try:
        fps = capture.get(cv2.CAP_PROP_FPS)
        count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        if not capture.isOpened() or not math.isfinite(fps) or fps < sampling_fps:
            raise ValueError('录像无法解码或帧率低于采样帧率')
        if not math.isfinite(count) or count < 3 or count / fps > 600:
            raise ValueError('录像必须包含有效帧数且不超过十分钟')
        index, next_time = 0, 0.0
        while True:
            ok, image = capture.read()
            if not ok:
                break
            if image.shape != (1080, 1920, 3):
                raise ValueError('建图录像必须是原生 1920×1080 画面')
            time = index / fps
            index += 1
            if time + 1e-6 < next_time:
                continue
            next_time += 1 / sampling_fps
            yield time, image[rect.y1:rect.y2, rect.x1:rect.x2].copy()
        if abs(index - count) > 1:
            raise ValueError('录像未完整解码，不能发布截断的地图')
    finally:
        capture.release()


def fusion_mask(image: np.ndarray, outer_radius: int, inner_radius: int) -> np.ndarray:
    """排除圆框外、玩家箭头和高亮动态标记，不推测被遮住的道路。"""
    mask = np.zeros((201, 201), np.uint8)
    cv2.circle(mask, (100, 100), outer_radius, 255, -1)
    cv2.circle(mask, (100, 100), inner_radius, 0, -1)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    dynamic = ((hsv[:, :, 1] > 90) & (hsv[:, :, 2] > 130)) | (
        (hsv[:, :, 1] < 60) & (hsv[:, :, 2] > 185)
    )
    mask[cv2.dilate(dynamic.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0] = 0
    return mask


def register_frames(
    video: Path, sampling_fps: float, outer_radius: int, inner_radius: int,
) -> tuple[list[RegisteredFrame], int]:
    """用静止开头建立原点；短暂拒绝后必须重新匹配，不能跨长空段拼接。"""
    accepted: list[RegisteredFrame] = []
    rejected, stable = 0, 0
    key: RegisteredFrame | None = None
    last_time = 0.0
    for time, image in video_frames(video, sampling_fps):
        last_time = time
        mask = fusion_mask(image, outer_radius, inner_radius)
        gray = cv2.GaussianBlur(np.min(image, axis=2), (3, 3), 0)
        features = extract_features(gray, mask)
        if key is None:
            if time > 2:
                raise ValueError('开头两秒内没有完整、可匹配的小地图')
            if features.descriptors is None or len(features.points) < 16:
                rejected += 1
                continue
            key = RegisteredFrame(image, mask, features, np.eye(3), time)
            accepted.append(key)
            stable = 1
            continue
        previous = accepted[-1]
        if time - previous.time > 1.01:
            raise ValueError('小地图连续超过一秒无法可靠匹配，请重新录制')
        match = match_features(features, key.features, (100, 100))
        reference = key
        if match is None and key is not previous:
            match = match_features(features, previous.features, (100, 100))
            reference = previous
        if match is None:
            rejected += 1
            continue
        transform = reference.transform @ np.vstack([np.asarray(match.matrix), [0., 0., 1.]])
        scale = math.hypot(transform[0, 0], transform[1, 0])
        angle = math.degrees(math.atan2(transform[1, 0], transform[0, 0]))
        # 限制相对出生画面的累计变换，不能用逐帧小变化绕过几何门槛。
        if not .98 <= scale <= 1.02 or abs(angle) > 2:
            rejected += 1
            continue
        frame = RegisteredFrame(image, mask, features, transform, time)
        xy = frame.xy
        if math.dist(xy, previous.xy) > 80 * (time - previous.time) + 2:
            rejected += 1
            continue
        if stable < 3:
            if math.dist(xy, (0, 0)) > 1 or abs(angle) > .25 or abs(scale - 1) > .002:
                raise ValueError('开头须保持静止至少三个采样帧，不能从移动中建立出生原点')
            stable += 1
        accepted.append(frame)
        # 保持一定重叠范围，减少每帧累积误差；匹配失败时只回退到最近可靠帧。
        if math.dist(xy, key.xy) >= 30 or reference is previous:
            key = frame
    if stable < 3 or len(accepted) < 3:
        raise ValueError('没有足够的稳定出生画面')
    if last_time - accepted[-1].time > 0.4:
        raise ValueError('录像结尾无法可靠匹配，不能发布不完整采集结果')
    return accepted, rejected


def fuse_frames(
    frames: list[RegisteredFrame], staging: Path,
) -> tuple[np.ndarray, np.ndarray, tuple[int, int]]:
    """分块取时间第 25 百分位，磁盘暂存限定内存使用。"""
    corners = np.array([[0., 0., 1.], [201., 0., 1.], [0., 201., 1.], [201., 201., 1.]])
    points = np.concatenate([(corners @ frame.transform.T)[:, :2] for frame in frames])
    origin = np.floor(points.min(axis=0)).astype(int) - 2
    size = np.ceil(points.max(axis=0)).astype(int) + 2 - origin
    width, height = (int(value) for value in size)
    if max(width, height) > 4096 or len(frames) * width * height > 512 * 1024 * 1024:
        raise ValueError('采集范围或帧数过大，请缩短录像或降低采样帧率')
    shape = (len(frames), height, width)
    values = np.memmap(staging / 'gray.bin', dtype=np.uint8, mode='w+', shape=shape)
    validity = np.memmap(staging / 'valid.bin', dtype=np.uint8, mode='w+', shape=shape)
    try:
        for index, frame in enumerate(frames):
            matrix = frame.transform[:2].copy()
            matrix[:, 2] -= origin
            values[index] = cv2.warpAffine(np.min(frame.image, axis=2), matrix, (width, height))
            validity[index] = cv2.warpAffine(frame.mask, matrix, (width, height), flags=cv2.INTER_NEAREST) > 0
        gray = np.zeros((height, width), np.uint8)
        mask = np.zeros((height, width), np.uint8)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)
            for y in range(0, height, 12):
                slab = np.asarray(values[:, y:y+12], dtype=np.float32)
                valid = np.asarray(validity[:, y:y+12]) > 0
                slab[~valid] = np.nan
                gray[y:y+12] = np.nan_to_num(np.nanpercentile(slab, 25, axis=0)).astype(np.uint8)
                mask[y:y+12] = valid.any(axis=0).astype(np.uint8) * 255
        return np.dstack([cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR), mask]), mask, (int(origin[0]), int(origin[1]))
    finally:
        del values, validity


def build_map(map_id: str, video: Path, output: Path, sampling_fps: float = 5) -> None:
    """在独立目录生成并通过运行加载校验，已有目录一律不覆盖。"""
    if not math.isfinite(sampling_fps) or not 2 <= sampling_fps <= 20:
        raise ValueError('采样帧率须在 2 至 20 之间')
    if output.exists():
        raise FileExistsError('输出目录已存在，请指定新的待验收目录')
    metadata = yaml.safe_load((resource_root(map_id) / 'map.yml').read_text(encoding='utf-8'))
    frames, rejected = register_frames(
        video, sampling_fps, metadata['mask']['outer_radius'], metadata['mask']['inner_radius'],
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.bagel-build-', dir=output.parent) as directory:
        staging = Path(directory)
        image, mask, origin = fuse_frames(frames, staging)
        # 参数沿用对应地图；旧地图的坐标、地标及构建记录不适用于新采集结果。
        for name in ('reference_centers', 'landmarks', 'build'):
            metadata.pop(name, None)
        metadata.update(origin_xy=list(origin), size_wh=[image.shape[1], image.shape[0]], spawn_xy=[100, 100])
        metadata['build'] = {
            'profile': 'min_channel_percentile_25', 'sampling_fps': sampling_fps,
            'registered_frames': len(frames), 'rejected_frames': rejected,
            'maximum_gap_seconds': 1, 'maximum_speed_pixels_per_second': 80,
        }
        published = staging / 'result'
        published.mkdir()
        for name, pixels in (('map.png', image), ('map_mask.png', mask)):
            ok, encoded = cv2.imencode('.png', pixels)
            if not ok or not np.array_equal(cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED), pixels):
                raise ValueError(f'{name} 编码回读不一致')
            (published / name).write_bytes(encoded.tobytes())
        (published / 'map.yml').write_text(yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False), encoding='utf-8')
        _load_snapshot(map_id, (published / 'map.yml').read_bytes(), (published / 'map.png').read_bytes(), (published / 'map_mask.png').read_bytes())
        if output.exists():
            raise FileExistsError('输出目录已存在，未替换采集结果')
        published.rename(output)
