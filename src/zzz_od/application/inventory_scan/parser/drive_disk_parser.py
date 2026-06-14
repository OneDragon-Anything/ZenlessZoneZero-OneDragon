import json
import re
import os
import cv2
from typing import Optional, Dict, List, Any
from one_dragon.utils.log_utils import log
from one_dragon.utils import os_utils


class DriveDiskParser:
    """驱动盘属性解析器，根据OCR结果生成JSON数据"""

    # 主属性映射（主属性都是百分比，需要加下划线后缀）
    MAIN_STAT_MAP = {
        # 英文
        'HP': 'hp_',
        'ATK': 'atk_',
        'DEF': 'def_',
        'CRIT Rate': 'crit_',
        'CRIT DMG': 'crit_dmg_',
        'Anomaly Proficiency': 'anomProf',
        'PEN Ratio': 'pen_',
        'Impact': 'impact',
        'Energy Regen': 'energyRegen_',
        'Energy': 'energyRegen_',
        'Regen': 'energyRegen_',
        'Anomaly Mastery': 'anomMas_',
        # 中文
        '生命值': 'hp_',
        '攻击力': 'atk_',
        '防御力': 'def_',
        '暴击率': 'crit_',
        '暴击伤害': 'crit_dmg_',
        '异常精通': 'anomProf',
        '穿透率': 'pen_',
        '冲击力': 'impact',
        '能量自动回复': 'energyRegen_',
        '异常掌控': 'anomMas_',
        'Anomaly Mastery': 'anomMas_',
        # OCR常见错误识别
        '昇常精通': 'anomProf',  # "异常精通"的OCR错误
        '昇常掌控': 'anomMas_',
        # 属性伤害加成（新增）
        '火': 'fire_dmg_',
        '冰': 'ice_dmg_',
        '电': 'electric_dmg_',
        '以太': 'ether_dmg_',
        '物理': 'physical_dmg_',
    }

    # 副属性映射
    SUB_STAT_MAP = {
        # 英文
        'HP': 'hp',
        'ATK': 'atk',
        'ATK.': 'atk',
        'DEF': 'def',
        'CRIT Rate': 'crit_',
        'CRIT DMG': 'crit_dmg_',
        'PEN Ratio': 'pen_',
        'PEN': 'pen',
        'Anomaly Proficiency': 'anomProf',
        'Impact': 'impact',
        # 中文
        '生命值': 'hp',
        '攻击力': 'atk',
        '防御力': 'def',
        '暴击率': 'crit_',
        '暴击伤害': 'crit_dmg_',
        '穿透率': 'pen_',
        '穿透值': 'pen',
        '异常精通': 'anomProf',
        '冲击力': 'impact',
        # OCR常见错误识别
        '昇常精通': 'anomProf',  # "异常精通"的OCR错误
        # 属性伤害加成（新增）
        '火': 'fire_dmg_',
        '冰': 'ice_dmg_',
        '电': 'electric_dmg_',
        '以太': 'ether_dmg_',
        '物理': 'physical_dmg_',
    }

    def __init__(self):
        self.disc_counter = 0
        # 初始化翻译服务
        from zzz_od.application.inventory_scan.translation import TranslationService
        self.translation_service = TranslationService()
        # 初始化头像匹配器
        from zzz_od.application.inventory_scan.utils.agent_icon_matcher import AgentIconMatcher
        self.icon_matcher = AgentIconMatcher()

        # 异常数据保存目录
        self.error_dir = os_utils.get_path_under_work_dir('.debug', 'inventory_errors')
        os.makedirs(self.error_dir, exist_ok=True)

    def parse_ocr_result(self, ocr_texts: List[Dict[str, Any]], screenshot=None, index: int = 0) -> Optional[Dict]:
        """
        解析OCR结果生成驱动盘JSON数据

        Args:
            ocr_texts: OCR识别结果列表，每项包含 text, confidence, position 等信息
                      position格式: (x1, y1, x2, y2)
            screenshot: 原始截图（用于异常保存）
            index: 截图索引（用于异常保存）

        Returns:
            驱动盘JSON数据字典，解析失败返回None
        """
        try:
            # 保留完整的OCR项（包含位置信息）
            ocr_items = []
            for item in ocr_texts:
                if isinstance(item, dict):
                    ocr_items.append(item)
                else:
                    ocr_items.append({'text': str(item)})

            # 1. 预处理：按阅读顺序排序 OCR 结果 (从上到下，从左到右)
            # OCR结果可能是乱序的，需要重新排序以确保 texts 列表符合阅读习惯
            ocr_items = self._sort_ocr_items(ocr_items)

            # 2. 生成有序的文本列表，并进行错别字修正
            texts = []
            for item in ocr_items:
                original_text = item.get('text', '')
                corrected_text = self.translation_service.correct_text(original_text)

                # 更新 OCR 结果中的文本
                item['text'] = corrected_text
                texts.append(corrected_text)

            # 解析套装名称（通常在前两个文本中）
            set_key = self._parse_set_name(texts)

            # 解析位置（[1] [2] [3] [4] [5] [6]）
            slot_key = self._parse_slot(texts)

            # 解析等级（Lv. 15/15）
            level = self._parse_level(texts)

            # 解析主属性（根据位置判断是否百分比）
            main_stat_key, main_stat_value = self._parse_main_stat(texts, slot_key)

            # 解析副属性（需要位置信息来匹配升级标记，且需要排除主属性）
            substats = self._parse_substats(ocr_items, main_stat_key)

            # **异常检测：15级驱动盘应该有4个不同种类的副属性**
            if level == 15:
                # 检查副属性种类数量
                unique_keys = set(sub['key'] for sub in substats)
                if len(unique_keys) < 4:
                    error_msg = f"异常检测：15级驱动盘只有{len(unique_keys)}种副属性（应该有4种不同的副属性）"
                    log.error(error_msg)
                    log.error(f"副属性列表: {substats}")
                    self._save_error_data(screenshot, ocr_texts, texts, level, substats, index, error_msg)
                    # 仍然返回数据，但已记录异常
                    # return None  # 如果要阻止这个驱动盘被添加，取消注释这行

            # 匹配头像
            agent_key = ""
            if screenshot is not None:
                # 头像区域（修正后）(54, 54) - (85, 85)
                if self.icon_matcher.is_region_colorful(screenshot, 54, 54, 85, 85):
                    agent_key = self.icon_matcher.match_agent_icon(screenshot, 54, 54, 85, 85)

            # 生成驱动盘数据
            self.disc_counter += 1
            disc_data = {
                'setKey': set_key,
                'rarity': 'S',  # 默认S级，可以根据RARITY字段判断
                'level': level,
                'slotKey': slot_key,
                'mainStatKey': main_stat_key,
                'substats': substats,
                'location': agent_key,
                'lock': False,
                'trash': False,
                'id': f'zzz_disc_{self.disc_counter}'
            }

            return disc_data

        except Exception as e:
            log.error(f"解析OCR结果失败: {e}")
            if screenshot is not None:
                self._save_error_data(screenshot, ocr_texts, texts if 'texts' in locals() else [], 0, [], index, str(e))
            return None

    def _parse_set_name(self, texts: List[str]) -> str:
        """解析套装名称"""
        # 找到包含[数字]的文本，提取套装名称
        set_name = None

        for text in texts:
            # 检查是否包含[数字]
            if re.search(r'\[\d\]', text):
                # 找到了[数字]，提取[数字]前的文字
                match = re.match(r'(.+?)\s*\[\d\]', text)
                if match:
                    set_name = match.group(1).strip()
                break

        if not set_name:
            set_name = texts[0] if texts else 'Unknown'

        # 使用translation服务翻译成英文
        en_name = self.translation_service.translate_equipment(set_name, 'EN')

        # 转换成驼峰命名key（移除空格）
        set_key = en_name.replace(' ', '')

        return set_key

    def _parse_slot(self, texts: List[str]) -> str:
        """解析装备位置"""
        for text in texts:
            match = re.search(r'\[(\d)\]', text)
            if match:
                return match.group(1)
            # 单独的数字1-6
            if text.strip() in ['1', '2', '3', '4', '5', '6']:
                return text.strip()
        return '1'

    def _parse_level(self, texts: List[str]) -> int:
        """解析等级"""
        for text in texts:
            # 匹配中文格式: 等级15/15
            match = re.search(r'等级\s*(\d+)', text)
            if match:
                return int(match.group(1))
            # 匹配英文格式: Lv. 15/15 或 Lv.15
            match = re.search(r'Lv\.?\s*(\d+)', text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return 0

    def _parse_main_stat(self, texts: List[str], slot_key: str) -> tuple[str, Optional[float]]:
        """
        解析主属性
        位置1-3：固定值（无下划线）- HP, ATK, DEF
        位置4-6：百分比（有下划线）- HP%, ATK%, DEF%, CRIT Rate%, etc.
        """
        main_stat_key = None
        main_stat_value = None

        # 找到 "Main Stat" 或 "主属性" 关键字
        main_stat_idx = -1
        for i, text in enumerate(texts):
            if 'Main Stat' in text or 'Main' in text or '主属性' in text:
                main_stat_idx = i
                break

        if main_stat_idx >= 0:
            # 主属性名称通常在下一行
            for i in range(main_stat_idx + 1, min(main_stat_idx + 3, len(texts))):
                for key in self.MAIN_STAT_MAP.keys():
                    if key in texts[i]:
                        # 根据位置判断是否百分比
                        value = self.MAIN_STAT_MAP[key]
                        if slot_key in ['1', '2', '3']:
                            # 位置1-3：固定值，移除下划线
                            # hp_ → hp, atk_ → atk, def_ → def
                            main_stat_key = value.rstrip('_')
                        else:
                            # 位置4-6：百分比，保持原样
                            # hp_ → hp_, crit_ → crit_, etc.
                            main_stat_key = value
                        break
                if main_stat_key:
                    break

            # 主属性值通常是百分比或数字
            for i in range(main_stat_idx + 1, min(main_stat_idx + 5, len(texts))):
                match = re.search(r'(\d+(?:\.\d+)?)%?', texts[i])
                if match and texts[i] not in self.MAIN_STAT_MAP:
                    main_stat_value = float(match.group(1))
                    break

        # 默认值处理：如果解析失败，根据位置返回默认值
        if main_stat_key is None:
            main_stat_key = 'hp' if slot_key in ['1', '2', '3'] else 'hp_'

        return main_stat_key, main_stat_value

    def _parse_substats(self, ocr_items: List[Dict], main_stat_key: str) -> List[Dict]:
        """
        解析副属性
        副属性不能和主属性重复！需要过滤掉主属性

        使用位置信息将文本分组到行，然后解析每一行
        """
        # 找到 "Sub-Stats" 或 "副属性" 关键字
        sub_stat_item = None
        for item in ocr_items:
            text = item.get('text', '')
            if 'Sub-Stats' in text or 'Sub' in text or '副属性' in text:
                sub_stat_item = item
                break

        if sub_stat_item is None:
            return []

        # 获取"副属性"标签的Y坐标
        sub_stat_position = sub_stat_item.get('position')
        if sub_stat_position is None:
            # 如果没有位置信息，回退到原来的索引方式
            return self._parse_substats_by_index(ocr_items, main_stat_key)

        sub_stat_y = sub_stat_position[1]  # Y坐标（top）

        # 筛选出Y坐标大于"副属性"标签的所有文本（即在"副属性"下方的文本）
        sub_items = []
        for item in ocr_items:
            position = item.get('position')
            if position and position[1] > sub_stat_y:  # Y坐标大于"副属性"
                sub_items.append(item)

        if not sub_items:
            return []

        # 按Y坐标分组（Y坐标差异小于30的认为是同一行）
        rows = []
        current_row = [sub_items[0]]

        for i in range(1, len(sub_items)):
            item = sub_items[i]
            prev_item = sub_items[i-1]

            # 获取Y坐标
            curr_y = item.get('position', [0, 0])[1]
            prev_y = prev_item.get('position', [0, 0])[1]

            # 如果Y坐标差异小于30，认为是同一行
            if abs(curr_y - prev_y) < 30:
                current_row.append(item)
            else:
                # 新的一行
                rows.append(current_row)
                current_row = [item]

        # 添加最后一行
        if current_row:
            rows.append(current_row)

        # 解析每一行
        substats = []
        for row in rows:
            # 按X坐标排序（从左到右）
            row.sort(key=lambda x: x.get('position', [0, 0])[0])

            # 提取文本
            row_texts = [item.get('text', '') for item in row]

            # 第一个文本通常是属性名
            if not row_texts:
                continue

            first_text = row_texts[0].strip()
            stat_key = None
            base_text = first_text
            upgrades = 0

            # 尝试从第一个文本中提取升级标记
            match = re.search(r'(.+?)\s*\+(\d+)', first_text)
            if match:
                base_text = match.group(1).strip()
                upgrades = int(match.group(2))

            # 匹配属性名
            # 1. 先尝试完全匹配（去除空格后）
            base_text_normalized = base_text.replace(' ', '').replace('\t', '')
            for key, value in self.SUB_STAT_MAP.items():
                key_normalized = key.replace(' ', '').replace('\t', '')
                if base_text_normalized == key_normalized:
                    stat_key = value
                    break

            # 2. 如果完全匹配失败，尝试子串匹配
            if not stat_key:
                for key, value in self.SUB_STAT_MAP.items():
                    if key in base_text:
                        stat_key = value
                        break

            if not stat_key:
                continue

            # 如果第一个文本中没有升级标记，检查第二个文本是否是升级标记
            if upgrades == 0 and len(row_texts) > 1:
                second_text = row_texts[1].strip()
                upgrade_match = re.match(r'^\+(\d+)$', second_text)
                if upgrade_match:
                    upgrades = int(upgrade_match.group(1))

            # 副属性默认有1次升级，加上额外升级次数
            upgrades += 1

            # 判断HP/ATK/DEF是否是百分比
            # 查找行中的数值（最后一个文本通常是数值）
            if stat_key in ['hp', 'atk', 'def']:
                is_percent = False
                for text in row_texts:
                    if re.match(r'^\d+(?:\.\d+)?%$', text.strip()):
                        is_percent = True
                        break

                if is_percent:
                    stat_key += '_'

            # **关键过滤：副属性不能和主属性重复！**
            if stat_key != main_stat_key:
                substats.append({
                    'key': stat_key,
                    'upgrades': upgrades
                })

        return substats

    def _parse_substats_by_index(self, ocr_items: List[Dict], main_stat_key: str) -> List[Dict]:
        """
        解析副属性
        副属性不能和主属性重复！需要过滤掉主属性

        OCR结果按Y坐标排序，相邻的文本属于同一行，通过顺序合并判断百分比
        """
        # 找到 "Sub-Stats" 或 "副属性" 关键字的索引
        sub_stat_idx = -1
        texts = []
        for i, item in enumerate(ocr_items):
            text = item.get('text', '')
            texts.append(text)
            if 'Sub-Stats' in text or 'Sub' in text or '副属性' in text:
                sub_stat_idx = i

        if sub_stat_idx < 0:
            return []

        # 提取Sub-Stats后的所有文本
        sub_texts = texts[sub_stat_idx + 1:]

        substats = []
        i = 0
        while i < len(sub_texts):
            text = sub_texts[i].strip()

            # 检查是否是属性名（可能包含升级标记）
            stat_key = None
            base_text = text
            upgrades = 0

            # 先尝试从文本中提取升级标记
            match = re.search(r'(.+?)\s*\+(\d+)', text)
            if match:
                base_text = match.group(1).strip()
                upgrades = int(match.group(2))

            # 匹配属性名 - 改进匹配逻辑
            # 1. 先尝试完全匹配（去除空格后）
            base_text_normalized = base_text.replace(' ', '').replace('\t', '')
            for key, value in self.SUB_STAT_MAP.items():
                key_normalized = key.replace(' ', '').replace('\t', '')
                if base_text_normalized == key_normalized:
                    stat_key = value
                    break

            # 2. 如果完全匹配失败，尝试子串匹配
            if not stat_key:
                for key, value in self.SUB_STAT_MAP.items():
                    if key in base_text:
                        stat_key = value
                        break

            if stat_key:
                # 如果文本中没有升级标记，向后查找直到找到升级标记或数值
                if upgrades == 0:
                    j = i + 1
                    while j < len(sub_texts):
                        next_text = sub_texts[j].strip()

                        # 检查是否是独立的升级标记
                        upgrade_match = re.match(r'^\+(\d+)$', next_text)
                        if upgrade_match:
                            upgrades = int(upgrade_match.group(1))
                            i = j  # 更新索引，跳过已处理的文本
                            break

                        # 检查是否是纯数字或百分比数字（表示已到数值）
                        if re.match(r'^\d+(?:\.\d+)?%?$', next_text):
                            # 到达数值了，不再是升级标记
                            break

                        j += 1

                # 副属性默认有1次升级，加上额外升级次数
                # 例如：+0表示1次，+1表示2次，+4表示5次
                upgrades += 1

                # 判断HP/ATK/DEF是否是百分比
                # 向后查找直到遇到纯数字或百分比数字
                if stat_key in ['hp', 'atk', 'def']:
                    is_percent = False
                    j = i + 1
                    while j < len(sub_texts):
                        next_text = sub_texts[j].strip()

                        # 检查是否是纯数字或百分比数字
                        if re.match(r'^\d+(?:\.\d+)?%?$', next_text):
                            # 找到数值，判断是否包含%
                            if '%' in next_text:
                                is_percent = True
                            break

                        j += 1

                    if is_percent:
                        stat_key += '_'

                # **关键过滤：副属性不能和主属性重复！**
                if stat_key != main_stat_key:
                    substats.append({
                        'key': stat_key,
                        'upgrades': upgrades
                    })

            i += 1

        return substats

    def _save_error_data(self, screenshot, ocr_texts: List[Dict], texts: List[str],
                         level: int, substats: List[Dict], index: int, error_msg: str):
        """
        保存异常数据到文件

        Args:
            screenshot: 原始截图
            ocr_texts: OCR识别结果
            texts: 提取的文本列表
            level: 驱动盘等级
            substats: 解析出的副属性
            index: 截图索引
            error_msg: 错误信息
        """
        try:
            import time
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            error_id = f"{timestamp}_index{index}"

            # 保存截图
            if screenshot is not None:
                img_path = os.path.join(self.error_dir, f"{error_id}.jpg")
                # 将 RGB 转换为 BGR 格式（OpenCV 默认格式）
                bgr_image = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)
                cv2.imwrite(img_path, bgr_image)
                log.info(f"异常截图已保存: {img_path}")

            # 保存OCR结果和错误信息
            error_data = {
                'error_id': error_id,
                'index': index,
                'error_msg': error_msg,
                'level': level,
                'substats': substats,
                'unique_substat_count': len(set(sub['key'] for sub in substats)),
                'texts': texts,
                'ocr_texts': ocr_texts
            }

            json_path = os.path.join(self.error_dir, f"{error_id}.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(error_data, f, indent=2, ensure_ascii=False)
            log.info(f"异常数据已保存: {json_path}")

        except Exception as e:
            log.error(f"保存异常数据失败: {e}")

    def _sort_ocr_items(self, ocr_items: List[Dict]) -> List[Dict]:
        """
        对OCR结果进行排序：从上到下，同一行从左到右
        """
        if not ocr_items:
            return []

        # 辅助函数：获取Y坐标
        def get_y(item):
            pos = item.get('position')
            return pos[1] if pos else 99999

        def get_x(item):
            pos = item.get('position')
            return pos[0] if pos else 0

        # 1. 初步按Y坐标排序
        # 这一步是为了让相邻行的元素大体在一起
        ocr_items.sort(key=get_y)

        # 2. 分行并按X坐标排序
        sorted_items = []
        current_row = [ocr_items[0]]

        # 行高阈值，参考原代码中的30，这里设为20更严格一点，避免跨行
        ROW_THRESHOLD = 20

        for i in range(1, len(ocr_items)):
            item = ocr_items[i]
            # 与当前行第一个元素比较Y坐标
            # 注意：这里假设行首元素代表了该行的"标准"高度
            if abs(get_y(item) - get_y(current_row[0])) < ROW_THRESHOLD:
                current_row.append(item)
            else:
                # 结束当前行
                # 行内按X坐标排序
                current_row.sort(key=get_x)
                sorted_items.extend(current_row)
                # 新起一行
                current_row = [item]

        # 处理最后一行
        if current_row:
            current_row.sort(key=get_x)
            sorted_items.extend(current_row)

        return sorted_items

    def generate_export_json(self, discs: List[Dict]) -> str:
        """
        生成导出的JSON字符串

        Args:
            discs: 驱动盘数据列表

        Returns:
            格式化的JSON字符串
        """
        export_data = {
            'format': 'ZOD',
            'dbVersion': 2,
            'source': 'Zenless Optimizer',
            'version': 1,
            'discs': discs
        }

        return json.dumps(export_data, indent=2, ensure_ascii=False)


def test_ocr_first_image():
    """测试OCR第一个驱动盘图片"""
    import sys
    import os

    # 设置启动路径
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..'))
    src_path = os.path.join(project_root, 'src')
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    import cv2
    from one_dragon.utils import os_utils
    from zzz_od.context.zzz_context import ZContext

    # 初始化上下文
    ctx = ZContext()
    ctx.init()

    # 获取第一个截图路径
    screenshots_dir = os_utils.get_path_under_work_dir('.debug', 'inventory_screenshots')
    image_path = os.path.join(screenshots_dir, 'drive_disk-0.jpg')

    if not os.path.exists(image_path):
        print(f"图片不存在: {image_path}")
        return

    # 读取图片
    screenshot = cv2.imread(image_path)
    if screenshot is None:
        print(f"读取图片失败: {image_path}")
        return

    print(f"正在OCR图片: {image_path}")
    print(f"图片尺寸: {screenshot.shape}")

    # 直接OCR
    ocr_result = ctx.ocr.run_ocr_single_line(screenshot)

    print("\n=== OCR结果 ===")
    if not ocr_result:
        print("OCR结果为空")
        return

    for idx, item in enumerate(ocr_result):
        if isinstance(item, str):
            print(f"{idx}: {item}")
        elif isinstance(item, dict):
            print(f"{idx}: {item}")
        else:
            text = item.text if hasattr(item, 'text') else str(item)
            score = item.score if hasattr(item, 'score') else 'N/A'
            print(f"{idx}: {text} (confidence: {score})")

    # 解析结果
    print("\n=== 解析结果 ===")
    parser = DriveDiskParser()

    # 转换OCR结果
    ocr_items = []
    for item in ocr_result:
        if isinstance(item, str):
            ocr_items.append({'text': item, 'confidence': 1.0, 'position': None})
        elif isinstance(item, dict):
            ocr_items.append(item)
        else:
            box = item.box if hasattr(item, 'box') else None
            if box and len(box) >= 4:
                x1, y1 = min(p[0] for p in box), min(p[1] for p in box)
                x2, y2 = max(p[0] for p in box), max(p[1] for p in box)
                position = (x1, y1, x2, y2)
            else:
                position = None
            ocr_items.append({
                'text': item.text if hasattr(item, 'text') else str(item),
                'confidence': item.score if hasattr(item, 'score') else 1.0,
                'position': position
            })

    disc_data = parser.parse_ocr_result(ocr_items)
    if disc_data:
        import json
        print(json.dumps(disc_data, indent=2, ensure_ascii=False))
    else:
        print("解析失败")


if __name__ == '__main__':
    test_ocr_first_image()
