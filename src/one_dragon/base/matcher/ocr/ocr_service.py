import time

import cv2
import numpy as np
from cv2.typing import MatLike
from dataclasses import dataclass
from threading import Lock
from typing import List, Optional

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.matcher.match_result import MatchResultList
from one_dragon.base.matcher.ocr.ocr_match_result import OcrMatchResult
from one_dragon.base.matcher.ocr.ocr_matcher import OcrMatcher
from one_dragon.utils import cal_utils
from one_dragon.utils import str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log


@dataclass(frozen=True)
class OcrCacheEntry:
    """OCR缓存条目"""
    ocr_result_list: list[OcrMatchResult]  # OCR识别结果
    create_time: float  # 创建时间
    cache_key: str  # 缓存 key
    image_hash: str  # 图片哈希
    color_range_key: str  # 颜色范围键值


class OcrService:
    """
    OCR服务
    - 提供缓存
    - 提存并发识别 (未实现)
    """
    
    def __init__(self, ocr_matcher: OcrMatcher, max_cache_size: int = 2):
        """
        初始化OCR服务
        
        Args:
            ocr_matcher: OCR匹配器实例
            max_cache_size: 最大缓存条目数
        """
        self.ocr_matcher = ocr_matcher
        self.max_cache_size = max_cache_size
        
        # 缓存存储：key为图片哈希+颜色范围键，value为缓存条目
        self._cache: dict[str, OcrCacheEntry] = {}
        self._cache_list: list[OcrCacheEntry] = []
        self._cache_lock = Lock()
    
    def _generate_image_hash(self, image: MatLike) -> str:
        """
        生成图片哈希值
        
        Args:
            image: 输入图片
            
        Returns:
            图片的MD5哈希值
        """
        # 将图片转换为字节数组并计算哈希
        return id(image)
    
    def _generate_color_range_key(self, color_range: list[list[int]] | None) -> str:
        """
        生成颜色范围键值
        
        Args:
            color_range: 颜色范围 [[lower], [upper]]
            
        Returns:
            颜色范围的字符串键值
        """
        if color_range is None:
            return "0"

        range_arr = []
        for range in color_range:
            for num in range:
                range_arr.append(str(num))
        return '_'.join(range_arr)

    def _generate_cache_key(self, image_hash: str, color_range_key: str) -> str:
        """
        生成缓存键
        
        Args:
            image_hash: 图片哈希
            color_range_key: 颜色范围键
            
        Returns:
            缓存键
        """
        return f"{image_hash}_{color_range_key}"
    
    def _clean_expired_cache(self) -> None:
        """
        清除过期缓存
        Returns:

        """
        if len(self._cache_list) <= self.max_cache_size:
            return

        first_cache: OcrCacheEntry = self._cache_list.pop(0)
        self._cache.pop(first_cache.cache_key)
    
    def _apply_color_filter(self, image: MatLike, color_range: Optional[List]) -> MatLike:
        """
        应用颜色过滤
        
        Args:
            image: 输入图片
            color_range: 颜色范围 [[lower], [upper]]
            
        Returns:
            过滤后的图片
        """
        if color_range is None:
            return image
        
        # 应用颜色范围过滤
        mask = cv2.inRange(image, np.array(color_range[0]), np.array(color_range[1]))
        # 膨胀操作，增强文本区域
        from one_dragon.utils import cv2_utils
        mask = cv2_utils.dilate(mask, 5)
        filtered_image = cv2.bitwise_and(image, image, mask=mask)
        
        return filtered_image

    def get_ocr_result_list(
            self,
            image: MatLike,
            color_range: list[list[int]] | None = None,
            rect: Rect | None = None,
            threshold: float = 0,
            merge_line_distance: float = -1
    ) -> list[OcrMatchResult]:
        """
        获取全图OCR结果，优先从缓存获取

        Args:
            image: 输入图片
            color_range: 颜色范围过滤 [[lower], [upper]]
            rect: 识别特定的区域
            threshold: OCR阈值
            merge_line_distance: 行合并距离

        Returns:
            ocr_result_list: OCR识别结果列表
        """
        # 生成缓存键
        image_hash = self._generate_image_hash(image)
        color_range_key = self._generate_color_range_key(color_range)
        cache_key = self._generate_cache_key(image_hash, color_range_key)

        # 检查缓存
        if cache_key in self._cache:
            ocr_result_list = self._cache[cache_key].ocr_result_list
        else:
            # 应用颜色过滤
            processed_image = self._apply_color_filter(image, color_range)

            # 执行OCR
            ocr_result_list = self.ocr_matcher.ocr(processed_image, threshold, merge_line_distance)

            # 存储到缓存
            cache_entry = OcrCacheEntry(
                ocr_result_list=ocr_result_list,
                create_time=time.time(),
                cache_key=cache_key,
                image_hash=image_hash,
                color_range_key=color_range_key
            )
            self._cache[cache_key] = cache_entry
            self._clean_expired_cache()

        if rect is not None:
            # 过滤出指定区域内的结果
            area_result_list: list[OcrMatchResult] = []

            for ocr_result in ocr_result_list:
                # 检查匹配结果是否和指定区域重叠
                if cal_utils.cal_overlap_percent(ocr_result.rect, rect) > 0.7:
                    area_result_list.append(ocr_result)

            return area_result_list
        else:
            return ocr_result_list

    def get_ocr_result_map(
            self,
            image: MatLike,
            color_range: list[list[int]] | None = None,
            rect: Rect | None = None,
            threshold: float = 0,
            merge_line_distance: float = -1
    ) -> dict[str, MatchResultList]:
        """"
        获取全图OCR结果，优先从缓存获取

        Args:
            image: 输入图片
            color_range: 颜色范围过滤 [[lower], [upper]]
            rect: 识别特定的区域
            threshold: OCR阈值
            merge_line_distance: 行合并距离

        Returns:
            ocr_result_map: key=识别文本 value=识别结果列表
        """
        ocr_result_list = self.get_ocr_result_list(
            image=image,
            color_range=color_range,
            rect=rect,
            threshold=threshold,
            merge_line_distance=merge_line_distance
        )
        return self.convert_list_to_map(ocr_result_list)

    def convert_list_to_map(self, ocr_result_list: list[OcrMatchResult]) -> dict[str, MatchResultList]:
        """
        转换OCR识别结果 list -> map
        Args:
            ocr_result_list: OCR识别结果列表

        Returns:
            ocr_result_map: key=识别文本 value=识别结果列表
        """
        result_map: dict[str, MatchResultList] = {}
        for mr in ocr_result_list:
            word: str = mr.data
            if word not in result_map:
                result_map[word] = MatchResultList(only_best=False)
            result_map[word].append(mr, auto_merge=False)
        return result_map

    def find_text_in_area(
            self,
            image: MatLike,
            rect: Rect,
            target_text: str,
            color_range: list[list[int]] = None,
            threshold: float = 0.6
    ) -> bool:
        """
        在指定区域内查找目标文本

        Args:
            image: 输入图片
            rect: 目标区域
            target_text: 要查找的文本
            color_range: 颜色范围过滤
            threshold: 文本匹配阈值

        Returns:
            是否找到目标文本
        """
        ocr_result_list: list[OcrMatchResult] = self.get_ocr_result_list(
            image=image,
            rect=rect,
            color_range=color_range,
        )
        ocr_word_list: list[str] = [i.data for i in ocr_result_list]

        target_word = gt(target_text, 'game')
        target_idx = str_utils.find_best_match_by_difflib(target_word, ocr_word_list, cutoff=threshold)
        return target_idx is not None and target_idx >= 0

    def clear_cache(self) -> None:
        """清空所有缓存"""
        with self._cache_lock:
            self._cache.clear()
            log.debug("OCR缓存已清空")
