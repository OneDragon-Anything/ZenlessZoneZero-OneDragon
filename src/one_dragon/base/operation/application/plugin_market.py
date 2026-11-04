"""插件市场：商店条目模型与数据拉取。

市场数据来自插件商店站点发布的 plugins.json，包含每个插件的简介、仓库、
最新版本下载地址与更新日志。这里只负责拉取、解析和本地缓存，不涉及安装。
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log

MARKET_URL = 'https://onedragon-anyone.github.io/plugin-data/api/v1/plugins.json'
"""插件市场索引地址。

数据仓（OneDragon-Anyone/plugin-data）提供审核配置，构建产物发布到
plugin-data 站点的 api/v1/ 下；旧地址 plugin-registry/plugins.json 已废弃。
"""

CACHE_TTL_SECONDS = 600
"""市场数据的本地缓存有效期，过期后重新拉取。"""

MIN_BYTES_PER_SECOND = 1024
"""市场数据下载的最低持续速度，低于该值即中止，避免服务端慢速滴流时线程长期不结束。"""


@dataclass(frozen=True)
class MarketRelease:
    """市场条目的一次发布。"""

    version: str
    published_at: str
    download_url: str
    sha256: str
    changelog_html: str


@dataclass(frozen=True)
class MarketPlugin:
    """插件市场中的一个条目。"""

    plugin_id: str
    name: str
    summary: str
    author_name: str
    author_url: str
    repo: str
    tags: list[str]
    status: str
    readme_html: str
    latest: MarketRelease | None
    releases: list[MarketRelease]
    cover_url: str = ''
    pinned: bool = False
    """运营置顶，列表排序时排在前面。"""
    stale: bool = False
    """插件仓库长期无法访问，维护状态存疑。"""

    @property
    def is_listed(self) -> bool:
        """是否在市场中正常列出。"""
        return self.status == 'listed'

    @property
    def latest_version(self) -> str:
        """市场最新版本号，没有发布记录时为空字符串。"""
        return self.latest.version if self.latest is not None else ''

    @property
    def initial(self) -> str:
        """卡片图标用的首字。"""
        text = (self.name or self.plugin_id).strip()
        return text[0].upper() if text else '?'


@dataclass
class MarketSnapshot:
    """一次完整的市场读取结果。"""

    plugins: list[MarketPlugin]
    fetched_at: float
    from_cache: bool

    def get(self, plugin_id: str) -> MarketPlugin | None:
        for plugin in self.plugins:
            if plugin.plugin_id == plugin_id:
                return plugin
        return None


def _parse_release(raw: dict) -> MarketRelease | None:
    version = str(raw.get('version') or '').strip()
    if not version:
        return None
    return MarketRelease(
        version=version,
        published_at=str(raw.get('publishedAt') or ''),
        download_url=str(raw.get('downloadUrl') or ''),
        sha256=str(raw.get('sha256') or ''),
        changelog_html=str(raw.get('changelogHtml') or ''),
    )


def _parse_plugin(raw: dict) -> MarketPlugin | None:
    plugin_id = str(raw.get('id') or '').strip()
    if not plugin_id:
        return None

    author = raw.get('author') or {}
    latest = raw.get('latest')
    releases: list[MarketRelease] = []
    for item in raw.get('releases') or []:
        release = _parse_release(item) if isinstance(item, dict) else None
        if release is not None:
            releases.append(release)

    return MarketPlugin(
        plugin_id=plugin_id,
        name=str(raw.get('name') or plugin_id),
        summary=str(raw.get('summary') or ''),
        author_name=str(author.get('name') or '') if isinstance(author, dict) else '',
        author_url=str(author.get('url') or '') if isinstance(author, dict) else '',
        repo=str(raw.get('repo') or ''),
        tags=[str(tag) for tag in (raw.get('tags') or [])],
        status=str(raw.get('status') or ''),
        readme_html=str(raw.get('readmeHtml') or ''),
        latest=_parse_release(latest) if isinstance(latest, dict) else None,
        releases=releases,
        cover_url=str(raw.get('cover') or ''),
        pinned=bool(raw.get('pinned')),
        stale=bool(raw.get('stale')),
    )


def parse_market_payload(payload: dict | list) -> list[MarketPlugin]:
    """把 plugins.json 的原始内容解析成条目列表。

    站点发布的数据既可能是以 id 为键的字典，也可能是条目数组，两种都要接。

    Args:
        payload: plugins.json 反序列化后的内容。

    Returns:
        未排序的条目列表；非法条目被跳过。
    """
    raw_items = payload.values() if isinstance(payload, dict) else payload
    plugins: list[MarketPlugin] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        plugin = _parse_plugin(raw)
        if plugin is not None:
            plugins.append(plugin)
    return plugins


class PluginMarketService:
    """负责拉取并缓存插件市场数据。"""

    def __init__(self, cache_path: Path | None = None) -> None:
        self._cache_path: Path = cache_path or (
            Path(os_utils.get_path_under_work_dir('config')) / 'plugin_market_cache.json'
        )
        self._snapshot: MarketSnapshot | None = None
        self._lock: threading.Lock = threading.Lock()
        """两个插件页共用一份服务，可能同时从各自的后台线程调用 load()。"""

    @property
    def cache_path(self) -> Path:
        return self._cache_path

    def load(self, force: bool = False) -> MarketSnapshot:
        """读取市场数据，优先使用未过期的本地缓存。

        两个插件页共用同一份服务，两个后台线程可能同时进入。整段加载串行执行，
        拿到锁后重新检查快照，避免重复下载与同时写同一个缓存文件。

        Args:
            force: 忽略缓存有效期，强制重新拉取。

        Returns:
            市场快照。拉取失败且没有可用缓存时返回空列表的快照。
        """
        with self._lock:
            return self._load_locked(force)

    def _load_locked(self, force: bool) -> MarketSnapshot:
        now = time.time()
        if not force:
            if self._snapshot is not None and now - self._snapshot.fetched_at < CACHE_TTL_SECONDS:
                return self._snapshot
            cached = self._read_cache()
            if cached is not None and now - cached.fetched_at < CACHE_TTL_SECONDS:
                self._snapshot = cached
                return cached

        try:
            payload = self._download()
        except Exception as exc:  # noqa: BLE001 - 网络异常统一降级
            log.error(f'拉取插件市场数据失败: {exc}')
            cached = self._read_cache()
            if cached is not None:
                return MarketSnapshot(plugins=cached.plugins, fetched_at=cached.fetched_at, from_cache=True)
            return MarketSnapshot(plugins=[], fetched_at=0.0, from_cache=False)

        snapshot = MarketSnapshot(plugins=payload, fetched_at=now, from_cache=False)
        self._snapshot = snapshot
        self._write_cache(snapshot)
        return snapshot

    def _download(self) -> list[MarketPlugin]:
        # 延迟导入，避免模块加载期就引入网络依赖
        from one_dragon.utils import http_utils

        target = Path(os_utils.get_path_under_work_dir('config', 'temp')) / 'plugin_market.json'
        ok = http_utils.download_file(
            MARKET_URL,
            str(target),
            min_bytes_per_second=MIN_BYTES_PER_SECOND,
        )
        if not ok or not target.exists():
            raise RuntimeError('插件市场数据下载失败')
        payload = json.loads(target.read_text(encoding='utf-8'))
        if not isinstance(payload, (dict, list)):
            raise RuntimeError('插件市场数据格式异常')
        return parse_market_payload(payload)

    def _read_cache(self) -> MarketSnapshot | None:
        if not self._cache_path.exists():
            return None
        try:
            payload = json.loads(self._cache_path.read_text(encoding='utf-8'))
            fetched_at = float(payload.get('fetched_at') or 0)
            raw_plugins = payload.get('plugins') or {}
            if not isinstance(raw_plugins, dict):
                return None
            return MarketSnapshot(
                plugins=parse_market_payload(raw_plugins),
                fetched_at=fetched_at,
                from_cache=True,
            )
        except Exception as exc:  # noqa: BLE001 - 缓存损坏时按无缓存处理
            log.warning(f'读取插件市场缓存失败: {exc}')
            return None

    def _write_cache(self, snapshot: MarketSnapshot) -> None:
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            raw_plugins = {
                plugin.plugin_id: {
                    'id': plugin.plugin_id,
                    'name': plugin.name,
                    'summary': plugin.summary,
                    'author': {'name': plugin.author_name, 'url': plugin.author_url},
                    'repo': plugin.repo,
                    'tags': plugin.tags,
                    'status': plugin.status,
                    'readmeHtml': plugin.readme_html,
                    'cover': plugin.cover_url,
                    'pinned': plugin.pinned,
                    'stale': plugin.stale,
                    'latest': _release_to_raw(plugin.latest),
                    'releases': [_release_to_raw(release) for release in plugin.releases],
                }
                for plugin in snapshot.plugins
            }
            payload = {'fetched_at': snapshot.fetched_at, 'plugins': raw_plugins}
            self._cache_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
        except Exception as exc:  # noqa: BLE001 - 缓存写入失败不影响主流程
            log.warning(f'写入插件市场缓存失败: {exc}')


def _release_to_raw(release: MarketRelease | None) -> dict | None:
    if release is None:
        return None
    return {
        'version': release.version,
        'publishedAt': release.published_at,
        'downloadUrl': release.download_url,
        'sha256': release.sha256,
        'changelogHtml': release.changelog_html,
    }


_service_instance: PluginMarketService | None = None


def get_plugin_market_service() -> PluginMarketService:
    """取全局市场服务。

    两个插件页面共用一份，避免首次打开时并发拉同一份 plugins.json，
    也避免同时写同一个缓存文件。
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = PluginMarketService()
    return _service_instance
