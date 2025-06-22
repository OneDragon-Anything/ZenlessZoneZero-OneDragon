# coding: utf-8
from typing import Dict, Any
import cv2
import numpy as np
from one_dragon.base.cv_process.cv_step import CvStep, CvPipelineContext


class CvDilateStep(CvStep):

    def __init__(self):
        super().__init__('膨胀')

    def get_params(self) -> Dict[str, Any]:
        return {
            'kernel_size': {'type': 'int', 'default': 3, 'range': (1, 21), 'label': '膨胀核大小', 'tooltip': '膨胀操作的核大小，奇数。值越大，膨胀效果（连接区域）越强。'},
            'iterations': {'type': 'int', 'default': 1, 'range': (1, 10), 'label': '迭代次数', 'tooltip': '膨胀操作的执行次数。'},
        }

    def get_description(self) -> str:
        return "膨胀操作可以连接断开的区域。 `kernel_size` 是膨胀核的大小，越大膨胀效果越强。`iterations` 是迭代次数。"

    def _execute(self, context: CvPipelineContext, kernel_size: int = 3, iterations: int = 1, **kwargs):
        if context.mask_image is None:
            return
        kernel = np.ones((kernel_size, kernel_size), np.uint8)
        dilated_mask = cv2.dilate(context.mask_image, kernel, iterations=iterations)
        context.mask_image = dilated_mask
        context.display_image = cv2.bitwise_and(context.display_image, context.display_image, mask=dilated_mask)