# coding: utf-8
from typing import Dict, Any
import cv2
from one_dragon.base.cv_process.cv_step import CvStep, CvPipelineContext


class CvFindContoursStep(CvStep):

    def __init__(self):
        self.mode_map = {
            'EXTERNAL': cv2.RETR_EXTERNAL,
            'LIST': cv2.RETR_LIST,
            'CCOMP': cv2.RETR_CCOMP,
            'TREE': cv2.RETR_TREE,
        }
        self.method_map = {
            'NONE': cv2.CHAIN_APPROX_NONE,
            'SIMPLE': cv2.CHAIN_APPROX_SIMPLE,
        }
        super().__init__('查找轮廓')

    def get_description(self) -> str:
        return "在二值图像中查找轮廓。`mode` 是轮廓检索模式，`method` 是轮廓逼近方法。`draw_contours` 决定是否在图上画出轮廓。"

    def get_params(self) -> Dict[str, Any]:
        return {
            'mode': {'type': 'enum', 'default': 'EXTERNAL', 'options': list(self.mode_map.keys()), 'label': '轮廓检索模式', 'tooltip': 'EXTERNAL:只找最外层轮廓。LIST:查找所有轮廓，不建立层次结构。TREE:建立完整层次结构。'},
            'method': {'type': 'enum', 'default': 'SIMPLE', 'options': list(self.method_map.keys()), 'label': '轮廓逼近方法', 'tooltip': 'SIMPLE:压缩水平、垂直和对角线段，只保留端点。NONE:存储所有轮廓点。'},
            'draw_contours': {'type': 'bool', 'default': True, 'label': '绘制轮廓', 'tooltip': '是否在调试图像上用绿色线条画出找到的轮廓。'},
        }

    def _execute(self, context: CvPipelineContext, mode: str = 'EXTERNAL', method: str = 'SIMPLE', draw_contours: bool = True, **_kwargs):
        if context.mask_image is None:
            return

        # 【防卡死措施】：检查输入图像的噪点比例
        height, width = context.mask_image.shape
        total_pixels = height * width
        if total_pixels == 0:
            context.error_str = "错误：输入图像尺寸为0"
            context.success = False
            return

        cv2_mode = self.mode_map.get(mode)
        cv2_method = self.method_map.get(method)
        if cv2_mode is None or cv2_method is None:
            return

        contours, _ = cv2.findContours(context.mask_image, cv2_mode, cv2_method)
        context.contours = contours

        if not contours:
            context.success = False

        context.analysis_results.append(f"找到 {len(contours)} 个轮廓")

        if context.debug_mode and draw_contours:
            # 在一个新图像上绘制轮廓，以免影响下一步的处理
            display_with_contours = context.display_image.copy()
            cv2.drawContours(display_with_contours, contours, -1, (0, 255, 0), 2)
            context.display_image = display_with_contours
