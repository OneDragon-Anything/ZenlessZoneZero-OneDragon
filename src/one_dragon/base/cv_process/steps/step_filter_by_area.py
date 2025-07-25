# coding: utf-8
from typing import Dict, Any
import cv2
from one_dragon.base.cv_process.cv_step import CvStep, CvPipelineContext


class CvStepFilterByArea(CvStep):

    def __init__(self):
        super().__init__('按面积过滤')

    def get_params(self) -> Dict[str, Any]:
        return {
            'min_area': {'type': 'int', 'default': 0, 'range': (0, 100000), 'label': '最小面积', 'tooltip': '轮廓的最小像素面积。小于此值的轮廓将被过滤。'},
            'max_area': {'type': 'int', 'default': 10000, 'range': (0, 100000), 'label': '最大面积', 'tooltip': '轮廓的最大像素面积。大于此值的轮廓将被过滤。'},
            'draw_contours': {'type': 'bool', 'default': True, 'label': '绘制保留轮廓', 'tooltip': '是否在调试图像上画出经过面积过滤后保留下来的轮廓。'},
        }

    def get_description(self) -> str:
        return "根据轮廓的面积进行过滤。只保留面积在 `min_area` 和 `max_area` 之间的轮廓。"

    def _execute(self, context: CvPipelineContext, min_area: int = 0, max_area: int = 10000, draw_contours: bool = True, **kwargs):
        if not context.contours:
            context.analysis_results.append("没有轮廓可供过滤")
            return

        filtered_contours = []
        for i, contour in enumerate(context.contours):
            area = cv2.contourArea(contour)
            if min_area <= area <= max_area:
                filtered_contours.append(contour)
                context.analysis_results.append(f"轮廓 {i} 面积: {area} (保留)")
            else:
                context.analysis_results.append(f"轮廓 {i} 面积: {area} (过滤)")
        
        context.contours = filtered_contours
        if not filtered_contours:
            context.success = False
        context.analysis_results.append(f"按面积过滤后剩余 {len(filtered_contours)} 个轮廓")
        if context.debug_mode and draw_contours:
            # 重新绘制轮廓
            display_with_contours = context.display_image.copy()
            cv2.drawContours(display_with_contours, filtered_contours, -1, (0, 255, 0), 2)
            context.display_image = display_with_contours