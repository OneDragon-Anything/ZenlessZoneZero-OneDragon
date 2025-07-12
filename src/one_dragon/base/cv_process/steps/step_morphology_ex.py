# coding: utf-8
from typing import Dict, Any
import cv2
import numpy as np
from one_dragon.base.cv_process.cv_step import CvStep, CvPipelineContext


class CvMorphologyExStep(CvStep):
    
    def __init__(self):
        self.op_map = {
            '开运算': cv2.MORPH_OPEN,
            '闭运算': cv2.MORPH_CLOSE,
            '梯度': cv2.MORPH_GRADIENT,
            '顶帽': cv2.MORPH_TOPHAT,
            '黑帽': cv2.MORPH_BLACKHAT,
        }
        super().__init__('形态学')

    def get_params(self) -> Dict[str, Any]:
        return {
            'op': {'type': 'enum', 'default': '开运算', 'options': list(self.op_map.keys()), 'label': '操作类型', 'tooltip': '选择高级形态学操作。开运算=先腐蚀后膨胀（去噪），闭运算=先膨胀后腐蚀（填洞）。'},
            'kernel_size': {'type': 'int', 'default': 3, 'range': (1, 21), 'label': '核大小', 'tooltip': '形态学操作的核大小，奇数。'},
        }

    def get_description(self) -> str:
        return "执行高级形态学操作。`op` 是操作类型（如开运算、闭运算等），`kernel_size` 是操作核的大小。"

    def _execute(self, context: CvPipelineContext, op: str = '开运算', kernel_size: int = 3, **kwargs):
        if context.mask_image is None:
            return
        cv2_op = self.op_map.get(op)
        if cv2_op is None:
            return
        kernel = np.ones((kernel_size, kernel_size), np.uint8)
        morph_mask = cv2.morphologyEx(context.mask_image, cv2_op, kernel)
        context.mask_image = morph_mask
        context.display_image = cv2.bitwise_and(context.display_image, context.display_image, mask=morph_mask)