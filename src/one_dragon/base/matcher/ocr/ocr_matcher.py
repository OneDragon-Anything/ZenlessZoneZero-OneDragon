from collections.abc import Callable

from cv2.typing import MatLike

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.matcher.match_result import MatchResultList
from one_dragon.base.matcher.ocr.ocr_match_result import OcrMatchResult


class OcrMatcher:

    def __init__(self):
        pass

    def update_use_gpu(self, use_gpu: bool) -> None:
        """
        更新是否使用gpu
        Args:
            use_gpu: 是否使用gpu
        """
        pass

    def is_use_gpu(self) -> bool:
        """
        是否使用gpu
        Returns:
            是否使用gpu
        """
        return False

    def init_model(
            self,
            download_by_github: bool = True,
            download_by_gitee: bool = False,
            download_by_mirror_chan: bool = False,
            proxy_url: str | None = None,
            ghproxy_url: str | None = None,
            skip_if_existed: bool = True,
            progress_callback: Callable[[float, str], None] | None = None
    ) -> bool:
        raise NotImplementedError('由具体的OCR实现提供')

    def run_ocr_single_line(self, image: MatLike, threshold: float | None = None, strict_one_line: bool = True) -> str:
        """
        单行文本识别 手动合成一行 按匹配结果从左到右 从上到下
        理论中文情况不会出现过长分行的 这里只是为了兼容英语的情况
        :param image: 图片
        :param threshold: 阈值
        :param strict_one_line: True时认为当前只有单行文本 False时依赖程序合并成一行
        :return:
        """
        raise NotImplementedError('由具体的OCR实现提供')

    def run_ocr(self, image: MatLike, threshold: float | None = None,
                merge_line_distance: float = -1) -> dict[str, MatchResultList]:
        """
        对图片进行OCR 返回所有匹配结果
        :param image: 图片
        :param threshold: 匹配阈值
        :param merge_line_distance: 多少行距内合并结果 -1为不合并 理论中文情况不会出现过长分行的 这里只是为了兼容英语的情况
        :return: {key_word: []}
        """
        raise NotImplementedError('由具体的OCR实现提供')

    def ocr(
            self,
            image: MatLike,
            threshold: float = 0,
            merge_line_distance: float = -1,
    ) -> list[OcrMatchResult]:
        """
        对图片进行OCR 返回所有识别结果

        Args:
            image: 图片
            threshold: 匹配阈值
            merge_line_distance: 多少行距内合并结果 -1为不合并 理论中文情况不会出现过长分行的 这里只是为了兼容英语的情况

        Returns:
            ocr_result_list: 识别结果列表
        """
        raise NotImplementedError('由具体的OCR实现提供')

    def crop_and_run_ocr(
            self,
            image: MatLike,
            rect: Rect,
            threshold: float = 0,
            merge_line_distance: float = -1,
    ) -> dict[str, MatchResultList]:
        """
        裁剪图片后进行OCR 自动处理 overlay 坐标偏移
        :param image: 原图
        :param rect: 裁剪区域
        :param threshold: 匹配阈值
        :param merge_line_distance: 多少行距内合并结果 -1为不合并
        :return: {key_word: []}
        """
        from one_dragon.utils import cv2_utils
        part = cv2_utils.crop_image_only(image, rect)
        bus = getattr(self, 'overlay_debug_bus', None)
        if bus is not None:
            bus.set_crop_offset(rect.x1, rect.y1)
        try:
            result = self.run_ocr(part, threshold, merge_line_distance)
        finally:
            if bus is not None:
                bus.reset_crop_offset()
        return result
