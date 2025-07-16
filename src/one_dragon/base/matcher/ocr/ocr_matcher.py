from cv2.typing import MatLike
from typing import Optional, Callable

from one_dragon.base.matcher.match_result import MatchResultList
from one_dragon.base.matcher.ocr.ocr_match_result import OcrMatchResult


class OcrMatcher:

    def __init__(self):
        pass

    def init_model(
            self,
            download_by_github: bool = True,
            download_by_gitee: bool = False,
            download_by_mirror_chan: bool = False,
            proxy_url: Optional[str] = None,
            ghproxy_url: Optional[str] = None,
            skip_if_existed: bool = True,
            progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> bool:
        pass

    def run_ocr_single_line(self, image: MatLike, threshold: float = None, strict_one_line: bool = True) -> str:
        """
        单行文本识别 手动合成一行 按匹配结果从左到右 从上到下
        理论中文情况不会出现过长分行的 这里只是为了兼容英语的情况
        :param image: 图片
        :param threshold: 阈值
        :param strict_one_line: True时认为当前只有单行文本 False时依赖程序合并成一行
        :return:
        """
        pass

    def run_ocr(self, image: MatLike, threshold: float = None,
                merge_line_distance: float = -1) -> dict[str, MatchResultList]:
        """
        对图片进行OCR 返回所有匹配结果
        :param image: 图片
        :param threshold: 匹配阈值
        :param merge_line_distance: 多少行距内合并结果 -1为不合并 理论中文情况不会出现过长分行的 这里只是为了兼容英语的情况
        :return: {key_word: []}
        """
        pass

    def ocr(self, image: MatLike, threshold: float = 0,
                merge_line_distance: float = -1) -> list[OcrMatchResult]:
        """
        对图片进行OCR 返回所有识别结果

        Args:
            image: 图片
            threshold: 匹配阈值
            merge_line_distance: 多少行距内合并结果 -1为不合并 理论中文情况不会出现过长分行的 这里只是为了兼容英语的情况

        Returns:
            ocr_result_list: 识别结果列表
        """
        pass