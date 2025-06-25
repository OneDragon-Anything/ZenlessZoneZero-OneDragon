# coding: utf-8
from typing import Dict, Any
import cv2
from one_dragon.base.cv_process.cv_step import CvStep, CvPipelineContext
from one_dragon.utils import cv2_utils


class CvStepFilterByHSV(CvStep):

    def __init__(self):
        super().__init__('HSV 范围过滤')

    def get_params(self) -> Dict[str, Any]:
        return {
            'hsv_color': {'type': 'tuple_int', 'default': (0, 0, 0), 'range': [(0, 179), (0, 255), (0, 255)], 'label': '目标颜色 (HSV)', 'tooltip': '要匹配的中心颜色 (H, S, V)。H范围0-179，S和V范围0-255。'},
            'hsv_diff': {'type': 'tuple_int', 'default': (10, 255, 255), 'range': [(0, 90), (0, 255), (0, 255)], 'label': '容差范围 (HSV)', 'tooltip': 'HSV三个通道的容差范围。最终范围是 [中心颜色 - 容差, 中心颜色 + 容差]。'},
        }

    def get_description(self) -> str:
        return "根据 HSV 颜色过滤图像。 `hsv_color` 参数指定要匹配的中心颜色，`hsv_diff` 参数指定 H, S, V 三个通道的容差范围。"

    def _execute(self, context: CvPipelineContext, hsv_color: tuple = (0, 0, 0), hsv_diff: tuple = (10, 255, 255), **kwargs):
        mask = cv2_utils.filter_by_color(context.display_image, mode='hsv', hsv_color=hsv_color, hsv_diff=hsv_diff)
        context.mask_image = mask
        context.display_image = cv2.bitwise_and(context.display_image, context.display_image, mask=mask)