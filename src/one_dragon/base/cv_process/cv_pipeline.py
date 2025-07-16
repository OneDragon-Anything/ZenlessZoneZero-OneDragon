# coding: utf-8
from typing import List
import numpy as np
import time
from one_dragon.base.cv_process.cv_step import CvStep, CvPipelineContext


class CvPipeline:
    """
    一个图像处理流水线
    """

    def __init__(self):
        self.steps: List[CvStep] = []

    def execute(self, source_image: np.ndarray, service: 'CvService' = None, debug_mode: bool = True) -> CvPipelineContext:
        """
        按顺序执行流水线中的所有步骤，并记录时间
        :param source_image: 原始输入图像
        :param service: CvService 的引用
        :param debug_mode: 是否为调试模式
        :return: 包含所有结果的上下文
        """
        context = CvPipelineContext(source_image, service=service, debug_mode=debug_mode)
        pipeline_start_time = time.time()

        for i, step in enumerate(self.steps):
            step_start_time = time.time()
            step.execute(context)
            step_end_time = time.time()
            execution_time_ms = (step_end_time - step_start_time) * 1000
            context.step_execution_times.append((step.name, execution_time_ms))

        pipeline_end_time = time.time()
        context.total_execution_time = (pipeline_end_time - pipeline_start_time) * 1000
        return context