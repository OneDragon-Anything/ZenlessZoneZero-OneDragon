from enum import StrEnum

from one_dragon.base.operation.application.application_config import ApplicationConfig
from zzz_od.application.suibian_temple.operations.suibian_temple_adventure_dispatch import \
    SuibianTempleAdventureDispatchDuration


class SuibianTempleConfig(ApplicationConfig):

    def __init__(self, instance_idx: int, group_id: str):
        ApplicationConfig.__init__(self, 'suibian_temple', instance_idx, group_id)

    @property
    def yum_cha_sin(self) -> bool:
        """饮茶仙-开关"""
        return self.get('yum_cha_sin', True)

    @yum_cha_sin.setter
    def yum_cha_sin(self, value: bool):
        self.update('yum_cha_sin', value)

    @property
    def yum_cha_sin_period_refresh(self) -> bool:
        """饮茶仙-定期采办-是否刷新"""
        return self.get('yum_cha_sin_period_refresh', True)

    @yum_cha_sin_period_refresh.setter
    def yum_cha_sin_period_refresh(self, value: bool):
        self.update('yum_cha_sin_period_refresh', value)

    @property
    def adventure_duration(self) -> str:
        """游历-时间"""
        return self.get('adventure_duration', SuibianTempleAdventureDispatchDuration.HOUR_20.name)

    @adventure_duration.setter
    def adventure_duration(self, value: str):
        self.update('adventure_duration', value)

    @property
    def adventure_mission_1(self) -> str:
        """游历-任务1"""
        return self.get('adventure_mission_1', SuibianTempleAdventureMission.RESEARCH_3_4.name)

    @adventure_mission_1.setter
    def adventure_mission_1(self, value: str):
        self.update('adventure_mission_1', value)

    @property
    def adventure_mission_2(self) -> str:
        """游历-任务2"""
        return self.get('adventure_mission_2', SuibianTempleAdventureMission.RESEARCH_2_4.name)

    @adventure_mission_2.setter
    def adventure_mission_2(self, value: str):
        self.update('adventure_mission_2', value)

    @property
    def adventure_mission_3(self) -> str:
        """游历-任务3"""
        return self.get('adventure_mission_3', SuibianTempleAdventureMission.RESEARCH_1_4.name)

    @adventure_mission_3.setter
    def adventure_mission_3(self, value: str):
        self.update('adventure_mission_3', value)

    @property
    def adventure_mission_4(self) -> str:
        """游历-任务4"""
        return self.get('adventure_mission_4', SuibianTempleAdventureMission.COMMUNITY_3_4.name)

    @adventure_mission_4.setter
    def adventure_mission_4(self, value: str):
        self.update('adventure_mission_4', value)

    @property
    def craft_drag_times(self) -> int:
        """制造-最大下拉次数"""
        return self.get('craft_drag_times', 10)

    @craft_drag_times.setter
    def craft_drag_times(self, value: int):
        self.update('craft_drag_times', value)

    @property
    def good_goods_purchase_enabled(self) -> bool:
        """好物铺购买-开关"""
        return self.get('good_goods_purchase_enabled', False)

    @good_goods_purchase_enabled.setter
    def good_goods_purchase_enabled(self, value: bool):
        self.update('good_goods_purchase_enabled', value)

    @property
    def boo_box_purchase_enabled(self) -> bool:
        """邦巢-购买"""
        return self.get('boo_box_purchase_enabled', False)

    @boo_box_purchase_enabled.setter
    def boo_box_purchase_enabled(self, value: bool):
        self.update('boo_box_purchase_enabled', value)

    @property
    def boo_box_adventure_price(self) -> str:
        """邦巢-游历-最低价格"""
        return self.get('boo_box_adventure_price', BangbooPrice.S4.name)

    @boo_box_adventure_price.setter
    def boo_box_adventure_price(self, value: str):
        self.update('boo_box_adventure_price', value)

    @property
    def boo_box_craft_price(self) -> str:
        """邦巢-制造-最低价格"""
        return self.get('boo_box_craft_price', BangbooPrice.S4.name)

    @boo_box_craft_price.setter
    def boo_box_craft_price(self, value: str):
        self.update('boo_box_craft_price', value)

    @property
    def boo_box_sell_price(self) -> str:
        """邦巢-售卖-最低价格"""
        return self.get('boo_box_sell_price', BangbooPrice.S4.name)

    @boo_box_sell_price.setter
    def boo_box_sell_price(self, value: str):
        self.update('boo_box_sell_price', value)

    @property
    def pawnshop_omnicoin_enabled(self) -> bool:
        """德丰大押-百宝通-开关"""
        return self.get('pawnshop_omnicoin_enabled', True)

    @pawnshop_omnicoin_enabled.setter
    def pawnshop_omnicoin_enabled(self, value: bool):
        self.update('pawnshop_omnicoin_enabled', value)

    @property
    def pawnshop_omnicoin_priority(self) -> list[str]:
        """德丰大押-百宝通-优先级"""
        return self.get('pawnshop_omnicoin_priority', [
            i.name
            for i in PawnshopOmnicoinGoods
        ])

    @pawnshop_omnicoin_priority.setter
    def pawnshop_omnicoin_priority(self, value: list[str]):
        self.update('pawnshop_omnicoin_priority', value)

    @property
    def pawnshop_crest_enabled(self) -> bool:
        """德丰大押-云纹徽-开关"""
        return self.get('pawnshop_crest_enabled', True)

    @pawnshop_crest_enabled.setter
    def pawnshop_crest_enabled(self, value: bool):
        self.update('pawnshop_crest_enabled', value)

    @property
    def pawnshop_crest_priority(self) -> list[str]:
        """德丰大押-云纹徽-优先级"""
        return self.get('pawnshop_crest_priority', [
            i.name
            for i in PawnshopCrestGoods
        ])

    @pawnshop_crest_priority.setter
    def pawnshop_crest_priority(self, value: list[str]):
        self.update('pawnshop_crest_priority', value)

    @property
    def pawnshop_crest_unlimited_denny_enabled(self) -> bool:
        """德丰大押-云纹徽-不限购丁尼-开关"""
        return self.get('pawnshop_crest_unlimited_denny_enabled', False)

    @pawnshop_crest_unlimited_denny_enabled.setter
    def pawnshop_crest_unlimited_denny_enabled(self, value: bool):
        self.update('pawnshop_crest_unlimited_denny_enabled', value)


class SuibianTempleAdventureMission(StrEnum):

    CRAFT_1_1 = '制造区1-1'
    CRAFT_1_2 = '制造区1-2'
    CRAFT_1_3 = '制造区1-3'
    CRAFT_1_4 = "制造区1-4"

    CRAFT_2_1 = '制造区2-1'
    CRAFT_2_2 = '制造区2-2'
    CRAFT_2_3 = '制造区2-3'
    CRAFT_2_4 = "制造区2-4"

    CRAFT_3_1 = '制造区3-1'
    CRAFT_3_2 = '制造区3-2'
    CRAFT_3_3 = '制造区3-3'
    CRAFT_3_4 = "制造区3-4"

    COMMUNITY_1_1 = '社区旧址1-1'
    COMMUNITY_1_2 = '社区旧址1-2'
    COMMUNITY_1_3 = '社区旧址1-3'
    COMMUNITY_1_4 = "社区旧址1-4"

    COMMUNITY_2_1 = '社区旧址2-1'
    COMMUNITY_2_2 = '社区旧址2-2'
    COMMUNITY_2_3 = '社区旧址2-3'
    COMMUNITY_2_4 = "社区旧址2-4"

    COMMUNITY_3_1 = '社区旧址3-1'
    COMMUNITY_3_2 = '社区旧址3-2'
    COMMUNITY_3_3 = '社区旧址3-3'
    COMMUNITY_3_4 = "社区旧址3-4"

    RESEARCH_1_1 = '科研院旧址1-1'
    RESEARCH_1_2 = '科研院旧址1-2'
    RESEARCH_1_3 = '科研院旧址1-3'
    RESEARCH_1_4 = "科研院旧址1-4"

    RESEARCH_2_1 = '科研院旧址2-1'
    RESEARCH_2_2 = '科研院旧址2-2'
    RESEARCH_2_3 = '科研院旧址2-3'
    RESEARCH_2_4 = "科研院旧址2-4"

    RESEARCH_3_1 = '科研院旧址3-1'
    RESEARCH_3_2 = '科研院旧址3-2'
    RESEARCH_3_3 = '科研院旧址3-3'
    RESEARCH_3_4 = "科研院旧址3-4"


class BangbooPrice(StrEnum):

    S1 = '40000'
    S2 = '35000'
    S3 = '30000'
    S4 = '25000'
    NONE = '不购买'


class PawnshopOmnicoinGoods(StrEnum):

    HIFI_MASTER_COPY = "高保真母盘"
    SENIOR_INVESTIGATOR_LOG = '资深调查员记录'
    W_ENGINE_ENERGY_MODULE = '音擎能源模块'
    ETHER_PLATING_AGENT = '以太镀剂'
    PREPAID_POWER_CARD = '储值电卡'


class PawnshopCrestGoods(StrEnum):

    BANGBOO_SYSTEM_WIDGET = "邦布系统控件"
    DENNY = "丁尼"
