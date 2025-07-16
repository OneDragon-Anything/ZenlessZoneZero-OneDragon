# coding: utf-8
from typing import Dict, Any
import cv2
from one_dragon.base.cv_process.cv_step import CvStep, CvPipelineContext


class CvStepFilterByRadius(CvStep):

    def __init__(self):
        super().__init__('按半径过滤')

    def get_params(self) -> Dict[str, Any]:
        return {
            'min_radius': {'type': 'int', 'default': 0, 'range': (0, 1000), 'label': '最小半径', 'tooltip': '轮廓的最小外接圆半径。小于此值的轮廓将被过滤。'},
            'max_radius': {'type': 'int', 'default': 100, 'range': (0, 1000), 'label': '最大半径', 'tooltip': '轮廓的最小外接圆半径。大于此值的轮廓将被过滤。'},
            'draw_circle': {'type': 'bool', 'default': True, 'label': '绘制外接圆', 'tooltip': '是否在调试图像上画出保留轮廓的最小外接圆。'},
        }

    def get_description(self) -> str:
        return "根据轮廓的最小外接圆半径进行过滤。`draw_circle`决定是否画出外接圆。只保留半径在 `min_radius` 和 `max_radius` 之间的轮廓。"

    def _execute(self, context: CvPipelineContext, min_radius: int = 0, max_radius: int = 100, draw_circle: bool = True, **kwargs):
        if not context.contours:
            context.analysis_results.append("没有轮廓可供过滤")
            return

        filtered_contours = []
        circles_to_draw = []
        for i, contour in enumerate(context.contours):
            (x, y), radius = cv2.minEnclosingCircle(contour)
            if min_radius <= radius <= max_radius:
                filtered_contours.append(contour)
                context.analysis_results.append(f"轮廓 {i} 半径: {radius:.2f} (保留)")
                if context.debug_mode and draw_circle:
                    circles_to_draw.append(((int(x), int(y)), int(radius)))
            else:
                context.analysis_results.append(f"轮廓 {i} 半径: {radius:.2f} (过滤)")

        context.contours = filtered_contours
        if not filtered_contours:
            context.success = False
        context.analysis_results.append(f"按半径过滤后剩余 {len(filtered_contours)} 个轮廓")

        if context.debug_mode:
            # 重新绘制保留的轮廓和圆
            display_with_drawings = context.display_image.copy()
            cv2.drawContours(display_with_drawings, filtered_contours, -1, (0, 255, 0), 2)
            for center, radius in circles_to_draw:
                cv2.circle(display_with_drawings, center, radius, (0, 0, 255), 2)
            context.display_image = display_with_drawings