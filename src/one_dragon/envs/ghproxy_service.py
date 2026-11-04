
import requests

from one_dragon.envs.env_config import EnvConfig
from one_dragon.envs.repo_config import RepoConfig
from one_dragon.utils.log_utils import log

_PROBE_GITHUB_URL = 'https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon/raw/main/pyproject.toml'
"""探测用的 GitHub 小文件，取到内容就认为线路可用。"""

_PROBE_TIMEOUT_SECONDS = 8


class GhProxyService:
    """GitHub 代理线路的候选、探测与记录。

    候选来源只有两处：`config/repository.yml` 的 `gh_proxy` 段（内置线路）和
    配置文件里记录的上次成功线路，不再解析任何第三方页面。

    Args:
        env_config: 环境配置，读写当前线路和上次成功线路。
        repo_config: 仓库配置，提供内置候选线路。
    """

    def __init__(self, env_config: EnvConfig, repo_config: RepoConfig):
        self.env_config = env_config
        self.repo_config = repo_config

    def get_candidate_urls(self) -> list[str]:
        """按「当前使用 → 上次成功 → 内置顺序」返回去重后的代理地址。

        Returns:
            代理根地址列表，例如 `['https://gh-proxy.com', 'https://ghfast.top']`。
        """
        candidates: list[str] = []
        for url in (
            self.env_config.gh_proxy_url,
            self.env_config.last_gh_proxy_url,
            *self.repo_config.gh_proxy_urls,
        ):
            normalized = url.rstrip('/') if url else ''
            if not normalized or normalized in candidates:
                continue
            candidates.append(normalized)
        return candidates

    def update_proxy_url(self) -> bool:
        """逐条探测候选线路，把第一条可用的写回配置。

        每条线路只探测一次，探测成功立刻停止；全部失败时保留原地址不动。

        Returns:
            找到可用线路返回 True，全部不可用返回 False。
        """
        candidates = self.get_candidate_urls()
        log.info('开始探测 GitHub 代理线路 共 %d 条', len(candidates))
        for url in candidates:
            if self.check_url(url):
                log.info('GitHub 代理线路可用 %s', url)
                self.remember_success(url)
                return True
            log.warning('GitHub 代理线路不可用 %s', url)

        log.error('所有 GitHub 代理线路都不可用 保留原地址 %s', self.env_config.gh_proxy_url)
        return False

    def check_url(self, proxy_url: str) -> bool:
        """用 GitHub 上的小文件检查一条代理线路是否可用。

        Args:
            proxy_url: 代理根地址，例如 `https://gh-proxy.com`。

        Returns:
            能取到内容返回 True，非 200 或任何异常返回 False。
        """
        probe_url = f'{proxy_url.rstrip("/")}/{_PROBE_GITHUB_URL}'
        try:
            response = requests.get(probe_url, timeout=_PROBE_TIMEOUT_SECONDS, stream=True)
            try:
                if response.status_code != 200:
                    return False
                return any(True for _ in response.iter_content(chunk_size=1024))
            finally:
                response.close()
        except Exception:
            log.debug('代理线路探测失败 %s', probe_url, exc_info=True)
            return False

    def remember_success(self, proxy_url: str) -> None:
        """把一条线路记录为当前使用，同时也是下次首选。

        Args:
            proxy_url: 代理根地址。
        """
        normalized = proxy_url.rstrip('/')
        if not normalized:
            return
        self.env_config.gh_proxy_url = normalized
        self.env_config.last_gh_proxy_url = normalized

    def remember_success_by_url(self, proxied_url: str) -> str | None:
        """按拼好的下载地址反查并记录实际可用的线路。

        Args:
            proxied_url: 带代理前缀的地址，例如 `https://gh-proxy.com/https://github.com/...`。

        Returns:
            命中的代理根地址；地址不带已知代理前缀时返回 None。
        """
        for candidate in self.get_candidate_urls():
            if proxied_url.startswith(f'{candidate}/'):
                self.remember_success(candidate)
                return candidate
        return None

