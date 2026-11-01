"""插件封面加载与缓存。

封面有两个来源：
- 已安装插件：插件根目录里 `PLUGIN_COVER` 指向的本地图片，直接读盘。
- 市场条目：`plugins.json` 里 `cover` 给出的图片地址，下载一次后落盘缓存。

远程封面走后台线程下载，下载完成后通过 `cover_ready` 通知界面替换占位封面。
缓存目录放在 `config/temp/plugin_covers/`，属于可丢弃的运行时产物。
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urljoin, urlparse

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QImage, QImageReader, QPixmap

from one_dragon.base.operation.application.plugin_info import PluginInfo
from one_dragon.base.operation.application.plugin_market import MARKET_URL
from one_dragon.utils import http_utils, os_utils
from one_dragon.utils.log_utils import log

MAX_COVER_BYTES = 4 * 1024 * 1024
"""单张封面允许的最大体积，超过则放弃使用。"""

MARKET_SITE_ROOT = f"{MARKET_URL.split('/api/', 1)[0]}/"
"""插件商店站点根目录，例如 https://onedragon-anyone.github.io/plugin-data/。"""


def resolve_cover_url(raw_url: str) -> str:
    """把市场里的封面字段补成完整地址。

    相对路径按插件商店站点根目录解析，开头带不带 `/` 结果相同，
    例如 `covers/a.png` 与 `/covers/a.png` 都指向 `<站点根目录>/covers/a.png`。

    Args:
        raw_url: plugins.json 中的原始值，可能是完整地址或相对站点根目录的路径。

    Returns:
        可直接下载的完整 URL；空值返回空字符串。
    """
    value = (raw_url or '').strip()
    if not value:
        return ''
    if urlparse(value).scheme:
        return value
    return urljoin(MARKET_SITE_ROOT, value.lstrip('/'))


def _read_image(path: Path) -> QImage | None:
    """从磁盘读取封面位图数据，可在非 GUI 线程调用。"""
    if not path.is_file():
        return None

    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    image = reader.read()
    if image.isNull():
        return None

    if image.width() > 1200 or image.height() > 1200:
        image = image.scaled(
            1200,
            1200,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return image


def _load_pixmap(path: Path) -> QPixmap | None:
    """把封面读成位图，只能在 GUI 线程调用。"""
    image = _read_image(path)
    return None if image is None else QPixmap.fromImage(image)


class _DownloadTask(QRunnable):
    """后台下载一张封面到缓存目录。"""

    def __init__(self, service: PluginCoverService, plugin_id: str, url: str, target: Path) -> None:
        super().__init__()
        self._service: PluginCoverService = service
        self._plugin_id: str = plugin_id
        self._url: str = url
        self._target: Path = target

    def run(self) -> None:
        ok = False
        temp_path = self._target.with_suffix(self._target.suffix + '.part')
        try:
            self._target.parent.mkdir(parents=True, exist_ok=True)
            ok = http_utils.download_file(self._url, str(temp_path))
            if ok and temp_path.stat().st_size > MAX_COVER_BYTES:
                ok = False
            # 线程里只校验图片数据，不构造 QPixmap
            if not ok or _read_image(temp_path) is None:
                ok = False
            if ok:
                temp_path.replace(self._target)
        except Exception as exc:  # noqa: BLE001 - 封面失败只是回退默认图，不影响界面
            log.debug(f'下载插件封面失败 {self._url}: {exc}')
            ok = False
        finally:
            if not ok:
                temp_path.unlink(missing_ok=True)
            # 经信号排队回到 GUI 线程，下载状态只在 GUI 线程里改
            self._service._download_finished.emit(self._plugin_id, self._url, ok)


class PluginCoverService(QObject):
    """按插件标识提供封面位图，远程封面下载一次后复用磁盘缓存。"""

    cover_ready = Signal(str)
    """某个插件的封面可用，参数为插件标识。"""

    _download_finished = Signal(str, str, bool)
    """下载线程结束，参数为插件标识、地址、是否成功。仅内部使用。"""

    def __init__(self) -> None:
        super().__init__()
        self._cache_dir: Path = Path(os_utils.get_path_under_work_dir('config', 'temp', 'plugin_covers'))
        self._memory: dict[str, QPixmap | None] = {}
        self._failed: set[str] = set()
        """下载失败过的地址，避免每次重建卡片都重打一遍外网。手动刷新时清空。"""
        self._downloading: set[str] = set()
        self._pool: QThreadPool = QThreadPool.globalInstance()
        self._download_finished.connect(
            self._on_download_finished,
            Qt.ConnectionType.QueuedConnection,
        )

    # ------------------------------------------------------------------
    # 对外接口
    # ------------------------------------------------------------------

    def installed_cover(self, plugin_info: PluginInfo) -> QPixmap | None:
        """已安装插件的本地封面，没有则返回 None。"""
        cover_path = plugin_info.cover_path
        if cover_path is None:
            return None
        try:
            mtime_ns = cover_path.stat().st_mtime_ns
        except OSError:
            return None
        # 键里带上修改时间：插件更新替换了封面文件后会重新读取
        prefix = f'local:{cover_path}:'
        key = f'{prefix}{mtime_ns}'
        if key not in self._memory:
            for stale_key in [k for k in self._memory if k.startswith(prefix)]:
                del self._memory[stale_key]
            self._memory[key] = _load_pixmap(cover_path)
        return self._memory[key]

    def clear_failed(self) -> None:
        """清空下载失败记录，让之前失败的封面在下次显示时重新下载。"""
        self._failed.clear()

    def market_cover(self, plugin_id: str, cover_url: str) -> QPixmap | None:
        """市场条目的封面；缓存未命中时返回 None 并在后台下载。"""
        url = resolve_cover_url(cover_url)
        if not url:
            return None

        key = f'url:{url}'
        if key in self._memory:
            return self._memory[key]
        if url in self._failed:
            return None

        target = self._cache_path(url)
        pixmap = _load_pixmap(target)
        if pixmap is not None:
            self._memory[key] = pixmap
            return pixmap

        self._request(plugin_id, url, target)
        return None

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _cache_path(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]
        suffix = Path(urlparse(url).path).suffix.lower()
        if suffix not in ('.png', '.jpg', '.jpeg', '.webp', '.bmp'):
            suffix = '.img'
        return self._cache_dir / f'{digest}{suffix}'

    def _request(self, plugin_id: str, url: str, target: Path) -> None:
        # 按地址去重：多个条目共用同一张封面时不会并发写同一个缓存文件
        if url in self._downloading:
            return
        self._downloading.add(url)
        self._pool.start(_DownloadTask(self, plugin_id, url, target))

    def _on_download_finished(self, plugin_id: str, url: str, ok: bool) -> None:
        """下载结束后在 GUI 线程更新状态并通知界面。"""
        self._downloading.discard(url)
        if ok:
            self.cover_ready.emit(plugin_id)
        else:
            self._failed.add(url)


_instance: PluginCoverService | None = None


def get_plugin_cover_service() -> PluginCoverService:
    """取全局封面服务，两个插件页面共用同一份缓存。"""
    global _instance
    if _instance is None:
        _instance = PluginCoverService()
    return _instance
