"""从原始录像与已核验帧坐标重建 04 固定底图，不操作游戏。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import warnings
from pathlib import Path

import cv2
import numpy as np
import yaml

ROOT: Path = Path(__file__).resolve().parents[2]


def fusion_mask(image: np.ndarray, outer_radius: int, inner_radius: int) -> np.ndarray:
    """复现已选方案的圆环和高亮标记遮罩，不推测被遮住的道路。"""
    mask = np.zeros((201, 201), np.uint8)
    cv2.circle(mask, (100, 100), outer_radius, 255, -1)
    cv2.circle(mask, (100, 100), inner_radius, 0, -1)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    dynamic = (
        ((hsv[:, :, 1] > 90) & (hsv[:, :, 2] > 130))
        | ((hsv[:, :, 1] < 60) & (hsv[:, :, 2] > 185))
    ).astype(np.uint8)
    mask[cv2.dilate(dynamic, np.ones((3, 3), np.uint8)) > 0] = 0
    return mask


def rebuild_map(map_id: str, video: Path, output: Path) -> None:
    """先在临时目录生成并核验摘要，再以元数据最后写入的顺序安装整组。"""
    if map_id not in ('janus_high_a', 'janus_high_b'):
        raise ValueError('不支持的固定地图')
    root = ROOT / 'assets/game_data/bagel' / map_id
    metadata_bytes = (root / 'map.yml').read_bytes()
    source_bytes = (root / 'map_sources.json').read_bytes()
    metadata = yaml.safe_load(metadata_bytes)
    source = json.loads(source_bytes)
    if hashlib.sha256(source_bytes).hexdigest() != metadata['sha256']['map_sources.json']:
        raise ValueError('制图来源清单摘要不一致')
    with video.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != source['video_sha256']:
        raise ValueError('输入录像与已核验来源不一致，不能套用这组帧坐标')
    if source['format_version'] != 1 or source['map_id'] != map_id or source['profile'] != 'min_channel_percentile_25':
        raise ValueError('未知制图来源格式')
    translations = [frame['translation'] for frame in source['frames']]
    points = np.asarray([point for point in translations if point is not None], dtype=float)
    if points.ndim != 2 or points.shape[1] != 2 or not np.isfinite(points).all():
        raise ValueError('制图帧坐标无效')
    origin = np.floor(points.min(axis=0)).astype(int) - 2
    size = np.ceil(points.max(axis=0)).astype(int) + 203 - origin
    if origin.tolist() != metadata['origin_xy'] or size.tolist() != metadata['size_wh']:
        raise ValueError('帧坐标与既有地图坐标不一致')
    width, height = (int(value) for value in size)
    cv2.setNumThreads(2)
    with tempfile.TemporaryDirectory(prefix='bagel-build-') as directory:
        staging = Path(directory)
        frames_dir = staging / 'frames'
        frames_dir.mkdir()
        x1, y1, x2, y2 = source['crop_xyxy']
        subprocess.run([
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(video.resolve()),
            '-vf', f'fps={source["sampling_fps"]},crop={x2-x1}:{y2-y1}:{x1}:{y1}:exact=1',
            '-fps_mode', 'passthrough', str(frames_dir / '%05d.png'),
        ], check=True)
        files = sorted(frames_dir.glob('*.png'))
        if len(files) != len(translations):
            raise ValueError('解码帧数量与制图来源不一致')
        shape = (len(files), height, width)
        values = np.memmap(staging / 'gray.bin', dtype=np.uint8, mode='w+', shape=shape)
        validity = np.memmap(staging / 'valid.bin', dtype=np.uint8, mode='w+', shape=shape)
        try:
            for index, (file, xy) in enumerate(zip(files, translations, strict=True)):
                payload = file.read_bytes()
                frame = source['frames'][index]
                if frame['index'] != index or hashlib.sha256(payload).hexdigest() != frame['sha256']:
                    raise ValueError(f'第 {index} 帧解码结果与核验素材不一致')
                if xy is None:
                    values[index] = 0
                    validity[index] = 0
                    continue
                image = cv2.imdecode(np.frombuffer(payload, np.uint8), cv2.IMREAD_COLOR)
                if image is None or image.shape != (201, 201, 3):
                    raise ValueError(f'第 {index} 帧尺寸无效')
                mask = fusion_mask(image, source['outer_radius'], source['inner_radius'])
                matrix = np.array([[1., 0., xy[0] - origin[0]], [0., 1., xy[1] - origin[1]]])
                values[index] = cv2.warpAffine(np.min(image, axis=2), matrix, (width, height))
                validity[index] = cv2.warpAffine(mask, matrix, (width, height), flags=cv2.INTER_NEAREST) > 0
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
            rgba = np.dstack([cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR), mask])
            for name, image in (('map.png', rgba), ('map_mask.png', mask)):
                encoded = cv2.imencode('.png', image)[1].tobytes()
                if hashlib.sha256(encoded).hexdigest() != metadata['sha256'][name]:
                    raise ValueError(f'{name} 与已选方案不一致；检查依赖版本和构建参数')
                (staging / name).write_bytes(encoded)
                decoded = cv2.imdecode(np.frombuffer(encoded, np.uint8), cv2.IMREAD_UNCHANGED)
                if not np.array_equal(decoded, image):
                    raise ValueError(f'{name} 回读不一致')
            (staging / 'map_sources.json').write_bytes(source_bytes)
            (staging / 'map.yml').write_bytes(metadata_bytes)
            output.mkdir(parents=True, exist_ok=True)
            # 单文件原子替换，元数据最后写；运行加载仍用摘要拒绝半更新状态。
            for name in ('map.png', 'map_mask.png', 'map_sources.json', 'map.yml'):
                pending = output / f'.{name}.pending'
                pending.write_bytes((staging / name).read_bytes())
                os.replace(pending, output / name)
        finally:
            del values, validity


def main() -> None:
    """输出路径必须显式给定，游戏运行和打开编辑器不会触发制图。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--map-id', choices=['janus_high_a', 'janus_high_b'], required=True)
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rebuild_map(args.map_id, args.video, args.output)
    print(f'已核验并输出：{args.output.resolve()}')


if __name__ == '__main__':
    main()
