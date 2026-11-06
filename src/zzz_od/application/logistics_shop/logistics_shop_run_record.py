from datetime import datetime

from one_dragon.base.operation.application_run_record import AppRunRecord


class LogisticsShopRunRecord(AppRunRecord):

    """哨站后勤运行记录

    除基础的每日运行状态外 还记录本月已购买的储值电卡数量
    用于应用配置的月度限额(游戏内每月1号刷新限购)
    """

    def __init__(self, instance_idx: int | None = None, game_refresh_hour_offset: int = 0):
        AppRunRecord.__init__(
            self,
            'logistics_shop',
            instance_idx=instance_idx,
            game_refresh_hour_offset=game_refresh_hour_offset
        )

    @property
    def month_key(self) -> str:
        """月度计数所属月份 例如 2026-10"""
        return self.get('month_key', '')

    @month_key.setter
    def month_key(self, value: str):
        self.update('month_key', value)

    @property
    def monthly_bought(self) -> int:
        """本月已购买的储值电卡数量"""
        self._check_month_reset()
        return self.get('monthly_bought', 0)

    @monthly_bought.setter
    def monthly_bought(self, value: int):
        self._check_month_reset()
        self.update('monthly_bought', value)

    def add_monthly_bought(self, count: int = 1) -> None:
        """累计本月购买数量"""
        self.monthly_bought = self.monthly_bought + count

    def _check_month_reset(self) -> None:
        """跨月时重置月度计数 哨站后勤按自然月刷新"""
        current_month = datetime.now().strftime('%Y-%m')
        if self.month_key != current_month:
            self.month_key = current_month
            self.update('monthly_bought', 0)
