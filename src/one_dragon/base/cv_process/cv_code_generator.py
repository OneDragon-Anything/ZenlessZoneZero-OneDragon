# coding: utf-8
from typing import List
import cv2
from one_dragon.base.cv_process.cv_step import CvStep
from one_dragon.base.cv_process.steps import (
    CvStepFilterByRGB, CvStepFilterByHSV, CvErodeStep, CvDilateStep,
    CvMorphologyExStep, CvFindContoursStep, CvStepFilterByArea,
    CvStepFilterByArcLength, CvStepFilterByRadius, CvContourPropertiesStep,
    CvMatchShapesStep
)


class CvCodeGenerator:
    """
    根据流水线步骤生成代码
    """

    @staticmethod
    def generate_code(steps: List[CvStep]) -> str:
        """
        生成整个流水线的代码
        """
        if not steps:
            return "# 流水线为空"

        code_lines = [
            "import cv2",
            "import numpy as np",
            "from one_dragon.utils import cv2_utils",
            "",
            "# 假设 `img` 是输入的原始图像 (np.ndarray, RGB格式)",
            "mask = None",
            "contours = None"
        ]

        for step in steps:
            line = ""
            if isinstance(step, CvStepFilterByRGB):
                lower = step.params.get('lower_rgb')
                upper = step.params.get('upper_rgb')
                line = f"mask = cv2_utils.filter_by_color(img, mode='rgb', lower_rgb={lower}, upper_rgb={upper})"
            elif isinstance(step, CvStepFilterByHSV):
                hsv_color = step.params.get('hsv_color')
                hsv_diff = step.params.get('hsv_diff')
                line = f"mask = cv2_utils.filter_by_color(img, mode='hsv', hsv_color={hsv_color}, hsv_diff={hsv_diff})"
            elif isinstance(step, CvErodeStep):
                kernel_size = step.params.get('kernel_size')
                iterations = step.params.get('iterations')
                line = f"mask = cv2.erode(mask, np.ones(({kernel_size}, {kernel_size}), np.uint8), iterations={iterations})"
            elif isinstance(step, CvDilateStep):
                kernel_size = step.params.get('kernel_size')
                iterations = step.params.get('iterations')
                line = f"mask = cv2.dilate(mask, np.ones(({kernel_size}, {kernel_size}), np.uint8), iterations={iterations})"
            elif isinstance(step, CvMorphologyExStep):
                op_name = step.params.get('op')
                cv2_op = step.op_map.get(op_name)
                kernel_size = step.params.get('kernel_size')
                # 在代码中直接使用cv2的枚举值，并附上注释
                line = f"mask = cv2.morphologyEx(mask, cv2.{cv2_op}, np.ones(({kernel_size}, {kernel_size}), np.uint8))  # {op_name}"
            elif isinstance(step, CvFindContoursStep):
                mode_name = step.params.get('mode')
                method_name = step.params.get('method')
                cv2_mode = step.mode_map.get(mode_name)
                cv2_method = step.method_map.get(method_name)
                # 在代码中直接使用cv2的枚举值，并附上注释
                line = f"contours, _ = cv2.findContours(mask, cv2.{cv2_mode}, cv2.{cv2_method})  # mode={mode_name}, method={method_name}"
            elif isinstance(step, CvStepFilterByArea):
                min_area = step.params.get('min_area')
                max_area = step.params.get('max_area')
                line = f"contours = [c for c in contours if {min_area} <= cv2.contourArea(c) <= {max_area}]"
            elif isinstance(step, CvStepFilterByArcLength):
                closed = step.params.get('closed')
                min_length = step.params.get('min_length')
                max_length = step.params.get('max_length')
                line = f"contours = [c for c in contours if {min_length} <= cv2.arcLength(c, {closed}) <= {max_length}]"
            elif isinstance(step, CvStepFilterByRadius):
                min_radius = step.params.get('min_radius')
                max_radius = step.params.get('max_radius')
                line = f"contours = [c for c in contours if {min_radius} <= cv2.minEnclosingCircle(c)[1] <= {max_radius}]"
            elif isinstance(step, CvContourPropertiesStep):
                line = "# 轮廓属性分析步骤不生成代码，因为它主要用于调试显示"
            elif isinstance(step, CvMatchShapesStep):
                template_name = step.params.get('template_name')
                max_dissimilarity = step.params.get('max_dissimilarity')
                code_lines.append(f"# 加载模板轮廓 '{template_name}.npy'")
                code_lines.append(f"template_contour = np.load('assets/image_analysis_templates/{template_name}.npy')")
                line = f"contours = [c for c in contours if cv2.matchShapes(template_contour, c, cv2.CONTOURS_MATCH_I1, 0.0) <= {max_dissimilarity}]"
            else:
                line = f"# 未知步骤: {step.name}"

            if line:
                code_lines.append(line)

        return "\n".join(code_lines)