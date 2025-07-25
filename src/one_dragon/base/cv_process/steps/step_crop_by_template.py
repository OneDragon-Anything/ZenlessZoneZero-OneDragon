# coding: utf-8
from typing import Dict, Any
import cv2
from one_dragon.base.cv_process.cv_step import CvStep, CvPipelineContext
from one_dragon.utils import cv2_utils


class CvStepCropByTemplate(CvStep):

    def __init__(self):
        super().__init__('按模板裁剪')

    def get_params(self) -> Dict[str, Any]:
        return {
            'template_name': {'type': 'enum_template', 'default': '', 'label': '模板名称', 'tooltip': '定义了裁剪区域和（可选）匹配内容的模板。'},
            'enable_match': {'type': 'bool', 'default': False, 'label': '启用模板匹配', 'tooltip': '在裁剪出的图像上，是否再执行一次模板匹配进行验证。'},
            'match_threshold': {'type': 'float', 'default': 0.8, 'range': (0.0, 1.0), 'label': '匹配阈值', 'tooltip': '当启用模板匹配时，所使用的置信度阈值。'},
        }

    def get_description(self) -> str:
        return "根据模板定义的区域裁剪图像，并可选择性地进行模板匹配。"

    def _execute(self, context: CvPipelineContext, template_name: str = '', enable_match: bool = False, match_threshold: float = 0.8, **kwargs):
        if context.template_loader is None:
            context.analysis_results.append("错误: 缺少模板加载器 (TemplateLoader)")
            return

        # 高效获取单个模板
        try:
            sub_dir, template_id = template_name.split('/')
            template_info = context.template_loader.get_template(sub_dir, template_id)
        except ValueError:
            context.analysis_results.append(f"错误: 无效的模板名称格式 {template_name}")
            return

        if template_info is None:
            context.analysis_results.append(f"错误: 找不到模板 {template_name}")
            return

        rect = template_info.get_template_rect_by_point()
        if rect is None:
            context.analysis_results.append(f"错误: 模板 {template_name} 没有定义裁剪区域")
            return

        self._crop_image_and_update_context(context, rect, f"按模板 {template_name} 裁剪")

        if context.is_success and enable_match:
            match_result = cv2_utils.match_template(
                source=context.display_image,  # 使用更新后的 display_image
                template=template_info.raw,
                mask=template_info.mask,
                threshold=match_threshold
            )
            context.match_result = match_result
            best_match = match_result.max
            if best_match is not None and best_match.confidence >= match_threshold:
                context.analysis_results.append(
                    f"模板匹配成功，置信度: {best_match.confidence:.4f} at {best_match.left_top}"
                )
                # 在裁剪后的图上画出匹配位置
                cv2.rectangle(context.display_image, (best_match.x, best_match.y), (best_match.x + best_match.w, best_match.y + best_match.h), (0, 255, 255), 2)
            else:
                context.success = False
                if best_match is not None:
                    context.analysis_results.append(
                        f"模板匹配失败，最高置信度: {best_match.confidence:.4f} (低于阈值 {match_threshold})"
                    )
                else:
                    context.analysis_results.append(
                        f"模板匹配失败，没有找到任何匹配项"
                    )