"""下载最新正式版集成启动器，检查当前代码的新增导入是否可用。"""

import argparse
import json
import marshal
import os
import shutil
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
import zlib
from pathlib import Path
from urllib.parse import urlsplit


class _DownloadRedirectHandler(urllib.request.HTTPRedirectHandler):
    """仅同源重定向保留凭据，拒绝携带凭据的 HTTPS 请求降级。"""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> urllib.request.Request | None:
        source = urlsplit(req.full_url)
        target = urlsplit(newurl)
        if req.has_header('Authorization') and source.scheme == 'https' and target.scheme == 'http':
            raise urllib.error.HTTPError(req.full_url, code, '拒绝携带凭据的 HTTPS 请求重定向到 HTTP', headers, fp)
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        source_origin = (source.scheme, source.hostname, source.port if source.port is not None else (443 if source.scheme == 'https' else 80))
        target_origin = (target.scheme, target.hostname, target.port if target.port is not None else (443 if target.scheme == 'https' else 80))
        if redirected is not None and source_origin != target_origin:
            redirected.remove_header('Authorization')
        return redirected


REPOSITORY = 'OneDragon-Anything/ZenlessZoneZero-OneDragon'
ASSET_NAME = 'ZenlessZoneZero-OneDragon-RuntimeLauncher.zip'
PROJECT_CONFIG = Path('config/project.yml')
ARCHIVE_MAGIC = b'MEI\x0c\x0b\n\x0b\x0e'
PYZ_MAGIC = b'PYZ\x00'
PYZ_ITEM_MODULE = 0
PYZ_ITEM_PACKAGE = 1
PYZ_ITEM_NAMESPACE = 3


def _log(message: str) -> None:
    """输出 CI 日志。"""
    print(message, flush=True)


def _fetch_json(url: str, token: str) -> object:
    """读取 GitHub API 的 JSON 响应。"""
    request = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'ZenlessZoneZero-OneDragon CI',
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Bearer {token}',
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode('utf-8'))


def _download(url: str, destination: Path, token: str) -> None:
    """下载发布资产，临时网络错误最多重试三次。"""
    destination.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, 4):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'ZenlessZoneZero-OneDragon CI',
                    'Accept': 'application/octet-stream',
                    'Authorization': f'Bearer {token}',
                },
            )
            opener = urllib.request.build_opener(_DownloadRedirectHandler())
            with opener.open(request, timeout=300) as response, destination.open('wb') as output:
                shutil.copyfileobj(response, output)
            return
        except Exception as error:
            _log(f'下载失败（{attempt}/3）：{error}')
            if attempt == 3:
                raise
            time.sleep(2 * attempt)


def _latest_stable_release(token: str) -> tuple[str, str]:
    """返回最新非预发布版本的标签和 RuntimeLauncher 下载地址。"""
    data = _fetch_json(f'https://api.github.com/repos/{REPOSITORY}/releases?per_page=20', token)
    if not isinstance(data, list):
        raise RuntimeError('发布列表格式无效')

    for release in data:
        if not isinstance(release, dict) or release.get('draft') or release.get('prerelease'):
            continue
        tag = release.get('tag_name')
        assets = release.get('assets')
        if not isinstance(tag, str) or not tag or not isinstance(assets, list):
            raise RuntimeError('最新正式版的标签或资产列表无效')
        for asset in assets:
            if isinstance(asset, dict) and asset.get('name') == ASSET_NAME:
                url = asset.get('url')
                if isinstance(url, str) and url:
                    return tag, url
        raise RuntimeError(f'最新正式版 {tag} 没有找到 {ASSET_NAME}')
    raise RuntimeError('发布列表中没有正式版')


def _target_manifest(repository_root: Path) -> bytes:
    """按当前项目配置读取源码清单，不执行清单代码。"""
    import yaml

    data = yaml.safe_load((repository_root / PROJECT_CONFIG).read_text(encoding='utf-8'))
    manifest_path = data.get('manifest_path') if isinstance(data, dict) else None
    if not isinstance(manifest_path, str) or not manifest_path:
        raise RuntimeError('config/project.yml 缺少 manifest_path')

    target = (repository_root / manifest_path).resolve()
    if not target.is_relative_to(repository_root.resolve()) or not target.is_file():
        raise RuntimeError(f'模块清单不存在：{manifest_path}')
    return target.read_bytes()


def _pkg_archive(executable: bytes) -> tuple[int, int, int]:
    """定位 EXE 尾部的 PyInstaller PKG 归档。"""
    cookie_offset = executable.rfind(ARCHIVE_MAGIC)
    if cookie_offset < 0:
        raise RuntimeError('RuntimeLauncher 不包含可识别的 PyInstaller 归档')

    _magic, package_length, toc_offset, toc_length, _python_version = struct.unpack_from(
        '!8sIIii',
        executable,
        cookie_offset,
    )
    package_start = len(executable) - package_length
    if package_start < 0 or toc_offset < 0 or toc_length < 0:
        raise RuntimeError('RuntimeLauncher 的 PyInstaller 归档范围无效')
    return package_start, package_start + toc_offset, toc_length


def _archive_entries(executable: bytes) -> list[tuple[str, str, int, int, bool]]:
    """读取 PKG 目录，返回名称、类型、偏移、长度和是否压缩。"""
    package_start, toc_start, toc_length = _pkg_archive(executable)
    table = executable[toc_start:toc_start + toc_length]
    entries: list[tuple[str, str, int, int, bool]] = []
    position = 0
    while position + 18 <= len(table):
        entry_length, offset, length, _uncompressed_length, compressed, type_code = struct.unpack_from(
            '!IIIIBB',
            table,
            position,
        )
        if entry_length < 18 or position + entry_length > len(table):
            raise RuntimeError('RuntimeLauncher 的 PyInstaller 归档目录无效')
        name = table[position + 18:position + entry_length].split(b'\0', 1)[0].decode('utf-8')
        entries.append((name, chr(type_code), package_start + offset, length, bool(compressed)))
        position += entry_length
    if position != len(table):
        raise RuntimeError('RuntimeLauncher 的 PyInstaller 归档目录未完整解析')
    return entries


def _entry_bytes(executable: bytes, entry: tuple[str, str, int, int, bool]) -> bytes:
    """读取并按归档标记解压一个 PKG 条目。"""
    _name, _type_code, offset, length, compressed = entry
    data = executable[offset:offset + length]
    if len(data) != length:
        raise RuntimeError('RuntimeLauncher 的归档条目超出文件范围')
    return zlib.decompress(data) if compressed else data


def _extract_pyz(executable: bytes, destination: Path) -> int:
    """提取完整 PYZ，供发布包原有导入器直接读取。"""
    pyz_entry = next((entry for entry in _archive_entries(executable) if entry[1] == 'z'), None)
    if pyz_entry is None:
        raise RuntimeError('RuntimeLauncher 缺少 PYZ 归档')

    pyz = _entry_bytes(executable, pyz_entry)
    if not pyz.startswith(PYZ_MAGIC):
        raise RuntimeError('RuntimeLauncher 的 PYZ 归档格式无效')
    toc_offset = struct.unpack_from('!i', pyz, 8)[0]
    table = marshal.loads(pyz[toc_offset:])
    if not isinstance(table, list) or not table:
        raise RuntimeError('RuntimeLauncher 的 PYZ 目录无效')
    destination.write_bytes(pyz)
    return len(table)


def _extract_bootstrap_modules(executable: bytes, output_dir: Path) -> None:
    """提取 PyInstaller 导入器，供同版本解释器安装冻结导入。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    names = {'pyimod01_archive', 'pyimod02_importers', 'pyimod03_ctypes', 'pyimod04_pywin32'}
    entries = [entry for entry in _archive_entries(executable) if entry[0] in names and entry[1] == 'm']
    if len(entries) != len(names):
        raise RuntimeError('RuntimeLauncher 缺少 PyInstaller 冻结导入器')
    header = executable
    pyz_entry = next(entry for entry in _archive_entries(executable) if entry[1] == 'z')
    magic = _entry_bytes(header, pyz_entry)[4:8]
    pyc_header = magic + struct.pack('<III', 0, 0, 0)
    for entry in entries:
        code = marshal.loads(_entry_bytes(executable, entry))
        (output_dir / f'{entry[0]}.pyc').write_bytes(pyc_header + marshal.dumps(code))


def _write_bootstrap(
    bootstrap: Path,
    runtime_dir: Path,
    pyz_path: Path,
    importer_dir: Path,
    repository_root: Path,
    target_manifest: Path,
) -> None:
    """写入同版本解释器使用发布包依赖的导入检查引导。"""
    runtime_text = str(runtime_dir.resolve())
    pyz_text = str(pyz_path.resolve())
    importer_text = str(importer_dir.resolve())
    source_text = str((repository_root / 'src').resolve())
    manifest_text = str(target_manifest.resolve())
    bootstrap.write_text(
        f'''import os
import struct
from pathlib import Path

RUNTIME_DIR = Path(r"{runtime_text}")
PYZ_PATH = Path(r"{pyz_text}")
IMPORTER_DIR = Path(r"{importer_text}")
SOURCE_DIR = Path(r"{source_text}")
TARGET_MANIFEST = Path(r"{manifest_text}")

import sys

dll_directory_handle = os.add_dll_directory(str(RUNTIME_DIR))
sys.path[:] = [str(RUNTIME_DIR / "base_library.zip"), str(IMPORTER_DIR), str(RUNTIME_DIR), str(SOURCE_DIR)]
sys.frozen = True
sys._MEIPASS = str(RUNTIME_DIR)
sys._pyinstaller_pyz = str(PYZ_PATH)

import pyimod02_importers

pyimod02_importers.install()
import one_dragon

one_dragon.__path__.append(str(SOURCE_DIR / "one_dragon"))
from one_dragon.envs.runtime_compatibility import check_manifest_compatible

local_manifest = (RUNTIME_DIR / "module_manifest.py").read_bytes()
target_manifest = TARGET_MANIFEST.read_bytes()
raise SystemExit(0 if check_manifest_compatible(local_manifest, target_manifest) else 2)
''',
        encoding='utf-8',
    )


def _check_with_runtime(
    runtime_root: Path,
    repository_root: Path,
    target_manifest: Path,
    work_dir: Path,
) -> subprocess.CompletedProcess[str]:
    """用发布包的 PYZ、扩展模块和标准库检查新增导入。"""
    runtime_dir = runtime_root / '.runtime'
    if not (runtime_dir / 'python311.dll').is_file() or not (runtime_dir / 'base_library.zip').is_file():
        raise RuntimeError('RuntimeLauncher 包内缺少冻结运行时')

    executable = (runtime_root / 'OneDragon-RuntimeLauncher.exe').read_bytes()
    pyz_path = work_dir / 'PYZ.pyz'
    importer_dir = work_dir / 'pyinstaller_importers'
    module_count = _extract_pyz(executable, pyz_path)
    _extract_bootstrap_modules(executable, importer_dir)
    _log(f'已从 RuntimeLauncher 提取 {module_count} 个冻结模块')

    bootstrap = work_dir / 'runtime_compatibility_bootstrap.py'
    _write_bootstrap(bootstrap, runtime_dir, pyz_path, importer_dir, repository_root, target_manifest)
    return subprocess.run(
        [sys.executable, str(bootstrap.resolve())],
        cwd=runtime_root,
        capture_output=True,
        env={
            'SYSTEMROOT': os.environ.get('SYSTEMROOT', r'C:\\Windows'),
            'PATH': str(runtime_dir),
            'PYTHONPATH': '',
            'PYTHONHOME': '',
            'PYTHONDONTWRITEBYTECODE': '1',
            'PYTHONUTF8': '1',
        },
        check=False,
    )


def main() -> int:
    """执行发布包下载和兼容性检查。"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository-root', type=Path, default=Path('.'))
    parser.add_argument('--work-dir', type=Path, required=True)
    args = parser.parse_args()

    token = os.environ.get('GITHUB_TOKEN', '')
    if not token:
        raise RuntimeError('缺少 GITHUB_TOKEN')

    repository_root = args.repository_root.resolve()
    work_dir = args.work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    tag, asset_url = _latest_stable_release(token)
    _log(f'最新正式版：{tag}')

    archive = work_dir / ASSET_NAME
    _download(asset_url, archive, token)
    runtime_root = work_dir / 'runtime'
    if runtime_root.exists():
        shutil.rmtree(runtime_root)
    with zipfile.ZipFile(archive) as package:
        package.extractall(runtime_root)

    target_manifest = work_dir / 'target_module_manifest.py'
    target_manifest.write_bytes(_target_manifest(repository_root))
    result = _check_with_runtime(runtime_root, repository_root, target_manifest, work_dir)
    for stream in (result.stdout, result.stderr):
        if stream:
            _log(stream.decode('utf-8', errors='replace').rstrip())

    if result.returncode == 0:
        _log('当前代码兼容最新 RuntimeLauncher')
        return 0
    if result.returncode == 2:
        _log('当前代码不兼容最新 RuntimeLauncher')
        return 2
    raise RuntimeError(f'兼容性检查进程失败，退出码 {result.returncode}')


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        _log(f'错误：{error}')
        raise SystemExit(1) from error
