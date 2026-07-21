from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path
from typing import Any, BinaryIO, cast
from urllib.parse import quote

import requests

GITHUB_REPOSITORY = 'OneDragon-Anything/ZenlessZoneZero-OneDragon'
CNB_REPOSITORY = 'OneDragon-Anything/ZenlessZoneZero-OneDragon'
GITHUB_API_URL = 'https://api.github.com'
CNB_API_URL = 'https://api.cnb.cool'
CHUNK_SIZE = 1024 * 1024
PROGRESS_INTERVAL = 64 * 1024 * 1024


class ProgressReader:
    """读取上传文件并定期输出进度，避免大文件上传期间流水线无日志。"""

    def __init__(self, path: Path):
        self.path: Path = path
        self.total: int = path.stat().st_size
        self.current: int = 0
        self.next_report: int = PROGRESS_INTERVAL
        self.file: BinaryIO = path.open('rb')

    def __len__(self) -> int:
        return self.total

    def read(self, size: int = -1) -> bytes:
        data = self.file.read(size)
        self.current += len(data)
        if self.current >= self.next_report or self.current == self.total:
            _print_progress('上传', self.path.name, self.current, self.total)
            while self.next_report <= self.current:
                self.next_report += PROGRESS_INTERVAL
        return data

    def close(self) -> None:
        self.file.close()

    def __enter__(self) -> ProgressReader:
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()


def _print_progress(action: str, name: str, current: int, total: int) -> None:
    percent = current * 100 / total if total else 100
    print(
        f'{action} {name}: {current / 1024 / 1024:.1f} / '
        f'{total / 1024 / 1024:.1f} MiB ({percent:.1f}%)',
        flush=True,
    )


def _expect_status(response: requests.Response, expected: set[int]) -> None:
    if response.status_code in expected:
        return
    detail = response.text[:2000]
    raise RuntimeError(f'请求失败: {response.status_code} {response.url}\n{detail}')


def _response_json(response: requests.Response) -> dict[str, Any]:
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError(f'接口返回的不是对象: {response.url}')
    return cast(dict[str, Any], data)


def _build_release_payload(release: dict[str, Any]) -> dict[str, object]:
    tag_name = release.get('tag_name')
    if not isinstance(tag_name, str) or not tag_name:
        raise ValueError('GitHub Release 缺少 tag_name')

    name = release.get('name')
    body = release.get('body')
    target_commitish = release.get('target_commitish')
    prerelease = bool(release.get('prerelease'))

    return {
        'tag_name': tag_name,
        'name': name if isinstance(name, str) and name else tag_name,
        'body': body if isinstance(body, str) else '',
        'draft': False,
        'prerelease': prerelease,
        'target_commitish': target_commitish if isinstance(target_commitish, str) else 'main',
        'make_latest': 'false' if prerelease else 'true',
    }


def _select_assets(release: dict[str, Any]) -> list[dict[str, Any]]:
    assets = release.get('assets')
    if not isinstance(assets, list):
        raise ValueError('GitHub Release 的 assets 格式无效')

    selected: list[dict[str, Any]] = []
    for asset in assets:
        if not isinstance(asset, dict) or asset.get('state') != 'uploaded':
            continue
        name = asset.get('name')
        download_url = asset.get('browser_download_url')
        size = asset.get('size')
        if not isinstance(name, str) or Path(name).name != name or not name:
            raise ValueError(f'非法 Release 附件名: {name!r}')
        if not isinstance(download_url, str) or not download_url:
            raise ValueError(f'Release 附件缺少下载地址: {name}')
        if not isinstance(size, int) or size < 0:
            raise ValueError(f'Release 附件大小无效: {name}')
        selected.append(cast(dict[str, Any], asset))

    if not selected:
        raise ValueError('GitHub Release 没有可同步的附件')
    return selected


class ReleaseSynchronizer:
    """把一个 GitHub Release 的元数据和附件同步到 CNB。"""

    def __init__(self, cnb_token: str, github_token: str | None = None):
        self.cnb_token: str = cnb_token
        self.github_session: requests.Session = requests.Session()
        self.github_session.headers.update(
            {
                'Accept': 'application/vnd.github+json',
                'User-Agent': 'ZenlessZoneZero-OneDragon-CNB-Release-Sync',
                'X-GitHub-Api-Version': '2022-11-28',
            }
        )
        if github_token:
            self.github_session.headers['Authorization'] = f'Bearer {github_token}'

        self.cnb_session: requests.Session = requests.Session()
        self.cnb_session.headers.update(
            {
                'Accept': 'application/vnd.cnb.api+json',
                'Authorization': f'Bearer {cnb_token}',
                'User-Agent': 'ZenlessZoneZero-OneDragon-CNB-Release-Sync',
            }
        )

    def get_github_release(self, release_tag: str | None) -> dict[str, Any]:
        if release_tag:
            encoded_tag = quote(release_tag, safe='')
            url = f'{GITHUB_API_URL}/repos/{GITHUB_REPOSITORY}/releases/tags/{encoded_tag}'
        else:
            url = f'{GITHUB_API_URL}/repos/{GITHUB_REPOSITORY}/releases/latest'

        response = self.github_session.get(url, timeout=60)
        _expect_status(response, {200})
        release = _response_json(response)
        print(f"获取 GitHub Release: {release.get('tag_name')}", flush=True)
        return release

    def ensure_cnb_release(self, release: dict[str, Any]) -> dict[str, Any]:
        payload = _build_release_payload(release)
        tag_name = cast(str, payload['tag_name'])
        encoded_tag = quote(tag_name, safe='')
        release_url = f'{CNB_API_URL}/{CNB_REPOSITORY}/-/releases/tags/{encoded_tag}'
        response = self.cnb_session.get(release_url, timeout=60)

        if response.status_code == 404:
            create_url = f'{CNB_API_URL}/{CNB_REPOSITORY}/-/releases'
            response = self.cnb_session.post(create_url, json=payload, timeout=60)
            _expect_status(response, {201})
            result = _response_json(response)
            print(f'已创建 CNB Release: {tag_name}', flush=True)
            return result

        _expect_status(response, {200})
        result = _response_json(response)
        release_id = result.get('id')
        if not isinstance(release_id, str) or not release_id:
            raise RuntimeError('CNB Release 缺少 id')

        patch_payload = {
            key: payload[key]
            for key in ('name', 'body', 'draft', 'prerelease', 'make_latest')
        }
        patch_url = f'{CNB_API_URL}/{CNB_REPOSITORY}/-/releases/{release_id}'
        patch_response = self.cnb_session.patch(patch_url, json=patch_payload, timeout=60)
        _expect_status(patch_response, {200})
        print(f'已更新现有 CNB Release: {tag_name}', flush=True)
        return result

    def download_asset(self, asset: dict[str, Any], destination: Path) -> None:
        name = cast(str, asset['name'])
        download_url = cast(str, asset['browser_download_url'])
        expected_size = cast(int, asset['size'])
        next_report = PROGRESS_INTERVAL

        for attempt in range(1, 4):
            try:
                with self.github_session.get(
                    download_url,
                    stream=True,
                    timeout=(30, 300),
                ) as response:
                    _expect_status(response, {200})
                    current = 0
                    with destination.open('wb') as output:
                        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                            if not chunk:
                                continue
                            output.write(chunk)
                            current += len(chunk)
                            if current >= next_report or current == expected_size:
                                _print_progress('下载', name, current, expected_size)
                                while next_report <= current:
                                    next_report += PROGRESS_INTERVAL

                actual_size = destination.stat().st_size
                if actual_size != expected_size:
                    raise RuntimeError(
                        f'附件大小不一致: {name}, 期望 {expected_size}, 实际 {actual_size}'
                    )
                return
            except (OSError, requests.RequestException, RuntimeError) as exc:
                if attempt == 3:
                    raise
                print(f'下载失败，准备重试 ({attempt}/3): {name}: {exc}', flush=True)
                next_report = PROGRESS_INTERVAL

    def upload_asset(self, release_id: str, path: Path) -> None:
        upload_url_api = (
            f'{CNB_API_URL}/{CNB_REPOSITORY}/-/releases/{release_id}/asset-upload-url'
        )
        response = self.cnb_session.post(
            upload_url_api,
            json={
                'asset_name': path.name,
                'overwrite': True,
                'size': path.stat().st_size,
            },
            timeout=60,
        )
        _expect_status(response, {201})
        upload_info = _response_json(response)
        upload_url = upload_info.get('upload_url')
        verify_url = upload_info.get('verify_url')
        if not isinstance(upload_url, str) or not upload_url:
            raise RuntimeError(f'CNB 未返回附件上传地址: {path.name}')

        with ProgressReader(path) as reader:
            upload_response = requests.put(
                upload_url,
                headers={
                    'Authorization': f'Bearer {self.cnb_token}',
                    'Content-Length': str(reader.total),
                },
                data=reader,
                timeout=(30, 600),
            )
        _expect_status(upload_response, {200, 201, 204})

        if isinstance(verify_url, str) and verify_url:
            verify_response = self.cnb_session.post(verify_url, timeout=60)
            _expect_status(verify_response, {200, 201, 204})
        print(f'已上传 CNB Release 附件: {path.name}', flush=True)

    def sync(self, release_tag: str | None) -> None:
        release = self.get_github_release(release_tag)
        assets = _select_assets(release)
        cnb_release = self.ensure_cnb_release(release)
        release_id = cnb_release.get('id')
        if not isinstance(release_id, str) or not release_id:
            raise RuntimeError('CNB Release 缺少 id')

        with tempfile.TemporaryDirectory(prefix='zzz-od-cnb-release-') as temp_dir:
            temp_path = Path(temp_dir)
            for index, asset in enumerate(assets, start=1):
                name = cast(str, asset['name'])
                path = temp_path / name
                print(f'[{index}/{len(assets)}] 开始同步: {name}', flush=True)
                try:
                    self.download_asset(asset, path)
                    self.upload_asset(release_id, path)
                finally:
                    path.unlink(missing_ok=True)

        print(f"CNB Release 同步完成: {release.get('tag_name')}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description='同步 GitHub Release 到 CNB Release')
    parser.add_argument('--release-tag', help='指定 GitHub Release 标签；省略时同步最新正式版')
    parser.add_argument('--cnb-token', help='CNB 访问令牌，默认读取 CNB_TOKEN')
    parser.add_argument('--github-token', help='GitHub 访问令牌，默认读取 GITHUB_TOKEN')
    args = parser.parse_args()

    cnb_token = args.cnb_token or os.environ.get('CNB_TOKEN')
    if not cnb_token:
        parser.error('缺少 CNB Token，请传入 --cnb-token 或设置 CNB_TOKEN')

    github_token = args.github_token or os.environ.get('GITHUB_TOKEN')
    synchronizer = ReleaseSynchronizer(cnb_token, github_token)
    synchronizer.sync(args.release_tag)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
