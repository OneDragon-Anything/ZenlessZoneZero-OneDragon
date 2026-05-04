"""
权重槽位类型配置文件
"""

from enum import Enum


class SlotTypeEnum(Enum):
    """权重槽位类型枚举（英文标识）"""

    HP_ = "hp_"  # 生命值
    ATK_ = "atk_"  # 攻击力
    DEF_ = "def_"  # 防御力
    PEN_ = "pen_"  # 穿透率
    IMPACT = "impact"  # 冲击力
    CRIT_ = "crit_"  # 暴击率
    CRIT_DMG_ = "crit_dmg_"  # 暴击伤害
    PHYSICAL_DMG_ = "physical_dmg_"  # 物理伤害加成
    ETHER_DMG_ = "ether_dmg_"  # 以太伤害加成
    FIRE_DMG_ = "fire_dmg_"  # 火属性伤害加成
    ICE_DMG_ = "ice_dmg_"  # 冰属性伤害加成
    ELECTRIC_DMG_ = "electric_dmg_"  # 电属性伤害加成
    ANOM_MAS_ = "anomMas_"  # 异常掌控
    ANOM_PROF = "anomProf"  # 异常精通
    ENERGY_REGEN_ = "energyRegen_"  # 能量自动回复
    ATK = "atk"  # 小攻击
    HP = "hp"  # 小生命
    DEF = "def"  # 小防御
    PEN = "pen"  # 穿透值


class SlotTypeCnEnum(Enum):
    """权重槽位类型枚举（中文名称）"""

    HP_ = "生命值"
    ATK_ = "攻击力"
    DEF_ = "防御力"
    PEN_ = "穿透率"
    IMPACT = "冲击力"
    CRIT_ = "暴击率"
    CRIT_DMG_ = "暴击伤害"
    PHYSICAL_DMG_ = "物理伤害加成"
    ETHER_DMG_ = "以太伤害加成"
    FIRE_DMG_ = "火属性伤害加成"
    ICE_DMG_ = "冰属性伤害加成"
    ELECTRIC_DMG_ = "电属性伤害加成"
    ANOM_MAS_ = "异常掌控"
    ANOM_PROF = "异常精通"
    ENERGY_REGEN_ = "能量自动回复"
    ATK = "小攻击"
    HP = "小生命"
    DEF = "小防御"
    PEN = "穿透值"


def get_slot_type_cn(slot_type: str) -> str:
    """
    根据槽位类型获取中文名称

    Args:
        slot_type: 槽位类型（如 'hp_'）

    Returns:
        槽位中文名称（如 '生命值'）
    """
    try:
        # 将输入转换为枚举名称格式
        enum_name = slot_type.upper().replace("-", "_").replace(".", "_")
        return SlotTypeCnEnum[enum_name].value
    except KeyError:
        return slot_type


def get_all_slot_types() -> list:
    """
    获取所有槽位类型列表

    Returns:
        槽位类型列表（英文标识）
    """
    return [member.value for member in SlotTypeEnum]


def get_all_slot_type_cn() -> list:
    """
    获取所有槽位中文名称列表

    Returns:
        槽位中文名称列表
    """
    return [member.value for member in SlotTypeCnEnum]


def get_slot_mapping() -> dict:
    """
    获取槽位类型到中文名称的映射字典

    Returns:
        槽位类型到中文名称的映射
    """
    return {slot.value: cn.value for slot, cn in zip(SlotTypeEnum, SlotTypeCnEnum, strict=False)}


# 快捷访问常量
SLOT_MAPPING = get_slot_mapping()
"""槽位类型到中文名称的映射字典（快捷访问）"""


def get_weight_key_order() -> list:
    """
    获取权重项的键顺序（按照枚举定义的顺序）

    Returns:
        权重键顺序列表
    """
    return [member.value for member in SlotTypeEnum]


# dmg_type 到元素伤害加成键的映射
DMG_TYPE_TO_DMG_BONUS_KEY = {
    "ELECTRIC": "electric_dmg_",
    "ICE": "ice_dmg_",
    "FIRE": "fire_dmg_",
    "PHYSICAL": "physical_dmg_",
    "ETHER": "ether_dmg_",
}
"""伤害类型到伤害加成键的映射字典"""

DEFAULT_DMG_BONUS_KEY: str = "physical_dmg_"
"""默认伤害加成键（当无法匹配时使用）"""


# 属性分组配置
BASE_KEY_ORDER = [
    "hp_",
    "atk_",
    "def_",
    "pen_",
    "impact",
    "crit_",
    "crit_dmg_",
]
"""基础属性键顺序（不包含元素伤害加成）"""

OTHER_KEY_ORDER = ["anomMas_", "anomProf", "energyRegen_", "atk", "hp", "def", "pen"]
"""其他属性键顺序"""


# 排除选项配置（用于下拉框等场景）
EXCLUDED_OPTIONS = {"穿透值", "小防御", "小生命", "小攻击"}
"""排除的选项集合（中文名称）"""


# 小属性到大属性的映射（用于权重计算）
SMALL_TO_LARGE_MAP = {
    "小攻击": "攻击力",
    "小生命": "生命值",
    "小防御": "防御力",
    "穿透值": "穿透率",
}
"""小属性到对应大属性的映射字典（小属性权重为对应大属性的1/3）"""

SMALL_ATTRIBUTE_WEIGHT_RATIO: float = 1 / 3
"""小属性权重与大属性权重的比例"""


QUALITY_WEIGHTS = {"S": 1, "A": 0.67, "B": 0.33}
"""驱动盘品质权重"""

MAX_DISK_SCORE = 100
"""单个驱动盘的理论最高分数"""

SLOT_MAIN_POOLS = {
    1: ["小生命"],
    2: ["小攻击"],
    3: ["小防御"],
    4: [
        "攻击力",
        "生命值",
        "防御力",
        "暴击率",
        "暴击伤害",
        "异常精通",
    ],
    5: [
        "攻击力",
        "生命值",
        "防御力",
        "穿透率",
        "火属性伤害加成",
        "冰属性伤害加成",
        "电属性伤害加成",
        "以太伤害加成",
        "物理伤害加成",
    ],
    6: [
        "攻击力",
        "生命值",
        "防御力",
        "异常掌控",
        "冲击力",
        "能量自动回复",
    ],
}
"""每个部位的主词条可选池"""

MAIN_STAT_GAIN = {
    "攻击力": 1.67,
    "防御力": 1.67,
    "暴击率": 1.67,
    "暴击伤害": 1.67,
    "异常精通": 1.7,
    "小生命": 3.27,
    "小攻击": 2.77,
    "小防御": 2.04,
    "穿透率": 2.06,
    "异常掌控": 2.06,
    "冲击力": 2.06,
    "能量自动回复": 2.06,
    "火属性伤害加成": 1.0,
    "冰属性伤害加成": 1.0,
    "电属性伤害加成": 1.0,
    "以太伤害加成": 1.0,
    "物理伤害加成": 1.0,
}
"""主词条的增益系数"""

SUB_STATS_POOL = [
    "生命值",
    "攻击力",
    "防御力",
    "暴击率",
    "暴击伤害",
    "异常精通",
    "穿透值",
    "小生命",
    "小攻击",
    "小防御",
]
"""副词条可选池"""

MAX_LEVELS = {"S": 15, "A": 12, "B": 9}
"""每种品质的驱动盘的最大等级"""

MAX_SUB_PROPERTIES = {"S": 4, "A": 3, "B": 2}
"""每种品质的驱动盘的副词条上限"""
