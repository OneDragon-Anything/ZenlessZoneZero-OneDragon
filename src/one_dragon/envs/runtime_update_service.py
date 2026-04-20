import hashlib
import json
import os
import shutil
import subprocess
import textwrap
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from one_dragon.envs.env_config import EnvConfig, RuntimeUpdateSourceEnum
from one_dragon.envs.git_service import GitService
from one_dragon.envs.project_config import ProjectConfig
from one_dragon.utils import app_utils, os_utils
from one_dragon.utils.log_utils import log

RUNTIME_LAUNCHER_EXE = "OneDragon-RuntimeLauncher.exe"
RUNTIME_DIR_NAME = ".runtime"
RUNTIME_UPDATE_STATE = "runtime_update_state.json"
RUNTIME_UPDATE_LATEST_ASSET = "ZenlessZoneZero-OneDragon-RuntimeLauncher-Update-Latest.json"
S3_SOURCE = RuntimeUpdateSourceEnum.S3.value.value
GITHUB_SOURCE = RuntimeUpdateSourceEnum.GITHUB.value.value
AUTO_SOURCE = RuntimeUpdateSourceEnum.AUTO.value.value
MIRROR_SOURCE = RuntimeUpdateSourceEnum.MIRROR.value.value


@dataclass
class RuntimeUpdateSourcePayload:
    source: str
    full: dict[str, Any] | None
    diffs: list[dict[str, Any]]


@dataclass
class RuntimeUpdateCheckResult:
    current_version: str
    target_version: str
    channel: str
    release_notes: str
    selected_source: str
    selected_kind: str
    selected_item: dict[str, Any]
    available_sources: list[str]
    published_at: str = ""

    @property
    def has_update(self) -> bool:
        return bool(self.current_version != self.target_version and self.selected_item)


@dataclass
class RuntimePreparedUpdate:
    check_result: RuntimeUpdateCheckResult
    package_path: Path
    extract_dir: Path
    backup_dir: Path
    script_path: Path
    state_path: Path
    log_path: Path
    changes: dict[str, Any] | None


class RuntimeUpdateService:

    def __init__(self, project_config: ProjectConfig, env_config: EnvConfig, git_service: GitService):
        self.project_config = project_config
        self.env_config = env_config
        self.git_service = git_service
        self.work_dir = Path(os_utils.get_work_dir())

    @property
    def current_exe_path(self) -> Path:
        return self.work_dir / RUNTIME_LAUNCHER_EXE

    @property
    def runtime_dir_path(self) -> Path:
        return self.work_dir / RUNTIME_DIR_NAME

    @property
    def state_file_path(self) -> Path:
        return self.work_dir / RUNTIME_UPDATE_STATE

    @property
    def debug_runtime_update_dir(self) -> Path:
        return Path(os_utils.get_path_under_work_dir(".debug", "runtime_update"))

    def get_current_version(self) -> str:
        if not self.current_exe_path.exists():
            return ""
        return app_utils.get_exe_version(str(self.current_exe_path))

    def get_available_sources(self) -> list[tuple[str, str]]:
        sources = [(AUTO_SOURCE, "自动"), (GITHUB_SOURCE, "GitHub")]
        if self._get_s3_manifest_url("stable"):
            sources.insert(1, (S3_SOURCE, "S3/CDN"))
        return sources

    def check_for_updates(self, channel: str, preferred_source: str) -> RuntimeUpdateCheckResult:
        current_version = self.get_current_version()

        if preferred_source == AUTO_SOURCE:
            result = self._check_by_priority(channel)
        elif preferred_source == S3_SOURCE:
            manifest = self._fetch_manifest_from_s3(channel)
            result = self._select_update_from_manifest(manifest, current_version, channel, S3_SOURCE)
        elif preferred_source == GITHUB_SOURCE:
            manifest = self._fetch_manifest_from_github(channel)
            result = self._select_update_from_manifest(manifest, current_version, channel, GITHUB_SOURCE)
        else:
            raise ValueError(f"不支持的更新源: {preferred_source}")

        result.current_version = current_version
        return result

    def download_and_prepare_update(
        self,
        check_result: RuntimeUpdateCheckResult,
        progress_signal: dict[str, str | None] | None = None,
        progress_callback=None,
    ) -> RuntimePreparedUpdate:
        target_version = check_result.target_version
        selected_source = check_result.selected_source
        selected_kind = check_result.selected_kind
        selected_item = check_result.selected_item

        stage_root = self.work_dir / ".update_staging" / f"{target_version}_{selected_source}"
        extract_dir = stage_root / "extract"
        backup_dir = self.work_dir / ".update_backup"
        log_dir = self.debug_runtime_update_dir
        script_path = stage_root / "apply_runtime_update.ps1"
        package_name = (
            f"{selected_kind}-{selected_source}-{target_version}.zip"
            if selected_kind == "diff"
            else f"{selected_kind}-{selected_source}-{target_version}.zip"
        )
        package_path = stage_root / package_name

        if stage_root.exists():
            shutil.rmtree(stage_root, ignore_errors=True)
        stage_root.mkdir(parents=True, exist_ok=True)
        extract_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)

        download_url = self._apply_download_proxy(selected_item["url"])
        if not self._download_file(download_url, package_path, progress_signal, progress_callback):
            raise RuntimeError("下载更新包失败")

        expected_sha = selected_item.get("sha256")
        if expected_sha:
            actual_sha = self._sha256(package_path)
            if actual_sha.upper() != str(expected_sha).upper():
                raise RuntimeError("更新包校验失败")

        self._extract_zip(package_path, extract_dir)

        changes = None
        if selected_kind == "diff":
            changes_path = extract_dir / "changes.json"
            if not changes_path.is_file():
                raise RuntimeError("diff 包缺少 changes.json")
            changes = json.loads(changes_path.read_text(encoding="utf-8"))

        log_path = log_dir / f"runtime_update_{os_utils.now_timestamp_str()}.log"
        self._write_apply_script(
            script_path=script_path,
            current_pid=os.getpid(),
            extract_dir=extract_dir,
            backup_dir=backup_dir,
            log_path=log_path,
            state_path=self.state_file_path,
            target_version=target_version,
            source=selected_source,
            kind=selected_kind,
            changes=changes,
        )

        return RuntimePreparedUpdate(
            check_result=check_result,
            package_path=package_path,
            extract_dir=extract_dir,
            backup_dir=backup_dir,
            script_path=script_path,
            state_path=self.state_file_path,
            log_path=log_path,
            changes=changes,
        )

    def launch_apply_script(self, prepared_update: RuntimePreparedUpdate) -> None:
        subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(prepared_update.script_path),
            ],
            cwd=str(self.work_dir),
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )

    def _check_by_priority(self, channel: str) -> RuntimeUpdateCheckResult:
        current_version = self.get_current_version()
        manifest = None
        sources: list[str] = []

        try:
            manifest = self._fetch_manifest_from_s3(channel)
            sources.append(S3_SOURCE)
            return self._select_update_from_manifest(manifest, current_version, channel, AUTO_SOURCE)
        except Exception as e:
            log.warning(f"S3/CDN 更新检查失败，准备回退到 GitHub: {e}")

        manifest = self._fetch_manifest_from_github(channel)
        sources.append(GITHUB_SOURCE)
        result = self._select_update_from_manifest(manifest, current_version, channel, GITHUB_SOURCE)
        result.available_sources = sources
        return result

    def _select_update_from_manifest(
        self,
        manifest: dict[str, Any],
        current_version: str,
        channel: str,
        preferred_source: str,
    ) -> RuntimeUpdateCheckResult:
        target_version = str(manifest.get("version", "")).strip()
        if not target_version:
            raise RuntimeError("latest.json 缺少 version")

        sources = manifest.get("sources", {})
        if not isinstance(sources, dict):
            raise RuntimeError("latest.json 缺少 sources")

        source_order = (
            [S3_SOURCE, GITHUB_SOURCE]
            if preferred_source == AUTO_SOURCE
            else [preferred_source]
        )
        available_sources = [key for key in source_order if key in sources]

        for source in source_order:
            payload = self._parse_source_payload(source, sources.get(source))
            if payload is None:
                continue
            diff_item = self._find_diff(payload.diffs, current_version)
            if current_version and diff_item is not None:
                return RuntimeUpdateCheckResult(
                    current_version=current_version,
                    target_version=target_version,
                    channel=channel,
                    release_notes=str(manifest.get("release_notes", "")),
                    selected_source=source,
                    selected_kind="diff",
                    selected_item=diff_item,
                    available_sources=available_sources,
                    published_at=str(manifest.get("published_at", "")),
                )
            if payload.full is not None:
                return RuntimeUpdateCheckResult(
                    current_version=current_version,
                    target_version=target_version,
                    channel=channel,
                    release_notes=str(manifest.get("release_notes", "")),
                    selected_source=source,
                    selected_kind="full",
                    selected_item=payload.full,
                    available_sources=available_sources,
                    published_at=str(manifest.get("published_at", "")),
                )

        raise RuntimeError("没有可用的 RuntimeLauncher 更新包")

    @staticmethod
    def _parse_source_payload(source: str, payload: Any) -> RuntimeUpdateSourcePayload | None:
        if not isinstance(payload, dict):
            return None
        full = payload.get("full")
        diffs = payload.get("diffs", [])
        return RuntimeUpdateSourcePayload(
            source=source,
            full=full if isinstance(full, dict) else None,
            diffs=diffs if isinstance(diffs, list) else [],
        )

    @staticmethod
    def _find_diff(diffs: list[dict[str, Any]], current_version: str) -> dict[str, Any] | None:
        for item in diffs:
            if not isinstance(item, dict):
                continue
            if str(item.get("from", "")).strip() == current_version:
                return item
        return None

    def _fetch_manifest_from_s3(self, channel: str) -> dict[str, Any]:
        url = self._get_s3_manifest_url(channel)
        if not url:
            raise RuntimeError("未配置 S3/CDN 更新地址")
        return self._fetch_json(url)

    def _fetch_manifest_from_github(self, channel: str) -> dict[str, Any]:
        latest_stable, latest_beta = self.git_service.get_latest_tag()
        target_tag = latest_beta if channel == "beta" else latest_stable
        if not target_tag:
            raise RuntimeError("无法获取 GitHub 最新标签")

        manifest_url = (
            f"{self.project_config.github_homepage}/releases/download/"
            f"{target_tag}/{RUNTIME_UPDATE_LATEST_ASSET}"
        )
        try:
            return self._fetch_json(manifest_url)
        except Exception as e:
            log.warning(f"GitHub latest.json 获取失败，使用全量包兜底: {e}")
            zip_name = f"{self.project_config.project_name}-RuntimeLauncher.zip"
            full_url = (
                f"{self.project_config.github_homepage}/releases/download/"
                f"{target_tag}/{zip_name}"
            )
            return {
                "version": target_tag,
                "channel": channel,
                "release_notes": "",
                "published_at": "",
                "sources": {
                    GITHUB_SOURCE: {
                        "full": {
                            "url": full_url,
                            "sha256": "",
                            "size": 0,
                        },
                        "diffs": [],
                    }
                },
            }

    def _get_s3_manifest_url(self, channel: str) -> str:
        base_url = str(self.project_config.runtime_update_cdn_base_url or "").strip().rstrip("/")
        if not base_url:
            return ""
        return f"{base_url}/channels/{channel}/latest.json"

    def _fetch_json(self, url: str) -> dict[str, Any]:
        final_url = self._apply_download_proxy(url)
        req = urllib.request.Request(
            final_url,
            headers={
                "User-Agent": "ZenlessZoneZero-OneDragon Runtime Updater",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if not isinstance(data, dict):
                raise RuntimeError("latest.json 内容不合法")
            return data

    def _apply_download_proxy(self, url: str) -> str:
        if "github.com" in url and self.env_config.is_gh_proxy and self.env_config.gh_proxy_url:
            return f"{self.env_config.gh_proxy_url.rstrip('/')}/{url}"
        return url

    def _download_file(
        self,
        url: str,
        dest: Path,
        progress_signal: dict[str, str | None] | None = None,
        progress_callback=None,
    ) -> bool:
        dest.parent.mkdir(parents=True, exist_ok=True)
        opener = None
        if self.env_config.is_personal_proxy and self.env_config.personal_proxy:
            proxy = self.env_config.personal_proxy
            if not proxy.startswith(("http://", "https://", "socks5://")):
                proxy = f"http://{proxy}"
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": proxy, "https": proxy})
            )

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "ZenlessZoneZero-OneDragon Runtime Updater",
                "Accept": "application/octet-stream",
            },
        )
        response = None
        try:
            response = opener.open(req, timeout=60) if opener else urllib.request.urlopen(req, timeout=60)
            total = int(response.headers.get("Content-Length", "0") or "0")
            downloaded = 0
            with dest.open("wb") as f:
                while True:
                    if progress_signal is not None and progress_signal.get("signal") == "cancel":
                        raise RuntimeError("下载已取消")
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback is not None and total > 0:
                        progress = min(downloaded / total, 1.0)
                        progress_callback(progress, f"正在下载 {downloaded / 1024 / 1024:.2f}/{total / 1024 / 1024:.2f} MB")
            if progress_callback is not None:
                progress_callback(1, f"下载完成 {dest.name}")
            return True
        finally:
            if response is not None:
                response.close()

    @staticmethod
    def _sha256(path: Path) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest().upper()

    @staticmethod
    def _extract_zip(zip_path: Path, extract_dir: Path) -> None:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

    def _write_apply_script(
        self,
        script_path: Path,
        current_pid: int,
        extract_dir: Path,
        backup_dir: Path,
        log_path: Path,
        state_path: Path,
        target_version: str,
        source: str,
        kind: str,
        changes: dict[str, Any] | None,
    ) -> None:
        changes_json = json.dumps(changes or {}, ensure_ascii=False)
        state_json = json.dumps(
            {
                "version": target_version,
                "source": source,
                "updated_at": os_utils.now_timestamp_str(),
                "result": "success",
            },
            ensure_ascii=False,
        )
        failed_state_json = json.dumps(
            {
                "version": target_version,
                "source": source,
                "updated_at": os_utils.now_timestamp_str(),
                "result": "failed",
            },
            ensure_ascii=False,
        )
        script = textwrap.dedent(
            f"""
            $ErrorActionPreference = 'Stop'
            $TargetDir = '{self.work_dir.as_posix()}'
            $ExtractDir = '{extract_dir.as_posix()}'
            $BackupDir = '{backup_dir.as_posix()}'
            $LogPath = '{log_path.as_posix()}'
            $StatePath = '{state_path.as_posix()}'
            $CurrentPid = {current_pid}
            $UpdateKind = '{kind}'
            $ChangesJson = @'
            {changes_json}
            '@
            $StateJson = @'
            {state_json}
            '@
            $FailedStateJson = @'
            {failed_state_json}
            '@

            function WriteLog {{
                param([string]$Message)
                $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
                Add-Content -Path $LogPath -Value "[$timestamp] $Message" -Encoding UTF8
            }}

            function RemoveIfExists {{
                param([string]$Path)
                if (Test-Path -LiteralPath $Path) {{
                    Remove-Item -LiteralPath $Path -Recurse -Force
                }}
            }}

            function RestoreBackup {{
                WriteLog '开始回滚 RuntimeLauncher'
                RemoveIfExists (Join-Path $TargetDir '{RUNTIME_DIR_NAME}')
                if (Test-Path -LiteralPath (Join-Path $BackupDir '{RUNTIME_DIR_NAME}')) {{
                    Copy-Item -LiteralPath (Join-Path $BackupDir '{RUNTIME_DIR_NAME}') -Destination (Join-Path $TargetDir '{RUNTIME_DIR_NAME}') -Recurse -Force
                }}
                if (Test-Path -LiteralPath (Join-Path $BackupDir '{RUNTIME_LAUNCHER_EXE}')) {{
                    Copy-Item -LiteralPath (Join-Path $BackupDir '{RUNTIME_LAUNCHER_EXE}') -Destination (Join-Path $TargetDir '{RUNTIME_LAUNCHER_EXE}') -Force
                }}
            }}

            function ApplyFullImpl {{
                WriteLog '应用全量更新包'
                RemoveIfExists (Join-Path $TargetDir '{RUNTIME_DIR_NAME}')
                Copy-Item -LiteralPath (Join-Path $ExtractDir '{RUNTIME_DIR_NAME}') -Destination (Join-Path $TargetDir '{RUNTIME_DIR_NAME}') -Recurse -Force
                Copy-Item -LiteralPath (Join-Path $ExtractDir '{RUNTIME_LAUNCHER_EXE}') -Destination (Join-Path $TargetDir '{RUNTIME_LAUNCHER_EXE}') -Force
            }}

            function ApplyDiffImpl {{
                WriteLog '应用增量更新包'
                $changes = ConvertFrom-Json -InputObject $ChangesJson
                if (-not (Test-Path -LiteralPath (Join-Path $TargetDir '{RUNTIME_DIR_NAME}'))) {{
                    New-Item -ItemType Directory -Path (Join-Path $TargetDir '{RUNTIME_DIR_NAME}') -Force | Out-Null
                }}
                if (Test-Path -LiteralPath (Join-Path $ExtractDir '{RUNTIME_DIR_NAME}')) {{
                    Copy-Item -Path (Join-Path $ExtractDir '{RUNTIME_DIR_NAME}\\*') -Destination (Join-Path $TargetDir '{RUNTIME_DIR_NAME}') -Recurse -Force
                }}
                if (Test-Path -LiteralPath (Join-Path $ExtractDir '{RUNTIME_LAUNCHER_EXE}')) {{
                    Copy-Item -LiteralPath (Join-Path $ExtractDir '{RUNTIME_LAUNCHER_EXE}') -Destination (Join-Path $TargetDir '{RUNTIME_LAUNCHER_EXE}') -Force
                }}
                foreach ($rel in $changes.deleted) {{
                    $deletePath = Join-Path $TargetDir $rel
                    RemoveIfExists $deletePath
                }}
            }}

            try {{
                New-Item -ItemType Directory -Path (Split-Path -Parent $LogPath) -Force | Out-Null
                Start-Sleep -Milliseconds 500
                while (Get-Process -Id $CurrentPid -ErrorAction SilentlyContinue) {{
                    Start-Sleep -Milliseconds 300
                }}

                RemoveIfExists $BackupDir
                New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

                if (Test-Path -LiteralPath (Join-Path $TargetDir '{RUNTIME_LAUNCHER_EXE}')) {{
                    Copy-Item -LiteralPath (Join-Path $TargetDir '{RUNTIME_LAUNCHER_EXE}') -Destination (Join-Path $BackupDir '{RUNTIME_LAUNCHER_EXE}') -Force
                }}
                if (Test-Path -LiteralPath (Join-Path $TargetDir '{RUNTIME_DIR_NAME}')) {{
                    Copy-Item -LiteralPath (Join-Path $TargetDir '{RUNTIME_DIR_NAME}') -Destination (Join-Path $BackupDir '{RUNTIME_DIR_NAME}') -Recurse -Force
                }}

                if ($UpdateKind -eq 'diff') {{
                    WriteLog '准备执行增量更新'
                    ApplyDiffImpl
                }} else {{
                    WriteLog '准备执行全量更新'
                    ApplyFullImpl
                }}

                Set-Content -Path $StatePath -Value $StateJson -Encoding UTF8
                Start-Process -FilePath (Join-Path $TargetDir '{RUNTIME_LAUNCHER_EXE}')
                RemoveIfExists $BackupDir
                RemoveIfExists $ExtractDir
                WriteLog 'RuntimeLauncher 更新完成'
            }} catch {{
                WriteLog ("更新失败: " + $_.Exception.Message)
                Set-Content -Path $StatePath -Value $FailedStateJson -Encoding UTF8
                RestoreBackup
                throw
            }}
            """
        ).strip()
        script_path.write_text(script, encoding="utf-8-sig")
