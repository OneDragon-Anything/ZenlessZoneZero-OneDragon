import os
from pathlib import Path

from one_dragon.base.config.yaml_config import YamlConfig
from one_dragon.utils import os_utils


class KeySimYamlConfig(YamlConfig):
    """键鼠脚本配置。

    读取优先级：用户 config/key_sim/<name>.yml > 插件注册目录内的 <name>.yml > 仓库 sample。
    插件目录内的脚本位置由插件自由组织，不限定子目录名。
    """

    def __init__(self, config_name: str, plugin_dir: Path | None = None):
        """
        Args:
            config_name: 脚本名（不含 .yml 后缀）
            plugin_dir: 当前应用插件目录下已注册的键鼠脚本目录；为 None 时跳过插件查找
        """
        self._plugin_dir: Path | None = plugin_dir
        YamlConfig.__init__(self, config_name, sub_dir=['key_sim'], sample=True,
                            copy_from_sample=False)

    def _get_yaml_file_paths(self) -> tuple[str | None, str | None, str | None]:
        # 用户自定义脚本优先，可覆盖插件同名脚本
        user_dir = os_utils.get_path_under_work_dir('config', 'key_sim')
        user_yml = os.path.join(user_dir, f'{self.module_name}.yml')
        if os.path.exists(user_yml):
            return user_yml, user_yml, None
        # 其次插件目录内任意位置（目录结构由插件自由组织，不限定子目录名）
        if self._plugin_dir is not None and self._plugin_dir.is_dir():
            for plugin_yml in self._plugin_dir.rglob(f'{self.module_name}.yml'):
                return str(plugin_yml), str(plugin_yml), None
        # 最后回退仓库自带 sample 文件
        return YamlConfig._get_yaml_file_paths(self)
