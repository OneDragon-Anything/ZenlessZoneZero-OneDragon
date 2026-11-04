from pathlib import Path
from typing import ClassVar

import cv2
import numpy as np
import onnxruntime as ort
from cv2.typing import MatLike

from one_dragon.utils import yolo_config_utils
from one_dragon.yolo.onnx_model_loader import OnnxModelLoader


class LostVoidDepthEstimator(OnnxModelLoader):
    """
    迷失之地寻路避障用的单目深度模型 Depth Anything V2 Small
    用法：估计每个方向「脚下能走多远」
    - 平地上模型输出的逆深度 d 随画面行 y 线性变化 d = a*y + b 越往上越远
    - 墙、栏杆、箱子这类立着的东西 往上看 d 不再变小 竖直方向的变化率明显小于地面
    - 每列从下往上扫 第一个立着的东西所在的行 就是这个方向能走到的位置 行越靠下越近
    局限：角色正前方脚下被角色身体挡住 角色所在的列只能从头顶往上看
    模型在资源管理页下载 对应 config/repository.yml 的 lost_void_depth
    """

    MODEL_CATEGORY: ClassVar[str] = 'lost_void_depth'  # 与 config/repository.yml 里的模型资源名一致
    MODEL_NAME: ClassVar[str] = 'depth-anything-v2-small'

    INPUT_W: ClassVar[int] = 518  # 14 的倍数 接近 16:9
    INPUT_H: ClassVar[int] = 294
    MEAN: ClassVar[np.ndarray] = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    STD: ClassVar[np.ndarray] = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    ANALYSIS_SCALE: ClassVar[int] = 4  # 分析时把 1080p 缩小的倍数

    # 以下坐标都是 1080p 下的值
    COLUMN_X1: ClassVar[int] = 160  # 参与分析的横向范围
    COLUMN_X2: ClassVar[int] = 1760
    COLUMN_NUM: ClassVar[int] = 16
    SCAN_Y_START: ClassVar[int] = 1000  # 每列从这一行往上扫
    SCAN_Y_STOP: ClassVar[int] = 300  # 扫到这一行为止 再往上基本是远处背景
    CHARACTER_RECT: ClassVar[tuple[int, int, int, int]] = (820, 420, 1100, 1080)  # 角色所在区域 这几列从头顶开始扫
    CHARACTER_MARGIN: ClassVar[int] = 40  # 列中心离角色区域这么近也算角色所在的列
    HUD_X: ClassVar[int] = 1300  # 右下角技能按钮 这片区域的列从 HUD_Y 开始扫
    HUD_Y: ClassVar[int] = 760
    GROUND_FIT_Y1: ClassVar[int] = 650  # 用来拟合地面的行范围 角色两侧画面下方
    GROUND_FIT_Y2: ClassVar[int] = 1000
    GROUND_FIT_X_LIST: ClassVar[list[tuple[int, int]]] = [(200, 780), (1140, 1300)]  # 拟合地面的横向范围 避开角色和技能按钮

    SLOPE_STEP: ClassVar[int] = 4  # 竖直变化率按相隔几行(分析分辨率)计算
    SLOPE_RATIO: ClassVar[float] = 0.35  # 竖直变化率低于地面的这个比例 算立着的东西
    MIN_RUN: ClassVar[int] = 6  # 连续这么多行(分析分辨率)都是立着的 才算障碍 过滤噪点
    NEAR_ROW: ClassVar[int] = 600  # 障碍所在行不高于画面这一行(数值更大) 算近处挡路

    MIN_INTERVAL: ClassVar[float] = 0.3  # 两次推理的最小间隔 期间复用上次结果

    AIM_DIR_COST: ClassVar[int] = 15  # 选瞄准列时 每偏离目标一列相当于障碍近多少行
    AIM_KEEP_MARGIN: ClassVar[int] = 30  # 上次选的列仍不挡路 且代价比最优列多不超过这么多 就继续用 避免左右来回摆

    def __init__(self):
        """
        只用 GPU 推理 调用前先用 is_gpu_available 确认有 GPU 提供程序 用 is_model_existed 确认模型已下载 不走自动下载
        """
        OnnxModelLoader.__init__(
            self,
            model_name=LostVoidDepthEstimator.MODEL_NAME,
            model_download_url='',
            model_parent_dir_path=yolo_config_utils.get_model_category_dir(LostVoidDepthEstimator.MODEL_CATEGORY),
            gpu=True,
        )

        self._last_run_time: float = 0  # 上一次推理的时间
        self._last_rows: list[int] = []  # 上一次推理的每列障碍所在行

    @staticmethod
    def is_model_existed() -> bool:
        """
        深度模型是否已下载
        """
        model_dir = Path(yolo_config_utils.get_model_category_dir(LostVoidDepthEstimator.MODEL_CATEGORY))
        return (model_dir / LostVoidDepthEstimator.MODEL_NAME / 'model.onnx').exists()

    @staticmethod
    def is_gpu_available() -> bool:
        """
        是否有可用的 GPU 执行提供程序 OnnxModelLoader 没有时会悄悄退回 CPU 深度模型每帧都要推理 CPU 跑不动 所以这里要提前判断
        """
        availables = ort.get_available_providers()
        return 'CUDAExecutionProvider' in availables or 'DmlExecutionProvider' in availables

    @staticmethod
    def choose_aim_column(rows: list[int], target_idx: int, prev_idx: int | None, max_offset: int) -> int | None:
        """
        目标所在的列近处挡路时 在目标附近挑一列作为瞄准点
        每一列的代价 = 障碍所在行(越大越近) + 偏离目标的列数 × AIM_DIR_COST 取代价最小的不挡路列
        上次选的列还不挡路 且代价和最优列相差不大时继续用它 避免来回摆
        角色所在的列只能从头顶往上看 看不到脚下 不作为候选
        :param rows: 每列障碍所在行 get_column_obstacle_rows 的结果
        :param target_idx: 目标所在的列
        :param prev_idx: 上次选的列 没有时为空
        :param max_offset: 最多偏离目标几列
        :return: 目标所在列不挡路 或者附近没有不挡路的列时返回 None 不需要偏转
        """
        if len(rows) == 0 or not LostVoidDepthEstimator.is_near_blocked(rows[target_idx]):
            return None

        char_y1 = LostVoidDepthEstimator.CHARACTER_RECT[1]
        cost_map: dict[int, int] = {}
        for i in range(max(target_idx - max_offset, 0), min(target_idx + max_offset, len(rows) - 1) + 1):
            if LostVoidDepthEstimator.is_near_blocked(rows[i]) or LostVoidDepthEstimator.get_scan_start(i) == char_y1:
                continue
            cost_map[i] = rows[i] + abs(i - target_idx) * LostVoidDepthEstimator.AIM_DIR_COST
        if len(cost_map) == 0:
            return None

        best_idx = min(cost_map, key=lambda i: cost_map[i])
        if prev_idx in cost_map and cost_map[prev_idx] <= cost_map[best_idx] + LostVoidDepthEstimator.AIM_KEEP_MARGIN:
            return prev_idx
        return best_idx

    def estimate_disparity(self, screen: MatLike) -> np.ndarray:
        """
        模型输出的逆深度 越大越近 缩放到分析分辨率
        :param screen: 游戏画面 RGB
        """
        resized = cv2.resize(screen, (LostVoidDepthEstimator.INPUT_W, LostVoidDepthEstimator.INPUT_H),
                             interpolation=cv2.INTER_CUBIC)
        x = (resized.astype(np.float32) / 255.0 - LostVoidDepthEstimator.MEAN) / LostVoidDepthEstimator.STD
        x = np.transpose(x, (2, 0, 1))[np.newaxis, ...]

        disparity = self.run_session(self.output_names, {self.input_names[0]: x})[0][0]

        scale = LostVoidDepthEstimator.ANALYSIS_SCALE
        return cv2.resize(disparity, (screen.shape[1] // scale, screen.shape[0] // scale),
                          interpolation=cv2.INTER_LINEAR)

    @staticmethod
    def fit_ground_slope(disparity: np.ndarray) -> float:
        """
        用角色两侧画面下方的地面拟合 d = a*y + b 返回地面的竖直变化率 a
        每行取中位数后直线拟合 去掉偏离大的行再拟合几次 减少障碍物的影响
        """
        scale = LostVoidDepthEstimator.ANALYSIS_SCALE
        y_list: list[float] = []
        value_list: list[float] = []
        for y in range(LostVoidDepthEstimator.GROUND_FIT_Y1 // scale, LostVoidDepthEstimator.GROUND_FIT_Y2 // scale):
            row = np.concatenate([disparity[y, x1 // scale:x2 // scale]
                                  for x1, x2 in LostVoidDepthEstimator.GROUND_FIT_X_LIST])
            y_list.append(y)
            value_list.append(float(np.median(row)))

        ys = np.array(y_list, dtype=np.float32)
        values = np.array(value_list, dtype=np.float32)
        a, b = np.polyfit(ys, values, 1)
        for _ in range(3):
            residual = np.abs(values - (a * ys + b))
            keep = residual < max(float(np.median(residual)) * 2.5, 1e-6)
            a, b = np.polyfit(ys[keep], values[keep], 1)
        return float(a)

    def get_column_obstacle_rows(self, screen: MatLike, screenshot_time: float) -> list[int]:
        """
        每列从下往上第一个立着的东西所在的行(1080p) 行越大越近 一直扫到顶都没有时为 SCAN_Y_STOP
        距离上次推理不足 MIN_INTERVAL 时直接返回上次结果
        :param screen: 游戏画面 RGB
        :param screenshot_time: 截图时间
        :return: 地面拟合失败(比如技能特效铺满画面)时返回空列表 表示这一帧无法判断
        """
        if screenshot_time - self._last_run_time < LostVoidDepthEstimator.MIN_INTERVAL:
            return self._last_rows

        disparity = self.estimate_disparity(screen)
        ground_slope = LostVoidDepthEstimator.fit_ground_slope(disparity)
        rows: list[int] = []
        if ground_slope > 0:  # 正常地面越往下越近 拟合出来不是正数说明画面被遮挡
            rows = LostVoidDepthEstimator.scan_columns(disparity, ground_slope)

        self._last_run_time = screenshot_time
        self._last_rows = rows
        return rows

    @staticmethod
    def scan_columns(disparity: np.ndarray, ground_slope: float) -> list[int]:
        """
        每列从下往上扫 竖直变化率连续 MIN_RUN 行低于地面的 SLOPE_RATIO 就是立着的东西
        """
        scale = LostVoidDepthEstimator.ANALYSIS_SCALE
        step = LostVoidDepthEstimator.SLOPE_STEP
        slope = np.zeros_like(disparity)
        slope[:-step] = (disparity[step:] - disparity[:-step]) / step
        is_vertical = slope < ground_slope * LostVoidDepthEstimator.SLOPE_RATIO

        rows: list[int] = []
        for i in range(LostVoidDepthEstimator.COLUMN_NUM):
            x1, x2 = LostVoidDepthEstimator.get_column_range(i)
            # 一行里过半像素是立着的 这一行才算立着
            column_vertical = np.mean(is_vertical[:, x1 // scale:x2 // scale], axis=1) > 0.5

            run = 0
            hit_row = LostVoidDepthEstimator.SCAN_Y_STOP
            for y in range(LostVoidDepthEstimator.get_scan_start(i) // scale,
                           LostVoidDepthEstimator.SCAN_Y_STOP // scale, -1):
                if not column_vertical[y]:
                    run = 0
                    continue
                run += 1
                if run >= LostVoidDepthEstimator.MIN_RUN:
                    hit_row = (y + run) * scale
                    break
            rows.append(hit_row)
        return rows

    @staticmethod
    def get_scan_start(idx: int) -> int:
        """
        第 idx 列开始往上扫的行 角色挡住的列从头顶开始 技能按钮挡住的列从按钮上方开始
        """
        x1, x2 = LostVoidDepthEstimator.get_column_range(idx)
        center_x = (x1 + x2) / 2
        char_x1, char_y1, char_x2, _ = LostVoidDepthEstimator.CHARACTER_RECT
        margin = LostVoidDepthEstimator.CHARACTER_MARGIN
        if char_x1 - margin < center_x < char_x2 + margin:
            return char_y1
        if center_x > LostVoidDepthEstimator.HUD_X:
            return LostVoidDepthEstimator.HUD_Y
        return LostVoidDepthEstimator.SCAN_Y_START

    @staticmethod
    def is_near_blocked(row: int) -> bool:
        """
        障碍所在行是否算近处挡路
        """
        return row >= LostVoidDepthEstimator.NEAR_ROW

    @staticmethod
    def get_column_range(idx: int) -> tuple[int, int]:
        """
        第 idx 列在 1080p 下的横向范围
        """
        col_w = (LostVoidDepthEstimator.COLUMN_X2 - LostVoidDepthEstimator.COLUMN_X1) / LostVoidDepthEstimator.COLUMN_NUM
        return (int(LostVoidDepthEstimator.COLUMN_X1 + idx * col_w),
                int(LostVoidDepthEstimator.COLUMN_X1 + (idx + 1) * col_w))

    @staticmethod
    def get_column_idx(x: float) -> int:
        """
        1080p 下横坐标 x 所在的列 超出分析范围时取最边上的列
        """
        col_w = (LostVoidDepthEstimator.COLUMN_X2 - LostVoidDepthEstimator.COLUMN_X1) / LostVoidDepthEstimator.COLUMN_NUM
        idx = int((x - LostVoidDepthEstimator.COLUMN_X1) // col_w)
        return min(max(idx, 0), LostVoidDepthEstimator.COLUMN_NUM - 1)
