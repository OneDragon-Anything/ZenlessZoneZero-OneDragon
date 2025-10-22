import json
import requests

from one_dragon.envs.env_config import EnvConfig
from one_dragon.envs.project_config import ProjectConfig
from one_dragon.envs.mirrorchyan_config import MirrorChyanConfig


MIRROR_CHYAN_BASE_URL = 'https://mirrorchyan.com/api'


class MirrorChyanService:
    """Mirror酱服务"""

    def __init__(self, project_config: ProjectConfig, env_config: EnvConfig,
                 mirrorchyan_config: MirrorChyanConfig):
        self.project_config: ProjectConfig = project_config
        self.env_config: EnvConfig = env_config
        self.mirrorchyan_config: MirrorChyanConfig = mirrorchyan_config

    def _get_latest_resource_data(self) -> dict:
        """
        获取最新资源数据
        :return: 资源数据字典，失败时返回空字典
        """
        try:
            url = f'{MIRROR_CHYAN_BASE_URL}/resources/{self.project_config.project_name}/latest'
            response = requests.get(url)
            if response.status_code == 200:
                data = json.loads(response.text)
                if data.get('code') == 0 and 'data' in data:
                    return data['data']
            return {}
        except Exception:
            return {}

    def get_latest_version(self) -> str:
        """
        获取最新版本号
        :return: 最新版本号，失败时返回空字符串
        """
        data = self._get_latest_resource_data()
        return data.get('version_name', '').strip()

    def get_url(self) -> str:
        """
        获取最新版本的下载链接
        :return: 下载链接，失败时返回空字符串
        """
        data = self._get_latest_resource_data()
        return data.get('url', '').strip()

    def get_release_note(self) -> str:
        """
        获取最新版本的发布说明
        :return: 发布说明，失败时返回空字符串
        """
        data = self._get_latest_resource_data()
        return data.get('release_note', '').strip()
