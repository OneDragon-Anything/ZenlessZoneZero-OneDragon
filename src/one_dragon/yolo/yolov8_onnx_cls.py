import time

import numpy as np
from cv2.typing import MatLike
from typing import Optional, List

from one_dragon.yolo import onnx_utils
from one_dragon.yolo.onnx_model_loader import OnnxModelLoader
import cv2

class RunContext:

    def __init__(self, raw_image: MatLike, run_time: Optional[float] = None):
        """
        推理过程的上下文
        用于保存临时变量
        """
        self.run_time: float = time.time() if run_time is None else run_time
        """识别时间"""

        self.img: MatLike = raw_image
        """预测用的图片"""

        self.img_height: int = raw_image.shape[0]
        """原图的高度"""

        self.img_width: int = raw_image.shape[1]
        """原图的宽度"""

        self.conf: float = 0.9
        """检测时用的置信度阈值"""

        self.scale_height: int = 0
        """缩放后的高度"""

        self.scale_width: int = 0
        """缩放后的宽度"""


class ClassificationResult:

    def __init__(self,
                 raw_image: MatLike,
                 class_idx: int,
                 run_time: Optional[float] = None,):
        self.run_time: float = time.time() if run_time is None else run_time  # 识别时间
        self.raw_image: MatLike = raw_image  # 识别的原始图片
        self.class_idx: int = class_idx  # 分类的下标 -1代表无法识别（不满足阈值）


class Yolov8Classifier(OnnxModelLoader):

    def __init__(self,
                 model_name: str,
                 model_parent_dir_path: str,  # 默认使用本文件的目录
                 model_download_url: str,
                 gh_proxy: bool = True,
                 gh_proxy_url: Optional[str] = None,
                 personal_proxy: Optional[str] = None,
                 gpu: bool = False,
                 backup_model_name: Optional[str] = None,
                 keep_result_seconds: float = 2,
                 ):
        """
        :param model_name: 模型名称 在根目录下会有一个以模型名称创建的子文件夹
        :param model_parent_dir_path: 放置所有模型的根目录
        :param gpu: 是否启用GPU加速
        :param keep_result_seconds: 保留多长时间的识别结果
        """
        OnnxModelLoader.__init__(
            self,
            model_name=model_name,
            model_download_url=model_download_url,
            model_parent_dir_path=model_parent_dir_path,
            gh_proxy=gh_proxy,
            gh_proxy_url=gh_proxy_url,
            personal_proxy=personal_proxy,
            gpu=gpu,
            backup_model_name=backup_model_name
        )

        self.keep_result_seconds: float = keep_result_seconds  # 保留识别结果的秒数
        self.run_result_history: List[ClassificationResult] = []  # 历史识别结果

    def run(self, image: MatLike, conf: float = 0.9, run_time: Optional[float] = None) -> ClassificationResult:
        """
        对图片进行识别
        :param image: 使用 opencv 读取的图片 RGB通道
        :param conf: 置信度阈值
        :return: 识别结果
        """
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        t1 = time.time()
        context = RunContext(image, run_time)
        context.conf = conf

        input_tensor = self.prepare_input(context)
        t2 = time.time()

        outputs = self.inference(input_tensor)
        t3 = time.time()

        result = self.process_output(outputs, context)
        t4 = time.time()

        # log.info(f'识别完毕 预处理耗时 {t2 - t1:.3f}s, 推理耗时 {t3 - t2:.3f}s, 后处理耗时 {t4 - t3:.3f}s')

        self.record_result(context, result)
        return result

    def prepare_input(self, context: RunContext) -> np.ndarray:
        """
        推理前的预处理
        """
        input_tensor, scale_height, scale_width = onnx_utils.scale_input_image_u(context.img, self.onnx_input_width, self.onnx_input_height)
        context.scale_height = scale_height
        context.scale_width = scale_width
        return input_tensor

    def inference(self, input_tensor: np.ndarray):
        """
        图片输入到模型中进行推理
        :param input_tensor: 输入模型的图片 RGB通道
        :return: onnx模型推理得到的结果
        """
        outputs = self.session.run(self.output_names, {self.input_names[0]: input_tensor})
        return outputs

    def process_output(self, output, context: RunContext) -> ClassificationResult:
        """
        :param output: 推理结果
        :param context: 上下文
        :return: 最终得到的识别结果
        """
        scores = np.squeeze(output[0]).T
        idx = np.argmax(scores)
        conf = scores[idx]
        result = ClassificationResult(
            raw_image=context.img,
            run_time=context.run_time,
            class_idx=idx if conf >= context.conf else -1
        )
        return result

    def record_result(self, context: RunContext, result: ClassificationResult) -> None:
        """
        记录本帧识别结果
        :param context: 识别上下文
        :param result: 识别结果
        :return: 组合结果
        """
        self.run_result_history.append(result)
        self.run_result_history = [i for i in self.run_result_history
                                   if context.run_time - i.run_time > self.keep_result_seconds]

    @property
    def last_run_result(self) -> Optional[ClassificationResult]:
        if len(self.run_result_history) > 0:
            return self.run_result_history[len(self.run_result_history) - 1]
        else:
            return None
