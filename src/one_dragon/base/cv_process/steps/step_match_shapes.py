# coding: utf-8
from typing import Dict, Any
import cv2
from one_dragon.base.cv_process.cv_step import CvStep, CvPipelineContext


class CvMatchShapesStep(CvStep):

    def __init__(self):
        super().__init__('形状匹配')

    def get_params(self) -> Dict[str, Any]:
        return {
            'template_name': {'type': 'enum_template', 'default': '', 'label': '模板轮廓名称', 'tooltip': '用于形状比较的模板轮廓。'},
            'max_dissimilarity': {'type': 'float', 'default': 0.5, 'range': (0.0, 10.0), 'label': '最大差异度', 'tooltip': '形状差异度的上限。值越小表示形状越相似。只有差异度低于此值的轮廓才会被保留。'},
            'draw_contours': {'type': 'bool', 'default': True, 'label': '绘制匹配轮廓', 'tooltip': '是否在调试图像上画出形状匹配成功的轮廓。'},
        }

    def get_description(self) -> str:
        return "将输入轮廓与一个预存的模板轮廓进行形状匹配。返回值越小，形状越相似。"

    def _execute(self, context: CvPipelineContext, template_name: str = '', max_dissimilarity: float = 0.5, draw_contours: bool = True, **kwargs):
        if context.service is None:
            context.analysis_results.append(f"错误：CvService未初始化，无法加载模板")
            return

        template_contour = context.service.load_template_contour(template_name)

        if template_contour is None:
            context.analysis_results.append(f"错误：无法加载模板 {template_name}")
            return

        if not context.contours:
            context.analysis_results.append("没有轮廓可供匹配")
            return

        filtered_contours = []
        for i, contour in enumerate(context.contours):
            dissimilarity = cv2.matchShapes(template_contour, contour, cv2.CONTOURS_MATCH_I1, 0.0)
            if dissimilarity <= max_dissimilarity:
                filtered_contours.append(contour)
                context.analysis_results.append(f"轮廓 {i} 相似度: {dissimilarity:.4f} (保留)")
            else:
                context.analysis_results.append(f"轮廓 {i} 相似度: {dissimilarity:.4f} (过滤)")

        context.contours = filtered_contours
        if not filtered_contours:
            context.success = False
        context.analysis_results.append(f"按形状匹配后剩余 {len(filtered_contours)} 个轮廓")
        if context.debug_mode and draw_contours:
            # 重新绘制轮廓
            display_with_contours = context.display_image.copy()
            cv2.drawContours(display_with_contours, filtered_contours, -1, (0, 255, 0), 2)
            context.display_image = display_with_contours