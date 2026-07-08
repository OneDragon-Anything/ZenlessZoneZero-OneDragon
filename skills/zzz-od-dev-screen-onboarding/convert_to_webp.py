"""PNG → webp q90(归档代表截图 / 整屏测试 fixture)。中文路径安全(np.fromfile + tofile,非 cv2.imread/imwrite)。

用法:
  python convert_to_webp.py <图片.png>   单张
  python convert_to_webp.py <目录>       目录下所有 PNG(批量)
转后删原 PNG。整屏通常识别无损;但精度(小地图角度)/ 含细文字 OCR 压前先实测验证。
"""
import argparse
from pathlib import Path

import cv2
import numpy as np


def convert(target: Path) -> None:
    paths = [target] if target.is_file() else sorted(target.glob("*.png"))
    assert paths, f"无 PNG: {target}"
    tot_p = tot_w = 0
    for p in paths:
        img = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)
        assert img is not None, f"读取失败: {p}"
        sp = p.stat().st_size
        ok, buf = cv2.imencode(".webp", img, [cv2.IMWRITE_WEBP_QUALITY, 90])
        assert ok, f"编码失败: {p}"
        w = p.with_suffix(".webp")
        buf.tofile(str(w))
        sw = w.stat().st_size
        tot_p += sp
        tot_w += sw
        p.unlink()
        print(f"{p.name}: {sp // 1024}K -> {sw // 1024}K")
    if len(paths) > 1:
        print(f"合计 {len(paths)} 张: {tot_p / 1048576:.1f}M -> {tot_w / 1048576:.1f}M (省 {(1 - tot_w / tot_p) * 100:.0f}%)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="PNG → webp q90(归档代表截图 / 整屏测试 fixture)。中文路径安全。转后删原 PNG。",
        epilog="整屏通常识别无损;精度(小地图角度)/ 含细文字 OCR 压前先实测验证。",
    )
    parser.add_argument("path", help="PNG 文件(单张)或目录(批量转该目录下所有 PNG)")
    convert(Path(parser.parse_args().path))
