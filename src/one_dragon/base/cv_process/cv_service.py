# coding: utf-8
import contextvars
import os
from typing import Dict, List, Type

import cv2
import numpy as np
import yaml

from one_dragon.base.cv_process.cv_pipeline import CvPipeline, CvPipelineContext
from one_dragon.base.cv_process.cv_step import CvStep
from one_dragon.base.cv_process.steps import (
    CvContourPropertiesStep,
    CvDilateStep,
    CvErodeStep,
    CvFindContoursStep,
    CvMatchShapesStep,
    CvMorphologyExStep,
    CvStepCropByArea,
    CvStepCropByTemplate,
    CvStepCropToAnnulus,
    CvStepFilterByArcLength,
    CvStepFilterByArea,
    CvStepFilterByAspectRatio,
    CvStepFilterByCentroidDistance,
    CvStepFilterByHSV,
    CvStepFilterByRadius,
    CvStepFilterByRGB,
    CvStepGrayscale,
    CvStepHistogramEqualization,
    CvStepOcr,
    CvStepThreshold,
    CvTemplateMatchingStep,
)
from one_dragon.base.operation.application.plugin_info import PluginSource
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.utils import os_utils, yaml_utils

# 当前插件上下文：插件 Application 执行期间记录插件名，
# 裸名流水线解析时优先查该插件目录，其次主仓。
_current_plugin: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    'cv_pipeline_current_plugin', default=None
)


def set_current_plugin(plugin_name: str | None) -> contextvars.Token:
    """
    设置当前插件上下文，返回 Token 用于恢复
    :param plugin_name: 插件名（插件目录名）；None 表示主仓上下文
    """
    return _current_plugin.set(plugin_name)


def reset_current_plugin(token: contextvars.Token) -> None:
    """恢复插件上下文"""
    _current_plugin.reset(token)


class CvService:
    """
    一个纯净的、无UI依赖的CV流水线服务
    负责流水线的加载、保存、执行等核心功能
    流水线来源为多目录：主仓 + 各插件（按 source 区分，裸名 + 插件上下文解析）
    """
    PIPELINE_DIR: str = os_utils.get_path_under_work_dir('assets', 'image_analysis_pipelines')
    TEMPLATE_DIR: str = os_utils.get_path_under_work_dir('assets', 'image_analysis_templates')
    PIPELINE_SUB_DIR: str = os.path.join('assets', 'image_analysis_pipelines')

    def __init__(self, od_ctx: OneDragonContext):
        """
        服务初始化
        :param od_ctx: 总上下文
        """
        self.od_ctx: OneDragonContext = od_ctx
        self.ocr = od_ctx.ocr
        self.template_loader = od_ctx.template_loader

        # 插件流水线目录列表 [(插件名, 目录路径), ...]，随插件加载刷新
        self._plugin_pipeline_dirs: list[tuple[str, str]] = []
        self.refresh_plugin_pipeline_dirs()

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

    def run_pipeline(self, pipeline_name: str, image: np.ndarray, debug_mode: bool = False, start_time: float | None = None, timeout: float | None = None) -> CvPipelineContext:
        """
        加载并运行指定的流水线
        :param pipeline_name: 流水线名称
        :param image: RGB图像
        :param debug_mode: 是否为调试模式
        :param start_time: 流水线开始执行的时间
        :param timeout: 允许的执行时间（秒），None表示无限制
        :return: 包含所有结果的上下文
        """
        pipeline = self.load_pipeline(pipeline_name)
        if pipeline is None:
            ctx = CvPipelineContext(image, service=self, debug_mode=debug_mode, start_time=start_time, timeout=timeout)
            ctx.error_str = f"流水线 {pipeline_name} 加载失败"
            return ctx

        result = pipeline.execute(image, service=self, debug_mode=debug_mode, start_time=start_time, timeout=timeout)
        self._emit_overlay_vision(pipeline_name, result)
        return result

    def _emit_overlay_vision(self, pipeline_name: str, context: CvPipelineContext) -> None:
        bus = getattr(self.od_ctx, "overlay_debug_bus", None)
        if bus is None or context is None:
            return

        try:
            from one_dragon.base.operation.overlay_debug_bus import (
                PerfMetricSample,
                TimelineItem,
                VisionDrawItem,
            )
        except Exception:
            return

        bus.add_performance(
            PerfMetricSample(
                metric="cv_pipeline_ms",
                value=float(context.total_execution_time),
                unit="ms",
                ttl_seconds=20.0,
                meta={"pipeline": pipeline_name},
            )
        )
        bus.add_timeline(
            TimelineItem(
                category="vision",
                title=f"cv:{pipeline_name}",
                detail=f"{context.total_execution_time:.1f}ms",
                level="DEBUG",
                ttl_seconds=15.0,
            )
        )

        # 1) contours
        contour_rects = context.get_absolute_rects()
        for x1, y1, x2, y2 in contour_rects[:20]:
            bus.add_vision(
                VisionDrawItem(
                    source="cv",
                    label=f"{pipeline_name}:contour",
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    color="#62d96b",
                    ttl_seconds=1.4,
                )
            )

        # 2) template/crop match result
        if context.match_result is not None and context.match_result.max is not None:
            best = context.match_result.max
            bus.add_vision(
                VisionDrawItem(
                    source="cv",
                    label=f"{pipeline_name}:match",
                    x1=best.x + context.crop_offset[0],
                    y1=best.y + context.crop_offset[1],
                    x2=best.x + best.w + context.crop_offset[0],
                    y2=best.y + best.h + context.crop_offset[1],
                    score=best.confidence,
                    color="#50e3c2",
                    ttl_seconds=1.6,
                )
            )

        # 3) OCR from pipeline context
        if context.ocr_result:
            pushed = 0
            for text, match_list in context.ocr_result.items():
                if match_list is None:
                    continue
                for match in match_list.arr:
                    if pushed >= 30:
                        break
                    label = str(text or "").strip()
                    if len(label) > 28:
                        label = label[:25] + "..."
                    bus.add_vision(
                        VisionDrawItem(
                            source="cv",
                            label=f"{pipeline_name}:{label}",
                            x1=match.x + context.crop_offset[0],
                            y1=match.y + context.crop_offset[1],
                            x2=match.x + match.w + context.crop_offset[0],
                            y2=match.y + match.h + context.crop_offset[1],
                            score=match.confidence,
                            color="#7fd6ff",
                            ttl_seconds=1.4,
                        )
                    )
                    pushed += 1
                if pushed >= 30:
                    break

    def refresh_plugin_pipeline_dirs(self) -> None:
        """
        枚举各插件的流水线目录 plugins/<插件名>/assets/image_analysis_pipelines/
        只收集存在该目录的插件
        """
        dirs: list[tuple[str, str]] = []
        for plugin_root, source in self.od_ctx.application_plugin_dirs:
            if source != PluginSource.THIRD_PARTY:
                continue
            if not plugin_root.is_dir():
                continue
            for child in plugin_root.iterdir():
                if not child.is_dir():
                    continue
                pipeline_dir = child / self.PIPELINE_SUB_DIR
                if pipeline_dir.is_dir():
                    dirs.append((child.name, str(pipeline_dir)))
        self._plugin_pipeline_dirs = dirs

    def get_plugin_pipeline_dir(self, plugin_name: str) -> str | None:
        """
        获取指定插件的流水线目录
        :param plugin_name: 插件名（插件目录名）
        """
        for name, dir_path in self._plugin_pipeline_dirs:
            if name == plugin_name:
                return dir_path
        return None

    def get_plugin_names(self) -> list[str]:
        """
        获取存在流水线目录的插件名列表
        """
        return [name for name, _ in self._plugin_pipeline_dirs]

    def _resolve_pipeline_dir(self, source: str | None = None) -> str | None:
        """
        解析流水线来源目录
        :param source: 来源；'' 表示主仓，插件名表示对应插件，None 表示按当前上下文解析
        （插件 Application 执行期间 ContextVar 非空 → 该插件目录，否则主仓）
        """
        if source is not None:
            if source == '':
                return self.PIPELINE_DIR
            return self.get_plugin_pipeline_dir(source)

        current_plugin = _current_plugin.get()
        if current_plugin:
            plugin_dir = self.get_plugin_pipeline_dir(current_plugin)
            if plugin_dir is not None:
                return plugin_dir
        return self.PIPELINE_DIR

    def get_pipeline_names(self, source: str | None = '') -> list[str]:
        """
        获取指定来源的流水线名称（裸名）
        :param source: ''（默认）表示主仓；插件名表示对应插件目录
        """
        if source is None:
            source = ''
        dir_path = self._resolve_pipeline_dir(source)
        if dir_path is None or not os.path.isdir(dir_path):
            return []
        names = []
        for file_name in os.listdir(dir_path):
            if file_name.endswith('.yml'):
                names.append(file_name[:-4])
        return names

    def save_pipeline(self, name: str, pipeline: CvPipeline, source: str | None = None) -> bool:
        """
        将流水线保存到文件
        :param name: 流水线名称
        :param pipeline: 流水线实例
        :param source: 保存目标来源；None 表示按当前上下文解析（插件优先再主仓），'' 表示主仓，插件名表示对应插件目录
        """
        if not name:
            return False

        save_dir = self._resolve_pipeline_dir(source)
        if save_dir is None:
            return False

        data_to_save = [step.to_dict() for step in pipeline.steps]

        file_path = os.path.join(save_dir, f"{name}.yml")
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(data_to_save, f, allow_unicode=True, sort_keys=False)

        return True

    def load_pipeline(self, name: str, source: str | None = None) -> CvPipeline | None:
        """
        从文件加载流水线
        :param name: 流水线名称
        :param source: 来源；None 表示按当前上下文解析（插件优先再主仓），'' 表示主仓，插件名表示对应插件
        """
        dir_path = self._resolve_pipeline_dir(source)
        if dir_path is None:
            return None
        file_path = os.path.join(dir_path, f"{name}.yml")
        if not os.path.exists(file_path):
            return None

        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                pipeline_data = yaml_utils.safe_load(f)
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

    def delete_pipeline(self, name: str, source: str | None = None):
        """
        删除一个流水线文件
        :param name: 流水线名称
        :param source: 来源；None 表示按当前上下文解析，'' 表示主仓，插件名表示对应插件
        """
        dir_path = self._resolve_pipeline_dir(source)
        if dir_path is None:
            return
        file_path = os.path.join(dir_path, f"{name}.yml")
        if os.path.exists(file_path):
            os.remove(file_path)

    def rename_pipeline(self, old_name: str, new_name: str, source: str | None = None):
        """
        重命名流水线
        :param old_name: 旧名称
        :param new_name: 新名称
        :param source: 来源；None 表示按当前上下文解析，'' 表示主仓，插件名表示对应插件
        """
        if not old_name or not new_name or old_name == new_name:
            return

        dir_path = self._resolve_pipeline_dir(source)
        if dir_path is None:
            return

        old_file_path = os.path.join(dir_path, f"{old_name}.yml")
        new_file_path = os.path.join(dir_path, f"{new_name}.yml")
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
