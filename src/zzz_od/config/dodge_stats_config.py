from one_dragon.base.config.yaml_config import YamlConfig


class DodgeStatsConfig(YamlConfig):
    """用户统计数据，持久化存储累计格挡次数和一条龙运行次数"""

    def __init__(self):
        YamlConfig.__init__(self, module_name='dodge_stats')
        import threading
        self._lock = threading.Lock()

    @property
    def dodge_count(self) -> int:
        return self.get('dodge_count', 0)

    @dodge_count.setter
    def dodge_count(self, new_value: int) -> None:
        self.update('dodge_count', new_value, save=False)

    @property
    def one_dragon_count(self) -> int:
        return self.get('one_dragon_count', 0)

    @one_dragon_count.setter
    def one_dragon_count(self, new_value: int) -> None:
        self.update('one_dragon_count', new_value, save=False)

    def increment_dodge(self) -> None:
        """线程安全地递增格挡计数"""
        with self._lock:
            self.update('dodge_count', self.dodge_count + 1, save=False)

    def increment_one_dragon(self) -> None:
        """递增一条龙运行计数"""
        with self._lock:
            self.update('one_dragon_count', self.one_dragon_count + 1, save=False)

    def save_stats(self) -> None:
        """持久化当前计数到文件"""
        self.save()
