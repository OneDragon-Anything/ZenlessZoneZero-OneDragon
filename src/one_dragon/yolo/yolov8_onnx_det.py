import time

import csv
import numpy as np
import os
from cv2.typing import MatLike
from typing import Optional, List

from one_dragon.yolo import onnx_utils
from one_dragon.yolo.detect_utils import DetectFrameResult, DetectClass, DetectContext, DetectObjectResult, xywh2xyxy, \
    multiclass_nms
from one_dragon.yolo.onnx_model_loader import OnnxModelLoader


class Yolov8Detector(OnnxModelLoader):

    def __init__(self,
                 model_name: str,
                 model_parent_dir_path: str,
                 model_download_url: str,
                 gh_proxy: bool = True,
                 gh_proxy_url: Optional[str] = None,
                 personal_proxy: Optional[str] = None,
                 gpu: bool = False,
                 backup_model_name: Optional[str] = None,
                 keep_result_seconds: float = 2
                 ):
        """
        yolov8 detect 导出 onnx 后使用
        参考自 https://github.com/ibaiGorordo/ONNX-YOLOv8-Object-Detection
        :param model_name: 模型名称 在根目录下会有一个以模型名称创建的子文件夹
        :param backup_model_name: 备用模型名称 通常是上一个版本的模型 在新版本模型无法下载时兜底使用
        :param model_parent_dir_path: 放置所有模型的根目录
        :param gpu: 是否启用GPU运算
        :param keep_result_seconds: 保留多长时间的识别结果
        """
        OnnxModelLoader.__init__(
            self,
            model_name=model_name,
            model_parent_dir_path=model_parent_dir_path,
            model_download_url=model_download_url,
            gh_proxy=gh_proxy,
            gh_proxy_url=gh_proxy_url,
            personal_proxy=personal_proxy,
            gpu=gpu,
            backup_model_name=backup_model_name
        )

        self.keep_result_seconds: float = keep_result_seconds  # 保留识别结果的秒数
        self.run_result_history: List[DetectFrameResult] = []  # 历史识别结果

        self.idx_2_class: dict[int, DetectClass] = {}  # 分类
        self.class_2_idx: dict[str, int] = {}
        self.category_2_idx: dict[str, List[int]] = {}
        self._load_detect_classes(self.model_dir_path)

    def run(
        self,
        image: MatLike,
        conf: float = 0.6,
        iou: float = 0.5,
        run_time: Optional[float] = None,
        label_list: Optional[List[str]] = None,
        category_list: Optional[List[str]] = None,
    ) -> DetectFrameResult:
        """
        对图片进行识别

        Args:
            image: 图片 [h, w, c] rgb通道
            conf: 置信度阈值
            iou: iou阈值
            run_time: 识别时间
            label_list: 限定识别的标签
            category_list: 限定识别的标签分类

        Returns:
            DetectFrameResult: 识别结果
        """
        t1 = time.time()
        context = DetectContext(image, run_time)
        context.conf = conf
        context.iou = iou
        context.label_list = label_list
        context.category_list = category_list

        input_tensor = self.prepare_input(context)
        t2 = time.time()

        outputs = self.inference(input_tensor)
        t3 = time.time()

        results = self.process_output(outputs, context)
        t4 = time.time()

        # log.info(f'识别完毕 得到结果 {len(results)}个。预处理耗时 {t2 - t1:.3f}s, 推理耗时 {t3 - t2:.3f}s, 后处理耗时 {t4 - t3:.3f}s')

        return self.record_result(context, results)

    def prepare_input(self, context: DetectContext) -> np.ndarray:
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

    def process_output(self, output, context: DetectContext) -> List[DetectObjectResult]:
        """
        :param output: 推理结果
        :param context: 上下文
        :return: 最终得到的识别结果
        """
        predictions = np.squeeze(output[0]).T

        keep = np.ones(shape=(predictions.shape[1]), dtype=bool)

        if context.label_list is not None or context.category_list is not None:
            keep[4:] = False  # 前4位是坐标 先把所有标签都设置为False
            if context.label_list is not None:
                for label in context.label_list:
                    idx = self.class_2_idx.get(label)
                    if idx is not None:
                        keep[idx + 4] = True

            if context.category_list is not None:
                for category in context.category_list:
                    for idx in self.category_2_idx.get(category, []):
                        keep[idx + 4] = True

        predictions[:, keep == False] = 0

        # 按置信度阈值进行基本的过滤
        scores = np.max(predictions[:, 4:], axis=1)
        predictions = predictions[scores > context.conf, :]
        scores = scores[scores > context.conf]

        results: List[DetectObjectResult] = []
        if len(scores) == 0:
            return results

        # 选择置信度最高的类别
        class_ids = np.argmax(predictions[:, 4:], axis=1)

        # 提取Bounding box
        boxes = predictions[:, :4]  # 原始推理结果 xywh
        scale_shape = np.array([context.scale_width, context.scale_height, context.scale_width, context.scale_height])  # 缩放后图片的大小
        boxes = np.divide(boxes, scale_shape, dtype=np.float32)  # 转化到 0~1
        boxes *= np.array([context.img_width, context.img_height, context.img_width, context.img_height])  # 恢复到原图的坐标
        boxes = xywh2xyxy(boxes)  # 转化成 xyxy

        # 进行NMS 获取最后的结果
        indices = multiclass_nms(boxes, scores, class_ids, context.iou)

        for idx in indices:
            result = DetectObjectResult(rect=boxes[idx].tolist(),
                                        score=float(scores[idx]),
                                        detect_class=self.idx_2_class[int(class_ids[idx])]
                                        )
            results.append(result)

        return results

    def record_result(self, context: DetectContext, results: List[DetectObjectResult]) -> DetectFrameResult:
        """
        记录本帧识别结果
        :param context: 识别上下文
        :param results: 识别结果
        :return: 组合结果
        """
        new_frame = DetectFrameResult(
            raw_image=context.img,
            results=results,
            run_time=context.run_time
        )
        self.run_result_history.append(new_frame)
        self.run_result_history = [i for i in self.run_result_history
                                   if context.run_time - i.run_time <= self.keep_result_seconds]

        return new_frame

    @property
    def last_run_result(self) -> Optional[DetectFrameResult]:
        if len(self.run_result_history) > 0:
            return self.run_result_history[len(self.run_result_history) - 1]
        else:
            return None

    def _load_detect_classes(self, model_dir_path: str):
        """
        加载分类
        :param model_dir_path: model_dir_path: str
        :return:
        """
        csv_path = os.path.join(model_dir_path, 'labels.csv')
        with open(csv_path, mode='r', encoding='utf-8') as file:
            csv_reader = csv.reader(file)
            for row in csv_reader:
                if row[0] == 'idx':
                    continue
                c = DetectClass(int(row[0]), row[1], category=None if len(row) < 3 else row[2])
                self.idx_2_class[c.class_id] = c
                self.class_2_idx[c.class_name] = c.class_id

                if c.class_category not in self.category_2_idx:
                    self.category_2_idx[c.class_category] = []
                self.category_2_idx[c.class_category].append(c.class_id)
