from typing import Optional, Union, List, Tuple, ClassVar

from one_dragon.utils import yolo_config_utils
from one_dragon.yolo.detect_utils import DetectFrameResult, DetectObjectResult
from one_dragon.yolo.yolo_utils import ZZZ_MODEL_DOWNLOAD_URL
from one_dragon.yolo.yolov8_onnx_det import Yolov8Detector


class LostVoidDetector(Yolov8Detector):

    CLASS_INTERACT: ClassVar[str] = '0000-感叹号'
    CLASS_DISTANCE: ClassVar[str] = '0001-距离'
    CLASS_ENTRY: ClassVar[str] = 'xxxx-入口'

    def __init__(self,
                 model_name: str,
                 backup_model_name: str,
                 gh_proxy: bool = True,
                 gh_proxy_url: Optional[str] = None,
                 personal_proxy: Optional[str] = None,
                 gpu: bool = False,
                 keep_result_seconds: float = 2
                 ):
        """
        崩铁用的YOLO模型 参考自 https://github.com/ibaiGorordo/ONNX-YOLOv8-Object-Detection
        :param model_name: 模型名称 在根目录下会有一个以模型名称创建的子文件夹
        :param backup_model_name: 放置所有模型的根目录
        :param gpu: 是否启用GPU运算
        :param keep_result_seconds: 保留多长时间的识别结果
        """
        Yolov8Detector.__init__(
            self,
            model_name=model_name,
            backup_model_name=backup_model_name,
            model_parent_dir_path=yolo_config_utils.get_model_category_dir('lost_void_det'),
            model_download_url=ZZZ_MODEL_DOWNLOAD_URL,
            gh_proxy=gh_proxy,
            gh_proxy_url=gh_proxy_url,
            personal_proxy=personal_proxy,
            gpu=gpu,
            keep_result_seconds=keep_result_seconds
        )

    def is_frame_with_all(self, frame_result: Optional[DetectFrameResult] = None) -> Tuple[bool, bool, bool]:
        """
        判断某帧的识别结果里 是否存在 感叹号、距离、入口
        @param frame_result: 帧识别结果 不传入时使用最后一帧
        @return: 三个bool 是否存在 感叹号、距离、入口
        """
        if frame_result is None:
            frame_result = self.last_run_result
        if frame_result is None:
            return False, False, False

        with_interact = False
        with_distance = False
        with_entry = False
        for result in frame_result.results:
            if result.detect_class.class_name == LostVoidDetector.CLASS_INTERACT:
                with_interact = True
            elif result.detect_class.class_name == LostVoidDetector.CLASS_DISTANCE:
                with_distance = True
            else:
                with_entry = True

        return with_interact, with_distance, with_entry

    def is_frame_with(self, frame_result: Optional[DetectFrameResult] = None,
                      target_type: Union[List[str], str] = None) -> bool:
        """
        判断某帧的识别结果里 是否存在特定的类别
        @param frame_result: 帧识别结果 不传入时使用最后一帧
        @param target_type: 特定的类别 可一个或多个
        @return: 是否存在
        """
        if frame_result is None:
            frame_result = self.last_run_result
        if frame_result is None:
            return False
        target_type_set = set()
        if isinstance(target_type, str):
            target_type_set.add(target_type)
        elif isinstance(target_type, list):
            target_type_set.update(target_type)
        for result in frame_result.results:
            if result.detect_class.class_name in target_type:
                return True
        return False

    def get_result_by_x(self, frame_result: Optional[DetectFrameResult] = None,
                        target_type: str = None, by_max_x: bool = True) -> Optional[DetectObjectResult]:
        """
        获取某帧的识别结果里 特定类别的最右方结果
        @param frame_result: 帧识别结果 不传入时使用最后一帧
        @param target_type: 特定的类别
        @param by_max_x: 选择最大的x
        @return: 最右方的结果
        """
        if frame_result is None:
            frame_result = self.last_run_result
        if frame_result is None:
            return None
        target: Optional[DetectObjectResult] = None
        for result in frame_result.results:
            if result.detect_class.class_name == target_type:
                if (target is None
                        or (by_max_x and result.center[0] > target.center[0])
                        or (not by_max_x and result.center[0] < target.center[0])
                ):
                    target = result

        return target


def __debug():
    from zzz_od.context.zzz_context import ZContext
    ctx = ZContext()
    detector = LostVoidDetector(model_name=ctx.model_config.lost_void_det,
                                backup_model_name=ctx.model_config.lost_void_det_backup)

    from one_dragon.utils import debug_utils
    screen = debug_utils.get_debug_image('_1736869628156')
    frame_result = detector.run(screen)

    from one_dragon.yolo import detect_utils
    result_image = detect_utils.draw_detections(frame_result)
    from one_dragon.utils import cv2_utils
    cv2_utils.show_image(result_image, win_name='lost_void_detector', wait=0)
    import cv2
    cv2.destroyAllWindows()
    print(detector.is_frame_with(frame_result, '感叹号'))


if __name__ == '__main__':
    __debug()