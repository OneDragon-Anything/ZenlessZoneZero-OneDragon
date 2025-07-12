# coding: utf-8
from typing import Dict, Any
import cv2
from one_dragon.base.cv_process.cv_step import CvStep, CvPipelineContext
from one_dragon.utils import cv2_utils


class CvStepFilterByRGB(CvStep):

    def __init__(self):
        super().__init__('RGB 范围过滤')

    def get_params(self) -> Dict[str, Any]:
        return {
            'lower_rgb': {'type': 'tuple_int', 'default': (0, 0, 0), 'range': (0, 255), 'label': 'RGB下限', 'tooltip': '过滤颜色的RGB下限 (R, G, B)。所有通道值都低于此值的像素将被过滤。'},
            'upper_rgb': {'type': 'tuple_int', 'default': (255, 255, 255), 'range': (0, 255), 'label': 'RGB上限', 'tooltip': '过滤颜色的RGB上限 (R, G, B)。所有通道值都高于此值的像素将被过滤。'},
        }

    def get_description(self) -> str:
        return "根据 RGB 范围过滤图像，生成一个二值遮罩。 `lower_rgb` 和 `upper_rgb` 分别是 RGB 颜色的下界和上界。"

    def _execute(self, context: CvPipelineContext, lower_rgb: tuple = (0, 0, 0), upper_rgb: tuple = (255, 255, 255), **kwargs):
        mask = cv2_utils.filter_by_color(context.display_image, mode='rgb', lower_rgb=lower_rgb, upper_rgb=upper_rgb)
        context.mask_image = mask
        context.display_image = cv2.bitwise_and(context.display_image, context.display_image, mask=mask)