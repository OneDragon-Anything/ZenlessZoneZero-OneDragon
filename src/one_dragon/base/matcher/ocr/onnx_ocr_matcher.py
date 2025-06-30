import time

import os
from cv2.typing import MatLike
from logging import DEBUG
from typing import Callable, List, Optional

from one_dragon.base.matcher.match_result import MatchResult, MatchResultList
from one_dragon.base.matcher.ocr import ocr_utils
from one_dragon.base.matcher.ocr.ocr_match_result import OcrMatchResult
from one_dragon.base.matcher.ocr.ocr_matcher import OcrMatcher
from one_dragon.base.web.common_downloader import CommonDownloaderParam
from one_dragon.base.web.zip_downloader import ZipDownloader
from one_dragon.utils import os_utils
from one_dragon.utils import str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log


DEFAULT_OCR_MODEL_NAME: str = 'ppocrv5'
GITHUB_DOWNLOAD_URL: str = 'https://github.com/OneDragon-Anything/OneDragon-Env/releases/download'
GITEE_DOWNLOAD_URL: str = 'https://gitee.com/OneDragon-Anything/OneDragon-Env/releases/download'


def get_ocr_model_dir(ocr_model_name: str) -> str:
    return os_utils.get_path_under_work_dir('assets', 'models', 'onnx_ocr', ocr_model_name)


def get_ocr_download_url_github(ocr_model_name: str) -> str:
    return get_ocr_download_url(GITHUB_DOWNLOAD_URL, ocr_model_name)


def get_ocr_download_url_gitee(ocr_model_name: str) -> str:
    return get_ocr_download_url(GITEE_DOWNLOAD_URL, ocr_model_name)


def get_ocr_download_url(website: str, ocr_model_name: str) -> str:
    return f'{website}/{ocr_model_name}/{ocr_model_name}.zip'


def get_final_file_list(ocr_model_name: str) -> list[str]:
    """
    下载成功后 整个模型的所有文件
    :param ocr_model_name: 模型名称
    :return:
    """
    base_dir = get_ocr_model_dir(ocr_model_name)
    return [
        os.path.join(base_dir, 'det.onnx'),
        os.path.join(base_dir, 'rec.onnx'),
        os.path.join(base_dir, 'cls.onnx'),
        os.path.join(base_dir, 'ppocrv5_dict.txt'),
        os.path.join(base_dir, 'simfang.ttf'),
    ]



class OnnxOcrMatcher(OcrMatcher, ZipDownloader):
    """
    使用onnx的ocr模型 速度更快
    """

    def __init__(self, ocr_model_name: str = DEFAULT_OCR_MODEL_NAME):
        self.base_dir: str = get_ocr_model_dir(ocr_model_name)
        OcrMatcher.__init__(self)
        param = CommonDownloaderParam(
            save_file_path=self.base_dir,
            save_file_name=f'{ocr_model_name}.zip',
            github_release_download_url=get_ocr_download_url_github(ocr_model_name),
            gitee_release_download_url=get_ocr_download_url_gitee(ocr_model_name),
            mirror_chan_download_url='',
            check_existed_list=get_final_file_list(ocr_model_name)
        )
        ZipDownloader.__init__(
            self,
            param=param,
        )
        self._model = None
        self._loading: bool = False

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
        log.info('正在加载OCR模型')

        # 保证只有一个线程下载
        if self._loading:
            while self._loading:
                time.sleep(1)
            return self._model is not None
        self._loading = True

        # 先检查模型文件和下载模型
        done: bool = self.download(
            download_by_github=download_by_github,
            download_by_gitee=download_by_gitee,
            download_by_mirror_chan=download_by_mirror_chan,
            proxy_url=proxy_url,
            ghproxy_url=ghproxy_url,
            skip_if_existed=skip_if_existed,
            progress_callback=progress_callback
        )
        if not done:
            log.error('下载OCR模型失败')
            self._loading = False
            return False

        # 加载模型
        if self._model is None:
            from onnxocr.onnx_paddleocr import ONNXPaddleOcr

            try:
                self._model = ONNXPaddleOcr(
                    use_angle_cls=False, use_gpu=False,
                    det_model_dir=os.path.join(self.base_dir, 'det.onnx'),
                    rec_model_dir=os.path.join(self.base_dir, 'rec.onnx'),
                    cls_model_dir=os.path.join(self.base_dir, 'cls.onnx'),
                    rec_char_dict_path=os.path.join(self.base_dir, 'ppocrv5_dict.txt'),
                    vis_font_path=os.path.join(self.base_dir, 'simfang.ttf'),
                )
                self._loading = False
                log.info('加载OCR模型完毕')
                return True
            except Exception:
                log.error('OCR模型加载出错', exc_info=True)
                self._loading = False
                return False

        log.info('加载OCR模型完毕')
        self._loading = False
        return True

    def run_ocr_single_line(self, image: MatLike, threshold: float = 0, strict_one_line: bool = True) -> str:
        """
        单行文本识别 手动合成一行 按匹配结果从左到右 从上到下
        理论中文情况不会出现过长分行的 这里只是为了兼容英语的情况
        :param image: 图片
        :param threshold: 阈值
        :param strict_one_line: True时认为当前只有单行文本 False时依赖程序合并成一行
        :return:
        """
        if strict_one_line:
            return self._run_ocr_without_det(image, threshold)
        else:
            ocr_map: dict = self.run_ocr(image, threshold)
            tmp = ocr_utils.merge_ocr_result_to_single_line(ocr_map, join_space=False)
            return tmp

    def run_ocr(self, image: MatLike, threshold: float = 0,
                merge_line_distance: float = -1) -> dict[str, MatchResultList]:
        """
        对图片进行OCR 返回所有匹配结果
        :param image: 图片
        :param threshold: 匹配阈值
        :param merge_line_distance: 多少行距内合并结果 -1为不合并 理论中文情况不会出现过长分行的 这里只是为了兼容英语的情况
        :return: {key_word: []}
        """
        start_time = time.time()
        result_map: dict = {}
        scan_result_list: list = self._model.ocr(image, cls=False)
        if len(scan_result_list) == 0:
            log.debug('OCR结果 %s 耗时 %.2f', result_map.keys(), time.time() - start_time)
            return result_map

        scan_result = scan_result_list[0]
        for anchor in scan_result:
            anchor_position = anchor[0]
            anchor_text = anchor[1][0]
            anchor_score = anchor[1][1]
            if anchor_score < threshold:
                continue
            if anchor_text not in result_map:
                result_map[anchor_text] = MatchResultList(only_best=False)
            result_map[anchor_text].append(MatchResult(anchor_score,
                                                       anchor_position[0][0],
                                                       anchor_position[0][1],
                                                       anchor_position[1][0] - anchor_position[0][0],
                                                       anchor_position[3][1] - anchor_position[0][1],
                                                       data=anchor_text))

        if merge_line_distance != -1:
            result_map = ocr_utils.merge_ocr_result_to_multiple_line(result_map, join_space=True,
                                                                     merge_line_distance=merge_line_distance)
        log.debug('OCR结果 %s 耗时 %.2f', result_map.keys(), time.time() - start_time)
        return result_map

    def _run_ocr_without_det(self, image: MatLike, threshold: float = 0) -> str:
        """
        不使用检测模型分析图片内文字的分布
        默认传入的图片仅有文字信息
        :param image: 图片
        :param threshold: 匹配阈值
        :return: [[("text", "score"),]] 由于禁用了空格，可以直接取第一个元素
        """
        start_time = time.time()
        scan_result: list = self._model.ocr(image, det=False, cls=False)
        img_result = scan_result[0]  # 取第一张图片
        if len(img_result) > 1:
            log.debug("禁检测的OCR模型返回多个识别结果")  # 目前没有出现这种情况

        if img_result[0][1] < threshold:
            log.debug("OCR模型返回的识别结果置信度低于阈值")
            return ""
        log.debug('OCR结果 %s 耗时 %.2f', scan_result, time.time() - start_time)
        return img_result[0][0]

    def match_words(
            self,
            image: MatLike, words: List[str],
            threshold: float = 0,
            same_word: bool = False,
            ignore_case: bool = True,
            lcs_percent: float = -1,
            merge_line_distance: float = -1
    ) -> dict[str, MatchResultList]:
        """
        在图片中查找关键词 返回所有词对应的位置
        :param image: 图片
        :param words: 关键词
        :param threshold: 匹配阈值
        :param same_word: 要求整个词一样
        :param ignore_case: 忽略大小写
        :param lcs_percent: 最长公共子序列长度百分比 -1代表不使用 same_word=True时不生效
        :param merge_line_distance: 多少行距内合并结果 -1为不合并
        :return: {key_word: []}
        """
        all_match_result: dict = self.run_ocr(image, threshold, merge_line_distance=merge_line_distance)
        match_key = set()
        for k in all_match_result.keys():
            for w in words:
                ocr_result: str = k
                ocr_target = gt(w, 'ocr')
                if ignore_case:
                    ocr_result = ocr_result.lower()
                    ocr_target = ocr_target.lower()

                if same_word:
                    if ocr_result == ocr_target:
                        match_key.add(k)
                else:
                    if lcs_percent == -1:
                        if ocr_result.find(ocr_target) != -1:
                            match_key.add(k)
                    else:
                        if str_utils.find_by_lcs(ocr_target, ocr_result, percent=lcs_percent):
                            match_key.add(k)

        return {key: all_match_result[key] for key in match_key if key in all_match_result}

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
        start_time = time.time()
        ocr_result_list: list[OcrMatchResult] = []

        scan_result_list: list = self._model.ocr(image, cls=False)
        if len(scan_result_list) == 0:
            log.debug('OCR结果 [] 耗时 %.2f', time.time() - start_time)
            return ocr_result_list

        scan_result = scan_result_list[0]  # 只取第一张图片
        for anchor in scan_result:
            anchor_position = anchor[0]
            anchor_text = anchor[1][0]
            anchor_score = anchor[1][1]
            if anchor_score < threshold:
                continue

            result = OcrMatchResult(
                anchor_score,
                anchor_position[0][0],
                anchor_position[0][1],
                anchor_position[1][0] - anchor_position[0][0],
                anchor_position[3][1] - anchor_position[0][1],
                data=anchor_text)
            ocr_result_list.append(result)

        if merge_line_distance != -1:
            pass  # TODO

        if log.isEnabledFor(DEBUG):
            log.debug('OCR结果 %s 耗时 %.2f', [i.data for i in ocr_result_list], time.time() - start_time)

        return ocr_result_list


def __debug():
    ocr = OnnxOcrMatcher()
    ocr.init_model(
        download_by_github=False,
        download_by_gitee=True)

    from one_dragon.utils import debug_utils
    img = debug_utils.get_debug_image('1')
    print(ocr.run_ocr(img))


if __name__ == '__main__':
    __debug()
