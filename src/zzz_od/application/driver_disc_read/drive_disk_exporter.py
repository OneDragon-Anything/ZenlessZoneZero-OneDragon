import json
import time
from typing import List, Dict, Any
from pathlib import Path

# 套装名称映射 (中文 -> ZOD Key)
SET_NAME_MAP = {
    '混沌重金属': 'ChaoticMetal',
    '獠牙重金属': 'FangedMetal',
    '雷暴重金属': 'ThunderMetal',
    '炎狱重金属': 'InfernoMetal',
    '极地重金属': 'PolarMetal',
    '摇摆爵士': 'SwingJazz',
    '混沌爵士': 'ChaosJazz',
    '激素朋克': 'HormonePunk',
    '原始朋克': 'ProtoPunk',
    '震星迪斯科': 'ShockstarDisco',
    '啄木鸟电音': 'WoodpeckerElectro',
    '河豚电音': 'PufferElectro',
    '灵魂摇滚': 'SoulRock',
    '自由蓝调': 'FreedomBlues',
    '折枝剑歌': 'BranchBladeSong',
    '静听嘉音': 'AstralVoice',
    '如影相随': 'ShadowHarmony',
    '法厄同之歌': 'PhaethonsMelody',
    '云岿如我': 'YunkuiTales',
    '山大王': 'KingOfTheSummit',
    '拂晓生花': 'DawnsBloom',
    '月光骑士颂': 'MoonlightLullaby',
    '沧浪行歌': 'WhiteWaterBallad',
    '流光咏叹': 'ShiningAria',
}

# 属性名称映射 (中文 -> ZOD Key Base)
STAT_NAME_MAP = {
    '生命值': 'hp',
    '攻击力': 'atk',
    '防御力': 'def',
    '暴击率': 'crit_',
    '暴击伤害': 'crit_dmg_',
    '异常精通': 'anomProf',
    '异常掌控': 'anomMas_',
    '穿透率': 'pen_',
    '穿透值': 'pen',
    '冲击力': 'impact_',
    '能量自动回复': 'enerRegen_',
    '电属性伤害加成': 'electric_dmg_',
    '火属性伤害加成': 'fire_dmg_',
    '冰属性伤害加成': 'ice_dmg_',
    '物理伤害加成': 'physical_dmg_',
    '以太伤害加成': 'ether_dmg_',
}


class DriveDiskExporter:
    """
    驱动盘导出器
    负责将清洗后的数据转换为 ZOD (Zenless Optimizer) 标准 JSON 格式
    """

    def convert_to_zod_json(self, disc_data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        转换为 ZOD 格式
        """
        zod_discs = []
        for idx, disc in enumerate(disc_data_list):
            zod_disc = self._convert_single_disc(disc, idx)
            if zod_disc:
                zod_discs.append(zod_disc)

        return {
            "format": "ZOD",
            "dbVersion": 2,
            "source": "Zenless Optimizer",
            "version": 1,
            "discs": zod_discs
        }

    def _convert_single_disc(self, disc: Dict[str, Any], idx: int) -> Dict[str, Any]:
        """
        转换单个驱动盘数据
        """
        set_name_cn = disc.get('name', '')
        set_key = SET_NAME_MAP.get(set_name_cn, set_name_cn)  # 缺省使用原名

        slot_key = disc.get('slot', '1')
        level = int(disc.get('level', 0))
        rarity = disc.get('rarity', 'S')

        # 主属性
        main_stat_cn = disc.get('main_stat', '')
        main_stat_key = self._get_stat_key(main_stat_cn, is_main=True, slot=slot_key)

        # 副属性
        substats = []
        for sub in disc.get('substats', []):
            sub_name_cn = sub.get('name', '')
            sub_value_str = sub.get('value', '')
            upgrades = sub.get('upgrades', 0)
            
            sub_key = self._get_stat_key(sub_name_cn, is_main=False, value_str=sub_value_str)
            substats.append({
                "key": sub_key,
                "upgrades": upgrades
            })

        return {
            "setKey": set_key,
            "rarity": rarity,
            "level": level,
            "slotKey": slot_key,
            "mainStatKey": main_stat_key,
            "substats": substats,
            "location": "",
            "lock": False,
            "trash": False,
            "id": str(idx)  # 简单使用索引作为ID
        }

    def _get_stat_key(self, name: str, is_main: bool = False, slot: str = None, value_str: str = None) -> str:
        """
        根据属性名和上下文确定最终的 Key
        """
        base_key = STAT_NAME_MAP.get(name)
        if not base_key:
            return name

        # 已经是百分比Key（带下划线），直接返回
        if base_key.endswith('_'):
            return base_key
        
        # 特殊处理：异常精通、穿透值通常是固定值
        if base_key in ['anomProf', 'pen']:
            return base_key

        # HP/ATK/DEF 处理
        if base_key in ['hp', 'atk', 'def']:
            if is_main:
                # 主属性：1-3号位固定值，4-6号位百分比
                if slot in ['1', '2', '3']:
                    return base_key
                else:
                    return base_key + '_'
            else:
                # 副属性：看是否有百分号
                if value_str and '%' in value_str:
                    return base_key + '_'
                else:
                    return base_key
        
        return base_key
