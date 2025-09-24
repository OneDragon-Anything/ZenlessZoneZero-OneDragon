import time
from dataclasses import dataclass

import cv2
import numpy as np
from cv2.typing import MatLike

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
    image_id: int  # 图片在内存中的ID
    image: MatLike  # 将图片也缓存起来 防止旧图片没引用被回收 导致出现新图片ID与旧图片重复
    ocr_result_list: list[OcrMatchResult]  # OCR识别结果
    create_time: float  # 创建时间
    color_range: list[list[int]] | None  # 颜色范围


class OcrService:
    """
    OCR服务
    - 提供缓存
    - 提供并发识别 (未实现)

    缺点：
    - 全图识别后，识别得到的文本无法按选定区域进行精准切割。
      - 例如 [图标]真实文本，会将图标错误识别成某些文本拼在一起，无法通过选择区域精准识别真实文本部分.
    """
    
    def __init__(self, ocr_matcher: OcrMatcher, max_cache_size: int = 5):
        """
        初始化OCR服务
        
        Args:
            ocr_matcher: OCR匹配器实例
            max_cache_size: 最大缓存条目数
        """
        self.ocr_matcher = ocr_matcher
        self.max_cache_size = max_cache_size
        
        # 缓存存储：key=图片ID，value为缓存条目
        self._cache: dict[int, list[OcrCacheEntry]] = {}
        self._cache_list: list[OcrCacheEntry] = []

    def _clean_expired_cache(self) -> None:
        """
        清除过期缓存
        Returns:

        """
        while len(self._cache_list) > self.max_cache_size:
            oldest_entry = self._cache_list.pop(0)
            image_id = oldest_entry.image_id

            if image_id in self._cache:
                # 从与 image_id 关联的列表中移除特定的条目
                try:
                    self._cache[image_id].remove(oldest_entry)
                    # 如果这个 image_id 的列表现在为空，则从字典中移除该键
                    if not self._cache[image_id]:
                        self._cache.pop(image_id)
                except ValueError:
                    # 在罕见的并发场景下，如果条目已经被移除，可能会发生这种情况，但可以安全地忽略。
                    pass

    def _apply_color_filter(self, image: MatLike, color_range: list[list[int]]) -> MatLike:
        """
        应用颜色过滤，最后返回黑白图。
        不返回原图颜色是因为，如果使用黑色过滤，最后得到会是一个全黑的图片，无法进行识别。
        
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
        return cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)

    def _get_ocr_result_list_from_cache(
            self,
            image: MatLike,
            color_range: list[list[int]] | None = None,
    ) -> OcrCacheEntry | None:
        """
        从缓存中获取OCR结果
        Args:
            image: 输入图片
            color_range: 颜色范围过滤 [[lower], [upper]]

        Returns:
            缓存条目
        """
        image_id = id(image)
        cache_list = self._cache.get(image_id)
        if cache_list is None:
            return None

        for cache_entry in cache_list:
            # Python 的列表 == 操作符会自动处理嵌套结构和值的比较 包括None
            if cache_entry.color_range == color_range:
                return cache_entry

        return None

    def get_ocr_result_list(
            self,
            image: MatLike,
            color_range: list[list[int]] | None = None,
            rect: Rect | None = None,
            threshold: float = 0,
            merge_line_distance: float = -1,
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
        image_id = id(image)

        cache_entity = self._get_ocr_result_list_from_cache(
            image=image,
            color_range=color_range,
        )

        # 检查缓存
        if cache_entity is not None:
            ocr_result_list = cache_entity.ocr_result_list
        else:
            # 应用颜色过滤
            processed_image = self._apply_color_filter(image, color_range)

            # 执行OCR
            ocr_result_list = self.ocr_matcher.ocr(processed_image, threshold, merge_line_distance)

            # 存储到缓存
            cache_entry = OcrCacheEntry(
                ocr_result_list=ocr_result_list,
                create_time=time.time(),
                color_range=color_range,
                image_id=image_id,
                image=image,
            )
            if image_id not in self._cache:
                self._cache[image_id] = []
            self._cache[image_id].append(cache_entry)
            self._cache_list.append(cache_entry)
            self._clean_expired_cache()

        if rect is not None:
            # 过滤出指定区域内的结果
            area_result_list: list[OcrMatchResult] = []

            for ocr_result in ocr_result_list:
                # 检查匹配结果是否和指定区域重叠
                if cal_utils.cal_overlap_percent(ocr_result.rect, rect, base=ocr_result.rect) > 0.7:
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
        self._cache.clear()
        log.debug("OCR缓存已清空")
