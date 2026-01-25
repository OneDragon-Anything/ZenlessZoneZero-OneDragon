import re
from typing import Dict, Any, Optional, Tuple, List


class DriverDiscParser:
    """
    驱动盘数据解析与清洗器
    负责将 OCR 识别出的原始文本转换为结构化的数据
    """

    def parse(self, raw_data: Dict[str, str]) -> Dict[str, Any]:
        """
        解析 OCR 原始数据
        :param raw_data: OCR 识别结果字典 (支持原始 OCR key 或 预处理后的 key)
        :return: 清洗后的结构化数据
        """
        result = {}

        # 1. 解析名称和位置
        # 优先取 'name' (预处理后)，否则取 '驱动盘名称' (原始)
        raw_name = raw_data.get('name') or raw_data.get('驱动盘名称', '')
        set_name, parsed_slot = self._parse_name_and_slot(raw_name)
        
        # 优先使用显式的 slot 字段，如果没有则使用从名称中解析出的 slot
        slot = raw_data.get('slot')
        if not slot:
            slot = parsed_slot

        result['name'] = set_name
        result['slot'] = str(slot) if slot else ''

        # 2. 解析等级和稀有度
        # 如果有预处理后的 level/rating，直接使用
        pre_level = raw_data.get('level')
        pre_rating = raw_data.get('rating')
        
        if pre_level is not None and pre_rating:
            # 预处理数据中 level 已经是数字字符串，rating 是 S/A/B
            try:
                result['level'] = int(pre_level)
            except:
                result['level'] = 0
            
            result['rarity'] = pre_rating
            # 预处理数据丢失了 max_level 信息，根据 rarity 推断
            if pre_rating == 'S':
                result['max_level'] = 15
            elif pre_rating == 'A':
                result['max_level'] = 12
            else:
                result['max_level'] = 9
        else:
            # 尝试从原始 OCR 文本解析
            level_text = raw_data.get('驱动板等级', '')
            level, max_level, rarity = self._parse_level_and_rarity(level_text)
            result['level'] = level
            result['max_level'] = max_level
            result['rarity'] = rarity

        # 3. 解析主属性
        main_stat_name = raw_data.get('main_stat') or raw_data.get('驱动盘主属性', '')
        main_stat_value = raw_data.get('main_stat_value') or raw_data.get('驱动盘主属性值', '')
        result['main_stat'] = self._clean_stat_name(main_stat_name)
        result['main_stat_value'] = self._clean_stat_value(main_stat_value)

        # 4. 解析副属性
        substats = []
        for i in range(1, 5):
            # 尝试取预处理后的 key
            raw_sub_name = raw_data.get(f'sub_stat{i}')
            raw_sub_value = raw_data.get(f'sub_stat{i}_value')
            
            # 如果没有，尝试取原始 OCR key
            if raw_sub_name is None:
                raw_sub_name = raw_data.get(f'驱动盘副属性{i}', '')
            if raw_sub_value is None:
                raw_sub_value = raw_data.get(f'驱动盘副属性{i}值', '')

            sub_stat = self._parse_sub_stat(raw_sub_name, raw_sub_value)
            if sub_stat:
                substats.append(sub_stat)

        result['substats'] = substats

        return result

    def parse_flat(self, raw_data: Dict[str, str]) -> Dict[str, Any]:
        """
        解析并清洗数据，但保持扁平结构（适合 CSV 导出）
        """
        result = {}

        # 1. 解析名称和位置
        raw_name = raw_data.get('name') or raw_data.get('驱动盘名称', '')
        set_name, parsed_slot = self._parse_name_and_slot(raw_name)
        
        # 优先使用显式的 slot 字段，如果没有则使用从名称中解析出的 slot
        slot = raw_data.get('slot')
        if not slot:
            slot = parsed_slot

        result['name'] = set_name
        result['slot'] = str(slot) if slot else ''

        # 2. 解析等级和稀有度
        pre_level = raw_data.get('level')
        pre_rating = raw_data.get('rating')
        
        if pre_level is not None and pre_rating:
            try:
                result['level'] = int(pre_level)
            except:
                result['level'] = 0
            result['rating'] = pre_rating
        else:
            level_text = raw_data.get('驱动板等级', '')
            level, _, rarity = self._parse_level_and_rarity(level_text)
            result['level'] = level
            result['rating'] = rarity

        # 3. 解析主属性
        main_stat_name = raw_data.get('main_stat') or raw_data.get('驱动盘主属性', '')
        main_stat_value = raw_data.get('main_stat_value') or raw_data.get('驱动盘主属性值', '')
        result['main_stat'] = self._clean_stat_name(main_stat_name)
        result['main_stat_value'] = self._clean_stat_value(main_stat_value)

        # 4. 解析副属性 (保持扁平)
        for i in range(1, 5):
            raw_sub_name = raw_data.get(f'sub_stat{i}')
            raw_sub_value = raw_data.get(f'sub_stat{i}_value')
            
            if raw_sub_name is None:
                raw_sub_name = raw_data.get(f'驱动盘副属性{i}', '')
            if raw_sub_value is None:
                raw_sub_value = raw_data.get(f'驱动盘副属性{i}值', '')

            # 使用 _parse_sub_stat 进行清洗
            sub_stat = self._parse_sub_stat(raw_sub_name, raw_sub_value)
            
            if sub_stat:
                result[f'sub_stat{i}'] = sub_stat['name']
                # 如果有强化次数，拼接到名称后面? 或者单独字段?
                # 为了保持 CSV 简洁，且兼容 raw data 格式，建议拼回去或者加字段
                # 这里选择加字段 sub_statX_upgrades
                result[f'sub_stat{i}_value'] = sub_stat['value']
                # 只有大于0才记录，或者都记录
                if sub_stat['upgrades'] > 0:
                     result[f'sub_stat{i}'] = f"{sub_stat['name']}+{sub_stat['upgrades']}"
            else:
                result[f'sub_stat{i}'] = ''
                result[f'sub_stat{i}_value'] = ''

        return result

    def _parse_name_and_slot(self, raw_name: str) -> Tuple[str, str]:
        """
        解析套装名称和位置
        示例: "山大王[1]" -> ("山大王", "1")
              "山大王【1】" -> ("山大王", "1")
        """
        if not raw_name:
            return '', ''

        # 尝试匹配 [1] 或 【1】 格式 (兼容右括号缺失)
        match = re.search(r'(.+?)[\[【](\d)[\]】]?', raw_name)
        if match:
            return match.group(1).strip(), match.group(2)

        # 兜底：如果最后一位是数字，且前面是中文
        match = re.search(r'(.+?)(\d)$', raw_name)
        if match:
            return match.group(1).strip(), match.group(2)

        return raw_name.strip(), ''

    def _parse_level_and_rarity(self, level_text: str) -> Tuple[int, int, str]:
        """
        解析等级和稀有度
        示例: "等级15/15" -> (15, 15, 'S')
        """
        if not level_text:
            return 0, 0, 'B'

        match = re.search(r'(\d+)/(\d+)', level_text)
        if match:
            current = int(match.group(1))
            max_lvl = int(match.group(2))

            rarity = 'B'
            if max_lvl == 15:
                rarity = 'S'
            elif max_lvl == 12:
                rarity = 'A'

            return current, max_lvl, rarity

        return 0, 0, 'B'

    def _clean_stat_name(self, name: str) -> str:
        """
        清洗属性名称，去除 +x
        """
        if not name:
            return ''
        # 去除 +x (在副属性解析里会用到，这里主属性一般没有，但也处理一下)
        match = re.match(r'^(.*?)(?:\+\d+)?$', name)
        if match:
            name = match.group(1).strip()
        
        name = name.strip()
        if name.endswith('伤害力'):
            name = name.replace('伤害力', '伤害加成')
            
        return name

    def _clean_stat_value(self, value: str) -> str:
        """
        清洗属性值
        """
        if not value:
            return ''
        # 只保留数字、小数点、百分号
        return re.sub(r'[^\d\.%]', '', value)

    def _parse_sub_stat(self, raw_name: str, raw_value: str) -> Optional[Dict[str, Any]]:
        """
        解析副属性
        """
        if not raw_name or not raw_value:
            return None

        # 过滤无效属性 (如 "套装效果")
        if '套装' in raw_name:
            return None

        # 清洗数值
        clean_value = self._clean_stat_value(raw_value)
        if not clean_value:
            return None

        # 解析强化次数
        upgrades = 0
        stat_name = raw_name
        match = re.search(r'(.+?)\+(\d+)', raw_name)
        if match:
            stat_name = match.group(1).strip()
            upgrades = int(match.group(2))
        else:
            stat_name = raw_name.strip()

        # 修正名称
        if stat_name.endswith('伤害力'):
            stat_name = stat_name.replace('伤害力', '伤害加成')

        return {
            'name': stat_name,
            'value': clean_value,
            'upgrades': upgrades
        }
