import re
from typing import List, Tuple, Any

import cv2
from cv2.typing import MatLike

from one_dragon.base.cv_process.cv_pipeline import CvPipelineContext
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.target_state import DetectionTask, TargetStateDef, TargetCheckWay


class TargetStateChecker:
    """
    一个完全由数据驱动的通用目标状态检测器
    """

    def __init__(self, ctx: ZContext):
        """
        初始化检测器
        :param ctx: 全局上下文
        """
        self.ctx: ZContext = ctx
        self._check_way_handlers = {
            TargetCheckWay.CONTOUR_COUNT_IN_RANGE: self._check_contour_count,
            TargetCheckWay.OCR_RESULT_AS_NUMBER: self._check_ocr_as_number,
            TargetCheckWay.OCR_TEXT_CONTAINS: self._check_ocr_text_contains,
            TargetCheckWay.MAP_CONTOUR_LENGTH_TO_PERCENT: self._check_map_contour_length_to_percent,
        }

    def run_task(self, screen: MatLike, task: DetectionTask, debug_mode: bool = False) -> Tuple[CvPipelineContext, List[Tuple[str, Any]]]:
        """
        运行一个检测任务组，并返回所有解读出的状态
        :param screen: 屏幕截图
        :param task: 检测任务组的定义
        :param debug_mode: 是否开启CV流水线的调试模式
        :return: CV结果上下文, 状态元组列表 (state_name, result)
        """
        # 1. 运行一次CV流水线
        cv_result = self.ctx.cv_service.run_pipeline(task.pipeline_name, screen, debug_mode=debug_mode)

        # 2. 循环解读结果
        results = []
        for state_def in task.state_definitions:
            interpreted_value = self._interpret_result(cv_result, state_def)
            results.append((state_def.state_name, interpreted_value))

        return cv_result, results

    def _interpret_result(self, cv_result: CvPipelineContext, state_def: TargetStateDef) -> Any:
        """
        根据单个状态定义，解读一份CV结果。
        现在返回True, (True, value), False, 或 None
        """
        if cv_result is None or not cv_result.is_success:
            # CV失败时，视为未检测到
            return None if state_def.clear_on_miss else False

        handler = self._check_way_handlers.get(state_def.check_way)
        if handler:
            return handler(cv_result, state_def)
        else:
            log.debug(f"未知的 TargetCheckWay: {state_def.check_way} for state {state_def.state_name}")
            return False # 未知check_way视为不处理

    def _check_contour_count(self, cv_result: CvPipelineContext, state_def: TargetStateDef) -> bool | None:
        """
        处理 CONTOUR_COUNT_IN_RANGE
        """
        params = state_def.check_params
        count = len(cv_result.contours)
        min_count = params.get('min_count', 0)
        max_count = params.get('max_count', 999)
        if min_count <= count <= max_count:
            return True
        else:
            return None if state_def.clear_on_miss else False

    def _check_ocr_as_number(self, cv_result: CvPipelineContext, state_def: TargetStateDef) -> tuple | bool | None:
        """
        处理 OCR_RESULT_AS_NUMBER
        """
        try:
            # 兼容dict和OcrResult两种返回类型
            ocr_text = "".join(cv_result.ocr_result.keys()) if isinstance(cv_result.ocr_result,
                                                                          dict) else cv_result.ocr_result.get_text()
            match = re.search(r'\d+', ocr_text)
            if match:
                return True, int(match.group(0))
        except (ValueError, TypeError, AttributeError):
            pass  # 异常情况视为未识别到

        # 对于OCR_RESULT_AS_NUMBER，如果没有数字，则根据clear_on_miss决定
        return None if state_def.clear_on_miss else False

    def _check_ocr_text_contains(self, cv_result: CvPipelineContext, state_def: TargetStateDef) -> bool | None:
        """
        处理 OCR_TEXT_CONTAINS
        """
        params = state_def.check_params
        try:
            # 兼容dict和OcrResult两种返回类型
            ocr_text = "".join(cv_result.ocr_result.keys()) if isinstance(cv_result.ocr_result,
                                                                          dict) else cv_result.ocr_result.get_text()
            if not ocr_text: # 初始的空文本检查
                return None if state_def.clear_on_miss else False

            contains = params.get('contains', [])
            if isinstance(contains, str):
                contains = [contains]

            mode = params.get('mode', 'any')
            case_sensitive = params.get('case_sensitive', False)
            exclude = params.get('exclude', [])
            if isinstance(exclude, str):
                exclude = [exclude]

            # 处理大小写
            processed_ocr_text = ocr_text
            if not case_sensitive:
                processed_ocr_text = ocr_text.lower()
                processed_contains = [c.lower() for c in contains]
                processed_exclude = [e.lower() for e in exclude]
            else:
                processed_contains = contains
                processed_exclude = exclude

            # 检查排除项
            for ex_text in processed_exclude:
                if ex_text in processed_ocr_text:
                    return None if state_def.clear_on_miss else False

            # 检查包含项
            if mode == 'any':
                if any(c_text in processed_ocr_text for c_text in processed_contains):
                    return True
            elif mode == 'all':
                if all(c_text in processed_ocr_text for c_text in processed_contains):
                    return True
            
            # 如果以上条件都不满足，则说明未命中
            return None if state_def.clear_on_miss else False

        except (ValueError, TypeError, AttributeError):
            # 异常情况也视为无有效结果
            return None if state_def.clear_on_miss else False

    def _check_map_contour_length_to_percent(self, cv_result: CvPipelineContext, state_def: TargetStateDef) -> tuple | bool | None:
        """
        处理 MAP_CONTOUR_LENGTH_TO_PERCENT (最终逻辑)
        计算轮廓的【外接矩形宽度】与【遮罩图像宽度】的比值
        """
        # 1. 验证输入
        if not cv_result.contours:
            log.debug(f"状态 {state_def.state_name}: 未找到轮廓")
            return None if state_def.clear_on_miss else False

        if cv_result.mask_image is None:
            log.warn(f"状态 {state_def.state_name} 需要CV流水线提供 mask_image 输出，但未找到。")
            return None if state_def.clear_on_miss else False

        # 2. 获取参数
        contour_index = state_def.check_params.get('contour_index', 0)
        if len(cv_result.contours) <= contour_index:
            log.debug(f"状态 {state_def.state_name}: 轮廓索引 {contour_index} 越界 (共 {len(cv_result.contours)} 个轮廓)")
            return None if state_def.clear_on_miss else False

        # 3. 计算
        try:
            contour = cv_result.contours[contour_index]
            mask_width = cv_result.mask_image.shape[1]

            if mask_width == 0:
                log.debug(f"状态 {state_def.state_name}: 遮罩宽度为0")
                return None if state_def.clear_on_miss else False

            # 【核心修正】: 使用外接矩形的宽度，而不是轮廓周长
            _x, _y, w, _h = cv2.boundingRect(contour)
            contour_width = w

            ratio = min(contour_width, mask_width) / mask_width
            
            result_percent = int(ratio * 100)
            log.debug(f"状态 {state_def.state_name}: 轮廓宽度={contour_width}, 遮罩宽度={mask_width}, 比率={ratio:.2f}, 百分比={result_percent}%")
            
            return True, result_percent

        except Exception as e:
            log.exception(f"计算轮廓宽度与遮罩宽度比率时出错: {e}")
            return None if state_def.clear_on_miss else False