import re

import requests

from one_dragon.envs.env_config import EnvConfig
from one_dragon.utils.log_utils import log


class GhProxyService:

    def __init__(self, env_config: EnvConfig):
        self.env_config = env_config

    def update_proxy_url(self) -> None:
        """
        更新免费代理的url
        :return:
        """
        url = 'https://ghproxy.link/js/src_views_home_HomeView_vue.js'  # 打开 https://ghproxy.link/ 后找到的js文件
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://ghproxy.link/'
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            js_content = response.text
        except Exception:
            log.error('自动获取免费代理地址失败', exc_info=True)
            return

        url_prefix = '<a href=\\\\\\"'
        url_prefix_idx = js_content.find(url_prefix)
        if url_prefix_idx == -1:
            log.error('自动获取免费代理地址失败')
            return

        url_suffix = '\\\\\\" target='
        url_suffix_idx = js_content.find(url_suffix)
        if url_suffix_idx == -1:
            log.error('自动获取免费代理地址失败')
            return

        another_url_prefix_idx = js_content.find(url_prefix, url_suffix_idx)  # 理论上这个文件里只有一个 <a href> 标签 有多个时候忽略 等待后续再处理
        if another_url_prefix_idx != -1:
            log.error('自动获取免费代理地址失败 有多个 <a href> 标签')
            return

        proxy_url = js_content[url_prefix_idx + len(url_prefix):url_suffix_idx]
        # 判断 proxy_url 是一个 https 开头的域名 不包含任何路径 例如 https://ghfast.top
        pattern = r'^https://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        # 使用正则表达式匹配
        if not re.match(pattern, proxy_url):
            log.error('自动获取免费代理地址失败 提取域名不合法 %s', proxy_url)
            return

        log.info('自动获取免费代理地址成功 %s', proxy_url)
        self.env_config.gh_proxy_url = proxy_url


def __debug():
    service = GhProxyService(None)
    service.update_proxy_url()


if __name__ == '__main__':
    __debug()
