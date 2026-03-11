import argparse
import hashlib
import json
import os
import shutil
import tempfile
import time
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path


PROJECT_NAME = "ZenlessZoneZero-OneDragon"
RUNTIME_ZIP_NAME = f"{PROJECT_NAME}-RuntimeLauncher.zip"
LATEST_MANIFEST_NAME = f"{PROJECT_NAME}-RuntimeLauncher-Update-Latest.json"


def _log(msg: str) -> None:
    print(msg, flush=True)


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest().upper()


def _download(url: str, dest: Path, token: str | None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": f"{PROJECT_NAME} CI",
        "Accept": "application/octet-stream",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp, dest.open("wb") as f:
                shutil.copyfileobj(resp, f)
            return
        except Exception as e:
            if attempt >= 3:
                raise
            _log(f"[attempt {attempt}/3] download failed: {url} — {e}")
            time.sleep(attempt * 2)


def _fetch_releases(owner: str, repo: str, token: str | None) -> list[dict]:
    headers = {
        "User-Agent": f"{PROJECT_NAME} CI",
        "Accept": "application/vnd.github+json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data if isinstance(data, list) else []


def _extract_zip(zip_path: Path, dest: Path) -> None:
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest)


def _build_file_index(root: Path) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        result[rel] = {
            "size": path.stat().st_size,
            "sha256": _sha256(path),
            "path": path,
        }
    return result


def _create_diff_zip(old_zip: Path, new_zip: Path, output_zip: Path, old_version: str, new_version: str) -> bool:
    with tempfile.TemporaryDirectory(prefix="runtime_update_diff_") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        old_dir = temp_dir / "old"
        new_dir = temp_dir / "new"
        old_dir.mkdir(parents=True, exist_ok=True)
        new_dir.mkdir(parents=True, exist_ok=True)
        _extract_zip(old_zip, old_dir)
        _extract_zip(new_zip, new_dir)

        old_index = _build_file_index(old_dir)
        new_index = _build_file_index(new_dir)

        added: list[str] = []
        modified: list[str] = []
        deleted = sorted(set(old_index.keys()) - set(new_index.keys()))

        changed_files: list[tuple[str, Path]] = []
        for rel, meta in new_index.items():
            if rel not in old_index:
                added.append(rel)
                changed_files.append((rel, meta["path"]))
                continue
            old_meta = old_index[rel]
            if meta["sha256"] != old_meta["sha256"]:
                modified.append(rel)
                changed_files.append((rel, meta["path"]))

        if not changed_files and not deleted:
            return False

        output_zip.parent.mkdir(parents=True, exist_ok=True)
        if output_zip.exists():
            output_zip.unlink()

        changes = {
            "from_version": old_version,
            "to_version": new_version,
            "added": sorted(added),
            "modified": sorted(modified),
            "deleted": deleted,
        }

        with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for rel, src_path in changed_files:
                zf.write(src_path, rel)
            zf.writestr("changes.json", json.dumps(changes, ensure_ascii=False, indent=2))
        return True


def _asset_download_url(github_homepage: str, tag: str, asset_name: str) -> str:
    return f"{github_homepage}/releases/download/{tag}/{asset_name}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate RuntimeLauncher runtime update assets.")
    parser.add_argument("--repo-root", default=".", help="Repository root")
    parser.add_argument("--release-version", required=True, help="Current release version")
    parser.add_argument("--runtime-zip", default=RUNTIME_ZIP_NAME, help="Current runtime zip filename")
    parser.add_argument("--owner", default="OneDragon-Anything", help="GitHub owner")
    parser.add_argument("--repo", default="ZenlessZoneZero-OneDragon", help="GitHub repo")
    parser.add_argument("--github-homepage", default="https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon", help="GitHub repository homepage")
    parser.add_argument("--s3-public-base-url", default="", help="Public S3/CDN base url")
    parser.add_argument("--history-count", default=5, type=int, help="How many previous versions to diff against")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    runtime_zip = repo_root / args.runtime_zip
    if not runtime_zip.exists():
        raise SystemExit(f"Missing runtime zip: {runtime_zip}")

    assets_root = repo_root / "runtime_update_assets"
    if assets_root.exists():
        shutil.rmtree(assets_root)
    assets_root.mkdir(parents=True, exist_ok=True)

    channel = "beta" if "-beta." in args.release_version else "stable"
    token = os.environ.get("GITHUB_TOKEN") or None
    s3_base_url = args.s3_public_base_url.strip().rstrip("/")

    s3_versions_dir = assets_root / "versions" / args.release_version
    s3_versions_dir.mkdir(parents=True, exist_ok=True)
    s3_channels_dir = assets_root / "channels" / channel
    s3_channels_dir.mkdir(parents=True, exist_ok=True)

    runtime_full_name = "runtime-full.zip"
    shutil.copy2(runtime_zip, s3_versions_dir / runtime_full_name)

    github_diff_assets: list[dict[str, object]] = []
    s3_diff_assets: list[dict[str, object]] = []

    releases = _fetch_releases(args.owner, args.repo, token)
    same_channel_releases = [
        release
        for release in releases
        if isinstance(release, dict)
        and not release.get("draft", False)
        and str(release.get("tag_name")) != args.release_version
        and bool(release.get("prerelease", False)) == (channel == "beta")
    ]

    for release in same_channel_releases[: args.history_count]:
        tag_name = str(release.get("tag_name", "")).strip()
        if not tag_name:
            continue

        asset_url = None
        for asset in release.get("assets", []):
            if isinstance(asset, dict) and asset.get("name") == RUNTIME_ZIP_NAME:
                asset_url = asset.get("browser_download_url")
                break
        if not asset_url:
            continue

        prev_zip = assets_root / f"{tag_name}-{RUNTIME_ZIP_NAME}"
        _log(f"Download previous runtime zip: {tag_name}")
        _download(str(asset_url), prev_zip, token)

        diff_name = f"{PROJECT_NAME}-RuntimeLauncher-diff-from-{tag_name}-to-{args.release_version}.zip"
        diff_output = assets_root / diff_name
        created = _create_diff_zip(prev_zip, runtime_zip, diff_output, tag_name, args.release_version)
        if not created:
            continue

        s3_diff_name = f"diff-from-{tag_name}.zip"
        shutil.copy2(diff_output, s3_versions_dir / s3_diff_name)
        shutil.copy2(diff_output, repo_root / diff_name)
        github_diff_assets.append(
            {
                "from": tag_name,
                "asset_name": diff_name,
                "sha256": _sha256(diff_output),
                "size": diff_output.stat().st_size,
            }
        )
        s3_diff_assets.append(
            {
                "from": tag_name,
                "asset_name": s3_diff_name,
                "sha256": _sha256(s3_versions_dir / s3_diff_name),
                "size": (s3_versions_dir / s3_diff_name).stat().st_size,
            }
        )

    manifest: dict[str, object] = {
        "version": args.release_version,
        "channel": channel,
        "release_notes": "",
        "published_at": datetime.now(UTC).isoformat(),
        "sources": {
            "github": {
                "full": {
                    "url": _asset_download_url(args.github_homepage, args.release_version, RUNTIME_ZIP_NAME),
                    "sha256": _sha256(runtime_zip),
                    "size": runtime_zip.stat().st_size,
                },
                "diffs": [
                    {
                        "from": item["from"],
                        "url": _asset_download_url(args.github_homepage, args.release_version, str(item["asset_name"])),
                        "sha256": item["sha256"],
                        "size": item["size"],
                    }
                    for item in github_diff_assets
                ],
            }
        },
    }

    if s3_base_url:
        manifest["sources"]["s3"] = {
            "full": {
                "url": f"{s3_base_url}/versions/{args.release_version}/{runtime_full_name}",
                "sha256": _sha256(s3_versions_dir / runtime_full_name),
                "size": (s3_versions_dir / runtime_full_name).stat().st_size,
            },
            "diffs": [
                {
                    "from": item["from"],
                    "url": f"{s3_base_url}/versions/{args.release_version}/{item['asset_name']}",
                    "sha256": item["sha256"],
                    "size": item["size"],
                }
                for item in s3_diff_assets
            ],
        }

    s3_manifest_path = s3_channels_dir / "latest.json"
    s3_manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    github_manifest_path = repo_root / LATEST_MANIFEST_NAME
    github_manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
