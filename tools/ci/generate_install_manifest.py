import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


_DEFAULT_EXCLUDE_PREFIXES: list[str] = ["dist/", "deploy/build/", ".venv/", ".install/uv_cache/"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate install manifest for offline installer move/verify.")
    parser.add_argument("--root", default=".", help="Root directory to scan (default: .)")
    parser.add_argument("--output", default="install_manifest.json", help="Output manifest path")
    parser.add_argument(
        "--exclude-prefix",
        action="append",
        default=None,
        metavar="PREFIX",
        help=(
            "Exclude path prefix (posix) relative to root. "
            "Can be specified multiple times. "
            f"Defaults to: {', '.join(_DEFAULT_EXCLUDE_PREFIXES)}"
        ),
    )
    parser.add_argument(
        "--ignore-read-errors",
        action="store_true",
        help="Skip files that cannot be read/hashed (NOT recommended for CI)",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    output_path = Path(args.output)
    output_abs = output_path.resolve() if output_path.is_absolute() else (root / output_path).resolve()

    raw_prefixes: list[str] = args.exclude_prefix if args.exclude_prefix is not None else _DEFAULT_EXCLUDE_PREFIXES
    exclude_prefixes: list[str] = []
    for p in raw_prefixes:
        if not p:
            continue
        norm = p.replace("\\", "/")
        if not norm.endswith("/"):
            norm += "/"
        exclude_prefixes.append(norm)

    version = os.environ.get("RELEASE_VERSION") or os.environ.get("GITHUB_REF_NAME") or ""
    generated_at = datetime.now(UTC).isoformat()

    entries: list[dict] = []
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue

        # 永远不要把输出文件本身纳入清单，否则二次生成时会出现 sha 与最终文件内容不一致
        try:
            if file_path.resolve() == output_abs:
                continue
        except Exception:
            # resolve 失败时退化为字符串比较
            if str(file_path).lower() == str(output_abs).lower():
                continue

        rel = file_path.relative_to(root).as_posix()
        if any(rel.startswith(prefix) for prefix in exclude_prefixes):
            continue

        try:
            entries.append(
                {
                    "path": rel,
                    "size": file_path.stat().st_size,
                    "sha256": sha256(file_path),
                }
            )
        except OSError:
            if args.ignore_read_errors:
                continue
            raise

    entries.sort(key=lambda x: x["path"])

    manifest = {
        "version": version,
        "generated_at": generated_at,
        "files": entries,
    }

    output_abs.parent.mkdir(parents=True, exist_ok=True)
    output_abs.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
