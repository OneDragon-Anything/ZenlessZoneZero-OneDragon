# coding: utf-8
from typing import Dict, Any
import cv2
import numpy as np
from scipy.spatial import KDTree
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
        # 数量保护检查
        if len(context.contours) > 1000:
            context.success = False
            context.analysis_results.append("轮廓数量超过1000，跳过处理")
            context.contours = []  # 清空轮廓列表
            return

        if len(context.contours) < 2:
            context.analysis_results.append("轮廓数量不足2，跳过质心距离过滤")
            return

        # 1. 计算所有质心
        centroids = []
        valid_indices = []  # 记录有效质心的原始索引
        for i, contour in enumerate(context.contours):
            moments = cv2.moments(contour)
            if moments["m00"] != 0:
                cx = int(moments["m10"] / moments["m00"])
                cy = int(moments["m01"] / moments["m00"])
                centroids.append([cx, cy])
                valid_indices.append(i)
            else:
                context.analysis_results.append(f"轮廓 {i} 面积为0 (过滤)")

        # 2. 使用K-D树进行高效邻近查询
        if len(centroids) < 2:
            context.contours = []
            context.success = False
            context.analysis_results.append(f"有效轮廓数量不足2，无法过滤")
            return

        # 构建K-D树
        kdtree = KDTree(centroids)

        # 查找每个点的邻居
        filtered_contours = []
        retained_indices = []

        # 查询每个点在指定半径内的邻居索引列表（包含自身）
        # query_ball_point返回的是一个列表的列表，每个子列表是对应点的邻居索引
        neighbor_indices_list = kdtree.query_ball_point(centroids, max_distance)

        for i, neighbor_indices in enumerate(neighbor_indices_list):
            # 如果邻居数量>1，说明除了自身外还有其他邻居，不是孤立点
            if len(neighbor_indices) > 1:
                original_idx = valid_indices[i]
                filtered_contours.append(context.contours[original_idx])
                retained_indices.append(str(original_idx))

        context.analysis_results.append(f"轮廓 {', '.join(retained_indices) if retained_indices else '无'} 被保留")
        context.contours = filtered_contours
        if not filtered_contours:
            context.success = False
        context.analysis_results.append(f"按质心距离过滤后剩余 {len(filtered_contours)} 个轮廓")

        if context.debug_mode and draw_contours and filtered_contours:
            display_with_contours = context.display_image.copy()
            cv2.drawContours(display_with_contours, filtered_contours, -1, (0, 255, 0), 2)
            context.display_image = display_with_contours