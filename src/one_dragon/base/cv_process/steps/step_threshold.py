# coding: utf-8
from typing import Dict, Any
import cv2
from one_dragon.base.cv_process.cv_step import CvStep, CvPipelineContext


class CvStepThreshold(CvStep):

    def __init__(self):
        self.method_map = {
            'BINARY': cv2.THRESH_BINARY,
            'OTSU': cv2.THRESH_OTSU,
            'ADAPTIVE_GAUSSIAN': cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            'ADAPTIVE_MEAN': cv2.ADAPTIVE_THRESH_MEAN_C,
        }
        super().__init__('二值化')

    def get_params(self) -> Dict[str, Any]:
        return {
            'method': {'type': 'enum', 'default': 'OTSU', 'options': list(self.method_map.keys()), 'label': '二值化算法', 'tooltip': '选择将灰度图转为黑白图的算法。OTSU和自适应方法能自动寻找阈值。'},
            'threshold_value': {'type': 'int', 'default': 127, 'range': (0, 255), 'label': '固定阈值', 'tooltip': '当算法为BINARY时生效。高于此值的像素变为白色，低于则为黑色。'},
            'adaptive_block_size': {'type': 'int', 'default': 11, 'range': (3, 99), 'label': '自适应-块大小', 'tooltip': '用于自适应阈值的邻域大小，必须是奇数。'},
            'adaptive_c': {'type': 'int', 'default': 2, 'range': (-50, 50), 'label': '自适应-常量C', 'tooltip': '从均值或加权均值中减去的常数，用于微调自适应阈值。'},
        }

    def get_description(self) -> str:
        return "将灰度图像转换为黑白二值图像，这是轮廓分析的前提。支持多种算法以适应不同光照场景。"

    def _execute(self, context: CvPipelineContext, method: str = 'OTSU', threshold_value: int = 127, adaptive_block_size: int = 11, adaptive_c: int = 2, **kwargs):
        # 确保在灰度图上操作
        if context.mask_image is None or len(context.mask_image.shape) != 2:
            context.analysis_results.append("错误: 请先执行灰度化步骤")
            return

        gray_image = context.mask_image

        if adaptive_block_size % 2 == 0:
            adaptive_block_size += 1 # 必须为奇数
            context.analysis_results.append(f"警告: 自适应块大小已调整为奇数 {adaptive_block_size}")

        thresh_image = None
        if method in ['ADAPTIVE_GAUSSIAN', 'ADAPTIVE_MEAN']:
            cv2_method = self.method_map.get(method)
            thresh_image = cv2.adaptiveThreshold(gray_image, 255, cv2_method,
                                                 cv2.THRESH_BINARY, adaptive_block_size, adaptive_c)
            context.analysis_results.append(f"已应用自适应二值化 (方法: {method})")
        elif method == 'OTSU':
            _, thresh_image = cv2.threshold(gray_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            context.analysis_results.append("已应用OTSU二值化")
        else: # BINARY
            _, thresh_image = cv2.threshold(gray_image, threshold_value, 255, cv2.THRESH_BINARY)
            context.analysis_results.append(f"已应用全局二值化 (阈值: {threshold_value})")

        context.mask_image = thresh_image
        context.display_image = cv2.cvtColor(thresh_image, cv2.COLOR_GRAY2RGB)