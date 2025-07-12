# coding: utf-8
from typing import Dict, Any
import cv2
from one_dragon.base.cv_process.cv_step import CvStep, CvPipelineContext


class CvStepFilterByAspectRatio(CvStep):

    def __init__(self):
        super().__init__('按长宽比过滤')

    def get_params(self) -> Dict[str, Any]:
        return {
            'min_ratio': {'type': 'float', 'default': 0.0, 'range': (0.0, 100.0), 'label': '最小长宽比', 'tooltip': '外接矩形的最小长宽比 (宽/高)。低于此值的轮廓将被过滤。'},
            'max_ratio': {'type': 'float', 'default': 10.0, 'range': (0.0, 100.0), 'label': '最大长宽比', 'tooltip': '外接矩形的最大长宽比 (宽/高)。高于此值的轮廓将被过滤。'},
            'draw_contours': {'type': 'bool', 'default': True, 'label': '绘制保留轮廓', 'tooltip': '是否在调试图像上画出经过长宽比过滤后保留下来的轮廓。'},
        }

    def get_description(self) -> str:
        return "根据轮廓的长宽比进行过滤。长宽比计算方式为 `外接矩形宽度 / 高度`。"

    def _execute(self, context: CvPipelineContext, min_ratio: float = 0.0, max_ratio: float = 10.0, draw_contours: bool = True, **kwargs):
        if not context.contours:
            context.analysis_results.append("没有轮廓可供过滤")
            return

        filtered_contours = []
        for i, contour in enumerate(context.contours):
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / h if h > 0 else 0
            if min_ratio <= aspect_ratio <= max_ratio:
                filtered_contours.append(contour)
                context.analysis_results.append(f"轮廓 {i} 长宽比: {aspect_ratio:.2f} (保留)")
            else:
                context.analysis_results.append(f"轮廓 {i} 长宽比: {aspect_ratio:.2f} (过滤)")

        context.contours = filtered_contours
        if not filtered_contours:
            context.success = False
        context.analysis_results.append(f"按长宽比过滤后剩余 {len(filtered_contours)} 个轮廓")
        if context.debug_mode and draw_contours:
            # 重新绘制轮廓
            display_with_contours = context.display_image.copy()
            cv2.drawContours(display_with_contours, filtered_contours, -1, (0, 255, 0), 2)
            context.display_image = display_with_contours