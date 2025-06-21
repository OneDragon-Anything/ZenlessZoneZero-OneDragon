# coding: utf-8
from typing import Dict, Any, List
import cv2
import numpy as np
from one_dragon.base.matcher.match_result import MatchResult
from one_dragon.utils import cv2_utils


class CvPipelineContext:
    """
    一个图像处理流水线的上下文
    """
    def __init__(self, source_image: np.ndarray, service: 'CvService' = None, debug_mode: bool = True):
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


class CvStepFilterByRGB(CvStep):

    def __init__(self):
        super().__init__('RGB 范围过滤')

    def get_params(self) -> Dict[str, Any]:
        return {
            'lower_rgb': {'type': 'tuple_int', 'default': (0, 0, 0), 'range': (0, 255), 'label': 'RGB下限', 'tooltip': '过滤颜色的RGB下限 (R, G, B)。所有通道值都低于此值的像素将被过滤。'},
            'upper_rgb': {'type': 'tuple_int', 'default': (255, 255, 255), 'range': (0, 255), 'label': 'RGB上限', 'tooltip': '过滤颜色的RGB上限 (R, G, B)。所有通道值都高于此值的像素将被过滤。'},
        }

    def get_description(self) -> str:
        return "根据 RGB 范围过滤图像，生成一个二值遮罩。 `lower_rgb` 和 `upper_rgb` 分别是 RGB 颜色的下界和上界。"

    def _execute(self, context: CvPipelineContext, lower_rgb: tuple = (0, 0, 0), upper_rgb: tuple = (255, 255, 255), **kwargs):
        mask = cv2_utils.filter_by_color(context.display_image, mode='rgb', lower_rgb=lower_rgb, upper_rgb=upper_rgb)
        context.mask_image = mask
        context.display_image = cv2.bitwise_and(context.display_image, context.display_image, mask=mask)


class CvStepFilterByHSV(CvStep):

    def __init__(self):
        super().__init__('HSV 范围过滤')

    def get_params(self) -> Dict[str, Any]:
        return {
            'hsv_color': {'type': 'tuple_int', 'default': (0, 0, 0), 'range': [(0, 179), (0, 255), (0, 255)], 'label': '目标颜色 (HSV)', 'tooltip': '要匹配的中心颜色 (H, S, V)。H范围0-179，S和V范围0-255。'},
            'hsv_diff': {'type': 'tuple_int', 'default': (10, 255, 255), 'range': [(0, 90), (0, 255), (0, 255)], 'label': '容差范围 (HSV)', 'tooltip': 'HSV三个通道的容差范围。最终范围是 [中心颜色 - 容差, 中心颜色 + 容差]。'},
        }

    def get_description(self) -> str:
        return "根据 HSV 颜色过滤图像。 `hsv_color` 参数指定要匹配的中心颜色，`hsv_diff` 参数指定 H, S, V 三个通道的容差范围。"

    def _execute(self, context: CvPipelineContext, hsv_color: tuple = (0, 0, 0), hsv_diff: tuple = (10, 255, 255), **kwargs):
        mask = cv2_utils.filter_by_color(context.display_image, mode='hsv', hsv_color=hsv_color, hsv_diff=hsv_diff)
        context.mask_image = mask
        context.display_image = cv2.bitwise_and(context.display_image, context.display_image, mask=mask)

class CvStepGrayscale(CvStep):

    def __init__(self):
        super().__init__('灰度化')

    def get_description(self) -> str:
        return "将彩色图像转换为灰度图像，消除颜色信息，是后续处理步骤（如二值化）的前提。"

    def _execute(self, context: CvPipelineContext, **kwargs):
        if len(context.display_image.shape) == 3:  # 检查是否为彩色图
            gray_image = cv2.cvtColor(context.display_image, cv2.COLOR_RGB2GRAY)
            # 更新主显示图像为灰度图，但保持3通道以便于后续绘制彩色调试信息
            context.display_image = cv2.cvtColor(gray_image, cv2.COLOR_GRAY2RGB)
            context.mask_image = gray_image  # 将单通道灰度图存入mask，供下一步使用
            context.analysis_results.append("图像已转换为灰度")
        else:
            context.analysis_results.append("图像已经是灰度图，跳过灰度化")


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


class CvStepThreshold(CvStep):

    def __init__(self):
        self.method_map = {
            'BINARY': cv2.THRESH_BINARY,
            'OTSU': cv2.THRESH_OTSU,
            'ADAPTIVE_GAUSSIAN': cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            'ADAPTIVE_MEAN': cv2.ADAPTIVE_THRESH_MEAN_C,
        }
        super().__init__('二值化')

    def get_params(self) -> Dict[str, Any]:
        return {
            'method': {'type': 'enum', 'default': 'OTSU', 'options': list(self.method_map.keys()), 'label': '二值化算法', 'tooltip': '选择将灰度图转为黑白图的算法。OTSU和自适应方法能自动寻找阈值。'},
            'threshold_value': {'type': 'int', 'default': 127, 'range': (0, 255), 'label': '固定阈值', 'tooltip': '当算法为BINARY时生效。高于此值的像素变为白色，低于则为黑色。'},
            'adaptive_block_size': {'type': 'int', 'default': 11, 'range': (3, 99), 'label': '自适应-块大小', 'tooltip': '用于自适应阈值的邻域大小，必须是奇数。'},
            'adaptive_c': {'type': 'int', 'default': 2, 'range': (-50, 50), 'label': '自适应-常量C', 'tooltip': '从均值或加权均值中减去的常数，用于微调自适应阈值。'},
        }

    def get_description(self) -> str:
        return "将灰度图像转换为黑白二值图像，这是轮廓分析的前提。支持多种算法以适应不同光照场景。"

    def _execute(self, context: CvPipelineContext, method: str = 'OTSU', threshold_value: int = 127, adaptive_block_size: int = 11, adaptive_c: int = 2, **kwargs):
        # 确保在灰度图上操作
        if context.mask_image is None or len(context.mask_image.shape) != 2:
            context.analysis_results.append("错误: 请先执行灰度化步骤")
            return

        gray_image = context.mask_image

        if adaptive_block_size % 2 == 0:
            adaptive_block_size += 1 # 必须为奇数
            context.analysis_results.append(f"警告: 自适应块大小已调整为奇数 {adaptive_block_size}")

        thresh_image = None
        if method in ['ADAPTIVE_GAUSSIAN', 'ADAPTIVE_MEAN']:
            cv2_method = self.method_map.get(method)
            thresh_image = cv2.adaptiveThreshold(gray_image, 255, cv2_method,
                                                 cv2.THRESH_BINARY, adaptive_block_size, adaptive_c)
            context.analysis_results.append(f"已应用自适应二值化 (方法: {method})")
        elif method == 'OTSU':
            _, thresh_image = cv2.threshold(gray_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            context.analysis_results.append("已应用OTSU二值化")
        else: # BINARY
            _, thresh_image = cv2.threshold(gray_image, threshold_value, 255, cv2.THRESH_BINARY)
            context.analysis_results.append(f"已应用全局二值化 (阈值: {threshold_value})")

        context.mask_image = thresh_image
        context.display_image = cv2.cvtColor(thresh_image, cv2.COLOR_GRAY2RGB)

class CvErodeStep(CvStep):

    def __init__(self):
        super().__init__('腐蚀')

    def get_params(self) -> Dict[str, Any]:
        return {
            'kernel_size': {'type': 'int', 'default': 3, 'range': (1, 21), 'label': '腐蚀核大小', 'tooltip': '腐蚀操作的核大小，奇数。值越大，腐蚀效果（消除噪点）越强。'},
            'iterations': {'type': 'int', 'default': 1, 'range': (1, 10), 'label': '迭代次数', 'tooltip': '腐蚀操作的执行次数。'},
        }

    def get_description(self) -> str:
        return "腐蚀操作可以去除小的噪点。 `kernel_size` 是腐蚀核的大小，越大腐蚀效果越强。`iterations` 是迭代次数。"

    def _execute(self, context: CvPipelineContext, kernel_size: int = 3, iterations: int = 1, **kwargs):
        if context.mask_image is None:
            return
        kernel = np.ones((kernel_size, kernel_size), np.uint8)
        eroded_mask = cv2.erode(context.mask_image, kernel, iterations=iterations)
        context.mask_image = eroded_mask
        context.display_image = cv2.bitwise_and(context.display_image, context.display_image, mask=eroded_mask)


class CvDilateStep(CvStep):

    def __init__(self):
        super().__init__('膨胀')

    def get_params(self) -> Dict[str, Any]:
        return {
            'kernel_size': {'type': 'int', 'default': 3, 'range': (1, 21), 'label': '膨胀核大小', 'tooltip': '膨胀操作的核大小，奇数。值越大，膨胀效果（连接区域）越强。'},
            'iterations': {'type': 'int', 'default': 1, 'range': (1, 10), 'label': '迭代次数', 'tooltip': '膨胀操作的执行次数。'},
        }

    def get_description(self) -> str:
        return "膨胀操作可以连接断开的区域。 `kernel_size` 是膨胀核的大小，越大膨胀效果越强。`iterations` 是迭代次数。"

    def _execute(self, context: CvPipelineContext, kernel_size: int = 3, iterations: int = 1, **kwargs):
        if context.mask_image is None:
            return
        kernel = np.ones((kernel_size, kernel_size), np.uint8)
        dilated_mask = cv2.dilate(context.mask_image, kernel, iterations=iterations)
        context.mask_image = dilated_mask
        context.display_image = cv2.bitwise_and(context.display_image, context.display_image, mask=dilated_mask)


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


class CvFindContoursStep(CvStep):
    
    def __init__(self):
        self.mode_map = {
            'EXTERNAL': cv2.RETR_EXTERNAL,
            'LIST': cv2.RETR_LIST,
            'CCOMP': cv2.RETR_CCOMP,
            'TREE': cv2.RETR_TREE,
        }
        self.method_map = {
            'NONE': cv2.CHAIN_APPROX_NONE,
            'SIMPLE': cv2.CHAIN_APPROX_SIMPLE,
        }
        super().__init__('查找轮廓')

    def get_description(self) -> str:
        return "在二值图像中查找轮廓。`mode` 是轮廓检索模式，`method` 是轮廓逼近方法。`draw_contours` 决定是否在图上画出轮廓。"

    def get_params(self) -> Dict[str, Any]:
        return {
            'mode': {'type': 'enum', 'default': 'EXTERNAL', 'options': list(self.mode_map.keys()), 'label': '轮廓检索模式', 'tooltip': 'EXTERNAL:只找最外层轮廓。LIST:查找所有轮廓，不建立层次结构。TREE:建立完整层次结构。'},
            'method': {'type': 'enum', 'default': 'SIMPLE', 'options': list(self.method_map.keys()), 'label': '轮廓逼近方法', 'tooltip': 'SIMPLE:压缩水平、垂直和对角线段，只保留端点。NONE:存储所有轮廓点。'},
            'draw_contours': {'type': 'bool', 'default': True, 'label': '绘制轮廓', 'tooltip': '是否在调试图像上用绿色线条画出找到的轮廓。'},
        }

    def _execute(self, context: CvPipelineContext, mode: str = 'EXTERNAL', method: str = 'SIMPLE', draw_contours: bool = True, **kwargs):
        if context.mask_image is None:
            return
        
        cv2_mode = self.mode_map.get(mode)
        cv2_method = self.method_map.get(method)
        if cv2_mode is None or cv2_method is None:
            return

        contours, _ = cv2.findContours(context.mask_image, cv2_mode, cv2_method)
        context.contours = contours

        if not contours:
            context.success = False
        
        context.analysis_results.append(f"找到 {len(contours)} 个轮廓")

        if context.debug_mode and draw_contours:
            # 在一个新图像上绘制轮廓，以免影响下一步的处理
            display_with_contours = context.display_image.copy()
            cv2.drawContours(display_with_contours, contours, -1, (0, 255, 0), 2)
            context.display_image = display_with_contours


class CvStepFilterByArea(CvStep):

    def __init__(self):
        super().__init__('按面积过滤')

    def get_params(self) -> Dict[str, Any]:
        return {
            'min_area': {'type': 'int', 'default': 0, 'range': (0, 100000), 'label': '最小面积', 'tooltip': '轮廓的最小像素面积。小于此值的轮廓将被过滤。'},
            'max_area': {'type': 'int', 'default': 10000, 'range': (0, 100000), 'label': '最大面积', 'tooltip': '轮廓的最大像素面积。大于此值的轮廓将被过滤。'},
            'draw_contours': {'type': 'bool', 'default': True, 'label': '绘制保留轮廓', 'tooltip': '是否在调试图像上画出经过面积过滤后保留下来的轮廓。'},
        }

    def get_description(self) -> str:
        return "根据轮廓的面积进行过滤。只保留面积在 `min_area` 和 `max_area` 之间的轮廓。"

    def _execute(self, context: CvPipelineContext, min_area: int = 0, max_area: int = 10000, draw_contours: bool = True, **kwargs):
        if not context.contours:
            context.analysis_results.append("没有轮廓可供过滤")
            return

        filtered_contours = []
        for i, contour in enumerate(context.contours):
            area = cv2.contourArea(contour)
            if min_area <= area <= max_area:
                filtered_contours.append(contour)
                context.analysis_results.append(f"轮廓 {i} 面积: {area} (保留)")
            else:
                context.analysis_results.append(f"轮廓 {i} 面积: {area} (过滤)")
        
        context.contours = filtered_contours
        if not filtered_contours:
            context.success = False
        context.analysis_results.append(f"按面积过滤后剩余 {len(filtered_contours)} 个轮廓")
        if context.debug_mode and draw_contours:
            # 重新绘制轮廓
            display_with_contours = context.display_image.copy()
            cv2.drawContours(display_with_contours, filtered_contours, -1, (0, 255, 0), 2)
            context.display_image = display_with_contours


class CvStepFilterByArcLength(CvStep):

    def __init__(self):
        super().__init__('按周长过滤')

    def get_params(self) -> Dict[str, Any]:
        return {
            'closed': {'type': 'bool', 'default': True, 'label': '轮廓是否闭合', 'tooltip': '计算周长时是否将轮廓视为闭合曲线。'},
            'min_length': {'type': 'int', 'default': 0, 'range': (0, 10000), 'label': '最小周长', 'tooltip': '轮廓的最小周长。小于此值的轮廓将被过滤。'},
            'max_length': {'type': 'int', 'default': 1000, 'range': (0, 10000), 'label': '最大周长', 'tooltip': '轮廓的最大周长。大于此值的轮廓将被过滤。'},
            'draw_contours': {'type': 'bool', 'default': True, 'label': '绘制保留轮廓', 'tooltip': '是否在调试图像上画出经过周长过滤后保留下来的轮廓。'},
        }

    def get_description(self) -> str:
        return "根据轮廓的周长进行过滤。`closed`指定轮廓是否闭合。只保留周长在 `min_length` 和 `max_length` 之间的轮廓。"

    def _execute(self, context: CvPipelineContext, closed: bool = True, min_length: int = 0, max_length: int = 1000, draw_contours: bool = True, **kwargs):
        if not context.contours:
            context.analysis_results.append("没有轮廓可供过滤")
            return
        
        filtered_contours = []
        for i, contour in enumerate(context.contours):
            length = cv2.arcLength(contour, closed)
            if min_length <= length <= max_length:
                filtered_contours.append(contour)
                context.analysis_results.append(f"轮廓 {i} 周长: {length:.2f} (保留)")
            else:
                context.analysis_results.append(f"轮廓 {i} 周长: {length:.2f} (过滤)")

        context.contours = filtered_contours
        if not filtered_contours:
            context.success = False
        context.analysis_results.append(f"按周长过滤后剩余 {len(filtered_contours)} 个轮廓")
        if context.debug_mode and draw_contours:
            # 重新绘制轮廓
            display_with_contours = context.display_image.copy()
            cv2.drawContours(display_with_contours, filtered_contours, -1, (0, 255, 0), 2)
            context.display_image = display_with_contours


class CvStepFilterByRadius(CvStep):

    def __init__(self):
        super().__init__('按半径过滤')

    def get_params(self) -> Dict[str, Any]:
        return {
            'min_radius': {'type': 'int', 'default': 0, 'range': (0, 1000), 'label': '最小半径', 'tooltip': '轮廓的最小外接圆半径。小于此值的轮廓将被过滤。'},
            'max_radius': {'type': 'int', 'default': 100, 'range': (0, 1000), 'label': '最大半径', 'tooltip': '轮廓的最小外接圆半径。大于此值的轮廓将被过滤。'},
            'draw_circle': {'type': 'bool', 'default': True, 'label': '绘制外接圆', 'tooltip': '是否在调试图像上画出保留轮廓的最小外接圆。'},
        }

    def get_description(self) -> str:
        return "根据轮廓的最小外接圆半径进行过滤。`draw_circle`决定是否画出外接圆。只保留半径在 `min_radius` 和 `max_radius` 之间的轮廓。"

    def _execute(self, context: CvPipelineContext, min_radius: int = 0, max_radius: int = 100, draw_circle: bool = True, **kwargs):
        if not context.contours:
            context.analysis_results.append("没有轮廓可供过滤")
            return

        filtered_contours = []
        circles_to_draw = []
        for i, contour in enumerate(context.contours):
            (x, y), radius = cv2.minEnclosingCircle(contour)
            if min_radius <= radius <= max_radius:
                filtered_contours.append(contour)
                context.analysis_results.append(f"轮廓 {i} 半径: {radius:.2f} (保留)")
                if context.debug_mode and draw_circle:
                    circles_to_draw.append(((int(x), int(y)), int(radius)))
            else:
                context.analysis_results.append(f"轮廓 {i} 半径: {radius:.2f} (过滤)")

        context.contours = filtered_contours
        if not filtered_contours:
            context.success = False
        context.analysis_results.append(f"按半径过滤后剩余 {len(filtered_contours)} 个轮廓")

        if context.debug_mode:
            # 重新绘制保留的轮廓和圆
            display_with_drawings = context.display_image.copy()
            cv2.drawContours(display_with_drawings, filtered_contours, -1, (0, 255, 0), 2)
            for center, radius in circles_to_draw:
                cv2.circle(display_with_drawings, center, radius, (0, 0, 255), 2)
            context.display_image = display_with_drawings
class CvContourPropertiesStep(CvStep):

    def __init__(self):
        super().__init__('轮廓属性分析')

    def get_params(self) -> Dict[str, Any]:
        return {
            'show_bounding_box': {'type': 'bool', 'default': True, 'label': '显示外接矩形', 'tooltip': '是否在图像上用蓝色矩形框出每个轮廓。'},
            'show_center': {'type': 'bool', 'default': True, 'label': '显示质心', 'tooltip': '是否在图像上用红色点标出每个轮廓的质心。'},
        }

    def get_description(self) -> str:
        return "计算每个轮廓的详细几何属性，并将其输出到分析结果中。也会在图像上绘制辅助信息。"

    def _execute(self, context: CvPipelineContext, show_bounding_box: bool = True, show_center: bool = True, **kwargs):
        if not context.debug_mode:
            return  # 非调试模式直接跳过

        if not context.contours:
            context.analysis_results.append("没有轮廓可供分析")
            return

        display_with_props = context.display_image.copy()
        total_contours = len(context.contours)
        context.analysis_results.append(f"开始分析 {total_contours} 个轮廓的属性...")

        for i, contour in enumerate(context.contours):
            moments = cv2.moments(contour)
            if moments["m00"] == 0:
                continue  # 忽略面积为0的轮廓

            # 计算质心
            cx = int(moments["m10"] / moments["m00"])
            cy = int(moments["m01"] / moments["m00"])

            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = float(w) / h if h != 0 else 0

            result_str = (
                f"  [轮廓 {i}]: "
                f"面积={area:.2f}, "
                f"周长={perimeter:.2f}, "
                f"质心=({cx}, {cy}), "
                f"外接矩形=({x},{y},{w},{h}), "
                f"长宽比={aspect_ratio:.2f}"
            )
            context.analysis_results.append(result_str)

            # 绘制
            if show_bounding_box:
                cv2.rectangle(display_with_props, (x, y), (x + w, y + h), (255, 0, 0), 2)  # 蓝色矩形
            if show_center:
                cv2.circle(display_with_props, (cx, cy), 5, (0, 0, 255), -1)  # 红色中心点

        context.display_image = display_with_props
        context.analysis_results.append("轮廓属性分析完成。")
class CvMatchShapesStep(CvStep):

    def __init__(self):
        super().__init__('形状匹配')

    def get_params(self) -> Dict[str, Any]:
        return {
            'template_name': {'type': 'enum_template', 'default': '', 'label': '模板轮廓名称', 'tooltip': '用于形状比较的模板轮廓。'},
            'max_dissimilarity': {'type': 'float', 'default': 0.5, 'range': (0.0, 10.0), 'label': '最大差异度', 'tooltip': '形状差异度的上限。值越小表示形状越相似。只有差异度低于此值的轮廓才会被保留。'},
            'draw_contours': {'type': 'bool', 'default': True, 'label': '绘制匹配轮廓', 'tooltip': '是否在调试图像上画出形状匹配成功的轮廓。'},
        }

    def get_description(self) -> str:
        return "将输入轮廓与一个预存的模板轮廓进行形状匹配。返回值越小，形状越相似。"

    def _execute(self, context: CvPipelineContext, template_name: str = '', max_dissimilarity: float = 0.5, draw_contours: bool = True, **kwargs):
        if context.service is None:
            context.analysis_results.append(f"错误：CvService未初始化，无法加载模板")
            return

        template_contour = context.service.load_template_contour(template_name)

        if template_contour is None:
            context.analysis_results.append(f"错误：无法加载模板 {template_name}")
            return

        if not context.contours:
            context.analysis_results.append("没有轮廓可供匹配")
            return

        filtered_contours = []
        for i, contour in enumerate(context.contours):
            dissimilarity = cv2.matchShapes(template_contour, contour, cv2.CONTOURS_MATCH_I1, 0.0)
            if dissimilarity <= max_dissimilarity:
                filtered_contours.append(contour)
                context.analysis_results.append(f"轮廓 {i} 相似度: {dissimilarity:.4f} (保留)")
            else:
                context.analysis_results.append(f"轮廓 {i} 相似度: {dissimilarity:.4f} (过滤)")

        context.contours = filtered_contours
        if not filtered_contours:
            context.success = False
        context.analysis_results.append(f"按形状匹配后剩余 {len(filtered_contours)} 个轮廓")
        if context.debug_mode and draw_contours:
            # 重新绘制轮廓
            display_with_contours = context.display_image.copy()
            cv2.drawContours(display_with_contours, filtered_contours, -1, (0, 255, 0), 2)
            context.display_image = display_with_contours


class CvStepFilterByAspectRatio(CvStep):

    def __init__(self):
        super().__init__('按长宽比过滤')

    def get_params(self) -> Dict[str, Any]:
        return {
            'min_ratio': {'type': 'float', 'default': 0.0, 'range': (0.0, 100.0), 'label': '最小长宽比', 'tooltip': '外接矩形的最小长宽比 (宽/高)。低于此值的轮廓将被过滤。'},
            'max_ratio': {'type': 'float', 'default': 10.0, 'range': (0.0, 100.0), 'label': '最大长宽比', 'tooltip': '外接矩形的最大长宽比 (宽/高)。高于此值的轮廓将被过滤。'},
            'draw_contours': {'type': 'bool', 'default': True, 'label': '绘制保留轮廓', 'tooltip': '是否在调试图像上画出经过长宽比过滤后保留下来的轮廓。'},
        }

    def get_description(self) -> str:
        return "根据轮廓的长宽比进行过滤。长宽比计算方式为 `外接矩形宽度 / 高度`。"

    def _execute(self, context: CvPipelineContext, min_ratio: float = 0.0, max_ratio: float = 10.0, draw_contours: bool = True, **kwargs):
        if not context.contours:
            context.analysis_results.append("没有轮廓可供过滤")
            return

        filtered_contours = []
        for i, contour in enumerate(context.contours):
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / h if h > 0 else 0
            if min_ratio <= aspect_ratio <= max_ratio:
                filtered_contours.append(contour)
                context.analysis_results.append(f"轮廓 {i} 长宽比: {aspect_ratio:.2f} (保留)")
            else:
                context.analysis_results.append(f"轮廓 {i} 长宽比: {aspect_ratio:.2f} (过滤)")

        context.contours = filtered_contours
        if not filtered_contours:
            context.success = False
        context.analysis_results.append(f"按长宽比过滤后剩余 {len(filtered_contours)} 个轮廓")
        if context.debug_mode and draw_contours:
            # 重新绘制轮廓
            display_with_contours = context.display_image.copy()
            cv2.drawContours(display_with_contours, filtered_contours, -1, (0, 255, 0), 2)
            context.display_image = display_with_contours


class CvTemplateMatchingStep(CvStep):

    def __init__(self):
        self.method_map = {
            'TM_CCOEFF_NORMED': cv2.TM_CCOEFF_NORMED,
            'TM_CCORR_NORMED': cv2.TM_CCORR_NORMED,
            'TM_SQDIFF_NORMED': cv2.TM_SQDIFF_NORMED,
        }
        super().__init__('模板匹配')

    def get_params(self) -> Dict[str, Any]:
        return {
            'template_name': {'type': 'enum_template_image', 'default': '', 'label': '模板图像名称', 'tooltip': '用于在原图中滑窗搜索的模板小图。'},
            'threshold': {'type': 'float', 'default': 0.8, 'range': (0.0, 1.0), 'label': '匹配置信度', 'tooltip': '匹配结果的置信度阈值。只有高于此值的匹配才会被接受。'},
            'method': {'type': 'enum', 'default': 'TM_CCOEFF_NORMED', 'options': list(self.method_map.keys()), 'label': '匹配算法', 'tooltip': '选择模板匹配的计算方法。'},
        }

    def get_description(self) -> str:
        return "在当前图像上寻找与模板图像最匹配的区域。这个步骤不依赖之前的二值化或轮廓步骤。"

    def _execute(self, context: CvPipelineContext, template_name: str = '', threshold: float = 0.8, method: str = 'TM_CCOEFF_NORMED', **kwargs):
        from one_dragon_qt.logic.image_analysis_logic import ImageAnalysisLogic
        logic = ImageAnalysisLogic()
        # TODO: 模板加载应该支持图像
        template_image = None # logic.load_template_image(template_name) 

        if template_image is None:
            context.analysis_results.append(f"错误：无法加载图像模板 {template_name}")
            return

        cv2_method = self.method_map.get(method)
        if cv2_method is None:
            context.analysis_results.append(f"错误：无效的匹配方法 {method}")
            return

        result = cv2.matchTemplate(context.display_image, template_image, cv2_method)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            h, w, _ = template_image.shape
            top_left = max_loc
            bottom_right = (top_left[0] + w, top_left[1] + h)
            
            # 在显示图像上绘制矩形
            cv2.rectangle(context.display_image, top_left, bottom_right, (0, 255, 255), 2)
            context.analysis_results.append(f"找到匹配，置信度 {max_val:.4f} at {top_left}")
        else:
            context.analysis_results.append(f"未找到足够置信度的匹配 (最高 {max_val:.4f})")
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


class CvStepFilterByCentroidDistance(CvStep):

    def __init__(self):
        super().__init__('按质心距离过滤')

    def get_params(self) -> Dict[str, Any]:
        return {
            'max_distance': {'type': 'int', 'default': 10, 'range': (0, 1000), 'label': '最大邻近距离', 'tooltip': '一个轮廓的质心到另一个轮廓质心的最大距离。若一个轮廓在此距离内没有任何邻居，则被视为孤立点并被过滤。'},
            'draw_contours': {'type': 'bool', 'default': True, 'label': '绘制保留轮廓', 'tooltip': '是否在调试图像上画出非孤立的轮廓。'},
        }

    def get_description(self) -> str:
        return "根据轮廓质心之间的距离进行过滤。如果一个轮廓在指定的`max_distance`内找不到任何其他轮廓的质心，它就会被过滤掉。"

    def _execute(self, context: CvPipelineContext, max_distance: int = 10, draw_contours: bool = True, **kwargs):
        if len(context.contours) < 2:
            context.analysis_results.append("轮廓数量不足2，跳过质心距离过滤")
            return

        # 1. 计算所有质心
        centroids = []
        for contour in context.contours:
            moments = cv2.moments(contour)
            if moments["m00"] != 0:
                cx = int(moments["m10"] / moments["m00"])
                cy = int(moments["m01"] / moments["m00"])
                centroids.append((cx, cy))
            else:
                centroids.append(None)  # 面积为0的轮廓

        # 2. 过滤
        filtered_contours = []
        retained_indices = []
        for i, contour in enumerate(context.contours):
            if centroids[i] is None:
                context.analysis_results.append(f"轮廓 {i} 面积为0 (过滤)")
                continue

            is_isolated = True
            for j, other_centroid in enumerate(centroids):
                if i == j or other_centroid is None:
                    continue
                
                dist = np.linalg.norm(np.array(centroids[i]) - np.array(other_centroid))
                if dist <= max_distance:
                    is_isolated = False
                    break
            
            if not is_isolated:
                filtered_contours.append(contour)
                retained_indices.append(str(i))

        context.analysis_results.append(f"轮廓 {', '.join(retained_indices) if retained_indices else '无'} 被保留")
        context.contours = filtered_contours
        if not filtered_contours:
            context.success = False
        context.analysis_results.append(f"按质心距离过滤后剩余 {len(filtered_contours)} 个轮廓")

        if context.debug_mode and draw_contours:
            display_with_contours = context.display_image.copy()
            cv2.drawContours(display_with_contours, filtered_contours, -1, (0, 255, 0), 2)
            context.display_image = display_with_contours


class CvStepOcr(CvStep):

    def __init__(self):
        super().__init__('OCR识别')

    def get_params(self) -> Dict[str, Any]:
        return {
            'draw_text_box': {'type': 'bool', 'default': True, 'label': '绘制识别结果', 'tooltip': '是否在调试图像上绘制OCR识别出的文本框和内容。'},
            'override_settings': {'type': 'bool', 'default': False, 'label': '覆盖全局配置', 'tooltip': '[核心] 是否启用此步骤的独立OCR配置。启用后，下方所有参数才会生效。'},

            # 从 OnnxOcrMatcher 的 ocr_options 同步过来的参数
            'use_gpu': {'type': 'bool', 'default': False, 'label': '使用GPU加速', 'tooltip': '是否使用GPU进行计算。修改此项会触发模型重载，可能需要等待片刻。'},
            'use_angle_cls': {'type': 'bool', 'default': False, 'label': '启用方向分类', 'tooltip': '是否启用180度方向分类。能识别颠倒的文字，但会轻微增加耗时。'},
            'det_limit_side_len': {'type': 'float', 'default': 960.0, 'range': (100.0, 2000.0), 'label': '检测图像边长', 'tooltip': 'OCR前会将图像缩放到最长边不超过此值。值越小速度越快，但可能丢失小文字。'},
            'det_db_thresh': {'type': 'float', 'default': 0.3, 'range': (0.0, 1.0), 'label': '检测-像素阈值', 'tooltip': '判断一个像素点是否属于文本区域的概率阈值。处理模糊文字时可适当调低。'},
            'det_db_box_thresh': {'type': 'float', 'default': 0.6, 'range': (0.0, 1.0), 'label': '检测-文本框阈值', 'tooltip': '将像素点组合成文本框的置信度阈值。如果漏字，可适当调低此值。'},
            'det_db_unclip_ratio': {'type': 'float', 'default': 1.5, 'range': (1.0, 4.0), 'label': '检测-文本框扩张', 'tooltip': '按比例扩张检测到的文本框。对于粘连或艺术字，调大此值有助于框住完整文字。'},
            'rec_batch_num': {'type': 'int', 'default': 6, 'range': (1, 32), 'label': '识别-批处理数', 'tooltip': '识别时一次处理的文本框数量。在GPU模式下，增加此值可提升性能。'},
            'max_text_length': {'type': 'int', 'default': 25, 'range': (5, 50), 'label': '识别-最大长度', 'tooltip': '限制单个文本框能识别出的最大字符数。'},
            'drop_score': {'type': 'float', 'default': 0.5, 'range': (0.0, 1.0), 'label': '识别-置信度过滤', 'tooltip': '只有识别可信度高于此值的文本才会被最终采纳。'},
            'cls_thresh': {'type': 'float', 'default': 0.9, 'range': (0.0, 1.0), 'label': '分类-方向置信度', 'tooltip': '方向分类器判断文本方向（0度或180度）的可信度阈值。'},
        }

    def get_description(self) -> str:
        return "对当前图像进行OCR识别。可临时覆盖全局OCR设置。"

    def _execute(self, context: CvPipelineContext,
                 draw_text_box: bool = True,
                 override_settings: bool = False,
                 # OCR options
                 use_gpu: bool = False,
                 use_angle_cls: bool = False,
                 det_limit_side_len: float = 960.0,
                 det_db_thresh: float = 0.3,
                 det_db_box_thresh: float = 0.6,
                 det_db_unclip_ratio: float = 1.5,
                 rec_batch_num: int = 6,
                 max_text_length: int = 25,
                 drop_score: float = 0.5,
                 cls_thresh: float = 0.9,
                 **kwargs):
        if context.ocr is None:
            context.analysis_results.append("错误: OCR 功能未初始化")
            return

        if override_settings:
            # 直接使用方法参数构建新配置
            new_options = {
                'use_gpu': use_gpu,
                'use_angle_cls': use_angle_cls,
                'det_limit_side_len': det_limit_side_len,
                'det_db_thresh': det_db_thresh,
                'det_db_box_thresh': det_db_box_thresh,
                'det_db_unclip_ratio': det_db_unclip_ratio,
                'rec_batch_num': rec_batch_num,
                'max_text_length': max_text_length,
                'drop_score': drop_score,
                'cls_thresh': cls_thresh,
            }
            context.analysis_results.append(f"应用OCR设置: {new_options}")
            context.ocr.update_options(new_options)

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


class CvStepCropByArea(CvStep):

    def __init__(self):
        super().__init__('按区域裁剪')

    def get_params(self) -> Dict[str, Any]:
        return {
            'screen_name': {'type': 'enum_screen_name', 'default': '', 'label': '画面名称', 'tooltip': '选择一个已定义的画面。'},
            'area_name': {'type': 'enum_area_name', 'default': '', 'label': '区域名称', 'tooltip': '选择该画面下的一个区域进行裁剪。', 'parent': 'screen_name'}
        }

    def get_description(self) -> str:
        return "根据画面和区域的名称，从画面配置中找到对应区域进行裁剪。"

    def _execute(self, context: CvPipelineContext, screen_name: str = '', area_name: str = '', **kwargs):
        if context.od_ctx is None or context.od_ctx.screen_loader is None:
            context.error_str = "错误: 缺少画面加载器 (ScreenLoader)"
            context.success = False
            return

        if not screen_name or not area_name:
            context.error_str = "错误: 未选择画面名称或区域名称"
            context.success = False
            return

        area = context.od_ctx.screen_loader.get_area(screen_name, area_name)
        if area is None:
            context.error_str = f"错误: 在画面 '{screen_name}' 中未找到区域 '{area_name}'"
            context.success = False
            return

        self._crop_image_and_update_context(context, area.rect, f"按区域 {screen_name}->{area_name} 裁剪")