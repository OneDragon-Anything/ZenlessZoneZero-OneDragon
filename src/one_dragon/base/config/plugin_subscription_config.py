"""插件订阅记录。

订阅指从插件商店的网页源安装或更新。本地导入、手动放进 plugins 目录只算安装，
不写订阅记录。一条订阅记录把市场条目、本地应用、插件目录绑在一起，
并保存用户跳过的版本号。
"""

from __future__ import annotations

from one_dragon.base.config.yaml_config import YamlConfig


class PluginSubscriptionConfig(YamlConfig):
    """插件订阅记录配置。"""

    def __init__(self) -> None:
        YamlConfig.__init__(self, module_name='plugin_subscription')

    @property
    def records(self) -> dict[str, dict]:
        """全部订阅记录，键为市场条目 id。"""
        raw = self.get('records', {})
        if not isinstance(raw, dict):
            return {}
        return {str(key): value for key, value in raw.items() if isinstance(value, dict)}

    def get_record(self, registry_id: str) -> dict | None:
        """按市场条目 id 取订阅记录。

        Args:
            registry_id: 市场条目 id。

        Returns:
            记录字典，不存在时返回 None。
        """
        return self.records.get(registry_id)

    def upsert_record(
        self,
        registry_id: str,
        app_id: str,
        plugin_dir_name: str,
        installed_version: str = '',
        source: str = 'market',
    ) -> None:
        """写入或更新一条订阅记录，保留原有的忽略版本。

        Args:
            registry_id: 市场条目 id。
            app_id: 插件声明的应用 id。
            plugin_dir_name: 插件在 plugins 目录下的目录名。
            installed_version: 已安装版本号。
            source: market 表示从网页源安装或更新；local 只为记下跳过的版本，不算订阅。
        """
        if not registry_id:
            return
        current = self.records
        old = current.get(registry_id) or {}
        current[registry_id] = {
            'app_id': app_id,
            'plugin_dir_name': plugin_dir_name,
            'installed_version': installed_version,
            'ignored_version': str(old.get('ignored_version') or ''),
            'source': source,
        }
        self.update('records', current)

    def remove_record(self, registry_id: str) -> None:
        """删除一条订阅记录。

        Args:
            registry_id: 市场条目 id。
        """
        current = self.records
        if registry_id not in current:
            return
        current.pop(registry_id)
        self.update('records', current)

    def set_ignored_version(self, registry_id: str, version: str) -> None:
        """记录用户跳过的版本。

        Args:
            registry_id: 市场条目 id。
            version: 被忽略的版本号，传空字符串表示取消忽略。
        """
        current = self.records
        record = current.get(registry_id)
        if record is None:
            return
        # 必须换成新字典：record 与 self.data 里的是同一个对象，原地改会让
        # update() 判断新旧值相等而跳过保存
        current[registry_id] = {**record, 'ignored_version': version}
        self.update('records', current)

    def find_registry_id(self, app_id: str, plugin_dir_name: str) -> str | None:
        """反查某个本地插件对应的市场条目 id。

        先按目录名匹配，再退回应用 id，两者都取第一个命中项。

        Args:
            app_id: 插件声明的应用 id。
            plugin_dir_name: 插件在 plugins 目录下的目录名。

        Returns:
            命中的市场条目 id，未命中返回 None。
        """
        records = self.records
        if plugin_dir_name:
            for registry_id, record in records.items():
                if str(record.get('plugin_dir_name') or '') == plugin_dir_name:
                    return registry_id
        if app_id:
            for registry_id, record in records.items():
                if str(record.get('app_id') or '') == app_id:
                    return registry_id
        return None


_instance: PluginSubscriptionConfig | None = None


def get_plugin_subscription_config() -> PluginSubscriptionConfig:
    """取全局订阅记录。

    插件管理与插件商店必须共用同一份实例：配置保存时会把整份内存快照写回
    文件，两个实例各自持有旧快照会互相覆盖，导致订阅记录丢失。
    """
    global _instance
    if _instance is None:
        _instance = PluginSubscriptionConfig()
    return _instance
