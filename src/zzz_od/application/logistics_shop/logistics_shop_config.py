from enum import StrEnum

from one_dragon.base.operation.application.application_config import ApplicationConfig


class LogisticsShopConfig(ApplicationConfig):

    def __init__(self, instance_idx: int, group_id: str):
        ApplicationConfig.__init__(self, 'logistics_shop', instance_idx, group_id)

    @property
    def cleaning_card_enabled(self) -> bool:
        """储值电卡-不限购条目-开关 使用深度清扫服务卡购买 默认关闭"""
        return self.get('cleaning_card_enabled', False)

    @cleaning_card_enabled.setter
    def cleaning_card_enabled(self, value: bool):
        self.update('cleaning_card_enabled', value)

    @property
    def single_run_limit(self) -> int:
        """储值电卡-单轮购买上限"""
        return self.get('single_run_limit', 10)

    @single_run_limit.setter
    def single_run_limit(self, value: int):
        self.update('single_run_limit', value)

    @property
    def monthly_limit(self) -> int:
        """储值电卡-月度限额 游戏内每月限购10张"""
        return self.get('monthly_limit', 10)

    @monthly_limit.setter
    def monthly_limit(self, value: int):
        self.update('monthly_limit', value)

    @property
    def min_performance_reserve(self) -> int:
        """保底零号业绩 余额低于该值时停止购买"""
        return self.get('min_performance_reserve', 0)

    @min_performance_reserve.setter
    def min_performance_reserve(self, value: int):
        self.update('min_performance_reserve', value)


class LogisticsShopGoods(StrEnum):

    """哨站后勤-哨站后勤页签的商品名称 用于OCR泛化匹配"""

    TUNER = '调律快音器'
    BANGBOU_TICKET = '邦布券'
    DAILY_PERFORMANCE = '日常业绩'
    PREPAID_POWER_CARD = '储值电卡'
    CLEANING_SERVICE_CARD = '「深度清扫」服务卡'
    RELIC_TREASURE = '遗存秘藏'
    W_ENGINE_RESIDUE = '音擎残芯'
    BANGBOO_SYSTEM_WIDGET = '邦布系统控件'
    RESOURCE_INVESTIGATOR_LOG = '资源调查员记录'
