import time
import urllib.request
from collections.abc import Callable
from pathlib import Path

from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log


def download_file(download_url: str, save_file_path: str,
                  proxy: str | None = None, progress_signal: dict[str, str | None] | None = None,
                  progress_callback: Callable[[float, str], None] | None = None) -> bool:
    """
    下载文件
    :param download_url: 下载的url
    :param save_file_path: 保存的文件路径，包含文件名
    :param proxy: 使用的代理地址
    :param progress_signal: 进度信号字典，当字典中 'signal' 键的值为 'cancel' 时会取消下载
    :param progress_callback: 下载进度的回调，进度发生改变时，通过该方法通知调用方。
    :return: 是否下载成功
    """
    proxy_handler = (
        urllib.request.ProxyHandler({'http': proxy, 'https': proxy})
        if proxy is not None else urllib.request.ProxyHandler({})
    )
    opener = urllib.request.build_opener(proxy_handler)

    last_log_time = time.time()
    save_path = Path(save_file_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)

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

        request = urllib.request.Request(download_url)
        with opener.open(request, timeout=60) as response, save_path.open('wb') as file:
            total_size = int(response.headers.get('Content-Length', '0') or 0)
            downloaded_bytes = 0
            chunk_size = 1024 * 64

            while True:
                if progress_signal is not None and progress_signal.get('signal') == 'cancel':
                    raise DownloadCancelledError("下载已取消")

                chunk = response.read(chunk_size)
                if not chunk:
                    break

                file.write(chunk)
                downloaded_bytes += len(chunk)
                log_download_progress(downloaded_bytes, total_size)

        msg = f"{gt('下载完成')} {save_file_path}"
        log.info(msg)
        if progress_callback is not None:
            progress_callback(1, msg)
        return True
    except DownloadCancelledError:
        save_path.unlink(missing_ok=True)
        msg = f"{gt('下载已取消')}"
        log.info(msg)
        if progress_callback is not None:
            progress_callback(0, msg)
        return False
    except Exception as e:
        save_path.unlink(missing_ok=True)
        msg = f"{gt('下载失败')} {e}"
        if progress_callback is not None:
            progress_callback(0, msg)
        log.error(msg, exc_info=True)
        return False

class DownloadCancelledError(Exception):
    pass
