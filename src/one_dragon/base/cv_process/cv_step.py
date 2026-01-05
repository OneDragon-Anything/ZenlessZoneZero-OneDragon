# coding: utf-8
from typing import Dict, Any, List, TYPE_CHECKING
import cv2
import numpy as np
import time
from one_dragon.base.matcher.match_result import MatchResult
from one_dragon.utils import cv2_utils

if TYPE_CHECKING:
    from one_dragon.base.cv_process.cv_service import CvService


class CvPipelineContext:
    """
    一个图像处理流水线的上下文
    """
    def __init__(self, source_image: np.ndarray, service: 'CvService | None' = None, debug_mode: bool = True, start_time: float | None = None, timeout: float | None = None):
        self.source_image: np.ndarray = source_image  # 原始输入图像 (只读)
        self.service: 'CvService' = service
        self.debug_mode: bool = debug_mode  # 是否为调试模式
        self.display_image: np.ndarray = source_image.copy()  # 用于UI显示的主图像，可被修改
        self.crop_offset: tuple[int, int] = (0, 0)  # display_image 左上角相对于 source_image 的坐标偏移
        self.mask_image: np.ndarray = None  # 二值掩码图像
        self.contours: List[np.ndarray] = []  # 检测到的轮廓列表
        self.analysis_results: List[str] = []  # 存储分析结果的字符串列表
        self.match_result: MatchResult = None
        self.ocr_result = None  # OcrResult from ocr step
        self.step_execution_times: list[tuple[str, float]] = []
        self.total_execution_time: float = 0.0
        self.error_str: str = None  # 致命错误信息
        self.success: bool = True  # 流水线逻辑是否成功

        # 超时控制相关
        self.start_time: float = start_time if start_time is not None else time.time()
        self.timeout: float = timeout  # 允许的执行时间（秒），None表示无限制

    @property
    def is_success(self) -> bool:
        """
        判断流水线是否执行成功
        :return:
        """
        return self.error_str is None and self.success

    @property
    def od_ctx(self) -> 'OneDragonContext':
        """
        通过service获取上下文
        :return:
        """
        return self.service.od_ctx if self.service else None

    @property
    def template_loader(self):
        return self.service.template_loader if self.service else None

    @property
    def ocr(self):
        return self.service.ocr if self.service else None

    def check_timeout(self) -> bool:
        """
        检查是否已经超时
        :return: True表示已超时，False表示未超时
        """
        if self.timeout is None:
            return False
        return time.time() - self.start_time > self.timeout

    def get_absolute_rects(self) -> List[tuple[int, int, int, int]]:
        """
        获取所有轮廓的绝对坐标矩形框(x1, y1, x2, y2格式)
        Returns:
            轮廓的绝对坐标列表，每个元素为 (x1, y1, x2, y2) 格式
        """
        rects = []
        for contour in self.contours:
            x, y, w, h = cv2.boundingRect(contour)
            # 转换为绝对坐标
            x1 = x + self.crop_offset[0]
            y1 = y + self.crop_offset[1]
            x2 = x1 + w
            y2 = y1 + h
            rects.append((x1, y1, x2, y2))
        return rects

    def get_absolute_rect_pairs(self) -> List[tuple[np.ndarray, tuple[int, int, int, int]]]:
        """
        获取轮廓和对应的绝对坐标矩形框对(x1, y1, x2, y2格式)
        Returns:
            轮廓和对应绝对坐标的列表，每个元素为 (轮廓, (x1, y1, x2, y2))
        """
        pairs = []
        for contour in self.contours:
            x, y, w, h = cv2.boundingRect(contour)
            # 转换为绝对坐标
            x1 = x + self.crop_offset[0]
            y1 = y + self.crop_offset[1]
            x2 = x1 + w
            y2 = y1 + h
            pairs.append((contour, (x1, y1, x2, y2)))
        return pairs

    def format_absolute_rect_xywh(self, x: int, y: int, w: int, h: int) -> str:
        """
        格式化相对矩形坐标为xywh格式的绝对坐标字符串
        Args:
            x: 相对X坐标
            y: 相对Y坐标
            w: 宽度
            h: 高度

        Returns:
            绝对矩形坐标的字符串表示，格式如: "(100, 200, 50, 30)"，表示(x, y, w, h)
        """
        abs_x = x + self.crop_offset[0]
        abs_y = y + self.crop_offset[1]
        return f"({abs_x}, {abs_y}, {w}, {h})"

    def format_absolute_rect_xyxy(self, x: int, y: int, w: int, h: int) -> str:
        """
        格式化相对矩形坐标为xyxy格式的绝对坐标字符串
        Args:
            x: 相对X坐标
            y: 相对Y坐标
            w: 宽度
            h: 高度

        Returns:
            绝对矩形坐标的字符串表示，格式如: "(100, 200, 150, 230)"，表示(x1, y1, x2, y2)
        """
        x1 = x + self.crop_offset[0]
        y1 = y + self.crop_offset[1]
        x2 = x1 + w
        y2 = y1 + h
        return f"({x1}, {y1}, {x2}, {y2})"


class CvStep:
    """
    所有图像处理步骤的基类
    """

    def __init__(self, name: str):
        self.name = name
        self.params: Dict[str, Any] = {}
        self._init_params()

    def _init_params(self):
        """
        使用默认值初始化参数
        """
        param_defs = self.get_params()
        for param_name, definition in param_defs.items():
            self.params[param_name] = definition.get('default')

    def get_params(self) -> Dict[str, Any]:
        """
        获取该步骤的所有可调参数及其定义
        :return:
        """
        return {}

    def to_dict(self) -> Dict[str, Any]:
        """
        将步骤转换为可序列化的字典
        """
        # 创建 params 的一个副本，并将元组转换为列表
        params_copy = {}
        for key, value in self.params.items():
            if isinstance(value, tuple):
                params_copy[key] = list(value)
            else:
                params_copy[key] = value

        return {
            'step': self.name,
            'params': params_copy
        }

    def update_from_dict(self, data: Dict[str, Any]):
        """
        从字典更新步骤的参数
        """
        param_defs = self.get_params()
        params_data = data.get('params', {})
        for param_name, value in params_data.items():
            if param_name in param_defs:
                # 如果定义的类型是元组，而加载的是列表，则进行转换
                if param_defs[param_name].get('type') == 'tuple_int' and isinstance(value, list):
                    self.params[param_name] = tuple(value)
                else:
                    self.params[param_name] = value

    def get_description(self) -> str:
        """
        获取该步骤的详细说明
        :return:
        """
        return ""

    def execute(self, context: CvPipelineContext, **kwargs):
        """
        执行处理步骤
        :param context: 流水线上下文
        """
        # 合并运行时参数和实例参数，运行时参数优先
        run_params = {**self.params, **kwargs}
        self._execute(context, **run_params)

    def _execute(self, context: CvPipelineContext, **kwargs):
        """
        子类需要重写的执行方法
        """
        pass

    def _crop_image_and_update_context(self, context: CvPipelineContext, rect, operation_name: str):
        """
        一个统一的裁剪方法，执行裁剪并更新上下文中的坐标偏移
        :param context: 流水线上下文
        :param rect: 裁剪区域
        :param operation_name: 用于日志记录的操作名称
        """
        if rect is None:
            context.error_str = f"错误: {operation_name} 的裁剪区域为空"
            context.success = False
            return

        context.display_image = cv2_utils.crop_image_only(context.display_image, rect)

        # 累加偏移量
        context.crop_offset = (context.crop_offset[0] + rect.x1, context.crop_offset[1] + rect.y1)

        context.analysis_results.append(f"已执行 {operation_name}，区域: {rect}，当前总偏移: {context.crop_offset}")
