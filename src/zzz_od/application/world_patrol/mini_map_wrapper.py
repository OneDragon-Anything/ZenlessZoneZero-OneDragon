from functools import cached_property

import cv2
import numpy as np
from cv2.typing import MatLike

from one_dragon.utils import mini_map_angle_utils

TOTAL_VIEW_ANGLE: int = 105  # 光映广场 - 喵吉长官 往南走有大块空地 在这里截图多个取的平均值
RADIUS_RANGE: tuple[float, float] = (0.2, 0.4)  # 计算视野角度时使用的半价范围


class MiniMapWrapper:

    def __init__(self, rgb: MatLike):
        self.rgb: MatLike = rgb
        self.kernel = np.ones((3, 3), np.uint8)

    @cached_property
    def _yuv_and_channels(self) -> tuple[MatLike, list[MatLike]]:
        yuv = cv2.cvtColor(self.rgb, cv2.COLOR_RGB2YUV)
        channels = cv2.split(yuv)
        return yuv, list(channels)

    @cached_property
    def yuv(self) -> MatLike:
        return self._yuv_and_channels[0]

    @cached_property
    def yuv_y(self) -> MatLike:
        return self._yuv_and_channels[1][0]

    @cached_property
    def yuv_u(self) -> MatLike:
        return self._yuv_and_channels[1][1]

    @cached_property
    def yuv_v(self) -> MatLike:
        return self._yuv_and_channels[1][2]

    @cached_property
    def _hsv_and_channels(self) -> tuple[MatLike, list[MatLike]]:
        hsv = cv2.cvtColor(self.rgb, cv2.COLOR_RGB2HSV)
        channels = cv2.split(hsv)
        return hsv, list(channels)

    @cached_property
    def hsv(self) -> MatLike:
        return self._hsv_and_channels[0]

    @cached_property
    def hsv_h(self) -> MatLike:
        return self._hsv_and_channels[1][0]

    @cached_property
    def hsv_s(self) -> MatLike:
        return self._hsv_and_channels[1][1]

    @cached_property
    def hsv_v(self) -> MatLike:
        return self._hsv_and_channels[1][2]

    @cached_property
    def view_mask(self) -> MatLike:
        """视野区域的扇形"""
        u = self.yuv_u
        v = self.yuv_v
        u_mask = cv2.inRange(u, np.array([100]), np.array([110]))
        v_mask = cv2.inRange(v, np.array([140]), np.array([150]))
        view_mask = cv2.bitwise_or(u_mask, v_mask)
        # 填充白色区域内部的小黑洞，让扇形区域变得更加完整和连通。可以想象成它会“关闭”物体上的小裂缝。
        view_mask = cv2.morphologyEx(view_mask, cv2.MORPH_CLOSE, self.kernel)
        # 移除背景中的孤立白点（噪声），让背景更干净。可以想象成它会“开启”物体之间的狭窄连接，抹去小杂物。
        view_mask = cv2.morphologyEx(view_mask, cv2.MORPH_OPEN, self.kernel)
        # 让扇形区域的边缘从锐利的黑白分界线，变成一个平滑过渡的灰色地带。
        return cv2.GaussianBlur(view_mask, (3, 3), 0)

    @cached_property
    def view_angle(self) -> float:
        """视野朝向 正右=0 逆时针=加"""
        return mini_map_angle_utils.calculate(view_mask = self.view_mask, view_angle=TOTAL_VIEW_ANGLE, radius_range=RADIUS_RANGE)[0]

    @cached_property
    def road_mask(self) -> MatLike:
        """道路部分 中间正方形区域"""
        road_mask = cv2.inRange(self.rgb, np.array([0, 0, 0]), np.array([40, 40, 40]))

        rgb_max = np.max(self.rgb, axis=2)
        rgb_min = np.min(self.rgb, axis=2)
        diff_mask = (rgb_max - rgb_min) > 5
        road_mask[diff_mask] = 0

        # 只要圆圈以内的
        road_mask = cv2.bitwise_and(road_mask, self.circle_mask)

        # CLAHE 可以让道路更有辨识度 但背景亮时 会让灰色带变得更亮 颜色偏差很大 很难选择
        # clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(3, 3))
        # road_mask = clahe.apply(self.yuv_y)
        # road_mask = cv2.inRange(road_mask, np.array([0]), np.array([30]))

        road_mask = cv2.bitwise_or(road_mask, self.player_mask)
        # 填充白色区域内部的小黑洞，让扇形区域变得更加完整和连通。可以想象成它会“关闭”物体上的小裂缝。
        road_mask = cv2.morphologyEx(road_mask, cv2.MORPH_CLOSE, self.kernel)
        # 移除背景中的孤立白点（噪声），让背景更干净。可以想象成它会“开启”物体之间的狭窄连接，抹去小杂物。
        road_mask = cv2.morphologyEx(road_mask, cv2.MORPH_OPEN, self.kernel)
        return road_mask

    @cached_property
    def player_mask(self) -> MatLike:
        # 步骤1: HSV 颜色范围过滤
        # 根据docstring中的 hsv_color 和 hsv_diff 计算上下限
        # H: 24 ± 10 => [14, 34]
        # S: 180 ± 90 => [90, 270] -> 裁剪到OpenCV范围 [90, 255]
        # V: 255 ± 80 => [175, 335] -> 裁剪到OpenCV范围 [175, 255]
        lower_bound = np.array([14, 90, 175])
        upper_bound = np.array([34, 255, 255])
        hsv_mask = cv2.inRange(self.hsv, lower_bound, upper_bound)

        # 步骤2: 查找轮廓
        # RETR_EXTERNAL: 只检测最外层的轮廓
        # CHAIN_APPROX_SIMPLE: 压缩水平、垂直和对角线段，只保留其端点
        contours, _ = cv2.findContours(hsv_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 步骤3-5: 过滤轮廓
        filtered_contours = []
        for contour in contours:
            # 按周长过滤
            perimeter = cv2.arcLength(contour, True)
            if not (60 <= perimeter <= 70):
                continue

            # 按面积过滤
            area = cv2.contourArea(contour)
            if not (240 <= area <= 300):
                continue

            # 如果所有检查都通过，则认为是目标轮廓
            filtered_contours.append(contour)

        # 步骤6: 创建最终掩码
        # 创建一个与原图同样大小的黑色背景
        h, w = self.rgb.shape[:2]
        final_mask = np.zeros((h, w), dtype=np.uint8)

        # 如果找到了符合条件的轮廓，就将其填充为白色
        if filtered_contours:
            # 将所有找到的轮廓画到掩码上（通常只会找到一个）
            cv2.drawContours(final_mask, filtered_contours, -1, 255, thickness=cv2.FILLED)

        return final_mask

    @cached_property
    def play_mask_found(self) -> bool:
        """
        Returns:
            bool: 是否能找到玩家的指标
        """
        return np.sum(np.where(self.player_mask > 0)) > 50

    @cached_property
    def circle_mask(self) -> MatLike:
        """
        Returns:
            MatLike: 圆形的掩码图
        """
        r = self.rgb.shape[0] // 2
        circle_mask: MatLike = np.zeros((self.rgb.shape[0], self.rgb.shape[1]), dtype=np.uint8)
        cv2.circle(circle_mask, [r, r], r - 7, [255], -1)
        cv2.circle(circle_mask, [207, 189], 50, [0], -1)
        return circle_mask
