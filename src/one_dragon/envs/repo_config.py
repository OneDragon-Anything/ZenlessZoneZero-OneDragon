from dataclasses import dataclass
from urllib.parse import urlparse

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_config import YamlConfig


@dataclass(frozen=True)
class RepositoryItem:
    """YAML 中的一项代码源。"""

    repository_id: str
    label: str
    url: str
    use_proxy: bool

    @property
    def config_item(self) -> ConfigItem:
        return ConfigItem(self.label, self.url)


@dataclass(frozen=True)
class RegionPreset:
    """YAML 中的一项代码源地区预设。"""

    region_id: str
    label: str
    repository_id: str
    values: dict[str, str]

    @property
    def config_item(self) -> ConfigItem:
        return ConfigItem(self.label, self.region_id)


@dataclass(frozen=True)
class SourceOption:
    """YAML 中的一项下载源。"""

    source_id: str
    label: str
    value: str

    @property
    def config_item(self) -> ConfigItem:
        return ConfigItem(self.label, self.value)


class RepoConfig(YamlConfig):
    """项目代码仓库、下载源和地区预设配置。

    使用 OneDragon 框架的项目应在 ``config/repository.yml`` 中提供：

    - ``repositories``：包含 ``primary`` 和 ``options`` 的代码源配置组；
    - 顶层下载源配置组：每组包含 ``default`` 和 ``options``；
    - ``regions``：地区预设映射，包含显示标题、代码源和环境配置值。

    最小 YAML 示例：

    .. code-block:: yaml

        repositories:
          primary: main
          options:
            main:
              label: 主仓库
              url: https://example.com/example.git
              use_proxy: false
        env_source:
          default: main
          options:
            main:
              label: 默认
              value: https://example.com/env/releases/download
        regions:
          default:
            label: 默认
            repository: main
            values: {}
    """

    _SOURCE_EXCLUDED_KEYS = {'repositories', 'regions'}

    def __init__(self) -> None:
        YamlConfig.__init__(self, module_name='repository')
        repository_config = self._get_repository_config()
        self.repositories: tuple[RepositoryItem, ...] = self._load_repositories(repository_config)
        self._repositories_by_id: dict[str, RepositoryItem] = {
            repository.repository_id: repository for repository in self.repositories
        }
        primary_repository_id = repository_config.get('primary', '')
        if not isinstance(primary_repository_id, str) or not primary_repository_id:
            raise ValueError('repositories 必须配置 primary')
        self.primary_repository: RepositoryItem = self._get_repository(
            primary_repository_id,
            '主仓库',
        )
        self.regions: tuple[RegionPreset, ...] = self._load_regions()
        self._regions_by_id: dict[str, RegionPreset] = {
            region.region_id: region for region in self.regions
        }
        self.sources: dict[str, tuple[SourceOption, ...]] = self._load_sources()
        self.source_defaults: dict[str, str] = self._load_source_defaults()

    def _get_repository_config(self) -> dict:
        raw_repositories = self.get('repositories', {})
        if not isinstance(raw_repositories, dict):
            raise ValueError('config/repository.yml 必须配置 repositories')
        if not raw_repositories:
            raise ValueError('repositories 必须配置 primary')
        if 'primary' not in raw_repositories:
            raise ValueError('repositories 必须配置 primary')
        if 'options' not in raw_repositories:
            raise ValueError('repositories 必须配置 options')
        return raw_repositories

    def _load_repositories(self, repository_config: dict) -> tuple[RepositoryItem, ...]:
        raw_repositories = repository_config.get('options', {})
        if not isinstance(raw_repositories, dict) or not raw_repositories:
            raise ValueError('repositories.options 必须配置代码源')

        repositories: list[RepositoryItem] = []
        for repository_id, raw_repository in raw_repositories.items():
            if not isinstance(repository_id, str) or not isinstance(raw_repository, dict):
                raise ValueError('代码源配置必须是 ID 到对象的映射')
            label = raw_repository.get('label', '')
            url = raw_repository.get('url', '')
            use_proxy = raw_repository.get('use_proxy', False)
            if not repository_id or not isinstance(label, str) or not label or not isinstance(url, str) or not url:
                raise ValueError(f'代码源 {repository_id} 必须配置 label 和 url')
            if not isinstance(use_proxy, bool):
                raise ValueError(f'代码源 {repository_id} 的 use_proxy 必须是布尔值')
            parsed_url = urlparse(url)
            if parsed_url.scheme != 'https' or not parsed_url.netloc:
                raise ValueError(f'代码源 {repository_id} 必须使用 HTTPS 链接')
            repositories.append(
                RepositoryItem(
                    repository_id=repository_id,
                    label=label,
                    url=url,
                    use_proxy=use_proxy,
                )
            )
        return tuple(repositories)

    def _load_regions(self) -> tuple[RegionPreset, ...]:
        raw_regions = self.get('regions', {})
        if not isinstance(raw_regions, dict) or not raw_regions:
            raise ValueError('config/repository.yml 必须配置 regions')

        regions: list[RegionPreset] = []
        for region_id, raw_region in raw_regions.items():
            if not isinstance(region_id, str) or not isinstance(raw_region, dict):
                raise ValueError('地区预设配置必须是 ID 到对象的映射')
            label = raw_region.get('label', '')
            repository_id = raw_region.get('repository', '')
            values = raw_region.get('values', {})
            if not isinstance(label, str) or not label or not isinstance(repository_id, str) or not repository_id:
                raise ValueError(f'地区预设 {region_id} 必须配置 label 和 repository')
            if not isinstance(values, dict) or any(
                not isinstance(key, str) or not isinstance(value, str)
                for key, value in values.items()
            ):
                raise ValueError(f'地区预设 {region_id} 的 values 必须是字符串映射')
            self._get_repository(repository_id, f'地区 {region_id}')
            regions.append(
                RegionPreset(
                    region_id=region_id,
                    label=label,
                    repository_id=repository_id,
                    values=dict(values),
                )
            )
        return tuple(regions)

    def _load_sources(self) -> dict[str, tuple[SourceOption, ...]]:
        if 'sources' in self.data:
            raise ValueError('config/repository.yml 不再支持顶层 sources，请将下载源配置放到顶层')
        if not isinstance(self.data, dict):
            return {}

        sources: dict[str, tuple[SourceOption, ...]] = {}
        for source_name, raw_source_group in self.data.items():
            if source_name in self._SOURCE_EXCLUDED_KEYS:
                continue
            if not isinstance(source_name, str) or not isinstance(raw_source_group, dict):
                raise ValueError('下载源配置必须是名称到对象的映射')
            raw_options = raw_source_group.get('options', {})
            if not isinstance(raw_options, dict):
                raise ValueError(f'下载源 {source_name} 的 options 必须是映射')
            options: list[SourceOption] = []
            for source_id, raw_option in raw_options.items():
                if not isinstance(source_id, str) or not isinstance(raw_option, dict):
                    raise ValueError(f'下载源 {source_name} 的选项配置无效')
                label = raw_option.get('label', '')
                value = raw_option.get('value', '')
                if not isinstance(label, str) or not label or not isinstance(value, str) or not value:
                    raise ValueError(f'下载源 {source_name} 的选项必须配置 label 和 value')
                options.append(SourceOption(source_id, label, value))
            sources[source_name] = tuple(options)
        return sources

    def _load_source_defaults(self) -> dict[str, str]:
        defaults: dict[str, str] = {}
        for source_name, raw_source_group in self.data.items():
            if source_name in self._SOURCE_EXCLUDED_KEYS or not isinstance(raw_source_group, dict):
                continue
            default_id = raw_source_group.get('default', '')
            options = self.sources.get(source_name, ())
            default_option = next(
                (option for option in options if option.source_id == default_id),
                None,
            )
            if not isinstance(default_id, str) or not default_id:
                raise ValueError(f'下载源 {source_name} 必须配置 default')
            if default_option is None:
                raise ValueError(f'下载源 {source_name} 的默认值 {default_id} 不在 options 中')
            defaults[source_name] = default_option.value
        return defaults

    def _get_repository(self, repository_id: str, field_name: str) -> RepositoryItem:
        repository = self._repositories_by_id.get(repository_id)
        if repository is None:
            raise ValueError(f'{field_name} {repository_id} 不在 repositories.options 中')
        return repository

    @property
    def repository_options(self) -> list[ConfigItem]:
        """获取供设置界面使用的代码源选项。"""
        return [repository.config_item for repository in self.repositories]

    @property
    def region_options(self) -> list[ConfigItem]:
        """获取供设置界面使用的地区预设选项。"""
        return [region.config_item for region in self.regions]

    def find_repository(self, value: str) -> RepositoryItem | None:
        """按仓库 ID、显示标题或 URL 查找代码源。"""
        for repository in self.repositories:
            if value in (repository.repository_id, repository.label, repository.url):
                return repository
        return None

    def get_region_preset(self, region_id: str) -> RegionPreset | None:
        """按地区 ID 查找地区预设。"""
        return self._regions_by_id.get(region_id)

    def get_source_options(self, source_name: str) -> list[ConfigItem]:
        """获取指定下载源的设置选项。"""
        return [option.config_item for option in self.sources.get(source_name, ())]

    def get_source_default(self, source_name: str) -> str:
        """获取指定下载源的默认值。"""
        return self.source_defaults.get(source_name, '')

    def get_source_values(self, source_name: str) -> tuple[SourceOption, ...]:
        """获取指定下载源的测速选项。"""
        return self.sources.get(source_name, ())
