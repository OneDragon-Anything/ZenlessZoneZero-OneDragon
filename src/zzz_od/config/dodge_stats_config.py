from one_dragon.base.config.yaml_config import YamlConfig


class DodgeStatsConfig(YamlConfig):
    """格挡统计配置，持久化存储累计格挡次数"""

    def __init__(self):
        YamlConfig.__init__(self, module_name='dodge_stats')

    @property
    def dodge_count(self) -> int:
        return self.get('dodge_count', 0)

    @dodge_count.setter
    def dodge_count(self, new_value: int) -> None:
        self.update('dodge_count', new_value)

    def increment(self) -> int:
        """线程安全地递增格挡计数，返回递增后的值"""
        import threading
        if not hasattr(self, '_lock'):
            self._lock = threading.Lock()
        with self._lock:
            new_count = self.dodge_count + 1
            self.update('dodge_count', new_count, save=False)
            return new_count

    def save_stats(self) -> None:
        """持久化当前计数到文件"""
        self.save()
