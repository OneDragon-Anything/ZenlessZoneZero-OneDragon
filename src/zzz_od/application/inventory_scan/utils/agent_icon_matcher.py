"""
代理人头像匹配工具
用于识别驱动盘和音擎上装备的代理人头像
"""
import os
import re
from pathlib import Path
from typing import Optional, Dict, List, Tuple

import cv2
import numpy as np
from cv2.typing import MatLike

from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log
from one_dragon.utils import cv2_utils


class AgentIconMatcher:
    """代理人头像匹配器"""

    def __init__(self):
        self.icon_dir = os_utils.get_path_under_work_dir('assets', 'wiki_data', 'icons')
        self.icon_cache: Dict[str, MatLike] = {}
        self.translation_dict: Dict = {}
        self._load_icons()
        self._load_translation_dict()

    def _load_icons(self):
        """加载所有代理人头像"""
        if not os.path.exists(self.icon_dir):
            log.warning(f"头像目录不存在: {self.icon_dir}")
            return

        icon_files = list(Path(self.icon_dir).glob("IconRoleCircle*.webp"))
        log.info(f"加载 {len(icon_files)} 个代理人头像")

        for icon_file in icon_files:
            icon = cv2_utils.read_image(str(icon_file))
            self.icon_cache[icon_file.name] = icon

    def _load_translation_dict(self):
        """加载翻译字典"""
        dict_path = os_utils.get_path_under_work_dir('assets', 'wiki_data', 'zzz_translation.json')
        try:
            if os.path.exists(dict_path):
                import json
                with open(dict_path, 'r', encoding='utf-8') as f:
                    self.translation_dict = json.load(f)
                log.info(f"加载翻译字典成功: {dict_path}")
        except Exception as e:
            log.error(f"加载翻译字典失败: {e}")

    def is_region_colorful(self, screenshot: MatLike, x1: int, y1: int, x2: int, y2: int) -> bool:
        """
        检测指定区域是否出现彩色

        Args:
            screenshot: 截图
            x1, y1, x2, y2: 区域坐标

        Returns:
            True 如果区域有彩色（S通道均值>20），False 否则
        """
        try:
            # 裁剪区域
            region = screenshot[y1:y2, x1:x2]

            # 左右各裁剪30%，只检测中间40%（避免边缘影响）
            width = region.shape[1]
            crop_left = int(width * 0.3)
            crop_right = int(width * 0.7)
            region = region[:, crop_left:crop_right]

            # 转换为HSV
            region_hsv = cv2.cvtColor(region, cv2.COLOR_RGB2HSV)

            # 计算S通道（饱和度）的平均值
            avg_s = float(region_hsv[:, :, 1].mean())

            # 检测平均S通道是否大于20（有彩色）
            is_colorful = avg_s > 20

            return is_colorful
        except Exception as e:
            log.error(f"检测区域彩色失败: {e}")
            return False

    def match_agent_icon(self, screenshot: MatLike, x1: int, y1: int, x2: int, y2: int) -> str:
        """
        匹配代理人头像

        Args:
            screenshot: 截图
            x1, y1, x2, y2: 头像区域坐标

        Returns:
            代理人key（如 "Billy"），未匹配到返回空字符串
        """
        try:
            # 裁剪头像区域
            small_icon = screenshot[y1:y2, x1:x2]

            if small_icon is None or small_icon.size == 0:
                return ""

            # 计算所有头像的匹配分数
            scores = []
            h, w = small_icon.shape[:2]

            for icon_name, full_icon in self.icon_cache.items():
                # 将全尺寸头像缩小到小图标尺寸
                scaled_full = cv2.resize(full_icon, (w, h), interpolation=cv2.INTER_AREA)

                # 模板匹配（TM_CCOEFF_NORMED）
                result = cv2.matchTemplate(small_icon, scaled_full, cv2.TM_CCOEFF_NORMED)
                score = result[0][0]

                scores.append((icon_name, score))

            # 按分数排序
            scores.sort(key=lambda x: x[1], reverse=True)

            if not scores:
                return ""

            # 获取最佳匹配的头像文件名
            best_icon_name = scores[0][0]

            # 从文件名提取图标名称
            # IconRoleCircle10.webp -> IconRole10
            icon_name_match = re.search(r'IconRoleCircle(\d+)', best_icon_name)
            if not icon_name_match:
                return ""

            icon_number = icon_name_match.group(1)
            icon_name = f"IconRole{icon_number}"

            # 在翻译字典中查找对应的代理人key
            agent_key = self._find_agent_key_by_icon(icon_name)

            if agent_key:
                log.debug(f"头像匹配成功: {best_icon_name} -> {agent_key}")
            else:
                log.warning(f"未找到对应的代理人: {icon_name}")

            return agent_key or ""

        except Exception as e:
            log.error(f"匹配代理人头像失败: {e}", exc_info=True)
            return ""

    def _find_agent_key_by_icon(self, icon_name: str) -> Optional[str]:
        """
        根据图标名称查找代理人key

        Args:
            icon_name: 图标名称（如 "IconRole10"）

        Returns:
            代理人key（如 "Billy"），未找到返回None
        """
        try:
            characters = self.translation_dict.get('character', {})
            for char_id, char_data in characters.items():
                if char_data.get('icon') == icon_name:
                    return char_data.get('code')
            return None
        except Exception as e:
            log.error(f"查找代理人key失败: {e}")
            return None