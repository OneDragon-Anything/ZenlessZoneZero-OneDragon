import cv2
import numpy as np

from one_dragon.base.screen.template_info import get_template_raw_path, get_template_mask_path
from one_dragon.utils import cv2_utils
from zzz_od.context.zzz_context import ZContext


def extract_map_icon(
        ctx: ZContext,
        icon: str,
        color_range_list: list,
):
    template = ctx.template_loader.get_template('map', icon)
    color_mask_list = []
    for color_range in color_range_list:
        color_mask = cv2.inRange(template.raw,
                                 np.array(color_range[0], dtype=np.uint8),
                                 np.array(color_range[1], dtype=np.uint8)
                                 )
        color_mask_list.append(color_mask)

    merge_mask = None
    for color_mask in color_mask_list:
        if merge_mask is None:
            merge_mask = color_mask
        else:
            merge_mask = cv2.bitwise_or(merge_mask, color_mask)

    # 只裁剪有内容的部分
    bw = np.where(merge_mask == 255)
    white_pixel_coordinates = list(zip(bw[1], bw[0]))

    # 找到最大最小坐标值
    max_x = max(white_pixel_coordinates, key=lambda i: i[0])[0]
    max_y = max(white_pixel_coordinates, key=lambda i: i[1])[1]

    min_x = min(white_pixel_coordinates, key=lambda i: i[0])[0]
    min_y = min(white_pixel_coordinates, key=lambda i: i[1])[1]

    # 四边都留1像素的空白
    new_raw = np.zeros((max_y - min_y + 2, max_x - min_x + 2, 3), dtype=np.uint8)
    new_raw[1:-1, 1:-1, :] = template.raw[min_y:max_y, min_x:max_x, :]

    new_mask = np.zeros((max_y - min_y + 2, max_x - min_x + 2), dtype=np.uint8)
    new_mask[1:-1, 1:-1] = merge_mask[min_y:max_y, min_x:max_x]

    # 使用的时候有mask 这里不扣图也没所谓
    # new_raw = cv2.bitwise_and(new_raw, new_raw, mask=new_mask)

    cv2_utils.show_image(new_raw, win_name='new_raw', wait=0)

    cv2_utils.save_image(new_raw, get_template_raw_path('map', icon))
    cv2_utils.save_image(new_mask, get_template_mask_path('map', icon))
    cv2.destroyAllWindows()


def __debug_extract_map_icon(icon: str):
    ctx = ZContext()

    icon_map = {
        # 传送点
        '3d_map_tp_icon_1': [
            ((180, 180, 180), (255, 255, 255)),
            ((0, 0, 0), (20, 20, 20)),
        ],

        # 传送点
        '3d_map_tp_icon_2': [
            ((140, 140, 140), (255, 255, 255)),
        ],

        # 传送点
        'map_icon_01': [
            ((100, 100, 100), (255, 255, 255)),
        ],

        # 玛瑟尔档案
        'map_icon_02': [
            ((0, 90, 120), (60, 160, 180)),
            ((40, 170, 70), (60, 210, 100)),
        ],

        # 小卡格车
        'map_icon_03': [
            ((100, 100, 0), (170, 150, 80)),
            ((40, 170, 70), (60, 210, 100)),
        ],

        # 战斗图标
        'map_icon_04': [
            ((100, 0, 0), (180, 100, 100)),
            ((40, 170, 70), (60, 210, 100)),
        ],

        # 采集点
        'map_icon_05': [
            ((100, 80, 0), (170, 150, 80)),
            ((40, 170, 70), (60, 210, 100)),
        ],

        # 应该是机关桥
        'map_icon_06': [
            ((160, 160, 160), (230, 230, 230)),
        ],

        # 秽浊流界
        'map_icon_07': [
            ((160, 0, 0), (255, 255, 255)),
            ((0, 170, 0), (255, 255, 255)),
        ],

        # 以太同调
        'map_icon_08': [
            ((0, 0, 120), (255, 255, 255)),
            ((0, 170, 0), (255, 255, 255)),
        ],

        # 流浪邦布想知道
        'map_icon_09': [
            ((0, 0, 120), (255, 255, 255)),
            ((0, 170, 0), (255, 255, 255)),
        ],
    }

    extract_map_icon(ctx, icon, icon_map.get(icon, []))

if __name__ == '__main__':
    __debug_extract_map_icon('map_icon_09')