from one_dragon.envs.env_config import GH_PROXY_URLS, EnvConfig


class GhProxyService:
    """GitHub 免费代理线路服务。

    内置多条候选线路（见 env_config.GH_PROXY_URLS），不依赖解析第三方页面。
    使用方每次按候选顺序尝试一条，失败切换下一条，全部失败才算失败；
    成功线路由使用方写回 env_config.gh_proxy_url，下次优先尝试。
    """

    def __init__(self, env_config: EnvConfig):
        self.env_config = env_config

    def get_proxy_candidates(self) -> list[str]:
        """获取代理候选线路：上次成功线路优先，内置线路按顺序在后（去重）。"""
        candidates: list[str] = []
        last_proxy = self.env_config.gh_proxy_url.strip()
        if last_proxy:
            candidates.append(last_proxy)
        for proxy_url in GH_PROXY_URLS:
            if proxy_url not in candidates:
                candidates.append(proxy_url)
        return candidates
