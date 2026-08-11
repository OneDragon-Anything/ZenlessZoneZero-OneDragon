from dataclasses import dataclass
from urllib.parse import urlparse

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_config import YamlConfig
from one_dragon.utils.log_utils import log


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


class RepoConfig(YamlConfig):
    """项目代码仓库和下载源配置。

    使用 OneDragon 框架的项目应在 ``config/repository.yml`` 中提供：

    - ``repositories``：包含 ``primary``、``primary_branch``、``branches`` 和 ``options`` 的代码仓库配置组；
    - 顶层下载源配置组：每组包含 ``default`` 和 ``options``。

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

    配置容错约定：任何字段缺失或无效都不会抛异常，缺省时回退默认值，
    无效项直接跳过，保证配置文件不完整时程序也能正常启动。
    """

    AUTO_REPOSITORY_VALUE = 'auto'
    DEFAULT_BRANCH = 'main'
    _SOURCE_EXCLUDED_KEYS = {'repositories', 'regions'}
    # 内置兜底下载源：配置文件缺失对应源时使用，保证任何情况下都有可用源
    _BUILTIN_SOURCE_OPTIONS: dict[str, tuple[SourceOption, ...]] = {
        'env_source': (
            SourceOption('github', 'GitHub 官方', 'https://github.com/OneDragon-Anything/OneDragon-Env/releases/download'),
        ),
        'pip_source': (
            SourceOption('pypi', 'PyPI 官方', 'https://pypi.org/simple'),
        ),
    }
    # 内置兜底代码源：配置文件完全没有 repositories 时使用
    _BUILTIN_REPOSITORIES: tuple[RepositoryItem, ...] = (
        RepositoryItem(
            'github', 'GitHub 官方',
            'https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon.git',
            True,
        ),
    )

    def __init__(self, resource_first: bool = False) -> None:
        YamlConfig.__init__(self, module_name='repository', resource_first=resource_first)
        repository_config = self._get_repository_config()

        self.branches: tuple[RepositoryBranch, ...] = self._load_branches(repository_config)
        primary_branch = repository_config.get('primary_branch', '')
        if not isinstance(primary_branch, str) or not primary_branch.strip():
            primary_branch = self.branches[0].branch_name if self.branches else self.DEFAULT_BRANCH
        self.primary_branch: str = primary_branch

        self.repositories: tuple[RepositoryItem, ...] = self._load_repositories(repository_config)
        self._repositories_by_id: dict[str, RepositoryItem] = {
            repository.repository_id: repository for repository in self.repositories
        }
        self.primary_repository: RepositoryItem = self._get_primary_repository(repository_config)
        self.regions: tuple[RegionPreset, ...] = self._load_regions(repository_config)
        self._regions_by_id: dict[str, RegionPreset] = {
            region.region_id: region for region in self.regions
        }

        self.sources: dict[str, tuple[SourceOption, ...]] = self._load_sources()
        self.source_defaults: dict[str, str] = self._load_source_defaults()

    def _get_repository_config(self) -> dict:
        raw_repositories = self.get('repositories', {})
        if not isinstance(raw_repositories, dict) or not raw_repositories:
            log.warning('config/repository.yml 缺少 repositories 配置，将使用空配置')
            return {}
        return raw_repositories

    def _load_branches(self, repository_config: dict) -> tuple[RepositoryBranch, ...]:
        raw_branches = repository_config.get('branches', {})
        if not isinstance(raw_branches, dict) or not raw_branches:
            return ()

        branches: list[RepositoryBranch] = []
        for branch_name, raw_branch in raw_branches.items():
            if not isinstance(branch_name, str) or not branch_name or not isinstance(raw_branch, dict):
                log.warning(f'跳过无效代码分支配置: {branch_name}')
                continue
            label = raw_branch.get('label', '')
            desc = raw_branch.get('desc', '')
            if not isinstance(label, str) or not label:
                log.warning(f'跳过无效代码分支 {branch_name}: 缺少 label')
                continue
            if not isinstance(desc, str):
                log.warning(f'跳过无效代码分支 {branch_name}: desc 不是字符串')
                continue
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
            log.warning('repositories.options 缺失，使用内置默认代码源')
            return self._BUILTIN_REPOSITORIES

        repositories: list[RepositoryItem] = []
        for repository_id, raw_repository in raw_repositories.items():
            if not isinstance(repository_id, str) or not repository_id or not isinstance(raw_repository, dict):
                log.warning(f'跳过无效代码源配置: {repository_id}')
                continue
            label = raw_repository.get('label', '')
            url = raw_repository.get('url', '')
            use_proxy = raw_repository.get('use_proxy', False)
            if not isinstance(label, str) or not label or not isinstance(url, str) or not url:
                log.warning(f'跳过无效代码源 {repository_id}: 缺少 label 或 url')
                continue
            if not isinstance(use_proxy, bool):
                log.warning(f'跳过无效代码源 {repository_id}: use_proxy 不是布尔值')
                continue
            parsed_url = urlparse(url)
            if parsed_url.scheme != 'https' or not parsed_url.netloc:
                log.warning(f'跳过无效代码源 {repository_id}: 必须使用 HTTPS 链接')
                continue
            repositories.append(
                RepositoryItem(
                    repository_id=repository_id,
                    label=label,
                    url=url,
                    use_proxy=use_proxy,
                )
            )
        return tuple(repositories)

    def _get_primary_repository(self, repository_config: dict) -> RepositoryItem:
        """获取主代码源，缺失或无效时回退到第一个可用代码源。"""
        primary_repository_id = repository_config.get('primary', '')
        if isinstance(primary_repository_id, str) and primary_repository_id:
            repository = self._repositories_by_id.get(primary_repository_id)
            if repository is not None:
                return repository
        if self.repositories:
            log.warning(f'主代码源 {primary_repository_id} 不可用，回退到 {self.repositories[0].repository_id}')
            return self.repositories[0]
        log.warning('没有可用的代码源配置')
        return RepositoryItem('', '', '', False)

    def _load_regions(self, repository_config: dict) -> tuple[RegionPreset, ...]:
        raw_regions = self.get('regions', {})
        if not isinstance(raw_regions, dict) or not raw_regions:
            return ()

        regions: list[RegionPreset] = []
        for region_id, raw_region in raw_regions.items():
            if not isinstance(region_id, str) or not region_id or not isinstance(raw_region, dict):
                log.warning(f'跳过无效地区预设配置: {region_id}')
                continue
            label = raw_region.get('label', '')
            repository_id = raw_region.get('repository', '')
            values = raw_region.get('values', {})
            if not isinstance(label, str) or not label or not isinstance(repository_id, str) or not repository_id:
                log.warning(f'跳过无效地区预设 {region_id}: 缺少 label 或 repository')
                continue
            if not isinstance(values, dict) or any(
                not isinstance(key, str) or not isinstance(value, str)
                for key, value in values.items()
            ):
                log.warning(f'跳过无效地区预设 {region_id}: values 必须是字符串映射')
                continue
            if self._repositories_by_id.get(repository_id) is None:
                log.warning(f'跳过无效地区预设 {region_id}: 代码源 {repository_id} 不存在')
                continue
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
            log.warning('config/repository.yml 不再支持顶层 sources，已忽略')
        if not isinstance(self.data, dict):
            return {}

        sources: dict[str, tuple[SourceOption, ...]] = {}
        for source_name, raw_source_group in self.data.items():
            if source_name in self._SOURCE_EXCLUDED_KEYS:
                continue
            if not isinstance(source_name, str) or not isinstance(raw_source_group, dict):
                log.warning(f'跳过无效下载源配置: {source_name}')
                continue
            raw_options = raw_source_group.get('options', {})
            if not isinstance(raw_options, dict):
                log.warning(f'跳过无效下载源 {source_name}: options 不是映射')
                continue
            options: list[SourceOption] = []
            for source_id, raw_option in raw_options.items():
                if not isinstance(source_id, str) or not source_id or not isinstance(raw_option, dict):
                    log.warning(f'跳过无效下载源 {source_name} 的选项: {source_id}')
                    continue
                label = raw_option.get('label', '')
                value = raw_option.get('value', '')
                if not isinstance(label, str) or not label or not isinstance(value, str) or not value:
                    log.warning(f'跳过无效下载源 {source_name} 的选项 {source_id}: 缺少 label 或 value')
                    continue
                options.append(SourceOption(source_id, label, value))
            sources[source_name] = tuple(options)
        # 配置缺失的常用下载源用内置官方源兜底
        for builtin_name, builtin_options in self._BUILTIN_SOURCE_OPTIONS.items():
            if not sources.get(builtin_name):
                log.warning(f'下载源 {builtin_name} 未配置，使用内置官方源')
                sources[builtin_name] = builtin_options
        return sources

    def _load_source_defaults(self) -> dict[str, str]:
        defaults: dict[str, str] = {}
        for source_name, raw_source_group in self.data.items():
            if source_name in self._SOURCE_EXCLUDED_KEYS or not isinstance(raw_source_group, dict):
                continue
            options = self.sources.get(source_name, ())
            if not options:
                continue
            default_id = raw_source_group.get('default', '')
            default_option = next(
                (option for option in options if option.source_id == default_id),
                None,
            )
            if default_option is None:
                default_option = options[0]
                log.warning(f'下载源 {source_name} 的默认值 {default_id} 无效，回退到 {default_option.source_id}')
            defaults[source_name] = default_option.value
        # 内置兜底源的默认值
        for builtin_name, builtin_options in self._BUILTIN_SOURCE_OPTIONS.items():
            if builtin_name not in defaults and builtin_options:
                defaults[builtin_name] = builtin_options[0].value
        return defaults

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
