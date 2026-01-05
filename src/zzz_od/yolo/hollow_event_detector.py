from typing import Optional

from one_dragon.utils import yolo_config_utils
from one_dragon.yolo.yolo_utils import ZZZ_MODEL_DOWNLOAD_URL
from one_dragon.yolo.yolov8_onnx_det import Yolov8Detector


class HollowEventDetector(Yolov8Detector):

    def __init__(self,
                 model_name: str = 'yolov8s-736-hollow-zero-event-0126',
                 backup_model_name: str = 'yolov8s-736-hollow-zero-event-0126',
                 gh_proxy: bool = True,
                 gh_proxy_url: Optional[str] = None,
                 personal_proxy: Optional[str] = None,
                 gpu: bool = False,
                 keep_result_seconds: float = 2
                 ):
        """
        崩铁用的YOLO模型 参考自 https://github.com/ibaiGorordo/ONNX-YOLOv8-Object-Detection
        :param model_name: 模型名称 在根目录下会有一个以模型名称创建的子文件夹
        :param model_parent_dir_path: 放置所有模型的根目录
        :param gpu: 是否启用GPU运算
        :param keep_result_seconds: 保留多长时间的识别结果
        """
        Yolov8Detector.__init__(
            self,
            model_name=model_name,
            backup_model_name=backup_model_name,
            model_parent_dir_path=yolo_config_utils.get_model_category_dir('hollow_zero_event'),
            model_download_url=ZZZ_MODEL_DOWNLOAD_URL,
            gh_proxy=gh_proxy,
            gh_proxy_url=gh_proxy_url,
            personal_proxy=personal_proxy,
            gpu=gpu,
            keep_result_seconds=keep_result_seconds
        )
