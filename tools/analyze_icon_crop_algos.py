import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def load_rgb(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {path}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def ahash(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    small = cv2.resize(gray, (8, 8), interpolation=cv2.INTER_AREA)
    return (small >= small.mean()).astype(np.uint8)


def hamming(a: np.ndarray, b: np.ndarray) -> int:
    return int(np.count_nonzero(a != b))


def tm_ccoef(a: np.ndarray, b: np.ndarray) -> float:
    ag = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
    bg = cv2.cvtColor(b, cv2.COLOR_RGB2GRAY)
    return float(cv2.matchTemplate(ag, bg, cv2.TM_CCOEFF_NORMED)[0, 0])


def tm_sqdiff(a: np.ndarray, b: np.ndarray) -> float:
    ag = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
    bg = cv2.cvtColor(b, cv2.COLOR_RGB2GRAY)
    return float(cv2.matchTemplate(ag, bg, cv2.TM_SQDIFF_NORMED)[0, 0])


def edge_ccoef(a: np.ndarray, b: np.ndarray) -> float:
    ag = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
    bg = cv2.cvtColor(b, cv2.COLOR_RGB2GRAY)
    ae = cv2.Canny(ag, 50, 150)
    be = cv2.Canny(bg, 50, 150)
    return float(cv2.matchTemplate(ae, be, cv2.TM_CCOEFF_NORMED)[0, 0])


def hist_corr(a: np.ndarray, b: np.ndarray) -> float:
    ha = cv2.calcHist([a], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
    hb = cv2.calcHist([b], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
    cv2.normalize(ha, ha)
    cv2.normalize(hb, hb)
    return float(cv2.compareHist(ha, hb, cv2.HISTCMP_CORREL))


def mse(a: np.ndarray, b: np.ndarray) -> float:
    d = a.astype(np.float32) - b.astype(np.float32)
    return float(np.mean(d * d))


def rank_of(scores: list[tuple[str, float]], name: str) -> int:
    for idx, (n, _) in enumerate(scores, 1):
        if n == name:
            return idx
    return -1


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze one icon crop against IconRoleCircle templates")
    parser.add_argument("crop", help="Path to crop image")
    parser.add_argument("--icons", default="assets/wiki_data/icons", help="IconRoleCircle*.webp dir")
    parser.add_argument("--expect", default="IconRoleCircle40.webp", help="Expected icon filename")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--out", default=".debug/icon_matching_test")
    args = parser.parse_args()

    crop_path = Path(args.crop)
    icon_dir = Path(args.icons)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    crop = load_rgb(crop_path)
    h, w = crop.shape[:2]
    crop_hash = ahash(crop)

    methods = {
        "tm_ccoef": {"higher": True, "scores": []},
        "tm_sqdiff": {"higher": False, "scores": []},
        "edge_ccoef": {"higher": True, "scores": []},
        "hist_corr": {"higher": True, "scores": []},
        "mse": {"higher": False, "scores": []},
        "ahash_dist": {"higher": False, "scores": []},
    }

    icon_paths = sorted(icon_dir.glob("IconRoleCircle*.webp"))
    if not icon_paths:
        raise FileNotFoundError(f"No IconRoleCircle*.webp in {icon_dir}")

    for p in icon_paths:
        icon = load_rgb(p)
        icon = cv2.resize(icon, (w, h), interpolation=cv2.INTER_AREA)
        methods["tm_ccoef"]["scores"].append((p.name, tm_ccoef(crop, icon)))
        methods["tm_sqdiff"]["scores"].append((p.name, tm_sqdiff(crop, icon)))
        methods["edge_ccoef"]["scores"].append((p.name, edge_ccoef(crop, icon)))
        methods["hist_corr"]["scores"].append((p.name, hist_corr(crop, icon)))
        methods["mse"]["scores"].append((p.name, mse(crop, icon)))
        methods["ahash_dist"]["scores"].append((p.name, float(hamming(crop_hash, ahash(icon)))))

    n_icons = len(icon_paths)
    ensemble = {p.name: 0.0 for p in icon_paths}
    report = {
        "crop": str(crop_path),
        "expect": args.expect,
        "iconCount": n_icons,
        "methods": {},
    }

    print(f"Crop: {crop_path}")
    print(f"Icons: {icon_dir} ({n_icons})")
    print(f"Expected: {args.expect}\\n")

    for method_name, cfg in methods.items():
        scores = cfg["scores"]
        scores.sort(key=lambda x: x[1], reverse=cfg["higher"])
        rank = rank_of(scores, args.expect)
        report["methods"][method_name] = {
            "rankOfExpected": rank,
            "top": [{"icon": n, "score": float(s)} for n, s in scores[: args.top]],
        }
        for rank_idx, (name, _) in enumerate(scores, 1):
            ensemble[name] += (n_icons - rank_idx + 1)

        print(f"[{method_name}] rank(expect)={rank}")
        for name, score in scores[: args.top]:
            print(f"  {name:<24} {score:.6f}")
        print()

    ensemble_scores = sorted(ensemble.items(), key=lambda x: x[1], reverse=True)
    ensemble_rank = rank_of(ensemble_scores, args.expect)
    report["ensemble"] = [{"icon": n, "score": float(s)} for n, s in ensemble_scores[: args.top]]
    report["ensembleRankOfExpected"] = ensemble_rank

    print(f"[ensemble] rank(expect)={ensemble_rank}")
    for name, score in ensemble_scores[: args.top]:
        print(f"  {name:<24} {score:.2f}")

    out_json = out_dir / f"analysis_{crop_path.stem}.json"
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    try:
        out_json.write_text(payload, encoding="utf-8")
        print(f"\\nSaved: {out_json}")
    except PermissionError:
        fallback = Path(".debug") / f"analysis_{crop_path.stem}.json"
        fallback.parent.mkdir(parents=True, exist_ok=True)
        fallback.write_text(payload, encoding="utf-8")
        print(f"\\nSaved (fallback): {fallback}")

