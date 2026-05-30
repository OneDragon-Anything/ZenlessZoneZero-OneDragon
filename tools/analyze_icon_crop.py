import argparse
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np


def read_image(path: str) -> np.ndarray:
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Failed to read image: {path}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def compute_ahash(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    small = cv2.resize(gray, (8, 8), interpolation=cv2.INTER_AREA)
    avg = float(small.mean())
    return (small >= avg).astype(np.uint8)


def ahash_distance(a: np.ndarray, b: np.ndarray) -> int:
    return int(np.count_nonzero(a != b))


def mse(a: np.ndarray, b: np.ndarray) -> float:
    diff = a.astype(np.float32) - b.astype(np.float32)
    return float(np.mean(diff * diff))


def hist_corr(a: np.ndarray, b: np.ndarray) -> float:
    # 3D color histogram correlation
    hist_a = cv2.calcHist([a], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
    hist_b = cv2.calcHist([b], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
    cv2.normalize(hist_a, hist_a)
    cv2.normalize(hist_b, hist_b)
    return float(cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL))


def hs_hist_corr(a: np.ndarray, b: np.ndarray) -> float:
    ah = cv2.cvtColor(a, cv2.COLOR_RGB2HSV)
    bh = cv2.cvtColor(b, cv2.COLOR_RGB2HSV)
    # 仅使用 H/S，尽量减少亮度(V)波动影响
    hist_a = cv2.calcHist([ah], [0, 1], None, [30, 32], [0, 180, 0, 256])
    hist_b = cv2.calcHist([bh], [0, 1], None, [30, 32], [0, 180, 0, 256])
    cv2.normalize(hist_a, hist_a)
    cv2.normalize(hist_b, hist_b)
    return float(cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL))


def normalize_luminance_gray(image: np.ndarray) -> np.ndarray:
    # LAB + CLAHE: 抵抗 UI 明暗变化
    bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    merged = cv2.merge([l, a, b])
    out_bgr = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
    out_gray = cv2.cvtColor(out_bgr, cv2.COLOR_BGR2GRAY)
    return out_gray


def ncc_norm(a: np.ndarray, b: np.ndarray) -> float:
    ag = normalize_luminance_gray(a)
    bg = normalize_luminance_gray(b)
    result = cv2.matchTemplate(ag, bg, cv2.TM_CCOEFF_NORMED)
    return float(result[0][0])


def edge_ncc(a: np.ndarray, b: np.ndarray) -> float:
    ag = normalize_luminance_gray(a)
    bg = normalize_luminance_gray(b)
    ae = cv2.Canny(ag, 50, 150)
    be = cv2.Canny(bg, 50, 150)
    result = cv2.matchTemplate(ae, be, cv2.TM_CCOEFF_NORMED)
    return float(result[0][0])


def ncc(a: np.ndarray, b: np.ndarray) -> float:
    # Use grayscale normalized cross-correlation
    ag = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
    bg = cv2.cvtColor(b, cv2.COLOR_RGB2GRAY)
    result = cv2.matchTemplate(ag, bg, cv2.TM_CCOEFF_NORMED)
    return float(result[0][0])


def sqdiff(a: np.ndarray, b: np.ndarray) -> float:
    # Use grayscale normalized squared difference
    ag = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
    bg = cv2.cvtColor(b, cv2.COLOR_RGB2GRAY)
    result = cv2.matchTemplate(ag, bg, cv2.TM_SQDIFF_NORMED)
    return float(result[0][0])


def score_icons(
    crop: np.ndarray,
    icon_paths: List[Path],
) -> Tuple[List[Tuple[str, float]], List[Tuple[str, float]], List[Tuple[str, float]], List[Tuple[str, float]], List[Tuple[str, int]], List[Tuple[str, float]], List[Tuple[str, float]]]:
    crop_h, crop_w = crop.shape[:2]
    crop_hash = compute_ahash(crop)

    ncc_scores = []
    sqdiff_scores = []
    mse_scores = []
    hist_scores = []
    ahash_scores = []
    ncc_norm_scores = []
    edge_ncc_scores = []

    for p in icon_paths:
        icon = read_image(str(p))
        icon_rs = cv2.resize(icon, (crop_w, crop_h), interpolation=cv2.INTER_AREA)

        ncc_scores.append((p.name, ncc(crop, icon_rs)))
        sqdiff_scores.append((p.name, sqdiff(crop, icon_rs)))
        mse_scores.append((p.name, mse(crop, icon_rs)))
        ncc_norm_scores.append((p.name, ncc_norm(crop, icon_rs)))
        edge_ncc_scores.append((p.name, edge_ncc(crop, icon_rs)))
        hist_scores.append((p.name, hs_hist_corr(crop, icon_rs)))
        ahash_scores.append((p.name, ahash_distance(crop_hash, compute_ahash(icon_rs))))

    ncc_scores.sort(key=lambda x: x[1], reverse=True)
    sqdiff_scores.sort(key=lambda x: x[1])  # lower is better
    mse_scores.sort(key=lambda x: x[1])  # lower is better
    hist_scores.sort(key=lambda x: x[1], reverse=True)
    ahash_scores.sort(key=lambda x: x[1])  # lower is better
    ncc_norm_scores.sort(key=lambda x: x[1], reverse=True)
    edge_ncc_scores.sort(key=lambda x: x[1], reverse=True)

    return ncc_scores, sqdiff_scores, mse_scores, hist_scores, ahash_scores, ncc_norm_scores, edge_ncc_scores


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze icon crop against IconRoleCircle assets.")
    parser.add_argument("crop", help="Path to crop image (jpg/png)")
    parser.add_argument("--icons", default="assets/wiki_data/icons", help="Directory containing IconRoleCircle*.webp")
    parser.add_argument("--top", type=int, default=10, help="Top N results per method")
    parser.add_argument("--expect", default="", help="Expected icon filename, e.g. IconRoleCircle40.webp")
    args = parser.parse_args()

    crop_path = args.crop
    icon_dir = args.icons

    crop = read_image(crop_path)
    icon_paths = sorted(Path(icon_dir).glob("IconRoleCircle*.webp"))
    if not icon_paths:
        raise FileNotFoundError(f"No IconRoleCircle*.webp found in {icon_dir}")

    ncc_scores, sqdiff_scores, mse_scores, hist_scores, ahash_scores, ncc_norm_scores, edge_ncc_scores = score_icons(crop, icon_paths)

    print(f"Crop: {crop_path}")
    print(f"Icons: {icon_dir} ({len(icon_paths)} files)")
    print("")

    def show(title: str, items: List[Tuple[str, float]]) -> None:
        print(title)
        for name, score in items[: args.top]:
            print(f"{name}\t{score:.6f}" if isinstance(score, float) else f"{name}\t{score}")
        print("")

    show("Top NCC (TM_CCOEFF_NORMED)", ncc_scores)
    show("Top SQDIFF (TM_SQDIFF_NORMED, lower better)", sqdiff_scores)
    show("Top MSE (lower better)", mse_scores)
    show("Top HS-Hist Corr (higher better, illumination robust)", hist_scores)
    show("Top NCC after CLAHE normalize (higher better)", ncc_norm_scores)
    show("Top Edge NCC (higher better, illumination robust)", edge_ncc_scores)
    show("Top aHash Distance (lower better)", ahash_scores)

    if args.expect:
        print(f"Expected: {args.expect}")

        def print_rank(method_name: str, items: List[Tuple[str, float]]) -> None:
            rank = next((idx + 1 for idx, (name, _) in enumerate(items) if name == args.expect), -1)
            print(f"{method_name}\tRank={rank}")

        print_rank("NCC", ncc_scores)
        print_rank("NCC_CLAHE", ncc_norm_scores)
        print_rank("Edge_NCC", edge_ncc_scores)
        print_rank("HS_Hist", hist_scores)
        print_rank("SQDIFF", sqdiff_scores)
        print_rank("MSE", mse_scores)
        print_rank("aHash", ahash_scores)

