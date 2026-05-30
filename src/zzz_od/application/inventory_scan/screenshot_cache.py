import os
import cv2
from typing import Optional
from cv2.typing import MatLike
from one_dragon.utils import cv2_utils, os_utils
from one_dragon.utils.log_utils import log


class ScreenshotCache:
    """截图缓存管理器，支持多种类型的独立缓存"""

    def __init__(self, save_dir: Optional[str] = None, debug_mode: bool = False):
        """
        初始化截图缓存

        Args:
            save_dir: 截图保存目录，None表示不保存到文件
            debug_mode: 调试模式，True时保存到文件，False时只缓存到内存
        """
        self.save_dir = save_dir
        self.debug_mode = debug_mode

        # 3个独立的缓存
        self._drive_disk_cache: dict[int, MatLike] = {}
        self._wengine_cache: dict[int, MatLike] = {}
        self._agent_cache: dict[int, MatLike] = {}

        # 3个独立的索引计数器
        self._drive_disk_index = 0
        self._wengine_index = 0
        self._agent_index = 0

        # 缓存类型到字典的映射
        self._cache_map = {
            'drive_disk': self._drive_disk_cache,
            'wengine': self._wengine_cache,
            'agent': self._agent_cache
        }

        # 缓存类型到文件名前缀的映射
        self._prefix_map = {
            'drive_disk': 'drive_disk',
            'wengine': 'wengine',
            'agent': 'agent'
        }

        if self.save_dir is not None:
            os.makedirs(self.save_dir, exist_ok=True)

    def save(self, cache_type: str, screenshot: MatLike) -> int:
        """
        保存截图到指定类型的缓存

        Args:
            cache_type: 缓存类型 ('drive_disk', 'wengine', 'agent')
            screenshot: 截图数据

        Returns:
            截图索引
        """
        if cache_type not in self._cache_map:
            raise ValueError(f"不支持的缓存类型: {cache_type}")

        cache = self._cache_map[cache_type]
        
        # 获取当前索引并递增计数器
        if cache_type == 'drive_disk':
            index = self._drive_disk_index
            self._drive_disk_index += 1
        elif cache_type == 'wengine':
            index = self._wengine_index
            self._wengine_index += 1
        elif cache_type == 'agent':
            index = self._agent_index
            self._agent_index += 1
        else:
            raise ValueError(f"不支持的缓存类型: {cache_type}")

        # 先缓存到内存
        cache[index] = screenshot.copy()

        # 调试模式下保存到文件
        if self.debug_mode and self.save_dir is not None:
            try:
                prefix = self._prefix_map[cache_type]
                filename = f"{prefix}-{index}.jpg"
                filepath = os.path.join(self.save_dir, filename)

                # 转换为灰度图以减少体积
                gray = cv2.cvtColor(screenshot, cv2.COLOR_RGB2GRAY)
                cv2.imwrite(filepath, gray, [cv2.IMWRITE_JPEG_QUALITY, 85])
            except Exception as e:
                log.error(f"保存截图到文件失败({cache_type}, index={index}): {e}")

        return index

    def get(self, cache_type: str, index: int) -> Optional[MatLike]:
        """
        从指定类型缓存获取截图

        Args:
            cache_type: 缓存类型 ('drive_disk', 'wengine', 'agent')
            index: 截图索引

        Returns:
            截图数据，不存在返回None
        """
        if cache_type not in self._cache_map:
            raise ValueError(f"不支持的缓存类型: {cache_type}")

        cache = self._cache_map[cache_type]

        # 先从内存读取
        if index in cache:
            return cache[index].copy()

        # 内存中没有，尝试从文件读取
        if self.save_dir is not None:
            try:
                prefix = self._prefix_map[cache_type]
                filename = f"{prefix}-{index}.jpg"
                filepath = os.path.join(self.save_dir, filename)

                if os.path.exists(filepath):
                    screenshot = cv2.imread(filepath)
                    if screenshot is not None:
                        # 缓存到内存，避免重复读取文件
                        cache[index] = screenshot
                        return screenshot.copy()
            except Exception as e:
                log.error(f"从文件读取截图失败({cache_type}, index={index}): {e}")

        return None

    def get_all_indices(self, cache_type: str) -> list[int]:
        """
        获取指定类型的所有截图索引

        Args:
            cache_type: 缓存类型 ('drive_disk', 'wengine', 'agent')

        Returns:
            索引列表
        """
        if cache_type not in self._cache_map:
            raise ValueError(f"不支持的缓存类型: {cache_type}")

        cache = self._cache_map[cache_type]
        prefix = self._prefix_map[cache_type]

        # 如果有保存目录且目录存在，尝试从文件系统获取索引
        if self.save_dir is not None and os.path.exists(self.save_dir):
            try:
                files = [f for f in os.listdir(self.save_dir) if f.startswith(f'{prefix}-') and f.endswith('.jpg')]
                file_indices = sorted([int(f.split('-')[1].split('.')[0]) for f in files])
                # 合并内存缓存和文件的索引
                return sorted(set(file_indices + list(cache.keys())))
            except Exception as e:
                log.error(f"从文件系统获取截图索引失败({cache_type}): {e}")
                # fallback到内存缓存

        # 从内存缓存获取索引（包括文件读取失败的fallback情况）
        return sorted(cache.keys())

    def clear_cache(self, cache_type: str):
        """
        清空指定类型的内存缓存

        Args:
            cache_type: 缓存类型 ('drive_disk', 'wengine', 'agent')
        """
        if cache_type not in self._cache_map:
            raise ValueError(f"不支持的缓存类型: {cache_type}")

        self._cache_map[cache_type].clear()

    def reset_all(self):
        """
        清空所有缓存并重置索引计数器
        用于开始新一轮扫描时确保从头开始
        """
        # 清空所有内存缓存
        self._drive_disk_cache.clear()
        self._wengine_cache.clear()
        self._agent_cache.clear()
        
        # 重置所有索引计数器
        self._drive_disk_index = 0
        self._wengine_index = 0
        self._agent_index = 0
        
        log.info("已清空所有缓存并重置索引")

    def __len__(self) -> int:
        """返回所有缓存中的截图总数"""
        return len(self._drive_disk_cache) + len(self._wengine_cache) + len(self._agent_cache)