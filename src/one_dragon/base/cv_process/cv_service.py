# coding: utf-8
import os
from typing import List, Dict, Type

import cv2
import numpy as np
import yaml

from one_dragon.base.cv_process.cv_pipeline import CvPipeline, CvPipelineContext
from one_dragon.base.cv_process.cv_step import CvStep
from one_dragon.base.cv_process.steps import (
    CvStepFilterByRGB, CvStepFilterByHSV, CvErodeStep, CvDilateStep,
    CvMorphologyExStep, CvFindContoursStep, CvStepFilterByArea, CvStepFilterByArcLength,
    CvStepFilterByRadius, CvContourPropertiesStep, CvMatchShapesStep, CvStepCropByTemplate, CvStepFilterByAspectRatio,
    CvStepFilterByCentroidDistance, CvStepOcr, CvStepGrayscale, CvStepHistogramEqualization, CvStepThreshold,
    CvStepCropByArea, CvStepCropToAnnulus, CvTemplateMatchingStep
)
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.utils import os_utils


class CvService:
    """
    一个纯净的、无UI依赖的CV流水线服务
    负责流水线的加载、保存、执行等核心功能
    """
    PIPELINE_DIR: str = os_utils.get_path_under_work_dir('assets', 'image_analysis_pipelines')
    TEMPLATE_DIR: str = os_utils.get_path_under_work_dir('assets', 'image_analysis_templates')

    def __init__(self, od_ctx: OneDragonContext):
        """
        服务初始化
        :param od_ctx: 总上下文
        """
        self.od_ctx: OneDragonContext = od_ctx
        self.ocr = od_ctx.cv_ocr
        self.template_loader = od_ctx.template_loader

        # 可用的步骤类型
        self.available_steps: Dict[str, Type[CvStep]] = {
            '按区域裁剪': CvStepCropByArea,
            '按模板裁剪': CvStepCropByTemplate,
            '环形裁剪': CvStepCropToAnnulus,
            '灰度化': CvStepGrayscale,
            '直方图均衡化': CvStepHistogramEqualization,
            '二值化': CvStepThreshold,
            'RGB 范围过滤': CvStepFilterByRGB,
            'HSV 范围过滤': CvStepFilterByHSV,
            '腐蚀': CvErodeStep,
            '膨胀': CvDilateStep,
            '形态学': CvMorphologyExStep,
            '查找轮廓': CvFindContoursStep,
            '按面积过滤': CvStepFilterByArea,
            '按周长过滤': CvStepFilterByArcLength,
            '按半径过滤': CvStepFilterByRadius,
            '按长宽比过滤': CvStepFilterByAspectRatio,
            '按质心距离过滤': CvStepFilterByCentroidDistance,
            '轮廓属性分析': CvContourPropertiesStep,
            '形状匹配': CvMatchShapesStep,
            '模板匹配': CvTemplateMatchingStep,
            'OCR识别': CvStepOcr,
        }

        if not os.path.exists(self.PIPELINE_DIR):
            os.makedirs(self.PIPELINE_DIR)
        if not os.path.exists(self.TEMPLATE_DIR):
            os.makedirs(self.TEMPLATE_DIR)

    def run_pipeline(self, pipeline_name: str, image: np.ndarray, debug_mode: bool = False) -> CvPipelineContext:
        """
        加载并运行指定的流水线
        :param pipeline_name: 流水线名称
        :param image: RGB图像
        :param debug_mode: 是否为调试模式
        :return: 包含所有结果的上下文
        """
        pipeline = self.load_pipeline(pipeline_name)
        if pipeline is None:
            ctx = CvPipelineContext(image, service=self, debug_mode=debug_mode)
            ctx.error_str = f"流水线 {pipeline_name} 加载失败"
            return ctx

        return pipeline.execute(image, service=self, debug_mode=debug_mode)

    def get_pipeline_names(self) -> List[str]:
        """
        获取所有已保存流水线的名称
        """
        names = []
        for file_name in os.listdir(self.PIPELINE_DIR):
            if file_name.endswith('.yml'):
                names.append(file_name[:-4])
        return names

    def save_pipeline(self, name: str, pipeline: CvPipeline) -> bool:
        """
        将流水线保存到文件
        :param name: 流水线名称
        :param pipeline: 流水线实例
        """
        if not name:
            return False

        data_to_save = [step.to_dict() for step in pipeline.steps]

        file_path = os.path.join(self.PIPELINE_DIR, f"{name}.yml")
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(data_to_save, f, allow_unicode=True, sort_keys=False)

        return True

    def load_pipeline(self, name: str) -> CvPipeline | None:
        """
        从文件加载流水线
        :param name: 流水线名称
        """
        file_path = os.path.join(self.PIPELINE_DIR, f"{name}.yml")
        if not os.path.exists(file_path):
            return None

        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                pipeline_data = yaml.safe_load(f)
            except yaml.YAMLError:
                return None

        new_steps = []
        if pipeline_data is not None:
            for step_data in pipeline_data:
                step_name = step_data.get('step')
                step_class = self.available_steps.get(step_name)
                if step_class:
                    step_instance = step_class()
                    step_instance.update_from_dict(step_data)
                    new_steps.append(step_instance)

        pipeline = CvPipeline()
        pipeline.steps = new_steps
        return pipeline

    def delete_pipeline(self, name: str):
        """
        删除一个流水线文件
        :param name: 流水线名称
        """
        file_path = os.path.join(self.PIPELINE_DIR, f"{name}.yml")
        if os.path.exists(file_path):
            os.remove(file_path)

    def rename_pipeline(self, old_name: str, new_name: str):
        """
        重命名流水线
        :param old_name: 旧名称
        :param new_name: 新名称
        """
        if not old_name or not new_name or old_name == new_name:
            return

        old_file_path = os.path.join(self.PIPELINE_DIR, f"{old_name}.yml")
        new_file_path = os.path.join(self.PIPELINE_DIR, f"{new_name}.yml")

        if os.path.exists(old_file_path) and not os.path.exists(new_file_path):
            os.rename(old_file_path, new_file_path)

    def get_template_names(self) -> List[str]:
        """
        获取所有模板轮廓的名称
        """
        names = []
        for file_name in os.listdir(self.TEMPLATE_DIR):
            if file_name.endswith('.npy'):
                names.append(file_name[:-4])
        return names

    def save_template_contour(self, template_name: str, contour: np.ndarray) -> bool:
        """
        保存轮廓为模板
        """
        if not template_name:
            return False
        file_path = os.path.join(self.TEMPLATE_DIR, f"{template_name}.npy")
        try:
            np.save(file_path, contour)
            return True
        except Exception:
            return False

    def load_template_contour(self, template_name: str) -> np.ndarray:
        """
        加载模板轮廓
        :param template_name: 模板名称
        :return:
        """
        file_path = os.path.join(self.TEMPLATE_DIR, f"{template_name}.npy")
        if not os.path.exists(file_path):
            return None
        try:
            return np.load(file_path)
        except Exception:
            return None

    def delete_template_contour(self, template_name: str):
        """
        删除一个模板轮廓
        """
        file_path = os.path.join(self.TEMPLATE_DIR, f"{template_name}.npy")
        if os.path.exists(file_path):
            os.remove(file_path)

    def rename_template_contour(self, old_name: str, new_name: str):
        """
        重命名模板轮廓
        """
        if not old_name or not new_name or old_name == new_name:
            return
        old_file_path = os.path.join(self.TEMPLATE_DIR, f"{old_name}.npy")
        new_file_path = os.path.join(self.TEMPLATE_DIR, f"{new_name}.npy")
        if os.path.exists(old_file_path) and not os.path.exists(new_file_path):
            os.rename(old_file_path, new_file_path)