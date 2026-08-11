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
class RepositoryBranch:
    """YAML 中的一项代码分支。"""

    branch_name: str
    label: str
    desc: str

    @property
    def config_item(self) -> ConfigItem:
        return ConfigItem(self.label, self.branch_name, self.desc)


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


@dataclass(frozen=True)
class ResourceSource:
    """YAML 中的一项资源release下载源。"""

    source_id: str
    label: str
    use_proxy: bool

    @property
    def config_item(self) -> ConfigItem:
        return ConfigItem(self.label, self.source_id)


@dataclass(frozen=True)
class ModelResourceDefinition:
    """YAML 中的一项项目识别模型。"""

    config_key: str
    display_name: str
    default_model: str
    repo_key: str
    release_tag: str
    gpu_config_key: str | None
    required_files: tuple[str, ...]


class RepoConfig(YamlConfig):
    """项目代码仓库、下载源和地区预设配置。

    使用 OneDragon 框架的项目应在 ``config/repository.yml`` 中提供：

    - ``repositories``：包含 ``primary``、``primary_branch``、``branches`` 和 ``options`` 的代码仓库配置组；
    - 顶层下载源配置组：每组包含 ``default`` 和 ``options``；
    - ``regions``：地区预设映射，包含显示标题、代码源和环境配置值。

    最小 YAML 示例：

    .. code-block:: yaml

        repositories:
          primary: main
          primary_branch: main
          branches:
            main:
              label: 主分支
              desc: 选择后请点击同步最新代码
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

    AUTO_REPOSITORY_VALUE = 'auto'
    AUTO_RESOURCE_SOURCE_VALUE = 'auto'
    _SOURCE_EXCLUDED_KEYS = {'repositories', 'regions', 'resource_download'}

    def __init__(self) -> None:
        YamlConfig.__init__(self, module_name='repository')
        repository_config = self._get_repository_config()
        primary_branch = repository_config.get('primary_branch', '')
        if not isinstance(primary_branch, str) or not primary_branch.strip():
            raise ValueError('repositories 必须配置 primary_branch')
        self.primary_branch: str = primary_branch
        self.branches: tuple[RepositoryBranch, ...] = self._load_branches(repository_config)
        if not any(branch.branch_name == self.primary_branch for branch in self.branches):
            raise ValueError(
                f'repositories.primary_branch {self.primary_branch} 不在 repositories.branches 中'
            )
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
        self.resource_sources: tuple[ResourceSource, ...] = self._load_resource_sources()
        self._resource_sources_by_id: dict[str, ResourceSource] = {
            source.source_id: source for source in self.resource_sources
        }
        self.resource_recommend: dict[str, str] = self._load_resource_recommend()
        self.resource_repos: dict[str, dict[str, str]] = self._load_resource_repos()
        self.model_resources: tuple[ModelResourceDefinition, ...] = (
            self._load_model_resources()
        )

    def _get_repository_config(self) -> dict:
        raw_repositories = self.get('repositories', {})
        if not isinstance(raw_repositories, dict):
            raise ValueError('config/repository.yml 必须配置 repositories')
        if not raw_repositories:
            raise ValueError('repositories 必须配置 primary')
        if 'primary' not in raw_repositories:
            raise ValueError('repositories 必须配置 primary')
        if 'primary_branch' not in raw_repositories:
            raise ValueError('repositories 必须配置 primary_branch')
        if 'branches' not in raw_repositories:
            raise ValueError('repositories 必须配置 branches')
        if 'options' not in raw_repositories:
            raise ValueError('repositories 必须配置 options')
        return raw_repositories

    def _load_branches(self, repository_config: dict) -> tuple[RepositoryBranch, ...]:
        raw_branches = repository_config.get('branches', {})
        if not isinstance(raw_branches, dict) or not raw_branches:
            raise ValueError('repositories.branches 必须配置代码分支')

        branches: list[RepositoryBranch] = []
        for branch_name, raw_branch in raw_branches.items():
            if not isinstance(branch_name, str) or not branch_name or not isinstance(raw_branch, dict):
                raise ValueError('代码分支配置必须是分支名到对象的映射')
            label = raw_branch.get('label', '')
            desc = raw_branch.get('desc', '')
            if not isinstance(label, str) or not label:
                raise ValueError(f'代码分支 {branch_name} 必须配置 label')
            if not isinstance(desc, str):
                raise ValueError(f'代码分支 {branch_name} 的 desc 必须是字符串')
            branches.append(
                RepositoryBranch(
                    branch_name=branch_name,
                    label=label,
                    desc=desc,
                )
            )
        return tuple(branches)

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

    def _get_resource_download_config(self) -> dict:
        raw = self.data.get('resource_download', {})
        if raw is None:
            return {}
        if not isinstance(raw, dict):
            raise ValueError('resource_download 必须是映射')
        return raw

    def _load_resource_sources(self) -> tuple[ResourceSource, ...]:
        raw_sources = self._get_resource_download_config().get('sources', {})
        if not isinstance(raw_sources, dict):
            raise ValueError('resource_download.sources 必须是映射')

        sources: list[ResourceSource] = []
        for source_id, raw_source in raw_sources.items():
            if not isinstance(source_id, str) or not source_id or not isinstance(raw_source, dict):
                raise ValueError('resource_download.sources 必须是 ID 到对象的映射')
            label = raw_source.get('label', '')
            use_proxy = raw_source.get('use_proxy', False)
            if not isinstance(label, str) or not label:
                raise ValueError(f'资源下载源 {source_id} 必须配置 label')
            if not isinstance(use_proxy, bool):
                raise ValueError(f'资源下载源 {source_id} 的 use_proxy 必须是布尔值')
            sources.append(ResourceSource(source_id=source_id, label=label, use_proxy=use_proxy))
        return tuple(sources)

    def _load_resource_recommend(self) -> dict[str, str]:
        raw_recommend = self._get_resource_download_config().get('recommend', {})
        if not isinstance(raw_recommend, dict):
            raise ValueError('resource_download.recommend 必须是映射')

        recommend: dict[str, str] = {}
        for language, source_id in raw_recommend.items():
            if not isinstance(language, str) or not isinstance(source_id, str):
                raise ValueError('resource_download.recommend 必须是语言到源 ID 的映射')
            if source_id not in self._resource_sources_by_id:
                raise ValueError(f'resource_download.recommend 的 {source_id} 不在 sources 中')
            recommend[language] = source_id
        return recommend

    def _load_resource_repos(self) -> dict[str, dict[str, str]]:
        raw_repos = self._get_resource_download_config().get('repos', {})
        if not isinstance(raw_repos, dict):
            raise ValueError('resource_download.repos 必须是映射')

        repos: dict[str, dict[str, str]] = {}
        for repo_key, raw_urls in raw_repos.items():
            if not isinstance(repo_key, str) or not repo_key or not isinstance(raw_urls, dict):
                raise ValueError('resource_download.repos 必须是仓库到源 URL 的映射')
            urls: dict[str, str] = {}
            for source_id, url in raw_urls.items():
                if source_id not in self._resource_sources_by_id:
                    raise ValueError(f'资源仓库 {repo_key} 的 {source_id} 不在 sources 中')
                if not isinstance(url, str) or not url:
                    raise ValueError(f'资源仓库 {repo_key} 的 {source_id} 必须配置 URL')
                parsed_url = urlparse(url)
                if parsed_url.scheme != 'https' or not parsed_url.netloc:
                    raise ValueError(f'资源仓库 {repo_key} 的 {source_id} 必须使用 HTTPS 链接')
                urls[source_id] = url
            repos[repo_key] = urls
        return repos

    def _load_model_resources(self) -> tuple[ModelResourceDefinition, ...]:
        raw_models = self._get_resource_download_config().get('models', {})
        if not isinstance(raw_models, dict):
            raise ValueError('resource_download.models 必须是映射')

        models: list[ModelResourceDefinition] = []
        for config_key, raw_model in raw_models.items():
            if (
                not isinstance(config_key, str)
                or not config_key
                or not isinstance(raw_model, dict)
            ):
                raise ValueError('resource_download.models 必须是配置键到对象的映射')
            display_name = raw_model.get('label', '')
            default_model = raw_model.get('default', '')
            repo_key = raw_model.get('repo', '')
            release_tag = raw_model.get('tag', '')
            gpu_config_key = raw_model.get('gpu_config')
            required_files = raw_model.get(
                'required_files',
                ['model.onnx', 'labels.csv'],
            )
            if not isinstance(display_name, str) or not display_name:
                raise ValueError(f'模型资源 {config_key} 必须配置 label')
            if not isinstance(default_model, str) or not default_model:
                raise ValueError(f'模型资源 {config_key} 必须配置 default')
            if (
                not isinstance(repo_key, str)
                or not repo_key
                or repo_key not in self.resource_repos
            ):
                raise ValueError(
                    f'模型资源 {config_key} 的 repo 必须存在于 resource_download.repos'
                )
            if not isinstance(release_tag, str):
                raise ValueError(f'模型资源 {config_key} 的 tag 必须是字符串')
            if gpu_config_key is not None and not isinstance(gpu_config_key, str):
                raise ValueError(f'模型资源 {config_key} 的 gpu_config 必须是字符串')
            if (
                not isinstance(required_files, list)
                or not required_files
                or any(
                    not isinstance(file_name, str) or not file_name
                    for file_name in required_files
                )
            ):
                raise ValueError(
                    f'模型资源 {config_key} 的 required_files 必须是非空字符串列表'
                )
            models.append(
                ModelResourceDefinition(
                    config_key=config_key,
                    display_name=display_name,
                    default_model=default_model,
                    repo_key=repo_key,
                    release_tag=release_tag,
                    gpu_config_key=gpu_config_key,
                    required_files=tuple(required_files),
                )
            )
        return tuple(models)

    def _get_repository(self, repository_id: str, field_name: str) -> RepositoryItem:
        repository = self._repositories_by_id.get(repository_id)
        if repository is None:
            raise ValueError(f'{field_name} {repository_id} 不在 repositories.options 中')
        return repository

    @property
    def branch_options(self) -> list[ConfigItem]:
        """获取供代码版本下拉框使用的分支选项。"""
        return [branch.config_item for branch in self.branches]

    @property
    def repository_options(self) -> list[ConfigItem]:
        """获取供设置界面使用的自动和具体代码源选项。"""
        return [
            ConfigItem('自动', self.AUTO_REPOSITORY_VALUE),
            *(repository.config_item for repository in self.repositories),
        ]

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

    @property
    def resource_source_options(self) -> list[ConfigItem]:
        """获取供设置界面使用的自动和具体资源下载源选项。"""
        return [
            ConfigItem('自动', self.AUTO_RESOURCE_SOURCE_VALUE),
            *(source.config_item for source in self.resource_sources),
        ]

    def get_resource_source(self, source_id: str) -> ResourceSource | None:
        """按源 ID 查找资源下载源。"""
        return self._resource_sources_by_id.get(source_id)

    def get_recommended_resource_source(self, language: str) -> str | None:
        """按语言获取推荐的资源下载源 ID。"""
        return self.resource_recommend.get(language)

    def get_model_resource(
        self,
        config_key: str,
    ) -> ModelResourceDefinition | None:
        """按配置键获取项目模型资源定义。"""
        return next(
            (
                resource
                for resource in self.model_resources
                if resource.config_key == config_key
            ),
            None,
        )

    def get_resource_download_base_url(
        self,
        repo_key: str,
        tag: str,
        source_id: str,
    ) -> str:
        """获取资源仓库指定源的 release 下载根地址。"""
        release_root = self.resource_repos.get(repo_key, {}).get(source_id, '')
        if not release_root:
            return ''
        if tag:
            return f'{release_root}/download/{tag}'
        return f'{release_root}/latest/download'

    def get_model_download_base_url(
        self,
        config_key: str,
        source_id: str,
    ) -> str:
        """获取项目模型指定源的 release 下载根地址。"""
        resource = self.get_model_resource(config_key)
        if resource is None:
            return ''
        return self.get_resource_download_base_url(
            resource.repo_key,
            resource.release_tag,
            source_id,
        )

    def get_resource_asset_urls(self, repo_key: str, tag: str, file_name: str) -> dict[str, str]:
        """获取资源仓库各源的 release 附件下载地址。

        :param repo_key: resource_download.repos 中的仓库标识
        :param tag: release 标签 为空时使用 latest
        :param file_name: 附件文件名
        :return: 源 ID 到下载地址的映射
        """
        urls: dict[str, str] = {}
        for source_id in self.resource_repos.get(repo_key, {}):
            base_url = self.get_resource_download_base_url(
                repo_key,
                tag,
                source_id,
            )
            if base_url:
                urls[source_id] = f'{base_url}/{file_name}'
        return urls

    def get_resource_source_candidates(
        self,
        user_choice: str | None = None,
        last_success: str | None = None,
        language: str | None = None,
    ) -> list[str]:
        """获取资源下载的候选源顺序。

        顺序为: 用户指定 > 上次成功源 > 按语言推荐 > 其余源(按 YAML 顺序)。

        :param user_choice: 用户指定的源 ID auto 或 None 表示自动
        :param last_success: 上次下载成功的源 ID
        :param language: 当前语言 用于推荐
        :return: 源 ID 列表
        """
        candidates: list[str] = []

        def _add(source_id: str | None) -> None:
            if source_id and source_id in self._resource_sources_by_id and source_id not in candidates:
                candidates.append(source_id)

        if user_choice and user_choice != self.AUTO_RESOURCE_SOURCE_VALUE:
            _add(user_choice)
        _add(last_success)
        if language:
            _add(self.resource_recommend.get(language))
        for source in self.resource_sources:
            _add(source.source_id)
        return candidates
