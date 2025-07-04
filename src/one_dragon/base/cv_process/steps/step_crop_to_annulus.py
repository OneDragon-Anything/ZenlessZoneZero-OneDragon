# coding: utf-8
from typing import Dict, Any
import cv2
import numpy as np
from one_dragon.base.cv_process.cv_step import CvStep, CvPipelineContext


class CvStepCropToAnnulus(CvStep):

    def __init__(self):
        super().__init__('环形裁剪')

    def get_params(self) -> Dict[str, Any]:
        return {
            'center_x_offset': {'type': 'int', 'default': 0, 'label': '中心X偏移', 'tooltip': '在图像中心基础上，进行像素级别的水平偏移'},
            'center_y_offset': {'type': 'int', 'default': 0, 'label': '中心Y偏移', 'tooltip': '在图像中心基础上，进行像素级别的垂直偏移'},
            'outer_radius_reduction': {'type': 'int', 'default': 0, 'label': '外圆半径缩减', 'tooltip': '将自动计算的最大内切圆半径减去指定像素值'},
            'inner_radius': {'type': 'int', 'default': 20, 'label': '内圆半径(像素)', 'tooltip': '环形内圆的半径，单位为像素'},
            'notch_x': {'type': 'int', 'default': 0, 'label': '缺口中心X', 'tooltip': '缺口圆心的X坐标，相对于图像左上角'},
            'notch_y': {'type': 'int', 'default': 0, 'label': '缺口中心Y', 'tooltip': '缺口圆心的Y坐标，相对于图像左上角'},
            'notch_radius': {'type': 'int', 'default': 0, 'label': '缺口半径', 'tooltip': '缺口圆的半径，为0则不创建缺口'},
        }

    def get_description(self) -> str:
        return "将矩形图像裁剪为一个环形，可挖去缺口，并自动裁剪移除黑边。"

    def _execute(self, context: CvPipelineContext,
                 center_x_offset: int = 0, center_y_offset: int = 0,
                 outer_radius_reduction: int = 0, inner_radius: int = 20,
                 notch_x: int = 0, notch_y: int = 0, notch_radius: int = 0,
                 **kwargs):
        h, w = context.display_image.shape[:2]
        if h == 0 or w == 0:
            context.error_str = "错误: 图像尺寸为空，无法进行环形裁剪"
            context.success = False
            return

        center = ((w // 2) + center_x_offset, (h // 2) + center_y_offset)
        outer_radius = max(0, (min(h, w) // 2) - outer_radius_reduction)
        inner_radius = max(0, inner_radius)  # 确保内圆半径不为负
        notch_radius = max(0, notch_radius)

        # 确保内圆半径不大于外圆半径
        if inner_radius > outer_radius:
            inner_radius = outer_radius

        # 1. 创建遮罩
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(mask, center, outer_radius, 255, -1)
        cv2.circle(mask, center, inner_radius, 0, -1)

        # 2. 创建缺口
        if notch_radius > 0:
            cv2.circle(mask, (notch_x, notch_y), notch_radius, 0, -1)
        
        # 3. 应用遮罩
        masked_image = cv2.bitwise_and(context.display_image, context.display_image, mask=mask)

        # 4. 计算边界框并裁剪，移除黑边
        x1 = max(0, center[0] - outer_radius)
        y1 = max(0, center[1] - outer_radius)
        x2 = min(w, center[0] + outer_radius)
        y2 = min(h, center[1] + outer_radius)

        context.display_image = masked_image[y1:y2, x1:x2]
        context.mask_image = mask[y1:y2, x1:x2]

        context.analysis_results.append(f"已执行环形裁剪，中心: {center} 外圆半径: {outer_radius}, 内圆半径: {inner_radius}")
        if notch_radius > 0:
            context.analysis_results.append(f"已创建缺口，中心:({notch_x},{notch_y}) 半径:{notch_radius}")
        context.analysis_results.append(f"已裁剪区域，尺寸: {context.display_image.shape[1]}x{context.display_image.shape[0]}")