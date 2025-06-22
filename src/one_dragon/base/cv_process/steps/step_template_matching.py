# coding: utf-8
from typing import Dict, Any
import cv2
from one_dragon.base.cv_process.cv_step import CvStep, CvPipelineContext


class CvTemplateMatchingStep(CvStep):

    def __init__(self):
        self.method_map = {
            'TM_CCOEFF_NORMED': cv2.TM_CCOEFF_NORMED,
            'TM_CCORR_NORMED': cv2.TM_CCORR_NORMED,
            'TM_SQDIFF_NORMED': cv2.TM_SQDIFF_NORMED,
        }
        super().__init__('模板匹配')

    def get_params(self) -> Dict[str, Any]:
        return {
            'template_name': {'type': 'enum_template_image', 'default': '', 'label': '模板图像名称', 'tooltip': '用于在原图中滑窗搜索的模板小图。'},
            'threshold': {'type': 'float', 'default': 0.8, 'range': (0.0, 1.0), 'label': '匹配置信度', 'tooltip': '匹配结果的置信度阈值。只有高于此值的匹配才会被接受。'},
            'method': {'type': 'enum', 'default': 'TM_CCOEFF_NORMED', 'options': list(self.method_map.keys()), 'label': '匹配算法', 'tooltip': '选择模板匹配的计算方法。'},
        }

    def get_description(self) -> str:
        return "在当前图像上寻找与模板图像最匹配的区域。这个步骤不依赖之前的二值化或轮廓步骤。"

    def _execute(self, context: CvPipelineContext, template_name: str = '', threshold: float = 0.8, method: str = 'TM_CCOEFF_NORMED', **kwargs):
        from one_dragon_qt.logic.image_analysis_logic import ImageAnalysisLogic
        logic = ImageAnalysisLogic()
        # TODO: 模板加载应该支持图像
        template_image = None # logic.load_template_image(template_name) 

        if template_image is None:
            context.analysis_results.append(f"错误：无法加载图像模板 {template_name}")
            return

        cv2_method = self.method_map.get(method)
        if cv2_method is None:
            context.analysis_results.append(f"错误：无效的匹配方法 {method}")
            return

        result = cv2.matchTemplate(context.display_image, template_image, cv2_method)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            h, w, _ = template_image.shape
            top_left = max_loc
            bottom_right = (top_left[0] + w, top_left[1] + h)
            
            # 在显示图像上绘制矩形
            cv2.rectangle(context.display_image, top_left, bottom_right, (0, 255, 255), 2)
            context.analysis_results.append(f"找到匹配，置信度 {max_val:.4f} at {top_left}")
        else:
            context.analysis_results.append(f"未找到足够置信度的匹配 (最高 {max_val:.4f})")