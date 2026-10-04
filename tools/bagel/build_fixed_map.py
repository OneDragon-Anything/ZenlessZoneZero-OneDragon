"""从原生 1080p 新录像生成待验收底图，不操作游戏。"""

import argparse
from pathlib import Path

from zzz_od.application.bagel.bagel_map_builder import build_map
from zzz_od.application.bagel.bagel_route import SUPPORTED_MAP_IDS


def main() -> None:
    """录像先在出生点静止，再连续移动；输出目录必须尚不存在。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--map-id', choices=SUPPORTED_MAP_IDS, required=True)
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sampling-fps', type=float, default=5)
    args = parser.parse_args()
    build_map(args.map_id, args.video, args.output, args.sampling_fps)
    print('底图已生成；请核对定位和路线坐标后再替换正式资源。')


if __name__ == '__main__':
    main()
