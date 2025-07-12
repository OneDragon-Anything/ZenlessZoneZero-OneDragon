# coding: utf-8
from typing import Dict, Any
import cv2
import numpy as np
from one_dragon.base.cv_process.cv_step import CvStep, CvPipelineContext


class CvStepFilterByCentroidDistance(CvStep):

    def __init__(self):
        super().__init__('按质心距离过滤')

    def get_params(self) -> Dict[str, Any]:
        return {
            'max_distance': {'type': 'int', 'default': 10, 'range': (0, 1000), 'label': '最大邻近距离', 'tooltip': '一个轮廓的质心到另一个轮廓质心的最大距离。若一个轮廓在此距离内没有任何邻居，则被视为孤立点并被过滤。'},
            'draw_contours': {'type': 'bool', 'default': True, 'label': '绘制保留轮廓', 'tooltip': '是否在调试图像上画出非孤立的轮廓。'},
        }

    def get_description(self) -> str:
        return "根据轮廓质心之间的距离进行过滤。如果一个轮廓在指定的`max_distance`内找不到任何其他轮廓的质心，它就会被过滤掉。"

    def _execute(self, context: CvPipelineContext, max_distance: int = 10, draw_contours: bool = True, **kwargs):
        if len(context.contours) < 2:
            context.analysis_results.append("轮廓数量不足2，跳过质心距离过滤")
            return

        # 1. 计算所有质心
        centroids = []
        for contour in context.contours:
            moments = cv2.moments(contour)
            if moments["m00"] != 0:
                cx = int(moments["m10"] / moments["m00"])
                cy = int(moments["m01"] / moments["m00"])
                centroids.append((cx, cy))
            else:
                centroids.append(None)  # 面积为0的轮廓

        # 2. 过滤
        filtered_contours = []
        retained_indices = []
        for i, contour in enumerate(context.contours):
            if centroids[i] is None:
                context.analysis_results.append(f"轮廓 {i} 面积为0 (过滤)")
                continue

            is_isolated = True
            for j, other_centroid in enumerate(centroids):
                if i == j or other_centroid is None:
                    continue
                
                dist = np.linalg.norm(np.array(centroids[i]) - np.array(other_centroid))
                if dist <= max_distance:
                    is_isolated = False
                    break
            
            if not is_isolated:
                filtered_contours.append(contour)
                retained_indices.append(str(i))

        context.analysis_results.append(f"轮廓 {', '.join(retained_indices) if retained_indices else '无'} 被保留")
        context.contours = filtered_contours
        if not filtered_contours:
            context.success = False
        context.analysis_results.append(f"按质心距离过滤后剩余 {len(filtered_contours)} 个轮廓")

        if context.debug_mode and draw_contours:
            display_with_contours = context.display_image.copy()
            cv2.drawContours(display_with_contours, filtered_contours, -1, (0, 255, 0), 2)
            context.display_image = display_with_contours