import cv2
import numpy as np
from cv2.typing import MatLike

from one_dragon.utils import cv2_utils, mini_map_angle_utils
from zzz_od.context.zzz_context import ZContext


_TOTAL_VIEW_ANGLE: int = 105  # 光映广场 - 喵吉长官 往南走有大块空地 在这里截图多个取的平均值
_RADIUS_RANGE: tuple[float, float] = (0.2, 0.4)  # 计算视野角度时使用的半价范围


class MiniMapService:

    def __init__(
            self,
            ctx: ZContext,
    ):
        self.ctx: ZContext = ctx


    def cut_mini_map(self, screen: MatLike) -> MatLike:
        """
        截取小地图

        Args:
            screen: 游戏画面

        Returns:
            MatLike: 小地图图片
        """
        area = self.ctx.screen_loader.get_area('大世界', '小地图')
        return cv2_utils.crop_image_only(screen, area.rect)

    @staticmethod
    def get_view_mask(mini_map: MatLike, road_mask: MatLike | None = None) -> MatLike:
        # 使用hsv简单过滤的扇形
        hsv = cv2.cvtColor(mini_map, cv2.COLOR_RGB2HSV)
        view_mask = cv2.inRange(hsv, np.array([10, 60, 25]), np.array([25, 230, 150]))

        r, _, _ = cv2.split(mini_map)
        red_mask = cv2.inRange(r, np.array([50]), np.array([255]))
        view_mask = cv2.bitwise_and(view_mask, red_mask)
        return cv2.GaussianBlur(view_mask, (3, 3), 0)

    @staticmethod
    def cal_angle(mini_map: MatLike) -> float:
        """
        计算小地图上的视野朝向
        正右方为0度 逆时针为正

        Args:
            mini_map: 小地图图片

        Returns:
            float: 视野朝向角度
        """
        view_mask = MiniMapService.get_view_mask(mini_map)
        angle, _ = mini_map_angle_utils.calculate(view_mask, view_angle=_TOTAL_VIEW_ANGLE, radius_range=_RADIUS_RANGE)
        return angle

    @staticmethod
    def get_road_mask(mini_map: MatLike) -> MatLike:
        """
        获取道路mask

        Args:
            mini_map: 小地图

        Returns:
            MatLike: 道路mask
        """
        # 普通颜色过滤
        color_mask = cv2.inRange(mini_map, np.array([0, 0, 0]), np.array([50, 50, 50]))

        # rgb差值不超过3
        # 沿颜色通道（最后一个轴，axis=2）计算最大值和最小值
        max_channel = np.max(mini_map, axis=2)
        min_channel = np.min(mini_map, axis=2)

        # 计算最大与最小通道的差值，得到一个二维数组
        # 因为max_channel >= min_channel，所以结果不会是负数，无需取绝对值
        diff = max_channel - min_channel

        # 创建掩码，差值小于等于3的像素为True，否则为False
        # 然后将布尔值(True/False)转换为OpenCV期望的uint8格式（255/0）
        return (diff <= 3).astype(np.uint8) * 255


def __debug_total_angle(debug_image_name: str):
    ctx = ZContext()

    from one_dragon.utils import debug_utils
    screen = debug_utils.get_debug_image(debug_image_name)
    mini_map = ctx.mini_map_service.cut_mini_map(screen)

    mask = ctx.mini_map_service.get_view_mask(mini_map)
    _, results = mini_map_angle_utils.calculate_sector_angle(mask,radius_range=_RADIUS_RANGE,
                                                             debug_steps=True)
    from one_dragon.utils.mini_map_angle_visualizer import visualize_calculate_sector_angle
    visualize_calculate_sector_angle(mini_map, results)


def __debug_cal_angle(debug_image_name: str, save: bool = False):
    ctx = ZContext()

    from one_dragon.utils import debug_utils
    screen = debug_utils.get_debug_image(debug_image_name)
    mini_map = ctx.mini_map_service.cut_mini_map(screen)

    mask = ctx.mini_map_service.get_view_mask(mini_map)
    _, results = mini_map_angle_utils.calculate(mask, view_angle=_TOTAL_VIEW_ANGLE, radius_range=_RADIUS_RANGE, debug_steps=True)
    from one_dragon.utils.mini_map_angle_visualizer import visualize_calculate
    visualize_calculate(mini_map, results)

    if save:
        from one_dragon.utils import os_utils
        save_dir = os_utils.get_path_under_work_dir('zzz-od-test', 'test', 'zzz_od', 'context', 'test_mini_map_service', 'test_cal_angle')
        int_angle = int(results['view_angle'])
        idx: int = 1
        while True:
            file_name: str = f'{int_angle}_{idx}.png'
            import os
            file_path: str = os.path.join(save_dir, file_name)
            if os.path.exists(file_path):
                idx += 1
            else:
                break
        cv2_utils.save_image(mini_map, file_path)


if __name__ == '__main__':
    __debug_total_angle('_1752932914363')
    # __debug_cal_angle('ScreenshotHelperApp_1752932501766', save=True)
