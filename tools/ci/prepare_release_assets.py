import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path


def _log(msg: str) -> None:
    print(msg, flush=True)


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True)


def _download(url: str, dest: Path, *, token: str | None = None, retries: int = 3, timeout: int = 60) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)

    headers = {
        "User-Agent": "ZenlessZoneZero-OneDragon CI",
        "Accept": "application/octet-stream",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp, dest.open("wb") as f:
                shutil.copyfileobj(resp, f)
            return
        except Exception as e:
            _log(f"[attempt {attempt}/{retries}] Download failed: {url} — {e}")
            if attempt < retries:
                time.sleep(2 * attempt)
            else:
                raise


def _fetch_json(url: str, *, token: str | None = None, retries: int = 3, timeout: int = 60) -> object:
    headers = {
        "User-Agent": "ZenlessZoneZero-OneDragon CI",
        "Accept": "application/vnd.github+json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            _log(f"[attempt {attempt}/{retries}] JSON fetch failed: {url} — {e}")
            if attempt < retries:
                time.sleep(2 * attempt)
            else:
                raise


def _get_latest_model_asset(repo: str, pattern: str, *, token: str | None = None) -> dict | None:
    api_url = f"https://api.github.com/repos/{repo}/releases"
    data = _fetch_json(api_url, token=token)
    if not isinstance(data, list):
        return None

    rx = re.compile(pattern)
    best: dict | None = None
    max_number = -1

    for release in data:
        if not isinstance(release, dict):
            continue
        assets = release.get("assets")
        if not isinstance(assets, list):
            continue

        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = asset.get("name")
            if not isinstance(name, str):
                continue
            if not rx.search(name):
                continue

            url = asset.get("browser_download_url")
            if not isinstance(url, str) or not url:
                continue

            m = re.search(r"(\d{8})\.zip$", name)
            if m:
                number = int(m.group(1))
                if number > max_number:
                    max_number = number
                    best = {
                        "url": url,
                        "name": name,
                        "version_number": number,
                    }
            elif best is None:
                best = {
                    "url": url,
                    "name": name,
                    "version_number": 0,
                }

    return best


def _extract_zip(zip_path: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)


def _zip_dir_contents(
    root_dir: Path,
    zip_path: Path,
    *,
    root_prefix: str,
    exclude_prefixes: set[str] | None = None,
) -> None:
    """把 root_dir 下的内容打进 zip，可选 root_prefix 和排除前缀。"""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()

    prefix = root_prefix.strip("/\\")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in root_dir.rglob("*"):
            if p.is_file():
                rel = p.relative_to(root_dir).as_posix()
                if exclude_prefixes and any(rel.startswith(ep) for ep in exclude_prefixes):
                    continue
                arcname = f"{prefix}/{rel}" if prefix else rel
                zf.write(p, arcname)


def _zip_single_file(file_path: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.write(file_path, file_path.name)


# ---- 模型资源配置 ----

_MODEL_CONFIGS: list[dict[str, str]] = [
    {
        "label": "ppocrv5",
        "repo": "OneDragon-Anything/OneDragon-Env",
        "pattern": r"ppocrv5\.zip$",
        "dest_folder": "onnx_ocr",
        "fallback_url": "https://github.com/OneDragon-Anything/OneDragon-Env/releases/download/ppocrv5/ppocrv5.zip",
        "fallback_name": "ppocrv5",
    },
    {
        "label": "flash",
        "repo": "OneDragon-Anything/OneDragon-YOLO",
        "pattern": r"flash.*\.zip$",
        "dest_folder": "flash_classifier",
        "fallback_url": "https://github.com/OneDragon-Anything/OneDragon-YOLO/releases/download/zzz_model/yolov8n-640-flash-0127.zip",
        "fallback_name": "yolov8n-640-flash-0127",
    },
    {
        "label": "hollow",
        "repo": "OneDragon-Anything/OneDragon-YOLO",
        "pattern": r"hollow.*\.zip$",
        "dest_folder": "hollow_zero_event",
        "fallback_url": "https://github.com/OneDragon-Anything/OneDragon-YOLO/releases/download/zzz_model/yolov8s-736-hollow-zero-event-0126.zip",
        "fallback_name": "yolov8s-736-hollow-zero-event-0126",
    },
    {
        "label": "lost_void_det",
        "repo": "OneDragon-Anything/OneDragon-YOLO",
        "pattern": r"lost.*\.zip$",
        "dest_folder": "lost_void_det",
        "fallback_url": "https://github.com/OneDragon-Anything/OneDragon-YOLO/releases/download/zzz_model/yolov8n-736-lost-void-det-20250612.zip",
        "fallback_name": "yolov8n-736-lost-void-det-20250612",
    },
]


def _download_models(model_base: Path, temp_dir: Path, *, token: str | None) -> None:
    """根据 _MODEL_CONFIGS 下载并解压所有模型到 assets/models/。"""
    for cfg in _MODEL_CONFIGS:
        dest = model_base / cfg["dest_folder"]
        dest.mkdir(parents=True, exist_ok=True)

        _log(f"Resolve {cfg['label']} model")
        asset = _get_latest_model_asset(cfg["repo"], cfg["pattern"], token=token)

        tmp_zip = temp_dir / f"{cfg['label']}.zip"
        if asset:
            folder_name = asset["name"].removesuffix(".zip")
            url = asset["url"]
        else:
            folder_name = cfg["fallback_name"]
            url = cfg["fallback_url"]

        _log(f"Download: {url}")
        _download(url, tmp_zip, token=token)
        target = dest / folder_name
        target.mkdir(parents=True, exist_ok=True)
        _extract_zip(tmp_zip, target)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare release assets and package Full/Full-Environment.")
    parser.add_argument("--repo-root", default=".", help="Repository root (default: .)")
    parser.add_argument("--release-version", required=True, help="Release version")
    parser.add_argument("--dist-src", default="deploy/dist", help="Downloaded dist artifact directory")
    parser.add_argument("--dist-name", default="dist", help="Name of dist directory after moving to parent")
    parser.add_argument("--env-dir", default=".install", help="Offline env directory in repo root")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    release_version = args.release_version

    # token通过环境变量注入
    token = os.environ.get("GITHUB_TOKEN", "")

    dist_src = (repo_root / args.dist_src).resolve()
    if not dist_src.exists():
        raise SystemExit(f"dist-src not found: {dist_src}")

    parent_dir = repo_root.parent
    dist_dir = (parent_dir / args.dist_name).resolve()

    # 1. 先把 deploy/dist 挪到 repo 外，避免后续 git clean 把产物删掉
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    _log(f"Move dist: {dist_src} -> {dist_dir}")
    shutil.move(str(dist_src), str(dist_dir))

    # 2. 清理工作区（仅清理 repo 内），确保打包内容可控
    _log("Clean repo via git reset/clean")
    _run(["git", "reset", "--hard", "HEAD"], cwd=repo_root)
    _run(["git", "clean", "-fd"], cwd=repo_root)

    # 3. 准备 .install 离线资源
    env_dir = repo_root / args.env_dir
    env_dir.mkdir(parents=True, exist_ok=True)

    _log("Download offline uv + cpython")
    _download(
        "https://github.com/OneDragon-Anything/OneDragon-Env/releases/download/ZenlessZoneZero-OneDragon/uv-x86_64-pc-windows-msvc.zip",
        env_dir / "uv-x86_64-pc-windows-msvc.zip",
        token=token or None,
    )
    _download(
        "https://github.com/OneDragon-Anything/OneDragon-Env/releases/download/ZenlessZoneZero-OneDragon/cpython-3.11.zip",
        env_dir / "cpython-3.11.zip",
        token=token or None,
    )

    # 4. 检查是否有已签名的可执行文件，如果有则替换
    signed_dir = dist_dir / "signed"
    if signed_dir.exists():
        _log("Found signed executables, replacing...")
        for exe_name, parent in [
            ("OneDragon-Installer.exe", dist_dir),
            ("OneDragon-Launcher.exe", dist_dir),
            ("OneDragon-RuntimeLauncher.exe", dist_dir / "OneDragon-RuntimeLauncher"),
        ]:
            signed = signed_dir / exe_name
            if signed.exists():
                _log(f"  Replacing {exe_name}")
                shutil.copy2(signed, parent / exe_name)

    # 5. 打包启动器
    installer_exe = dist_dir / "OneDragon-Installer.exe"
    launcher_exe = dist_dir / "OneDragon-Launcher.exe"
    runtime_launcher_dir = dist_dir / "OneDragon-RuntimeLauncher"
    runtime_launcher_exe = runtime_launcher_dir / "OneDragon-RuntimeLauncher.exe"

    if not installer_exe.exists():
        raise SystemExit(f"Missing {installer_exe}")
    if not launcher_exe.exists():
        raise SystemExit(f"Missing {launcher_exe}")
    if not runtime_launcher_dir.exists():
        raise SystemExit(f"Missing {runtime_launcher_dir}")
    if not runtime_launcher_exe.exists():
        raise SystemExit(f"Missing {runtime_launcher_exe}")

    shutil.copy2(installer_exe, repo_root / "OneDragon-Installer.exe")
    shutil.copy2(launcher_exe, repo_root / "OneDragon-Launcher.exe")

    # 打包两个启动器（集成启动器不复制到 repo_root，避免混入 Full/Full-Environment）
    launcher_zip = dist_dir / "ZenlessZoneZero-OneDragon-Launcher.zip"
    _zip_single_file(launcher_exe, launcher_zip)

    runtime_launcher_zip = dist_dir / "ZenlessZoneZero-OneDragon-RuntimeLauncher.zip"
    _zip_dir_contents(runtime_launcher_dir, runtime_launcher_zip, root_prefix="", exclude_prefixes={"src/"})

    # WithRuntime: 集成启动器 + src（首次安装用，无需 git clone）
    with_runtime_zip = dist_dir / f"ZenlessZoneZero-OneDragon-{release_version}-WithRuntime.zip"
    _log(f"Create WithRuntime zip: {with_runtime_zip}")
    _zip_dir_contents(runtime_launcher_dir, with_runtime_zip, root_prefix="")

    # 6. 下载并解压模型到 assets/models
    temp_dir = repo_root / "temp_models"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    _download_models(repo_root / "assets/models", temp_dir, token=token or None)

    # 清理临时模型目录（避免打包进 Full/Full-Environment）
    shutil.rmtree(temp_dir, ignore_errors=True)

    # 7. Full 包清单 + 打包（在 repo_root 下打包全部内容；zip 输出在 dist_dir 以避免自包含）
    _log("Generate install manifest (Full)")
    _run([sys.executable, "tools/ci/generate_install_manifest.py"], cwd=repo_root)

    full_zip = dist_dir / f"ZenlessZoneZero-OneDragon-{release_version}-Full.zip"
    _log(f"Create Full zip: {full_zip}")
    _zip_dir_contents(repo_root, full_zip, root_prefix=f"ZenlessZoneZero-OneDragon-{release_version}-Full")

    # 8. Full-Environment：把环境包放入 .install 后重新生成清单并打包
    env_zip = dist_dir / "ZenlessZoneZero-OneDragon-Environment.zip"
    if not env_zip.exists():
        raise SystemExit(f"Missing {env_zip}")

    shutil.copy2(env_zip, env_dir / "ZenlessZoneZero-OneDragon-Environment.zip")

    _log("Generate install manifest (Full-Environment)")
    _run([sys.executable, "tools/ci/generate_install_manifest.py"], cwd=repo_root)

    full_env_zip = dist_dir / f"ZenlessZoneZero-OneDragon-{release_version}-Full-Environment.zip"
    _log(f"Create Full-Environment zip: {full_env_zip}")
    _zip_dir_contents(repo_root, full_env_zip, root_prefix=f"ZenlessZoneZero-OneDragon-{release_version}-Full-Environment")

    # 9. 复制安装器到版本化文件名
    shutil.copy2(repo_root / "OneDragon-Installer.exe", repo_root / f"ZenlessZoneZero-OneDragon-{release_version}-Installer.exe")

    # 10. 把 dist_dir 下所有 zip 移到 repo_root，供 release step 上传
    for z in dist_dir.glob("*.zip"):
        _log(f"Move zip to repo root: {z.name}")
        shutil.move(str(z), str(repo_root / z.name))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
