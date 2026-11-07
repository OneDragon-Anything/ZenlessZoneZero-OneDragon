import tempfile
import time
import urllib.parse
import urllib.request
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log


@dataclass(frozen=True, slots=True)
class HttpDownloadProgress:
    """HTTP 下载的结构化进度。"""

    phase: str
    downloaded_bytes: int = 0
    total_bytes: int = 0
    bytes_per_second: float = 0
    progress: float = 0
    message: str = ''


def download_file(
    download_url: str,
    save_file_path: str,
    proxy: str | None = None,
    min_bytes_per_second: float | None = None,
    progress_signal: dict[str, str | None] | None = None,
    progress_callback: Callable[[float, str], None] | None = None,
    status_callback: Callable[[HttpDownloadProgress], None] | None = None,
) -> bool:
    """下载文件。

    Args:
        download_url: 下载地址。
        save_file_path: 完整保存路径。
        proxy: 个人代理地址。
        min_bytes_per_second: 持续低于该速度时中止；None 表示不限制。
        progress_signal: 兼容旧调用方的取消信号。
        progress_callback: 兼容旧调用方的进度回调。
        status_callback: 结构化下载进度回调。

    Returns:
        下载是否成功。
    """
    proxy_handler = (
        urllib.request.ProxyHandler({'http': proxy, 'https': proxy})
        if proxy is not None else urllib.request.ProxyHandler({})
    )
    opener = urllib.request.build_opener(proxy_handler)

    started_at = time.monotonic()
    last_log_time = started_at
    last_status_time = started_at
    last_status_bytes = 0
    download_started_at: float | None = None
    speed_samples: deque[tuple[float, int]] = deque()
    save_path = Path(save_file_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None

    def report_download_progress(downloaded_bytes: int, total_size: int) -> None:
        """上报下载进度并限制界面刷新频率。"""
        nonlocal last_log_time, last_status_time, last_status_bytes
        now = time.monotonic()
        status_elapsed = now - last_status_time
        if status_elapsed < 0.25 and downloaded_bytes != total_size:
            return

        downloaded_mb = downloaded_bytes / 1024.0 / 1024.0
        if total_size > 0:
            total_size_mb = total_size / 1024.0 / 1024.0
            progress = downloaded_bytes / total_size
            msg = f"{gt('正在下载')} {downloaded_mb:.2f}/{total_size_mb:.2f} MB ({progress * 100:.2f}%)"
        else:
            progress = 0
            msg = f"{gt('正在下载')} {downloaded_mb:.2f} MB"

        speed = (
            (downloaded_bytes - last_status_bytes) / status_elapsed
            if status_elapsed > 0
            else 0
        )
        last_status_time = now
        last_status_bytes = downloaded_bytes
        speed_samples.append((now, downloaded_bytes))
        while (
            speed_samples
            and speed_samples[0][0] < now - 4
        ):
            speed_samples.popleft()

        if (
            min_bytes_per_second is not None
            and download_started_at is not None
            and now - download_started_at >= 10
            and len(speed_samples) >= 2
        ):
            sample_started_at, sample_started_bytes = speed_samples[0]
            sample_elapsed = now - sample_started_at
            if sample_elapsed >= 3:
                recent_speed = (
                    downloaded_bytes - sample_started_bytes
                ) / sample_elapsed
                if recent_speed < min_bytes_per_second:
                    raise DownloadTooSlowError(
                        f'下载速度持续过低：{recent_speed / 1024:.0f} KB/s'
                    )

        if now - last_log_time >= 1:
            last_log_time = now
            log.info(msg)
        if progress_callback is not None:
            progress_callback(progress, msg)
        if status_callback is not None:
            status_callback(
                HttpDownloadProgress(
                    phase='downloading',
                    downloaded_bytes=downloaded_bytes,
                    total_bytes=total_size,
                    bytes_per_second=speed,
                    progress=progress,
                    message=msg,
                )
            )

    try:
        msg = f"{gt('开始下载')} {download_url}"
        log.info(msg)
        if progress_callback is not None:
            progress_callback(0, msg)
        if status_callback is not None:
            status_callback(HttpDownloadProgress(phase='connecting', message=gt('正在连接')))

        url = urllib.parse.urlparse(download_url)
        if url.scheme not in ('http', 'https'):
            raise ValueError(f"不支持的下载协议：{download_url}")

        request = urllib.request.Request(download_url)
        # 读超时保持较短，避免网络停滞时取消请求长时间无响应。
        with opener.open(request, timeout=5) as response:
            download_started_at = time.monotonic()
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
                    report_download_progress(downloaded_bytes, total_size)

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
        if status_callback is not None:
            elapsed = max(time.monotonic() - started_at, 0.001)
            status_callback(
                HttpDownloadProgress(
                    phase='downloaded',
                    downloaded_bytes=downloaded_bytes,
                    total_bytes=total_size,
                    bytes_per_second=downloaded_bytes / elapsed,
                    progress=1,
                    message=gt('下载完成'),
                )
            )
        return True
    except DownloadCancelledError:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        msg = f"{gt('下载已取消')}"
        log.info(msg)
        if progress_callback is not None:
            progress_callback(0, msg)
        if status_callback is not None:
            status_callback(HttpDownloadProgress(phase='cancelled', message=msg))
        return False
    except Exception as e:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        msg = f"{gt('下载失败')} {e}"
        if progress_callback is not None:
            progress_callback(0, msg)
        if status_callback is not None:
            status_callback(HttpDownloadProgress(phase='failed', message=msg))
        log.error(msg, exc_info=True)
        return False


class DownloadCancelledError(Exception):
    pass


class DownloadIncompleteError(Exception):
    pass


class DownloadTooSlowError(Exception):
    pass
