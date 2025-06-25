# coding: utf-8
from typing import Dict, Any
import cv2
from one_dragon.base.cv_process.cv_step import CvStep, CvPipelineContext


class CvStepOcr(CvStep):

    def __init__(self):
        super().__init__('OCR识别')

    def get_params(self) -> Dict[str, Any]:
        return {
            'draw_text_box': {'type': 'bool', 'default': True, 'label': '绘制识别结果', 'tooltip': '是否在调试图像上绘制OCR识别出的文本框和内容。'},
            # 'override_settings': {'type': 'bool', 'default': False, 'label': '覆盖全局配置', 'tooltip': '[核心] 是否启用此步骤的独立OCR配置。启用后，下方所有参数才会生效。'},

            # 从 OnnxOcrMatcher 的 ocr_options 同步过来的参数
            # 'use_gpu': {'type': 'bool', 'default': False, 'label': '使用GPU加速', 'tooltip': '是否使用GPU进行计算。修改此项会触发模型重载，可能需要等待片刻。'},
            # 'use_angle_cls': {'type': 'bool', 'default': False, 'label': '启用方向分类', 'tooltip': '是否启用180度方向分类。能识别颠倒的文字，但会轻微增加耗时。'},
            # 'det_limit_side_len': {'type': 'float', 'default': 960.0, 'range': (100.0, 2000.0), 'label': '检测图像边长', 'tooltip': 'OCR前会将图像缩放到最长边不超过此值。值越小速度越快，但可能丢失小文字。'},
            # 'det_db_thresh': {'type': 'float', 'default': 0.3, 'range': (0.0, 1.0), 'label': '检测-像素阈值', 'tooltip': '判断一个像素点是否属于文本区域的概率阈值。处理模糊文字时可适当调低。'},
            # 'det_db_box_thresh': {'type': 'float', 'default': 0.6, 'range': (0.0, 1.0), 'label': '检测-文本框阈值', 'tooltip': '将像素点组合成文本框的置信度阈值。如果漏字，可适当调低此值。'},
            # 'det_db_unclip_ratio': {'type': 'float', 'default': 1.5, 'range': (1.0, 4.0), 'label': '检测-文本框扩张', 'tooltip': '按比例扩张检测到的文本框。对于粘连或艺术字，调大此值有助于框住完整文字。'},
            # 'rec_batch_num': {'type': 'int', 'default': 6, 'range': (1, 32), 'label': '识别-批处理数', 'tooltip': '识别时一次处理的文本框数量。在GPU模式下，增加此值可提升性能。'},
            # 'max_text_length': {'type': 'int', 'default': 25, 'range': (5, 50), 'label': '识别-最大长度', 'tooltip': '限制单个文本框能识别出的最大字符数。'},
            # 'drop_score': {'type': 'float', 'default': 0.5, 'range': (0.0, 1.0), 'label': '识别-置信度过滤', 'tooltip': '只有识别可信度高于此值的文本才会被最终采纳。'},
            # 'cls_thresh': {'type': 'float', 'default': 0.9, 'range': (0.0, 1.0), 'label': '分类-方向置信度', 'tooltip': '方向分类器判断文本方向（0度或180度）的可信度阈值。'},
        }

    def get_description(self) -> str:
        return "对当前图像进行OCR识别。可临时覆盖全局OCR设置。"

    def _execute(self, context: CvPipelineContext,
                 draw_text_box: bool = True,
                 # override_settings: bool = False,
                 # OCR options
                 # use_gpu: bool = False,
                 # use_angle_cls: bool = False,
                 # det_limit_side_len: float = 960.0,
                 # det_db_thresh: float = 0.3,
                 # det_db_box_thresh: float = 0.6,
                 # det_db_unclip_ratio: float = 1.5,
                 # rec_batch_num: int = 6,
                 # max_text_length: int = 25,
                 # drop_score: float = 0.5,
                 # cls_thresh: float = 0.9,
                 ):
        if context.ocr is None:
            context.analysis_results.append("错误: OCR 功能未初始化")
            return

        # if override_settings:
        #     # 直接使用方法参数构建新配置
        #     new_options = {
        #         'use_gpu': use_gpu,
        #         'use_angle_cls': use_angle_cls,
        #         'det_limit_side_len': det_limit_side_len,
        #         'det_db_thresh': det_db_thresh,
        #         'det_db_box_thresh': det_db_box_thresh,
        #         'det_db_unclip_ratio': det_db_unclip_ratio,
        #         'rec_batch_num': rec_batch_num,
        #         'max_text_length': max_text_length,
        #         'drop_score': drop_score,
        #         'cls_thresh': cls_thresh,
        #     }
        #     context.analysis_results.append(f"应用OCR设置: {new_options}")
        #     context.ocr.update_options(new_options)

        # 执行OCR
        ocr_results = context.ocr.run_ocr(context.display_image)
        context.ocr_result = ocr_results
        if not ocr_results:
            context.success = False
        context.analysis_results.append(f"OCR 识别到 {len(ocr_results)} 个文本项:")

        # 绘制结果
        display_with_ocr = context.display_image.copy()
        for text, match_list in ocr_results.items():
            for match in match_list:
                context.analysis_results.append(f"  - '{match.data}' (置信度: {match.confidence:.2f}) at {match.rect}")
                if context.debug_mode and draw_text_box:
                    cv2.rectangle(display_with_ocr, (match.rect.x1, match.rect.y1), (match.rect.x2, match.rect.y2), (255, 0, 255), 2)
        context.display_image = display_with_ocr