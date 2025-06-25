# coding: utf-8
import cv2
from one_dragon.base.cv_process.cv_step import CvStep, CvPipelineContext


class CvStepHistogramEqualization(CvStep):

    def __init__(self):
        super().__init__('直方图均衡化')

    def get_description(self) -> str:
        return "对灰度图像进行直方图均衡化，以增强全局对比度。对于光照过暗、过亮或对比度不足的图像有奇效。"

    def _execute(self, context: CvPipelineContext, **kwargs):
        # 确保在灰度图上操作
        if context.mask_image is not None and len(context.mask_image.shape) == 2:
            equalized_image = cv2.equalizeHist(context.mask_image)
            context.display_image = cv2.cvtColor(equalized_image, cv2.COLOR_GRAY2RGB)
            context.mask_image = equalized_image
            context.analysis_results.append("已应用直方图均衡化")
        else:
            context.analysis_results.append("错误: 请先执行灰度化步骤")