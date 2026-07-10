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


def get_small_to_large_mapping() -> dict[str, str]:
    """
    获取小属性到大属性的映射字典（基于枚举动态生成）

    Returns:
        小属性到对应大属性的映射字典（小属性权重为对应大属性的1/3）
    """
    mapping = {}

    # 遍历 SlotTypeCnEnum 枚举
    for member in SlotTypeCnEnum:
        enum_name = member.name
        enum_value = member.value

        # 识别小属性：枚举名称不包含下划线且值不包含下划线
        # 小属性：ATK, HP, DEF, PEN
        # 大属性：ATK_, HP_, DEF_, PEN_
        if '_' not in enum_name and '_' not in enum_value:
            # 寻找对应的大属性
            large_enum_name = enum_name + '_'
            try:
                large_member = SlotTypeCnEnum[large_enum_name]
                mapping[enum_value] = large_member.value
            except KeyError:
                # 如果没有对应的大属性，跳过
                continue

    return mapping


def get_slot_main_pools() -> dict[int, list[str]]:
    """
    获取每个部位的主词条可选池（基于枚举动态生成）

    Returns:
        每个部位的主词条可选池（部位编号: 词条列表）
    """
    pools = {}

    # 部位1-3：只有小属性
    pools[1] = [SlotTypeCnEnum.HP.value]  # 小生命
    pools[2] = [SlotTypeCnEnum.ATK.value]  # 小攻击
    pools[3] = [SlotTypeCnEnum.DEF.value]  # 小防御

    # 部位4：基础属性 + 暴击相关 + 异常精通
    pools[4] = [
        SlotTypeCnEnum.ATK_.value,    # 攻击力
        SlotTypeCnEnum.HP_.value,    # 生命值
        SlotTypeCnEnum.DEF_.value,    # 防御力
        SlotTypeCnEnum.CRIT_.value,   # 暴击率
        SlotTypeCnEnum.CRIT_DMG_.value, # 暴击伤害
        SlotTypeCnEnum.ANOM_PROF.value, # 异常精通
    ]

    # 部位5：基础属性 + 所有伤害类型
    pools[5] = [
        SlotTypeCnEnum.ATK_.value,      # 攻击力
        SlotTypeCnEnum.HP_.value,      # 生命值
        SlotTypeCnEnum.DEF_.value,      # 防御力
        SlotTypeCnEnum.PEN_.value,      # 穿透率
        SlotTypeCnEnum.FIRE_DMG_.value,      # 火属性伤害加成
        SlotTypeCnEnum.ICE_DMG_.value,       # 冰属性伤害加成
        SlotTypeCnEnum.ELECTRIC_DMG_.value,  # 电属性伤害加成
        SlotTypeCnEnum.ETHER_DMG_.value,     # 以太伤害加成
        SlotTypeCnEnum.PHYSICAL_DMG_.value,  # 物理伤害加成
    ]

    # 部位6：基础属性 + 特殊属性
    pools[6] = [
        SlotTypeCnEnum.ATK_.value,         # 攻击力
        SlotTypeCnEnum.HP_.value,          # 生命值
        SlotTypeCnEnum.DEF_.value,         # 防御力
        SlotTypeCnEnum.ANOM_MAS_.value,   # 异常掌控
        SlotTypeCnEnum.IMPACT.value,      # 冲击力
        SlotTypeCnEnum.ENERGY_REGEN_.value, # 能量自动回复
    ]

    return pools


def get_sub_stats_pool() -> list[str]:
    """
    获取副词条可选池（基于枚举动态生成）

    Returns:
        副词条可选池列表
    """
    pool = []

    # 基础属性
    pool.extend([
        SlotTypeCnEnum.HP_.value,      # 生命值
        SlotTypeCnEnum.ATK_.value,      # 攻击力
        SlotTypeCnEnum.DEF_.value,      # 防御力
    ])

    # 暴击相关
    pool.extend([
        SlotTypeCnEnum.CRIT_.value,     # 暴击率
        SlotTypeCnEnum.CRIT_DMG_.value,  # 暴击伤害
    ])

    # 异常精通（只包含异常精通，不包含异常掌控）
    pool.extend([
        SlotTypeCnEnum.ANOM_PROF.value,  # 异常精通
    ])

    # 其他属性
    pool.extend([
        SlotTypeCnEnum.PEN.value,       # 穿透值
    ])

    # 小属性
    pool.extend([
        SlotTypeCnEnum.HP.value,        # 小生命
        SlotTypeCnEnum.ATK.value,        # 小攻击
        SlotTypeCnEnum.DEF.value,        # 小防御
    ])

    return pool


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


# 角色类型伤害到词条英文标识的映射
DMG_TYPE_TO_DMG_BONUS_KEY = {
    "ELECTRIC": "electric_dmg_",
    "ICE": "ice_dmg_",
    "FIRE": "fire_dmg_",
    "PHYSICAL": "physical_dmg_",
    "ETHER": "ether_dmg_",
}
"""伤害类型到伤害加成键的映射字典"""








# 小属性到大属性的映射（用于权重计算，基于枚举动态生成）
SMALL_TO_LARGE_MAP = get_small_to_large_mapping()
"""小属性到对应大属性的映射字典（小属性权重为对应大属性的1/3）"""

SMALL_ATTRIBUTE_WEIGHT_RATIO: float = 1 / 3
"""小属性权重与大属性权重的比例"""


QUALITY_WEIGHTS = {"S": 1, "A": 0.67, "B": 0.33}
"""驱动盘品质权重"""

MAX_DISK_SCORE = 100
"""单个驱动盘的理论最高分数"""

# 每个部位的主词条可选池（基于枚举动态生成）
SLOT_MAIN_POOLS = get_slot_main_pools()
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

# 副词条可选池（基于枚举动态生成）
SUB_STATS_POOL = get_sub_stats_pool()
"""副词条可选池"""

MAX_LEVELS = {"S": 15, "A": 12, "B": 9}
"""每种品质的驱动盘的最大等级"""

MAX_SUB_PROPERTIES = {"S": 4, "A": 3, "B": 2}
"""每种品质的驱动盘的副词条上限"""
