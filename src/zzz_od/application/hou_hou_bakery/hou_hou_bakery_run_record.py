
from one_dragon.base.operation.application_run_record import AppRunRecord


class HouHouBakeryRunRecord(AppRunRecord):
    """吼吼饼铺运行记录: 按每日刷新管理签到状态。"""

    def __init__(self, instance_idx: int | None = None, game_refresh_hour_offset: int = 0):
        """初始化运行记录。

        Args:
            instance_idx: 实例下标。默认为None。
            game_refresh_hour_offset: 游戏刷新时间偏移(小时)。默认为0。
        """
        AppRunRecord.__init__(
            self,
            'hou_hou_bakery',
            instance_idx=instance_idx,
            game_refresh_hour_offset=game_refresh_hour_offset
        )
