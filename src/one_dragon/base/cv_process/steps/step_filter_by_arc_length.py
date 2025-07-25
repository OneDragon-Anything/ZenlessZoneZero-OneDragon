# coding: utf-8
from typing import Dict, Any
import cv2
from one_dragon.base.cv_process.cv_step import CvStep, CvPipelineContext


class CvStepFilterByArcLength(CvStep):

    def __init__(self):
        super().__init__('按周长过滤')

    def get_params(self) -> Dict[str, Any]:
        return {
            'closed': {'type': 'bool', 'default': True, 'label': '轮廓是否闭合', 'tooltip': '计算周长时是否将轮廓视为闭合曲线。'},
            'min_length': {'type': 'int', 'default': 0, 'range': (0, 10000), 'label': '最小周长', 'tooltip': '轮廓的最小周长。小于此值的轮廓将被过滤。'},
            'max_length': {'type': 'int', 'default': 1000, 'range': (0, 10000), 'label': '最大周长', 'tooltip': '轮廓的最大周长。大于此值的轮廓将被过滤。'},
            'draw_contours': {'type': 'bool', 'default': True, 'label': '绘制保留轮廓', 'tooltip': '是否在调试图像上画出经过周长过滤后保留下来的轮廓。'},
        }

    def get_description(self) -> str:
        return "根据轮廓的周长进行过滤。`closed`指定轮廓是否闭合。只保留周长在 `min_length` 和 `max_length` 之间的轮廓。"

    def _execute(self, context: CvPipelineContext, closed: bool = True, min_length: int = 0, max_length: int = 1000, draw_contours: bool = True, **kwargs):
        if not context.contours:
            context.analysis_results.append("没有轮廓可供过滤")
            return
        
        filtered_contours = []
        for i, contour in enumerate(context.contours):
            length = cv2.arcLength(contour, closed)
            if min_length <= length <= max_length:
                filtered_contours.append(contour)
                context.analysis_results.append(f"轮廓 {i} 周长: {length:.2f} (保留)")
            else:
                context.analysis_results.append(f"轮廓 {i} 周长: {length:.2f} (过滤)")

        context.contours = filtered_contours
        if not filtered_contours:
            context.success = False
        context.analysis_results.append(f"按周长过滤后剩余 {len(filtered_contours)} 个轮廓")
        if context.debug_mode and draw_contours:
            # 重新绘制轮廓
            display_with_contours = context.display_image.copy()
            cv2.drawContours(display_with_contours, filtered_contours, -1, (0, 255, 0), 2)
            context.display_image = display_with_contours