# coding: utf-8
from typing import Dict, Any
import cv2
from one_dragon.base.cv_process.cv_step import CvStep, CvPipelineContext


class CvContourPropertiesStep(CvStep):

    def __init__(self):
        super().__init__('轮廓属性分析')

    def get_params(self) -> Dict[str, Any]:
        return {
            'show_bounding_box': {'type': 'bool', 'default': True, 'label': '显示外接矩形', 'tooltip': '是否在图像上用蓝色矩形框出每个轮廓。'},
            'show_center': {'type': 'bool', 'default': True, 'label': '显示质心', 'tooltip': '是否在图像上用红色点标出每个轮廓的质心。'},
        }

    def get_description(self) -> str:
        return "计算每个轮廓的详细几何属性，并将其输出到分析结果中。也会在图像上绘制辅助信息。"

    def _execute(self, context: CvPipelineContext, show_bounding_box: bool = True, show_center: bool = True, **kwargs):
        if not context.debug_mode:
            return  # 非调试模式直接跳过

        if not context.contours:
            context.analysis_results.append("没有轮廓可供分析")
            return

        display_with_props = context.display_image.copy()
        total_contours = len(context.contours)
        context.analysis_results.append(f"开始分析 {total_contours} 个轮廓的属性...")

        for i, contour in enumerate(context.contours):
            moments = cv2.moments(contour)
            if moments["m00"] == 0:
                continue  # 忽略面积为0的轮廓

            # 计算质心
            cx = int(moments["m10"] / moments["m00"])
            cy = int(moments["m01"] / moments["m00"])

            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = float(w) / h if h != 0 else 0

            result_str = (
                f"  [轮廓 {i}]: "
                f"面积={area:.2f}, "
                f"周长={perimeter:.2f}, "
                f"质心=({cx}, {cy}), "
                f"外接矩形=({x},{y},{w},{h}), "
                f"长宽比={aspect_ratio:.2f}"
            )
            context.analysis_results.append(result_str)

            # 绘制
            if show_bounding_box:
                cv2.rectangle(display_with_props, (x, y), (x + w, y + h), (255, 0, 0), 2)  # 蓝色矩形
            if show_center:
                cv2.circle(display_with_props, (cx, cy), 5, (0, 0, 255), -1)  # 红色中心点

        context.display_image = display_with_props
        context.analysis_results.append("轮廓属性分析完成。")