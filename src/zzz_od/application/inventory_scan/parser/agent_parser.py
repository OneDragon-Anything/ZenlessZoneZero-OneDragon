import re
import json
from typing import Optional, Dict, Any, List
from difflib import SequenceMatcher
from one_dragon.utils.log_utils import log
from one_dragon.utils import os_utils
from cv2.typing import MatLike


class AgentParser:
    """代理人数据解析器"""

    def __init__(self):
        self.agent_counter = 0
        self.translation_dict = self._load_translation_dict()
        self.scanned_agent_keys = set()  # 记录已扫描的角色key，用于去重

    def _load_translation_dict(self) -> Dict:
        """加载翻译字典"""
        try:
            translation_path = os_utils.get_path_under_work_dir(
                'src', 'zzz_od', 'application', 'inventory_scan',
                'translation', 'translation_dict.json'
            )
            with open(translation_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('character', {})
        except Exception as e:
            log.error(f"加载翻译字典失败: {e}")
            return {}

    def parse_ocr_result(self, ocr_items: List[Dict[str, Any]], screenshot: MatLike) -> Optional[Dict]:
        """
        解析代理人OCR结果

        Args:
            ocr_items: OCR识别结果列表
            screenshot: 截图（暂未使用）

        Returns:
            解析后的代理人数据字典，如果解析失败则返回None
        """
        try:
            # 收集所有OCR结果（包含置信度）
            all_results = []
            for text, match_list in ocr_items.items():
                for match in match_list:
                    x = match.x if hasattr(match, 'x') else 0
                    y = match.y if hasattr(match, 'y') else 0
                    confidence = match.confidence if hasattr(match, 'confidence') else 0
                    all_results.append({
                        'text': text,
                        'x': x,
                        'y': y,
                        'confidence': confidence
                    })

            # 按X轴排序
            all_results.sort(key=lambda r: r['x'])

            # 解析各个字段
            agent_name = self._parse_agent_name(all_results)
            if not agent_name:
                log.error("无法解析代理人名称")
                return None

            # 检查是否在翻译表中
            if agent_name not in self.translation_dict:
                log.warning(f"角色 {agent_name} 不在翻译表中，跳过")
                return None

            # 检查是否重复
            if agent_name in self.scanned_agent_keys:
                log.warning(f"角色 {agent_name} 已扫描过，跳过重复")
                return None

            # 记录已扫描
            self.scanned_agent_keys.add(agent_name)

            agent_level = self._parse_agent_level(all_results)
            cinema_level = self._parse_cinema_level(all_results)
            skill_levels = self._parse_skill_levels(all_results)
            core_skill_level = self._parse_core_skill_level(all_results)

            # 解析level和promotion
            level_parts = agent_level.split('/')
            current_level = int(level_parts[0])
            max_level = int(level_parts[1])
            promotion = max_level // 10 - 1

            # 解析mindscape
            mindscape = int(cinema_level.split('/')[0])

            # 展开skills
            basic = int(skill_levels.get('normal', '1/12').split('/')[0])
            dodge = int(skill_levels.get('dodge', '1/12').split('/')[0])
            assist = int(skill_levels.get('assist', '1/12').split('/')[0])
            special = int(skill_levels.get('special', '1/12').split('/')[0])
            chain = int(skill_levels.get('chain', '1/12').split('/')[0])

            # 构建代理人数据
            self.agent_counter += 1
            agent_data = {
                'key': agent_name,
                'level': current_level,
                'core': core_skill_level,
                'mindscape': mindscape,
                'dodge': dodge,
                'basic': basic,
                'chain': chain,
                'special': special,
                'assist': assist,
                'promotion': promotion,
                'potential': 0,
                'equippedDiscs': {},
                'equippedWengine': "",
                'id': f'zzz_agent_{self.agent_counter}'
            }

            log.info(f"解析代理人数据: {agent_data}")
            return agent_data

        except Exception as e:
            log.error(f"解析代理人数据失败: {e}", exc_info=True)
            return None

    def _parse_agent_name(self, results: List[Dict]) -> Optional[str]:
        """解析代理人名称（按置信度排序，然后匹配翻译表）"""
        candidates = []
        for result in results:
            text = result['text']
            confidence = result.get('confidence', 0)

            # 跳过包含"等级"、数字、"/"的文本
            if '等级' in text or '/' in text:
                continue
            # 跳过纯数字
            if text.replace(' ', '').isdigit():
                continue
            # 包含中文字符的可能是名称
            if any('\u4e00' <= c <= '\u9fff' for c in text):
                candidates.append({
                    'name': text.strip(),
                    'confidence': confidence
                })

        # 按置信度排序
        if not candidates:
            return None

        candidates.sort(key=lambda c: c['confidence'], reverse=True)

        # 尝试匹配翻译表
        for candidate in candidates:
            ocr_name = candidate['name']
            matched_key = self._match_translation(ocr_name)
            if matched_key:
                log.info(f"OCR识别: {ocr_name} (置信度: {candidate['confidence']:.4f}) -> 匹配到: {matched_key}")
                return matched_key

        # 如果没有匹配到，返回置信度最高的OCR结果
        best_name = candidates[0]['name']
        log.warning(f"未在翻译表中找到匹配，使用OCR结果: {best_name} (置信度: {candidates[0]['confidence']:.4f})")
        return best_name

    def _match_translation(self, ocr_name: str) -> Optional[str]:
        """
        在翻译表中匹配角色名称（使用模糊匹配）

        Args:
            ocr_name: OCR识别的中文名称（如"浮波 柚叶"或"猫宮又奈"）

        Returns:
            匹配到的英文key（如"Yuzuha"或"Nekomata"），如果没有匹配则返回None
        """
        # 移除空格
        ocr_name_clean = ocr_name.replace(' ', '')

        best_match = None
        best_ratio = 0.0
        best_method = ""

        # 遍历翻译表
        for en_key, translations in self.translation_dict.items():
            chs_name = translations.get('CHS', '')
            if not chs_name:
                continue

            # 1. 完全匹配（优先级最高）
            if chs_name == ocr_name or chs_name == ocr_name_clean:
                log.info(f"完全匹配: {ocr_name_clean} -> {en_key}")
                return en_key

            # 2. 包含匹配（OCR名称包含翻译表中的名称）
            if chs_name in ocr_name_clean:
                ratio = len(chs_name) / len(ocr_name_clean)
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = en_key
                    best_method = f"包含匹配(ratio={ratio:.2f})"

            # 3. 反向包含匹配（翻译表中的名称包含OCR名称）
            if ocr_name_clean in chs_name:
                ratio = len(ocr_name_clean) / len(chs_name)
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = en_key
                    best_method = f"反向包含(ratio={ratio:.2f})"

            # 4. 模糊匹配（使用SequenceMatcher计算相似度）
            similarity = SequenceMatcher(None, ocr_name_clean, chs_name).ratio()
            if similarity > best_ratio and similarity >= 0.6:  # 相似度阈值60%
                best_ratio = similarity
                best_match = en_key
                best_method = f"模糊匹配(similarity={similarity:.2f})"

        if best_match:
            log.info(f"匹配成功: {ocr_name_clean} -> {best_match} ({best_method})")
            return best_match

        log.warning(f"未找到匹配: {ocr_name_clean}")
        return None

    def _parse_agent_level(self, results: List[Dict]):
        """解析代理人等级"""
        for result in results:
            text = result['text']
            # 优先匹配"等级XX/XX"格式（完整等级）
            match = re.search(r'等级(\d{2,})/(\d{2,})', text)
            if match:
                current = int(match.group(1))
                max_level = int(match.group(2))
                return f"{current}/{max_level}"
            # 兼容旧格式，只匹配"等级XX"
            match = re.search(r'等级(\d{2,})', text)
            if match:
                return f"{match.group(1)}/60"  # 默认最大等级为60
        return "1/60"  # 默认返回1/60

    def _parse_cinema_level(self, results: List[Dict]) -> str:
        """解析影画等级（命座）"""
        for result in results:
            text = result['text']
            # 匹配"X/Y"格式
            if '/' in text and len(text) <= 5:
                # 清理可能的OCR错误（如O识别成0）
                cleaned = text.replace('O', '0').replace('o', '0')
                match = re.search(r'(\d)/(\d)', cleaned)
                if match:
                    return f"{match.group(1)}/{match.group(2)}"
        return "0/6"

    def _parse_skill_levels(self, results: List[Dict]) -> Dict[str, str]:
        """解析技能等级"""
        # 找到"等级60"和"等级7"的Y坐标
        level_60_y = None
        level_7_y = None
        for result in results:
            text = result['text']
            if re.search(r'等级\d{2,}', text):
                level_60_y = result['y']
            elif re.search(r'等级\d{1}$', text):
                level_7_y = result['y']

        if not level_60_y or not level_7_y:
            log.warning("无法找到技能等级区域的边界")
            return self._default_skill_levels()

        # 找到Y坐标在两者之间的数字
        skill_numbers = []
        for result in results:
            if level_60_y < result['y'] < level_7_y:
                text = result['text']
                # 只保留数字
                if text.replace('/', '').isdigit():
                    skill_numbers.append({
                        'text': text,
                        'x': result['x']
                    })

        # 按X轴排序
        skill_numbers.sort(key=lambda r: r['x'])

        # 合并所有数字
        merged = ''.join([n['text'] for n in skill_numbers])

        # 每2个字符作为一个数字
        numbers = []
        for i in range(0, len(merged), 2):
            if i + 1 < len(merged):
                numbers.append(merged[i:i+2])

        # 每2个数字组成一组
        skill_names = ['normal', 'dodge', 'assist', 'special', 'chain']
        skills = {}
        for i in range(0, min(len(numbers), 10), 2):
            if i // 2 < len(skill_names):
                if i + 1 < len(numbers):
                    current = numbers[i]
                    max_level = numbers[i + 1]
                    skills[skill_names[i // 2]] = f"{current}/{max_level}"

        # 如果解析失败，返回默认值
        if len(skills) != 5:
            log.warning(f"技能等级解析不完整，只解析到{len(skills)}个技能")
            return self._default_skill_levels()

        return skills

    def _parse_core_skill_level(self, results: List[Dict]) -> int:
        """解析核心技能等级"""
        for result in results:
            text = result['text']
            # 匹配"等级X"格式（单个数字）
            match = re.search(r'等级(\d)$', text)
            if match:
                return int(match.group(1))
        return 0

    def _default_skill_levels(self) -> Dict[str, str]:
        """返回默认技能等级"""
        return {
            'normal': '1/12',
            'dodge': '1/12',
            'assist': '1/12',
            'special': '1/12',
            'chain': '1/12'
        }
