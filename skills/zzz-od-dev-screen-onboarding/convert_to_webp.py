"""PNG → webp(归档代表截图 / 整屏测试 fixture)。中文路径安全(np.fromfile + tofile,非 cv2.imread/imwrite)。

用法:
  python convert_to_webp.py <图片.png>              原地转 q90(保留原 PNG)
  python convert_to_webp.py <目录>                  批量原地转 q90(保留原 PNG)
  python convert_to_webp.py <目录> --delete         批量原地转 + 删原 PNG
  python convert_to_webp.py <图片.png> -o <目录>    转出到目录(保留原 PNG)
  python convert_to_webp.py <图片.png> -q 101       指定质量(默认 90,q101 无损)
整屏 q90 通常识别无损;精度 / OCR 敏感图可试 q101(无损)或保留 PNG。
"""
import argparse
from pathlib import Path

import cv2
import numpy as np


def convert(target: Path, quality: int, out_dir: Path | None, delete: bool) -> None:
    paths = [target] if target.is_file() else sorted(target.glob("*.png"))
    assert paths, f"无 PNG: {target}"
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
    tot_p = tot_w = 0
    for p in paths:
        img = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)
        assert img is not None, f"读取失败: {p}"
        sp = p.stat().st_size
        ok, buf = cv2.imencode(".webp", img, [cv2.IMWRITE_WEBP_QUALITY, quality])
        assert ok, f"编码失败: {p}"
        w = p.with_suffix(".webp") if out_dir is None else out_dir / p.with_suffix(".webp").name
        buf.tofile(str(w))
        sw = w.stat().st_size
        tot_p += sp
        tot_w += sw
        if delete:
            p.unlink()
        print(f"{p.name}: {sp // 1024}K -> {sw // 1024}K" + ("" if out_dir is None else f"  ({w})"))
    if len(paths) > 1:
        print(f"合计 {len(paths)} 张: {tot_p / 1048576:.1f}M -> {tot_w / 1048576:.1f}M (省 {(1 - tot_w / tot_p) * 100:.0f}%)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="PNG → webp(归档代表截图 / 整屏测试 fixture)。中文路径安全。默认原地转、保留原 PNG。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="整屏 q90 通常识别无损;精度(小地图角度)/ 含细文字 OCR 敏感 → 可试 q101(无损)或保留 PNG。",
    )
    parser.add_argument("path", help="PNG 文件(单张)或目录(批量转该目录所有 PNG)")
    parser.add_argument("-q", "--quality", type=int, default=90, help="webp 质量 0-101(默认 90;q101 无损)")
    parser.add_argument("-o", "--out", help="输出目录(保持原文件名,保留原 PNG);不指定则原地转(同目录)")
    parser.add_argument("--delete", action="store_true", help="转后删原 PNG(默认保留)")
    args = parser.parse_args()
    convert(Path(args.path), args.quality, Path(args.out) if args.out else None, args.delete)
