import tempfile
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path

from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log

# 系统代理探测结果缓存：None=未探测；(True, proxy_url)=探测过且可用；(False, None)=探测过但不可用
_system_proxy_probe: tuple[bool, str | None] | None = None

# 用于探测系统代理连通性的轻量目标
_SYSTEM_PROXY_PROBE_URL = 'https://www.google.com/generate_204'
_SYSTEM_PROXY_PROBE_TIMEOUT = 5


def get_usable_system_proxy() -> str | None:
    """获取当前可用的系统代理地址。

    进程内只探测一次：先读系统代理设置（Windows 下即浏览器代理），
    再用轻量请求验证连通性，可用才返回代理地址，不可用返回 None（后续直连）。
    结果缓存在内存中，不写任何配置文件。
    """
    global _system_proxy_probe
    if _system_proxy_probe is not None:
        return _system_proxy_probe[1]

    proxy_url: str | None = None
    try:
        system_proxies = urllib.request.getproxies()
        candidate = system_proxies.get('https') or system_proxies.get('http')
        if candidate:
            probe_opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({'http': candidate, 'https': candidate})
            )
            with probe_opener.open(_SYSTEM_PROXY_PROBE_URL, timeout=_SYSTEM_PROXY_PROBE_TIMEOUT) as resp:
                if resp.status == 204:
                    proxy_url = candidate
                    # 代理地址可能含 user:password@host，不记录完整地址避免泄露凭据
                    log.info('检测到可用的系统代理')
                else:
                    log.info('系统代理不可用（探测返回 %s），将使用直连', resp.status)
    except Exception:
        log.info('系统代理不可用（探测失败），将使用直连')
    finally:
        _system_proxy_probe = (proxy_url is not None, proxy_url)
    return proxy_url


def download_file(download_url: str, save_file_path: str,
                  proxy: str | None = None, progress_signal: dict[str, str | None] | None = None,
                  progress_callback: Callable[[float, str], None] | None = None,
                  use_system_proxy: bool = False) -> bool:
    """
    下载文件
    :param download_url: 下载的url
    :param save_file_path: 保存的文件路径，包含文件名
    :param proxy: 使用的代理地址；为 None 且 use_system_proxy=True 时自动探测系统代理
    :param progress_signal: 进度信号字典，当字典中 'signal' 键的值为 'cancel' 时会取消下载
    :param progress_callback: 下载进度的回调，进度发生改变时，通过该方法通知调用方。
    :param use_system_proxy: 是否在未指定 proxy 时自动使用系统代理（探测失败则回退直连）
    :return: 是否下载成功
    """
    effective_proxy = proxy
    if effective_proxy is None and use_system_proxy:
        effective_proxy = get_usable_system_proxy()

    # 优先用代理下载；代理方式失败且确实用了代理时，回退直连重试一次
    if effective_proxy is not None:
        success = _download_file_once(download_url, save_file_path, effective_proxy,
                                      progress_signal, progress_callback)
        if success:
            return True
        # 用户主动取消不是下载失败，不触发直连重试
        if progress_signal is not None and progress_signal.get('signal') == 'cancel':
            return False
        log.info('代理下载失败，回退直连重试')
        return _download_file_once(download_url, save_file_path, None,
                                   progress_signal, progress_callback)

    return _download_file_once(download_url, save_file_path, None,
                               progress_signal, progress_callback)


def _download_file_once(download_url: str, save_file_path: str,
                        proxy: str | None, progress_signal: dict[str, str | None] | None,
                        progress_callback: Callable[[float, str], None] | None) -> bool:
    """单次下载：proxy 为 None 时直连。"""
    proxy_handler = (
        urllib.request.ProxyHandler({'http': proxy, 'https': proxy})
        if proxy is not None else urllib.request.ProxyHandler({})
    )
    opener = urllib.request.build_opener(proxy_handler)

    last_log_time = time.time()
    save_path = Path(save_file_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None

    def log_download_progress(downloaded_bytes: int, total_size: int) -> None:
        nonlocal last_log_time
        now = time.time()
        if now - last_log_time < 1:
            return
        last_log_time = now

        downloaded_mb = downloaded_bytes / 1024.0 / 1024.0
        if total_size > 0:
            total_size_mb = total_size / 1024.0 / 1024.0
            progress = downloaded_bytes / total_size
            msg = f"{gt('正在下载')} {downloaded_mb:.2f}/{total_size_mb:.2f} MB ({progress * 100:.2f}%)"
        else:
            progress = 0
            msg = f"{gt('正在下载')} {downloaded_mb:.2f} MB"

        log.info(msg)
        if progress_callback is not None:
            progress_callback(progress, msg)

    try:
        msg = f"{gt('开始下载')} {download_url}"
        log.info(msg)
        if progress_callback is not None:
            progress_callback(0, msg)

        url = urllib.parse.urlparse(download_url)
        if url.scheme not in ('http', 'https'):
            raise ValueError(f"不支持的下载协议：{download_url}")

        request = urllib.request.Request(download_url)
        with opener.open(request, timeout=60) as response:
            total_size = int(response.headers.get('Content-Length', '0') or 0)
            downloaded_bytes = 0
            chunk_size = 1024 * 64

            with tempfile.NamedTemporaryFile('wb', dir=save_path.parent, delete=False) as file:
                temp_path = Path(file.name)
                while True:
                    if progress_signal is not None and progress_signal.get('signal') == 'cancel':
                        raise DownloadCancelledError("下载已取消")

                    chunk = response.read(chunk_size)
                    if not chunk:
                        break

                    file.write(chunk)
                    downloaded_bytes += len(chunk)
                    log_download_progress(downloaded_bytes, total_size)

            if total_size > 0 and downloaded_bytes != total_size:
                raise DownloadIncompleteError(
                    f"下载不完整：{downloaded_bytes}/{total_size} bytes"
                )

            temp_path.replace(save_path)
            temp_path = None

        msg = f"{gt('下载完成')} {save_file_path}"
        log.info(msg)
        if progress_callback is not None:
            progress_callback(1, msg)
        return True
    except DownloadCancelledError:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        msg = f"{gt('下载已取消')}"
        log.info(msg)
        if progress_callback is not None:
            progress_callback(0, msg)
        return False
    except Exception as e:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        msg = f"{gt('下载失败')} {e}"
        if progress_callback is not None:
            progress_callback(0, msg)
        log.error(msg, exc_info=True)
        return False


class DownloadCancelledError(Exception):
    pass


class DownloadIncompleteError(Exception):
    pass
