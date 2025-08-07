import io
import os

import cv2
import numpy as np
import requests
from PIL import Image
from cv2.typing import MatLike

from one_dragon.utils import os_utils, cv2_utils, debug_utils

IMAGE_URL_MAP = {
    'HKC_ZYZZQ_DLDC': 'https://act-upload.mihoyo.com/nap-obc-indep/2025/06/26/76099754/c3474736e3ff2b10ea0a46dee0604f89_2135290461906531157.png'
}


def get_map_image(image_url: str, resize: int = 120) -> MatLike:
    """
    获取地图图片
    已验证米游社的图片和真实游戏的有差异
    :param image_url: 图片链接
    :param resize: 缩放比例
    :return: 地图图片
    """
    url = f'{image_url}?x-oss-process=image/resize,p_{resize}'
    response = requests.get(url, stream=True)
    image_data = io.BytesIO(response.content)
    pil_image = Image.open(image_data)
    numpy_image = np.array(pil_image)
    if numpy_image.shape[2] == 4:  # RGBA image
        rgb = cv2.cvtColor(numpy_image, cv2.COLOR_RGBA2RGB)
    else:
        rgb = numpy_image

    road_mask = cv2.inRange(rgb, np.array([0, 0, 0]), np.array([30, 30, 30]))
    # 拓展边缘 四周至少要有一个小地图的距离
    # 计算 road_mask 中白色区域的边界框 (bounding box)
    coords = np.argwhere(road_mask > 0)

    min_y, min_x = coords.min(axis=0)
    max_y, max_x = coords.max(axis=0)

    # 计算需要向四周拓展的像素值，确保边缘有至少200像素的距离
    h, w = road_mask.shape
    margin = 200
    pad_top = max(0, margin - min_y)
    pad_bottom = max(0, margin - (h - 1 - max_y))
    pad_left = max(0, margin - min_x)
    pad_right = max(0, margin - (w - 1 - max_x))

    # 使用 cv2.copyMakeBorder 拓展原始图像
    border_value = [210, 210, 210]
    return cv2.copyMakeBorder(rgb, pad_top, pad_bottom, pad_left, pad_right,
                              cv2.BORDER_CONSTANT, value=border_value)


def get_area_map_image(area_id: str, resize: int = 120) -> MatLike:
    """
    获取某个区域的图片

    Args:
        area_id:
        resize:

    Returns:

    """
    save_dir = os_utils.get_path_under_work_dir('.debug', 'mys_large_map', area_id)
    file_name = f'{resize}.png'
    file_path = os.path.join(save_dir, file_name)
    if os.path.exists(file_path):
        return cv2_utils.read_image(file_path)
    else:
        image = get_map_image(IMAGE_URL_MAP[area_id], resize)
        cv2_utils.save_image(image, file_path)
        return image


def match_large_map_size(area_id: str, mini_map: MatLike) -> int:
    """
    匹配合适的大地图缩放比例

    Args:
        area_id:
        mini_map:

    Returns:

    """
    mask = cv2.inRange(mini_map, np.array([0, 0, 0]), np.array([30, 30, 30]))
    cv2_utils.show_image(mask, win_name='mm')
    for resize in range(120, 160):
        large_map = get_area_map_image(area_id, resize)
        source_mask = cv2.inRange(large_map, np.array([0, 0, 0]), np.array([30, 30, 30]))
        mrl = cv2_utils.match_template(
            source_mask[-400:, :],
            mask,
            threshold=0.1,
            # mask=mask,
            ignore_inf=True,
        )
        cv2_utils.show_image(source_mask[-400:, :], rects=mrl)
        cv2_utils.show_overlap(large_map[-400:, :], mini_map, mrl.max.x, mrl.max.y, win_name=f'overlap_{resize}', wait=0)


if __name__ == '__main__':
    mm = debug_utils.get_debug_image('94_1')
    match_large_map_size('HKC_ZYZZQ_DLDC', mm)