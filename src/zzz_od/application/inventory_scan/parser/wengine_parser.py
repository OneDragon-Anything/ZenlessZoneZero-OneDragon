import re
import json
import os
import time
from typing import Optional, Dict, List, Any
import cv2
from cv2.typing import MatLike

from one_dragon.utils.log_utils import log
from one_dragon.utils import os_utils


class WengineParser:
    """音擎属性解析器"""

    def __init__(self):
        self.wengine_counter = 0
        from zzz_od.application.inventory_scan.translation import TranslationService
        self.translation_service = TranslationService()
        from zzz_od.application.inventory_scan.utils.agent_icon_matcher import AgentIconMatcher
        self.icon_matcher = AgentIconMatcher()
        # 异常数据保存目录
        self.error_dir = os_utils.get_path_under_work_dir('.debug', 'inventory_errors')
        os.makedirs(self.error_dir, exist_ok=True)

    def parse_ocr_result(self, ocr_items: List[Dict[str, Any]], screenshot: MatLike) -> Optional[Dict]:
        """
        解析OCR结果生成音擎JSON数据

        Args:
            ocr_items: OCR识别结果列表
            screenshot: 原始截图（用于灰度检测）

        Returns:
            音擎JSON数据字典，解析失败返回None
        """
        try:
            texts = [item.get('text', '') for item in ocr_items]

            # 解析音擎名称
            wengine_key = self._parse_wengine_name(texts)

            # 解析等级和突破等级
            level, promotion = self._parse_level_and_promotion(texts)

            # 解析精炼等级（灰度检测）
            modification = self._parse_modification(screenshot)

            # 匹配头像
            agent_key = ""
            # 头像区域（修正后）(54, 54) - (85, 85)
            if self.icon_matcher.is_region_colorful(screenshot, 54, 54, 85, 85):
                agent_key = self.icon_matcher.match_agent_icon(screenshot, 54, 54, 85, 85)

            # 生成音擎数据
            self.wengine_counter += 1
            wengine_data = {
                'key': wengine_key,
                'level': level,
                'modification': modification,
                'promotion': promotion,
                'location': agent_key,
                'lock': False,
                'id': f'zzz_wengine_{self.wengine_counter}'
            }

            return wengine_data

        except Exception as e:
            log.error(f"解析OCR结果失败: {e}", exc_info=True)
            # 保存错误截图
            if screenshot is not None:
                self._save_error(screenshot, f"解析异常: {e}", ocr_items)
            return None

    def _save_error(self, screenshot: MatLike, error_msg: str, ocr_results: List[Dict]) -> None:
        """
        保存错误截图和相关信息

        Args:
            screenshot: 截图
            error_msg: 错误信息
            ocr_results: OCR识别结果
        """
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            error_id = f"wengine_{timestamp}_{self.wengine_counter}"

            # 保存截图
            if screenshot is not None:
                img_path = os.path.join(self.error_dir, f"{error_id}.jpg")
                # 将 RGB 转换为 BGR 格式（OpenCV 默认格式）
                bgr_image = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)
                cv2.imwrite(img_path, bgr_image, [cv2.IMWRITE_JPEG_QUALITY, 85])
                log.info(f"错误截图已保存: {img_path}")

            # 保存OCR结果和错误信息
            error_data = {
                'error_id': error_id,
                'error_msg': error_msg,
                'ocr_texts': ocr_results
            }

            json_path = os.path.join(self.error_dir, f"{error_id}.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(error_data, f, indent=2, ensure_ascii=False)
            log.info(f"错误信息已保存: {json_path}")

        except Exception as e:
            log.error(f"保存错误信息失败: {e}", exc_info=True)

    def _parse_wengine_name(self, texts: List[str]) -> str:
        """解析音擎名称"""
        # 音擎名称通常是第一个文本
        wengine_name = texts[0] if texts else 'Unknown'

        # 使用translation服务翻译成英文
        en_name = self.translation_service.translate_weapon(wengine_name, 'EN')

        # 转换成驼峰命名key（移除空格）
        wengine_key = en_name.replace(' ', '')

        return wengine_key

    def _parse_level_and_promotion(self, texts: List[str]) -> tuple[int, int]:
        """
        解析等级和突破等级
        从"等级A/B"中提取：level=A, promotion=B/10-1
        """
        level = 0
        promotion = 0

        for text in texts:
            # 匹配中文格式: 等级60/60
            match = re.search(r'等级\s*(\d+)/(\d+)', text)
            if match:
                level = int(match.group(1))
                max_level = int(match.group(2))
                promotion = max_level // 10 - 1
                break
            # 匹配英文格式: Lv. 60/60
            match = re.search(r'Lv\.?\s*(\d+)/(\d+)', text, re.IGNORECASE)
            if match:
                level = int(match.group(1))
                max_level = int(match.group(2))
                promotion = max_level // 10 - 1
                break

        return level, promotion

    def _parse_modification(self, screenshot: MatLike) -> int:
        """
        解析精炼等级（通过灰度检测）
        检测5个点的灰度值，相邻差异≤20则继续计数
        """
        # 转换为灰度图
        if len(screenshot.shape) == 3:
            gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        else:
            gray = screenshot

        # 检测5个点的灰度值
        gray_values = []
        for i in range(5):
            x = 260 + i * 30
            y = 160
            gray_value = int(gray[y, x])
            gray_values.append(gray_value)

        # 从第一个点开始，相邻点差异≤20则继续，>20则停止
        modification = 1  # 至少有1个星星
        for i in range(1, 5):
            diff = abs(gray_values[i] - gray_values[i-1])
            if diff <= 20:
                modification += 1
            else:
                break

        return modification

    def generate_export_json(self, wengines: List[Dict]) -> str:
        """生成导出的JSON字符串"""
        import json
        export_data = {
            'format': 'ZOD',
            'dbVersion': 2,
            'source': 'Zenless Optimizer',
            'version': 1,
            'wengines': wengines
        }
        return json.dumps(export_data, indent=2, ensure_ascii=False)
