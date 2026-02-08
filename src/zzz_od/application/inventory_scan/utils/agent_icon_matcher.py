"""
代理人头像匹配工具
用于识别驱动盘和音擎上装备的代理人头像
"""
import os
import re
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any

import cv2
import numpy as np
from cv2.typing import MatLike

from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log
from one_dragon.utils import cv2_utils


class AgentIconMatcher:
    """代理人头像匹配器"""

    def __init__(self, save_debug_images: bool = True):
        self.icon_dir = os_utils.get_path_under_work_dir('assets', 'wiki_data', 'icons')
        self.icon_cache: Dict[str, MatLike] = {}
        self.translation_dict: Dict = {}
        self.save_debug_images = save_debug_images
        self.debug_dir = os_utils.get_path_under_work_dir('.debug', 'icon_crops')
        self._unique_crops: Dict[str, Dict[str, Any]] = {}
        self._unique_crop_seq: int = 0
        self._hash_distance_threshold = 2
        if save_debug_images:
            os.makedirs(self.debug_dir, exist_ok=True)
        self._load_icons()
        self._load_translation_dict()

    def _load_icons(self):
        """加载所有代理人头像"""
        if not os.path.exists(self.icon_dir):
            log.warning(f"头像目录不存在: {self.icon_dir}")
            return

        icon_files = list(Path(self.icon_dir).glob("IconRoleCircle*.webp"))
        log.debug(f"加载 {len(icon_files)} 个代理人头像")

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
                log.debug(f"加载翻译字典成功: {dict_path}")
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
            region = screenshot[y1:y2, x1:x2]
            width = region.shape[1]
            crop_left = int(width * 0.3)
            crop_right = int(width * 0.7)
            region = region[:, crop_left:crop_right]
            region_hsv = cv2.cvtColor(region, cv2.COLOR_RGB2HSV)
            avg_s = float(region_hsv[:, :, 1].mean())
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
            small_icon = screenshot[y1:y2, x1:x2]

            if small_icon is None or small_icon.size == 0:
                return ""

            match_size = (31, 31)
            small_icon_rs = cv2.resize(small_icon, match_size, interpolation=cv2.INTER_AREA)
            small_icon_rs = self._apply_circle_mask(small_icon_rs)
            small_icon_gray = cv2.cvtColor(small_icon_rs, cv2.COLOR_RGB2GRAY)
            small_icon_edge = cv2.Canny(small_icon_gray, 50, 150)
            scores = []

            for icon_name, full_icon in self.icon_cache.items():
                scaled_full = cv2.resize(full_icon, match_size, interpolation=cv2.INTER_AREA)
                scaled_full = self._apply_circle_mask(scaled_full)
                scaled_full_gray = cv2.cvtColor(scaled_full, cv2.COLOR_RGB2GRAY)
                scaled_full_edge = cv2.Canny(scaled_full_gray, 50, 150)
                result = cv2.matchTemplate(small_icon_edge, scaled_full_edge, cv2.TM_CCOEFF_NORMED)
                score = result[0][0]

                scores.append((icon_name, score))

            scores.sort(key=lambda x: x[1], reverse=True)

            if not scores:
                return ""

            best_icon_name = scores[0][0]
            best_score = float(scores[0][1])
            icon_name_match = re.search(r'IconRoleCircle(\d+)', best_icon_name)
            if not icon_name_match:
                return ""

            icon_number = icon_name_match.group(1)
            icon_name = f"IconRole{icon_number}"

            agent_key = self._find_agent_key_by_icon(icon_name)

            if agent_key:
                log.debug(f"头像匹配成功: {best_icon_name} -> {agent_key}")
            else:
                log.warning(f"未找到对应的代理人: {icon_name}")

            self._cache_unique_crop_debug(
                small_icon=small_icon,
                best_icon_name=best_icon_name,
                best_score=best_score,
                agent_key=agent_key or "",
                top_scores=scores[:5]
            )

            return agent_key or ""

        except Exception as e:
            log.error(f"匹配代理人头像失败: {e}", exc_info=True)
            return ""

    def _apply_circle_mask(self, image: MatLike) -> MatLike:
        """对头像应用内圆mask。"""
        h, w = image.shape[:2]
        center = (w // 2, h // 2)
        radius = max(1, min(w, h) // 2 - 3)

        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(mask, center, radius, 255, -1)

        return cv2.bitwise_and(image, image, mask=mask)

    def _cache_unique_crop_debug(
            self,
            small_icon: MatLike,
            best_icon_name: str,
            best_score: float,
            agent_key: str,
            top_scores: List[tuple[str, float]]
    ) -> None:
        """缓存并保存唯一裁剪块的调试信息。"""
        if not self.save_debug_images:
            return

        try:
            ahash = self._compute_ahash(small_icon)
            record_key = self._find_existing_crop_key(ahash)

            now_iso = datetime.now().isoformat(timespec='seconds')

            if record_key is None:
                self._unique_crop_seq += 1
                record_key = f"icon_crop_{self._unique_crop_seq:04d}"
                img_file = f"{record_key}.jpg"
                img_path = os.path.join(self.debug_dir, img_file)
                json_path = os.path.join(self.debug_dir, f"{record_key}.json")

                bgr_icon = cv2.cvtColor(small_icon, cv2.COLOR_RGB2BGR)
                cv2.imwrite(img_path, bgr_icon)

                self._unique_crops[record_key] = {
                    'ahash': ahash,
                    'image': img_file,
                    'json_path': json_path,
                    'count': 1,
                    'firstSeen': now_iso,
                    'lastSeen': now_iso,
                    'bestMatch': best_icon_name,
                    'bestScore': round(best_score, 6),
                    'agentKey': agent_key,
                    'topMatches': [{'icon': name, 'score': round(float(score), 6)} for name, score in top_scores]
                }
            else:
                record = self._unique_crops[record_key]
                record['count'] += 1
                record['lastSeen'] = now_iso

                if best_score > record.get('bestScore', -1):
                    record['bestMatch'] = best_icon_name
                    record['bestScore'] = round(best_score, 6)
                    record['agentKey'] = agent_key
                    record['topMatches'] = [{'icon': name, 'score': round(float(score), 6)} for name, score in top_scores]

            self._write_crop_record_json(record_key)
        except Exception as e:
            log.error(f"保存唯一裁剪块调试信息失败: {e}")

    def _compute_ahash(self, image: MatLike) -> np.ndarray:
        """计算图片aHash，用于近似去重。"""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        small = cv2.resize(gray, (8, 8), interpolation=cv2.INTER_AREA)
        avg = float(small.mean())
        return (small >= avg).astype(np.uint8)

    def _find_existing_crop_key(self, ahash: np.ndarray) -> Optional[str]:
        """查找是否存在近似相同的已缓存裁剪块。"""
        for key, record in self._unique_crops.items():
            old_hash = record.get('ahash')
            if old_hash is None:
                continue
            distance = int(np.count_nonzero(old_hash != ahash))
            if distance <= self._hash_distance_threshold:
                return key
        return None

    def _write_crop_record_json(self, record_key: str) -> None:
        """将唯一裁剪块记录写入json。"""
        record = self._unique_crops[record_key]
        json_path = record.get('json_path')
        if not json_path:
            return

        payload = {
            'recordKey': record_key,
            'image': record.get('image'),
            'count': record.get('count', 0),
            'firstSeen': record.get('firstSeen'),
            'lastSeen': record.get('lastSeen'),
            'bestMatch': record.get('bestMatch', ''),
            'bestScore': record.get('bestScore', 0),
            'agentKey': record.get('agentKey', ''),
            'topMatches': record.get('topMatches', [])
        }

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

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
