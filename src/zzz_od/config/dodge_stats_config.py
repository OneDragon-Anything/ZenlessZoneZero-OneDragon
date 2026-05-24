import threading

from one_dragon.base.config.yaml_config import YamlConfig

# 需要在主页统计栏展示的应用 id → 显示名称
STATS_DISPLAY_APPS: dict[str, str] = {
    'charge_plan': '体力刷本',
    'lost_void': '迷失之地',
    'withered_domain': '枯萎之都',
    'trigrams_collection': '卦象集录',
    'notorious_hunt': '恶名狩猎',
    'world_patrol': '锄大地',
    'shiyu_defense': '式舆防卫战',
    'random_play': '录像店营业',
    'coffee': '咖啡店',
    'scratch_card': '刮刮卡',
    'suibian_temple': '随便观',
    'life_on_line': '真·拿命验收',
    'city_fund': '丽都城募',
    'ridu_weekly': '丽都周纪',
    'intel_board': '情报板',
    'email': '邮件',
    'redemption_code': '兑换码',
    'engagement_reward': '活跃度奖励',
    'drive_disc_dismantle': '驱动盘拆解',
}


class UserStatsConfig(YamlConfig):
    """用户统计数据，持久化存储累计格挡次数、一条龙运行次数和各应用运行次数"""

    def __init__(self):
        YamlConfig.__init__(self, module_name='dodge_stats')
        self._lock = threading.Lock()

    # ---------- 格挡计数 ----------

    @property
    def dodge_count(self) -> int:
        return self.get('dodge_count', 0)

    @dodge_count.setter
    def dodge_count(self, new_value: int) -> None:
        self.update('dodge_count', new_value, save=False)

    def increment_dodge(self) -> None:
        """线程安全地递增格挡计数"""
        with self._lock:
            self.update('dodge_count', self.dodge_count + 1, save=False)

    # ---------- 一条龙运行计数 ----------

    @property
    def one_dragon_count(self) -> int:
        return self.get('one_dragon_count', 0)

    @one_dragon_count.setter
    def one_dragon_count(self, new_value: int) -> None:
        self.update('one_dragon_count', new_value, save=False)

    def increment_one_dragon(self) -> None:
        """递增一条龙运行计数"""
        with self._lock:
            self.update('one_dragon_count', self.one_dragon_count + 1, save=False)

    # ---------- 各应用运行计数 ----------

    @property
    def app_counts(self) -> dict[str, int]:
        return self.get('app_counts', {})

    @app_counts.setter
    def app_counts(self, new_value: dict[str, int]) -> None:
        self.update('app_counts', new_value, save=False)

    def increment_app(self, app_id: str) -> None:
        """线程安全地递增指定应用的运行计数"""
        with self._lock:
            counts = self.app_counts
            counts[app_id] = counts.get(app_id, 0) + 1
            self.update('app_counts', counts, save=False)

    def get_app_count(self, app_id: str) -> int:
        """获取指定应用的运行计数"""
        return self.app_counts.get(app_id, 0)

    # ---------- 持久化 ----------

    def save_stats(self) -> None:
        """持久化当前计数到文件"""
        self.save()
