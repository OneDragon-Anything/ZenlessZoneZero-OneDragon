# coding: utf-8
from typing import List, TYPE_CHECKING
import numpy as np
import time
from one_dragon.base.cv_process.cv_step import CvStep, CvPipelineContext

if TYPE_CHECKING:
    from one_dragon.base.cv_process.cv_service import CvService


class CvPipeline:
    """
    一个图像处理流水线
    """

    def __init__(self):
        self.steps: List[CvStep] = []

    def execute(self, source_image: np.ndarray, service: 'CvService | None' = None, debug_mode: bool = True, start_time: float | None = None, timeout: float | None = None) -> CvPipelineContext:
        """
        按顺序执行流水线中的所有步骤，并记录时间
        :param source_image: 原始输入图像
        :param service: CvService 的引用
        :param debug_mode: 是否为调试模式
        :param start_time: 流水线开始执行的时间
        :param timeout: 允许的执行时间（秒），None表示无限制
        :return: 包含所有结果的上下文
        """
        context = CvPipelineContext(source_image, service=service, debug_mode=debug_mode, start_time=start_time, timeout=timeout)
        pipeline_start_time = context.start_time  # 使用context的开始时间

        for _, step in enumerate(self.steps):
            # 在每一步开始前检查超时
            if context.check_timeout():
                context.error_str = f"流水线执行超时 (限制 {context.timeout} 秒)"
                context.success = False
                break  # 超时则中断后续步骤

            step_start_time = time.time()
            step.execute(context)
            step_end_time = time.time()
            execution_time_ms = (step_end_time - step_start_time) * 1000
            context.step_execution_times.append((step.name, execution_time_ms))

        pipeline_end_time = time.time()
        context.total_execution_time = (pipeline_end_time - pipeline_start_time) * 1000
        return context