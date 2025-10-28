import base64
import math
import os
from typing import Union, List, Optional, Tuple

import cv2
import numpy as np
from cv2.typing import MatLike

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.matcher.match_result import MatchResultList, MatchResult

feature_detector = cv2.SIFT_create()


def read_image(file_path: str) -> Optional[MatLike]:
    """
    读取图片
    :param file_path: 图片路径
    :return:
    """
    if not os.path.exists(file_path):
        return None
    file_type = get_image_file_type(file_path)

    # 默认以BGR格式加载
    if file_type == 'webp':
        image = cv2.imread(file_path, cv2.IMREAD_COLOR)
    else:
        image = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)

    if image.ndim == 2:
        return image
    elif image.ndim == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    elif image.ndim == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
    else:
        return image


def save_image(img: MatLike, file_path: str) -> None:
    """
    保存图片
    :param img: RBG格式的图片
    :param file_path: 保存路径
    """
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    file_type = get_image_file_type(file_path)
    if file_type == 'webp':  # 无损压缩保存
        cv2.imwrite(file_path, img, [cv2.IMWRITE_WEBP_QUALITY, 100])
    else:
        cv2.imwrite(file_path, img)


def get_image_file_type(file_path: str) -> str:
    """
    从文件完整路径中提取文件类型

    Args:
        file_path: 文件路径

    Returns:
        str: 文件类型
    """
    return os.path.splitext(file_path)[1][1:]


def show_image(
        img: MatLike,
        rects: Union[MatchResult, MatchResultList, list[Rect]] = None,
        win_name: str = 'DEBUG',
        wait: Optional[int] = None,
        destroy_after: bool = False,
        max_width: int | None = None,
        max_height: int | None = None,
):
    """
    显示一张图片
    Args:
        img: 图片
        rects: 需要画出来的框
        win_name: 显示图片的窗口名称
        wait: 显示后等待按键的秒数 0=一直等待
        destroy_after: 显示后销毁窗口
        max_width: 显示的最大宽度，图片宽度超过这个宽度则等比例缩小
        max_height: 显示的最大高度，图片高度超过这个高度则等比例缩小

    Returns:

    """

    """
    显示一张图片
    :param img: 图片
    :param rects: 需要画出来的框
    :param win_name:
    :param wait: 显示后等待按键的秒数
    :param destroy_after: 显示后销毁窗口
    :return:
    """
    to_show = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    if rects is not None:
        if type(rects) == MatchResult:
            cv2.rectangle(to_show, (rects.x, rects.y), (rects.x + rects.w, rects.y + rects.h), (255, 0, 0), 1)
        elif type(rects) == MatchResultList:
            for i in rects:
                cv2.rectangle(to_show, (i.x, i.y), (i.x + i.w, i.y + i.h), (255, 0, 0), 1)
        elif isinstance(rects, list):
            for rect in rects:
                if isinstance(rect, MatchResult):
                    cv2.rectangle(to_show, (rect.x, rect.y), (rect.x + rect.w, rect.y + rect.h), (255, 0, 0), 1)
                elif type(rect) == Rect:
                    cv2.rectangle(to_show, (rect.x1, rect.y1), (rect.x2, rect.y2), (255, 0, 0), 1)

    if max_width is not None and to_show.shape[1] > max_width:
        scale = max_width / to_show.shape[1]
        to_show = cv2.resize(to_show, (int(to_show.shape[1] * scale), int(to_show.shape[0] * scale)))
    if max_height is not None and to_show.shape[0] > max_height:
        scale = max_height / to_show.shape[0]
        to_show = cv2.resize(to_show, (int(to_show.shape[1] * scale), int(to_show.shape[0] * scale)))

    cv2.imshow(win_name, to_show)
    if wait is not None:
        cv2.waitKey(wait)
    if destroy_after:
        cv2.destroyWindow(win_name)


def image_rotate(img: MatLike, angle: float, show_result: bool = False):
    """
    对图片按中心进行旋转
    :param img: 原图
    :param angle: 逆时针旋转的角度
    :param show_result: 显示结果
    :return: 旋转后图片
    """
    height, width = img.shape[:2]
    center = (width // 2, height // 2)

    # 获取旋转矩阵
    rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)

    # 应用旋转矩阵来旋转图像
    rotated_image = cv2.warpAffine(img, rotation_matrix, (width, height))

    if show_result:
        cv2.imshow('Result', rotated_image)

    return rotated_image


def mark_area_as_color(image: MatLike, pos: List, color, new_image: bool = False):
    """
    将图片的一个区域变颜色 然后返回新的图片
    :param image: 原图
    :param pos: 区域坐标 如果是矩形 传入 [x,y,w,h] 如果是圆形 传入 [x,y,r]。其他数组长度不处理
    :param new_image: 是否返回一张新的图
    :param color: 颜色
    :return: 新图
    """
    to_paint = image.copy() if new_image else image
    if not type(pos) is np.ndarray:
        pos = np.array([pos])
    for p in pos:
        if len(p) == 4:
            x, y, w, h = p[0], p[1], p[2], p[3]
            cv2.rectangle(to_paint, pt1=(x, y), pt2=(x + w, y + h), color=color, thickness=-1)
        if len(p) == 3:
            x, y, r = p[0], p[1], p[2]
            cv2.circle(to_paint, (x, y), r, color, -1)
    return to_paint


def match_template(source: MatLike, template: MatLike, threshold,
                   mask: np.ndarray = None, only_best: bool = True,
                   ignore_inf: bool = False) -> MatchResultList:
    """
    在原图中匹配模板 注意无法从负偏移量开始匹配 即需要保证目标模板不会在原图边缘位置导致匹配不到
    :param source: 原图
    :param template: 模板
    :param threshold: 阈值
    :param mask: 掩码
    :param only_best: 只返回最好的结果
    :param ignore_inf: 是否忽略无限大的结果
    :return: 所有匹配结果
    """
    tx, ty = template.shape[1], template.shape[0]
    # 进行模板匹配
    # show_image(source, win_name='source')
    # show_image(template, win_name='template')
    # show_image(mask, win_name='mask', wait=1)
    result = cv2.matchTemplate(source, template, cv2.TM_CCOEFF_NORMED, mask=mask)

    match_result_list = MatchResultList(only_best=only_best)
    filtered_locations = np.where(np.logical_and(
        result >= threshold,
        np.isfinite(result) if ignore_inf else np.ones_like(result))
    )  # 过滤低置信度的匹配结果

    # 遍历所有匹配结果，并输出位置和置信度
    for pt in zip(*filtered_locations[::-1]):
        confidence = result[pt[1], pt[0]]  # 获取置信度
        match_result_list.append(MatchResult(confidence, pt[0], pt[1], tx, ty))

    return match_result_list


def concat_vertically(img: MatLike, next_img: MatLike, decision_height: int = 150):
    """
    垂直拼接图片。
    假设两张图片是通过垂直滚动得到的，即宽度一样，部分内容重叠
    :param img: 图
    :param next_img: 下一张图
    :param decision_height: 用第二张图的多少高度来判断重叠部分
    :return:
    """
    # 截取一个横截面用来匹配 要用中心部分 四周空白较多容易误判
    for threshold in range(95, 70, -5):
        for dh in range(decision_height, next_img.shape[0] // 2, 10):
            cy = next_img.shape[0] // 2
            next_part = next_img[:-dh, :]
            r = match_template(img, next_part, threshold / 100.0).max
            if r is None:
                continue
            h, w, _ = img.shape
            overlap_h = h - r.y
            extra_part = next_img[overlap_h+1:, :]
            # 垂直拼接两张图像
            return cv2.vconcat([img, extra_part])
    raise Exception('拼接图片失败')


def concat_horizontally(img: MatLike, next_img: MatLike, decision_width: int = 200):
    """
    水平拼接图片。
    假设两张图片是通过水平滚动得到的，即高度一样，部分内容重叠
    :param img: 图
    :param next_img: 下一张图
    :param decision_width: 用第二张图的多少宽度来判断重叠部分
    :return:
    """
    # 截取一个横截面用来匹配 要用中心部分 四周空白较多容易误判
    cx = next_img.shape[1] // 2
    next_part = next_img[:, cx - decision_width:cx + decision_width]
    result = match_template(img, next_part, 0.8)
    # 找出置信度最高的结果
    r = result.max
    h, w, _ = img.shape
    overlap_w = w - r.x + cx - decision_width
    extra_part = next_img[:, overlap_w+1:]
    # 水平拼接两张图像
    return cv2.hconcat([img, extra_part])


def concat_horizontally_2(img: MatLike, next_img: MatLike, decision_width: int = 200) -> MatLike:
    """
    水平拼接图片。 两张图片可能高度有一点差异，宽度应该是一样的
    :param img: 图
    :param next_img: 下一张图
    :param decision_width: 用第二张图的多少宽度来判断重叠部分
    :return:
    """
    if img.shape == next_img.shape:  # 大小一致时 使用旧的方法
        return concat_horizontally(img, next_img, decision_width)

    part_1 = img[50:-50, decision_width:]  # 上下剪掉一点 左边剪掉一点
    result = match_template(next_img, part_1, 0.8).max

    if result is None:
        return None

    height_1 = result.y + part_1.shape[0] + 50
    width_1 = result

    # 截取一个横截面用来匹配 要用中心部分 四周空白较多容易误判
    cx = next_img.shape[1] // 2
    next_part = next_img[:, cx - decision_width:cx + decision_width]

    # 找出置信度最高的结果
    r = result.max
    h, w, _ = img.shape
    overlap_w = w - r.x + cx - decision_width
    extra_part = next_img[:, overlap_w+1:]
    # 水平拼接两张图像
    return cv2.hconcat([img, extra_part])


def is_same_image(i1: MatLike, i2: MatLike, threshold: float = 1) -> bool:
    """
    简单使用均方差判断两图是否一致
    :param i1: 图1
    :param i2: 图2
    :param threshold: 低于阈值认为是相等
    :return: 是否同一张图
    """
    if i1.shape != i2.shape:
        return False
    return np.mean((i1 - i2) ** 2) < threshold


def color_similarity_2d(image, color):
    """
    PhotoShop 魔棒功能的容差是一样的，颜色差值 = abs(max(RGB差值)) + abs(min(RGB差值))
    感谢 https://github.com/LmeSzinc/StarRailCopilot/wiki/MinimapTracking
    :param image:
    :param color:
    :return:
    """
    r, g, b = cv2.split(cv2.subtract(image, (*color, 0)))
    positive = cv2.max(cv2.max(r, g), b)
    r, g, b = cv2.split(cv2.subtract((*color, 0), image))
    negative = cv2.max(cv2.max(r, g), b)
    return cv2.subtract(255, cv2.add(positive, negative))


def show_overlap(
        source, template, x, y, template_scale: float = 1,
        win_name: str = 'DEBUG', wait: int = 1,
        max_width: int | None = None,
        max_height: int | None = None,
        template_mask: MatLike | None = None,
):
    to_show_source = source.copy()

    if template_scale != 1:
        # 缩放后的宽度和高度
        scaled_width = int(template.shape[1] * template_scale)
        scaled_height = int(template.shape[0] * template_scale)

        # 缩放小图
        to_show_template = cv2.resize(template, (scaled_width, scaled_height))
    else:
        to_show_template = template

    source_overlap_template(to_show_source, to_show_template, x, y, copy_img=False, template_mask=template_mask)
    show_image(to_show_source, win_name=win_name, wait=wait,
               max_width=max_width,
               max_height=max_height,)


def feature_detect_and_compute(img: MatLike, mask: Optional[MatLike] = None):
    return feature_detector.detectAndCompute(img, mask=mask)


def feature_keypoints_to_np(keypoints):
    return np.array([(kp.pt[0], kp.pt[1], kp.size, kp.angle, kp.response, kp.octave, kp.class_id) for kp in keypoints])


def feature_keypoints_from_np(np_arr):
    return np.array([cv2.KeyPoint(x=kp[0], y=kp[1], size=kp[2], angle=kp[3],
                                  response=kp[4], octave=int(kp[5]), class_id=int(kp[6])) for kp in np_arr])


def feature_match(source_kp, source_desc, template_kp, template_desc,
                  source_mask: Optional[MatLike] = None):
    if len(source_kp) == 0 or len(template_kp) == 0:
        return None, None, None, None

    # feature_matcher = cv2.FlannBasedMatcher()
    feature_matcher = cv2.BFMatcher()
    matches = feature_matcher.knnMatch(template_desc, source_desc, k=2)
    # 应用比值测试，筛选匹配点
    good_matches = []
    for m, n in matches:
        if m.distance < 0.75 * n.distance:
            good_matches.append(m)

    if len(good_matches) < 4:  # 不足4个优秀匹配点时 不能使用RANSAC
        return good_matches, None, None, None

    # 提取匹配点的坐标
    template_points = np.float32([template_kp[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)  # 模板的
    source_points = np.float32([source_kp[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)  # 原图的

    # 使用RANSAC算法估计模板位置和尺度
    _, mask = cv2.findHomography(template_points, source_points, cv2.RANSAC, 5.0, mask=source_mask)
    # 获取内点的索引 拿最高置信度的
    inlier_indices = np.where(mask.ravel() == 1)[0]
    if len(inlier_indices) == 0:  # mask 里没找到就算了 再用good_matches的结果也是很不准的
        return good_matches, None, None, None

    # 距离最短 置信度最高的结果
    best_match = None
    for i in range(len(good_matches)):
        if mask[i] == 1 and (best_match is None or good_matches[i].distance < best_match.distance):
            best_match = good_matches[i]

    query_point = source_kp[best_match.trainIdx].pt  # 原图中的关键点坐标 (x, y)
    train_point = template_kp[best_match.queryIdx].pt  # 模板中的关键点坐标 (x, y)

    # 获取最佳匹配的特征点的缩放比例
    query_scale = source_kp[best_match.trainIdx].size
    train_scale = template_kp[best_match.queryIdx].size
    template_scale = query_scale / train_scale

    # 模板图缩放后在原图上的偏移量
    offset_x = query_point[0] - train_point[0] * template_scale
    offset_y = query_point[1] - train_point[1] * template_scale

    return good_matches, offset_x, offset_y, template_scale


def feature_match_for_one(source_kp, source_desc, template_kp, template_desc,
                          template_width: int, template_height: int,
                          source_mask: Optional[MatLike] = None,
                          knn_distance_percent: float = 0.7) -> Optional[MatchResult]:
    """
    使用特征匹配找到一个匹配结果
    :param source_kp: 源图关键点
    :param source_desc: 源图描述子
    :param template_kp: 目标关键点
    :param template_desc: 目标描述子
    :param template_width: 目标原宽度
    :param template_height: 目标原高度
    :param source_mask: 源图掩码
    :param knn_distance_percent: 越小要求匹配程度越高
    :return: 缩放后的位置和大小
    """
    if len(source_kp) == 0 or len(template_kp) == 0:
        return None

    # feature_matcher = cv2.FlannBasedMatcher()
    feature_matcher = cv2.BFMatcher()
    matches = feature_matcher.knnMatch(template_desc, source_desc, k=2)
    # 应用比值测试，筛选匹配点
    good_matches = []
    for t in matches:
        if len(t) < 2:  # 没有match的情况
            return None
        m, n = t
        if m.distance < knn_distance_percent * n.distance:
            good_matches.append(m)

    if len(good_matches) < 4:  # 不足4个优秀匹配点时 不能使用RANSAC
        return None

    # 提取匹配点的坐标
    template_points = np.float32([template_kp[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)  # 模板的
    source_points = np.float32([source_kp[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)  # 原图的

    # 使用RANSAC算法估计模板位置和尺度
    homography_matrix, mask = cv2.findHomography(template_points, source_points, cv2.RANSAC, 5.0, mask=source_mask)
    # 获取内点的索引 拿最高置信度的
    inlier_indices = np.where(mask.ravel() == 1)[0]
    if len(inlier_indices) == 0:  # mask 里没找到就算了 再用good_matches的结果也是很不准的
        return None

    # 距离最短 置信度最高的结果
    best_match = None
    for i in range(len(good_matches)):
        if mask[i] == 1 and (best_match is None or good_matches[i].distance < best_match.distance):
            best_match = good_matches[i]

    query_point = source_kp[best_match.trainIdx].pt  # 原图中的关键点坐标 (x, y)
    train_point = template_kp[best_match.queryIdx].pt  # 模板中的关键点坐标 (x, y)

    # 获取最佳匹配的特征点的缩放比例
    query_scale = source_kp[best_match.trainIdx].size
    train_scale = template_kp[best_match.queryIdx].size
    template_scale = query_scale / train_scale

    # 模板图缩放后在原图上的偏移量
    offset_x = query_point[0] - train_point[0] * template_scale
    offset_y = query_point[1] - train_point[1] * template_scale

    scaled_width = int(template_width * template_scale)
    scaled_height = int(template_height * template_scale)

    # 计算综合置信度
    # 1. 内点比例 - RANSAC内点占总good_matches的比例
    inlier_ratio = len(inlier_indices) / len(good_matches)
    # 2. 距离因子 - 距离越小越好，但要处理0距离的情况
    distance_factor = 1.0 / (1.0 + best_match.distance / 100.0) if best_match.distance > 0 else 1.0
    # 3. 内点数量因子 - 内点越多越好
    inlier_count_factor = min(1.0, len(inlier_indices) / 10.0)

    confidence = (
        0.4 * inlier_ratio +
        0.4 * distance_factor +
        0.2 * inlier_count_factor
    )
    confidence = np.clip(confidence, 0.0, 1.0)

    return MatchResult(confidence, offset_x, offset_y, scaled_width, scaled_height, template_scale)


def feature_match_for_multi(
        source_kp, source_desc, template_kp, template_desc,
        template_width: int, template_height: int,
        source_mask: Optional[MatLike] = None,
        knn_distance_percent: float = 0.7) -> MatchResultList:
    """

    :param source_kp:
    :param source_desc:
    :param template_kp:
    :param template_desc:
    :param template_width:
    :param template_height:
    :param source_mask:
    :param knn_distance_percent:
    :return:
    """
    match_result_list = MatchResultList(only_best=False)

    if len(source_kp) == 0 or len(template_kp) == 0:
        return match_result_list

    # feature_matcher = cv2.FlannBasedMatcher()
    feature_matcher = cv2.BFMatcher()
    matches = feature_matcher.knnMatch(template_desc, source_desc, k=3)
    # 应用比值测试，筛选匹配点
    good_matches = []
    for m, n, p in matches:
        if m.distance < knn_distance_percent * n.distance and m.distance < knn_distance_percent * p.distance:
            good_matches.append(m)

    if len(good_matches) < 4:  # 不足4个优秀匹配点时 不能使用RANSAC
        return match_result_list

    # 提取匹配点的坐标
    template_points = np.float32([template_kp[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)  # 模板的
    source_points = np.float32([source_kp[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)  # 原图的

    # 使用RANSAC算法估计模板位置和尺度
    M, mask = cv2.findHomography(template_points, source_points, cv2.RANSAC, 5.0, mask=source_mask)
    # 获取内点的索引 拿最高置信度的
    inlier_indices = np.where(mask.ravel() == 1)[0]
    if len(inlier_indices) == 0:  # mask 里没找到就算了 再用good_matches的结果也是很不准的
        return match_result_list

    for i in range(len(good_matches)):
        if mask[i] == 1:
            match = good_matches[i]

            query_point = source_kp[match.trainIdx].pt  # 原图中的关键点坐标 (x, y)
            train_point = template_kp[match.queryIdx].pt  # 模板中的关键点坐标 (x, y)

            # 获取最佳匹配的特征点的缩放比例
            query_scale = source_kp[match.trainIdx].size
            train_scale = template_kp[match.queryIdx].size
            template_scale = query_scale / train_scale

            # 模板图缩放后在原图上的偏移量
            offset_x = query_point[0] - train_point[0] * template_scale
            offset_y = query_point[1] - train_point[1] * template_scale

            # 缩放后的宽度和高度
            scaled_width = template_width * template_scale
            scaled_height = template_height * template_scale

            match_result_list.append(MatchResult(1, offset_x, offset_y, scaled_width, scaled_height))


    return match_result_list


def connection_erase(
        mask: MatLike,
        threshold: int = 50,
        erase_white: bool = True,
        connectivity: int = 8
) -> MatLike:
    """
    通过连通性检测 消除一些噪点
    :param mask: 黑白图 掩码图
    :param threshold: 小于多少连通时 认为是噪点
    :param erase_white: 是否清除白色
    :param connectivity: 连通性检测方向 4 or 8
    :return: 消除噪点后的图
    """
    to_check_connection = mask if erase_white else cv2.bitwise_not(mask)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(to_check_connection, connectivity=connectivity)
    large_components = []
    for label in range(1, num_labels):
        if stats[label, cv2.CC_STAT_AREA] < threshold:
            large_components.append(label)

    result = mask.copy()
    for label in large_components:
        result[labels == label] = 0 if erase_white else 255

    return result


def crop_image(img, rect: Rect = None, copy: bool = False) -> Tuple[MatLike, Optional[Rect]]:
    """
    裁剪图片 裁剪区域可能超出图片范围
    :param img: 原图
    :param rect: 裁剪区域 (x1, y1, x2, y2)
    :param copy: 是否复制新图
    :return: 裁剪后图片 和 实际的裁剪区域
    """
    if rect is None:
        return (img.copy() if copy else img), None

    x1, y1, x2, y2 = rect.x1, rect.y1, rect.x2, rect.y2
    if x1 < 0:
        x1 = 0
    if x2 > img.shape[1]:
        x2 = img.shape[1]
    if y1 < 0:
        y1 = 0
    if y2 > img.shape[0]:
        y2 = img.shape[0]

    x1, y1 = int(x1), int(y1)
    x2, y2 = int(x2), int(y2)
    crop = img[y1: y2, x1: x2]
    return (crop.copy() if copy else crop), Rect(x1, y1, x2, y2)


def crop_image_only(img, rect: Rect = None, copy: bool = False) -> MatLike:
    """
    裁剪图片 裁剪区域可能超出图片范围
    :param img: 原图
    :param rect: 裁剪区域 (x1, y1, x2, y2)
    :param copy: 是否复制新图
    :return: 只返回裁剪后图片
    """
    return crop_image(img, rect=rect, copy=copy)[0]


def dilate(img, k):
    """
    膨胀一下 适合掩码图
    :param img:
    :param k:
    :return:
    """
    if k == 0:
        return img
    kernel = np.ones((k, k), np.uint8)
    return cv2.dilate(src=img, kernel=kernel, iterations=1)


def convert_to_standard(origin, mask, width: int = 51, height: int = 51, bg_color=None):
    """
    转化成 目标尺寸并居中
    :param origin:
    :param mask:
    :param width: 目标尺寸宽度
    :param height: 目标尺寸高度
    :param bg_color: 背景色
    :return:
    """
    final_mask = np.zeros((height, width), dtype=np.uint8)
    bw = np.where(mask == 255)
    if len(bw[0]) == 0:  # 遇袭情况下 有可能小地图上使用颜色扣图会完全扣不到 掩码全黑
        cx = mask.shape[1] // 2
        cy = mask.shape[0] // 2
        min_x, min_y = 0, 0
        max_x, max_y = mask.shape[1], mask.shape[0]
    else:
        white_pixel_coordinates = list(zip(bw[1], bw[0]))

        # 找到最大最小坐标值
        max_x = max(white_pixel_coordinates, key=lambda i: i[0])[0]
        max_y = max(white_pixel_coordinates, key=lambda i: i[1])[1]

        min_x = min(white_pixel_coordinates, key=lambda i: i[0])[0]
        min_y = min(white_pixel_coordinates, key=lambda i: i[1])[1]

        # 稍微扩大一下范围 why
        if max_x < mask.shape[1]:
            max_x += min(5, mask.shape[1] - max_x)
        if max_y < mask.shape[0]:
            max_y += min(5, mask.shape[0] - max_y)
        if min_x > 0:
            min_x -= min(5, min_x)
        if min_y > 0:
            min_y -= min(5, min_y)

        cx = (min_x + max_x) // 2
        cy = (min_y + max_y) // 2

    x1, y1 = cx - min_x, cy - min_y
    x2, y2 = max_x - cx, max_y - cy

    ccx = width // 2
    ccy = height // 2

    # 移动到 特定尺寸 居中
    final_mask[ccy-y1:ccy+y2, ccx-x1:ccx+x2] = mask[min_y:max_y, min_x:max_x]

    if len(origin.shape) > 2:
        final_origin = np.zeros((height, width, 3), dtype=np.uint8)
        final_origin[ccy-y1:ccy+y2, ccx-x1:ccx+x2, :] = origin[min_y:max_y, min_x:max_x, :]
    else:
        final_origin = np.zeros((height, width), dtype=np.uint8)
        final_origin[ccy - y1:ccy + y2, ccx - x1:ccx + x2] = origin[min_y:max_y, min_x:max_x]
    final_origin = cv2.bitwise_and(final_origin, final_origin, mask=final_mask)

    if bg_color is not None:  # 部分图标可以背景统一使用颜色
        final_origin[np.where(final_mask == 0)] = bg_color

    return final_origin, final_mask


def source_overlap_template(source, template, x, y, copy_img: bool = False, template_mask: MatLike | None = None):
    """
    在原图上覆盖模板图
    :param source: 原图
    :param template: 模板图 缩放后
    :param x: 偏移量
    :param y: 偏移量
    :param copy_img: 是否复制新图片
    :param template_mask: 模板图掩码
    :return:
    """
    to_overlap_source = source.copy() if copy_img else source
    if template_mask is None:
        template_mask = np.full_like(template, 255, dtype=np.uint8)

    rect1, rect2 = get_overlap_rect(source, template, x, y)
    sx_start, sy_start, sx_end, sy_end = rect1
    tx_start, ty_start, tx_end, ty_end = rect2

    # 定义目标图像中的感兴趣区域 (ROI)
    source_roi = to_overlap_source[sy_start:sy_end, sx_start:sx_end]
    template_roi = template[ty_start:ty_end, tx_start:tx_end]
    template_mask_roi = template_mask[ty_start:ty_end, tx_start:tx_end]

    mask_condition = template_mask_roi > 0

    # 使用布尔索引，只将模板中掩码为 True 的像素复制到 ROI。
    # NumPy 会自动将这个二维的布尔掩码应用到三维的彩色图像上。
    source_roi[mask_condition] = template_roi[mask_condition]

    return to_overlap_source


def get_overlap_rect(source, template, x, y):
    """
    根据模板图在原图上的偏移量 计算出覆盖区域
    :param source: 原图
    :param template: 模板图 缩放后
    :param x: 偏移量
    :param y: 偏移量
    :return:
    """
    # 获取要覆盖图像的宽度和高度
    overlay_height, overlay_width = template.shape[:2]

    # 覆盖图在原图上的坐标
    sx_start = int(x)
    sy_start = int(y)
    sx_end = sx_start + overlay_width
    sy_end = sy_start + overlay_height

    # 覆盖图要用的坐标
    tx_start = 0
    ty_start = 0
    tx_end = overlay_width
    ty_end = overlay_height

    # 覆盖图缩放后可以超出了原图的范围
    if sx_start < 0:
        tx_start -= sx_start
        sx_start -= sx_start
    if sx_end > source.shape[1]:
        tx_end -= sx_end - source.shape[1]
        sx_end -= sx_end - source.shape[1]

    if sy_start < 0:
        ty_start -= sy_start
        sy_start -= sy_start
    if sy_end > source.shape[0]:
        ty_end -= sy_end - source.shape[0]
        sy_end -= sy_end - source.shape[0]

    return (sx_start, sy_start, sx_end, sy_end), (tx_start, ty_start, tx_end, ty_end)


def get_four_corner(bw):
    """
    获取四个方向最远的白色像素点的位置
    :param bw: 黑白图
    :return:
    """
    white = np.where(bw == 255)
    if np.sum(bw == 255) == 0:
        return None, None, None, None
    left = (white[1][np.argmin(white[1])], white[0][np.argmin(white[1])])
    right = (white[1][np.argmax(white[1])], white[0][np.argmax(white[1])])
    top = (white[1][np.argmin(white[0])], white[0][np.argmin(white[0])])
    bottom = (white[1][np.argmax(white[0])], white[0][np.argmax(white[0])])
    return left, right, top, bottom


def scale_image(img: Optional[MatLike] = None, scale: Optional[float] = None, copy: bool = True) -> Optional[MatLike]:
    """
    按比例缩放图片
    :param img: 原图
    :param scale: 缩放比例
    :param copy: 是否复制新图
    :return: 缩放后图片
    """
    if img is None:
        return None
    if scale is None or scale == 1:
        return img.copy() if copy else img
    target_size = (int(img.shape[0] * scale), int(img.shape[1] * scale))
    return cv2.resize(img, target_size)


def to_base64(img: MatLike) -> str:
    """
    将图片转化成base64编码展示
    :param img:
    :return:
    """
    _, buffer = cv2.imencode('.png', img)
    base64_data = base64.b64encode(buffer)
    return base64_data.decode("utf-8")


def get_white_part(img: MatLike,
                   noise_threshold: Optional[int] = None):
    """
    获取白色的部分掩码
    :param img:
    :param noise_threshold: 噪音阈值。传入时会消除小于多少
    :return:
    """
    return color_in_range(img, lower=[220, 220, 220], upper=[255, 255, 255],
                          noise_threshold=noise_threshold)


def get_black_part(img: MatLike,
                   noise_threshold: Optional[int] = None):
    """
    获取白色的部分掩码
    :param img:
    :param noise_threshold: 噪音阈值。传入时会消除小于多少
    :return:
    """
    return color_in_range(img, lower=[0, 0, 0], upper=[50, 50, 50],
                          noise_threshold=noise_threshold)


def color_in_range(img: MatLike, lower: List[int], upper: List[int],
                   noise_threshold: Optional[int] = None):
    """
    获取颜色范围内的掩码
    :param img:
    :param lower: 颜色下限
    :param upper: 颜色上限
    :param noise_threshold: 噪音阈值。传入时会消除小于多少
    :return:
    """
    lower_color = np.array(lower, dtype=np.uint8)
    upper_color = np.array(upper, dtype=np.uint8)
    part = cv2.inRange(img, lower_color, upper_color)
    if noise_threshold is None:
        return part
    else:
        return connection_erase(part, noise_threshold)


def color_in_hsv_range(
        img: MatLike,
        lower: List[int],
        upper: List[int],
        white_noise_threshold: Optional[int] = None,
        black_noise_threshold: Optional[int] = None,
) -> MatLike:
    """
    获取HSV颜色范围内的掩码

    Args:
        img: RGB图片
        lower: HSV下限 (360, 100, 100)
        upper: HSV上限 (360, 100, 100)
        white_noise_threshold: 噪音阈值。传入时会消除连通量小于多少的白色块
        black_noise_threshold: 噪音阈值。传入时会消除连通量小于多少的黑色块

    Returns:
        掩码
    """
    lower_range = np.array([
        math.floor(lower[0] / 2.0),
        math.floor(lower[1] * 255.0 / 100),
        math.floor(lower[2] * 255.0 / 100),
    ], dtype=np.uint8)
    upper_range = np.array([
        math.ceil(upper[0] / 2.0),
        math.ceil(upper[1] * 255.0 / 100),
        math.ceil(upper[2] * 255.0 / 100),
    ], dtype=np.uint8)
    hsv_img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    part = cv2.inRange(hsv_img, lower_range, upper_range)

    if white_noise_threshold is not None:
        part = connection_erase(part, white_noise_threshold, erase_white=True)
    if black_noise_threshold is not None:
        part = connection_erase(part, black_noise_threshold, erase_white=False)

    return part


def find_character_avatars(img: MatLike, min_area: int = 800,
                          hsv_lower_bound: Tuple[int, int, int] = (0, 0, 0),
                          hsv_upper_bound: Tuple[int, int, int] = (10, 10, 255)) -> List[Tuple[int, int, int, int]]:
    """
    在图像中查找角色头像的轮廓
    使用HSV色彩空间过滤并通过连通区域检测找到头像位置

    :param img: 输入图像 (RGB格式)
    :param min_area: 最小有效区域面积，过滤小的噪点
    :param hsv_lower_bound: HSV下界 (H, S, V)
    :param hsv_upper_bound: HSV上界 (H, S, V)
    :return: 角色头像边界框列表，每个元素为 (x, y, w, h)
    """
    # 转换到HSV色彩空间并过滤低饱和度和色调值
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    mask = cv2.inRange(hsv, hsv_lower_bound, hsv_upper_bound)
    binary = cv2.bitwise_not(mask)

    # 查找连通区域
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 过滤小面积区域并返回边界框
    valid_contours = [cnt for cnt in contours if cv2.contourArea(cnt) >= min_area]

    avatar_boxes = []
    for cnt in valid_contours:
        x, y, w, h = cv2.boundingRect(cnt)
        avatar_boxes.append((x, y, w, h))

    return avatar_boxes


def find_character_avatar_center_with_offset(img: MatLike, area_offset: Tuple[int, int] = (0, 0),
                                           click_offset: Tuple[int, int] = (0, 80),
                                           min_area: int = 800,
                                           hsv_lower_bound: Tuple[int, int, int] = (0, 0, 0),
                                           hsv_upper_bound: Tuple[int, int, int] = (10, 10, 255)) -> Optional[Tuple[int, int]]:
    """
    查找第一个角色头像并返回带偏移的点击位置

    :param img: 输入图像 (RGB格式)
    :param area_offset: 区域偏移量 (x, y)，用于将相对坐标转换为绝对坐标
    :param click_offset: 点击偏移量 (x, y)，相对于头像中心的偏移
    :param min_area: 最小有效区域面积
    :param hsv_lower_bound: HSV下界
    :param hsv_upper_bound: HSV上界
    :return: 点击位置 (x, y) 或 None
    """
    avatar_boxes = find_character_avatars(img, min_area, hsv_lower_bound, hsv_upper_bound)

    if not avatar_boxes:
        return None

    # 选择第一个有效轮廓
    x, y, w, h = avatar_boxes[0]

    # 计算点击位置：轮廓中心加上偏移量
    center_x = x + w // 2 + area_offset[0] + click_offset[0]
    center_y = y + h // 2 + area_offset[1] + click_offset[1]

    return (center_x, center_y)


def filter_by_color(
    image: MatLike,
    mode: str,
    lower_rgb: Optional[Union[List[int], Tuple[int, int, int], np.ndarray]] = None,
    upper_rgb: Optional[Union[List[int], Tuple[int, int, int], np.ndarray]] = None,
    hsv_color: Optional[Union[List[int], Tuple[int, int, int], np.ndarray]] = None,
    hsv_diff: Optional[Union[List[int], Tuple[int, int, int], np.ndarray]] = None
) -> MatLike:
    """
    根据指定的模式和颜色范围，对图像进行颜色过滤。
    能正确处理HSV空间H通道的循环问题。
    :param image:       待过滤的图像 (RGB格式)
    :param mode:        颜色模式 'rgb' 或 'hsv'
    :param lower_rgb:   RGB下限
    :param upper_rgb:   RGB上限
    :param hsv_color:   HSV基准颜色
    :param hsv_diff:    HSV颜色容差
    :return:            二值化的 mask 图像。白色为符合条件，黑色为不符合。
    """
    if mode == 'hsv':
        if hsv_color is None or hsv_diff is None:
            return np.full((image.shape[0], image.shape[1]), 0, dtype=np.uint8)

        hsv_image = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)

        _hsv_color = np.array(hsv_color, dtype=np.int32)
        _hsv_diff = np.array(hsv_diff, dtype=np.int32)

        lower_s = np.clip(_hsv_color[1] - _hsv_diff[1], 0, 255)
        upper_s = np.clip(_hsv_color[1] + _hsv_diff[1], 0, 255)
        lower_v = np.clip(_hsv_color[2] - _hsv_diff[2], 0, 255)
        upper_v = np.clip(_hsv_color[2] + _hsv_diff[2], 0, 255)

        lower_h = _hsv_color[0] - _hsv_diff[0]
        upper_h = _hsv_color[0] + _hsv_diff[0]

        if lower_h < 0:
            # H值回绕到180附近
            lower1 = np.array([lower_h + 180, lower_s, lower_v], dtype=np.uint8)
            upper1 = np.array([179, upper_s, upper_v], dtype=np.uint8)
            mask1 = cv2.inRange(hsv_image, lower1, upper1)

            lower2 = np.array([0, lower_s, lower_v], dtype=np.uint8)
            upper2 = np.array([upper_h, upper_s, upper_v], dtype=np.uint8)
            mask2 = cv2.inRange(hsv_image, lower2, upper2)

            mask = cv2.bitwise_or(mask1, mask2)
        elif upper_h > 179:
            # H值回绕到0附近
            lower1 = np.array([lower_h, lower_s, lower_v], dtype=np.uint8)
            upper1 = np.array([179, upper_s, upper_v], dtype=np.uint8)
            mask1 = cv2.inRange(hsv_image, lower1, upper1)

            lower2 = np.array([0, lower_s, lower_v], dtype=np.uint8)
            upper2 = np.array([upper_h - 180, upper_s, upper_v], dtype=np.uint8)
            mask2 = cv2.inRange(hsv_image, lower2, upper2)

            mask = cv2.bitwise_or(mask1, mask2)
        else:
            # H值没有回绕
            lower = np.array([lower_h, lower_s, lower_v], dtype=np.uint8)
            upper = np.array([upper_h, upper_s, upper_v], dtype=np.uint8)
            mask = cv2.inRange(hsv_image, lower, upper)

        return mask
    elif mode == 'rgb':
        if lower_rgb is None or upper_rgb is None:
            return np.full((image.shape[0], image.shape[1]), 0, dtype=np.uint8)

        # cv2.inRange 需要 np.array
        _lower_rgb = np.array(lower_rgb, dtype=np.uint8)
        _upper_rgb = np.array(upper_rgb, dtype=np.uint8)
        mask = cv2.inRange(image, _lower_rgb, _upper_rgb)
        return mask
    else:
        # 未知模式，或者没有提供足够的参数，返回全黑的mask
        return np.full((image.shape[0], image.shape[1]), 0, dtype=np.uint8)


def get_hsv_range_in_rect(image: MatLike, left: int, top: int, right: int, bottom: int) -> dict:
    """
    获取矩形区域内所有像素的HSV范围
    :param image: RGB格式的图像
    :param left: 矩形左边界
    :param top: 矩形上边界
    :param right: 矩形右边界
    :param bottom: 矩形下边界
    :return: 包含HSV中心值、差值和范围的字典
    """
    if image is None or image.size == 0:
        return None

    # 确保坐标在图像范围内
    height, width = image.shape[:2]
    left = max(0, min(left, width - 1))
    top = max(0, min(top, height - 1))
    right = max(left + 1, min(right, width))
    bottom = max(top + 1, min(bottom, height))

    # 提取矩形区域
    roi = image[top:bottom, left:right]

    # 转换为HSV
    hsv_roi = cv2.cvtColor(roi, cv2.COLOR_RGB2HSV)

    # S、V通道保持原有的线性计算
    s_min, v_min = np.min(hsv_roi[:, :, 1:], axis=(0, 1))
    s_max, v_max = np.max(hsv_roi[:, :, 1:], axis=(0, 1))

    # 使用双区间比较算法计算H通道的中心值和差值
    h_values = hsv_roi[:, :, 0].flatten()
    h_min = int(np.min(h_values))
    h_max = int(np.max(h_values))

    # 计算线性区间长度：[min, max]
    linear_length = h_max - h_min

    # 计算环形区间长度：[max, min]
    circular_length = (180 - h_max) + h_min

    if linear_length <= circular_length:
        # 选择线性区间
        h_center = (h_min + h_max) // 2
        h_diff = linear_length // 2
    else:
        # 选择环形区间
        # 环形区间的中心计算：从max开始，加上环形长度的一半
        half_circular = circular_length // 2
        h_center = h_max + half_circular
        if h_center >= 180:
            h_center -= 180  # 转换为0-179范围
        h_diff = half_circular

    # S和V通道保持线性计算
    s_center = int((int(s_min) + int(s_max)) // 2)
    v_center = int((int(v_min) + int(v_max)) // 2)
    s_diff = int(s_max - s_min)
    v_diff = int(v_max - v_min)

    return {
        'center_hsv': (int(h_center), int(s_center), int(v_center)),
        'diff_hsv': (int(h_diff), int(s_diff), int(v_diff))
    }


def get_hsv_range_in_contour(image: MatLike, contour: np.ndarray) -> dict:
    """
    获取轮廓区域内所有像素的HSV范围
    :param image: RGB格式的图像
    :param contour: 轮廓点集
    :return: 包含HSV中心值、差值和范围的字典
    """
    if image is None or image.size == 0 or contour is None or len(contour) == 0:
        return None

    # 创建与图像同样大小的掩码
    mask = np.zeros(image.shape[:2], dtype=np.uint8)

    # 在掩码上绘制填充的轮廓
    cv2.drawContours(mask, [contour], -1, 255, -1)

    # 转换为HSV
    hsv_image = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)

    # 只分析轮廓内的像素
    masked_hsv = hsv_image[mask > 0]

    if len(masked_hsv) == 0:
        return None

    # S、V通道保持原有的线性计算
    s_min, v_min = np.min(masked_hsv[:, 1:], axis=0)
    s_max, v_max = np.max(masked_hsv[:, 1:], axis=0)

    # 使用双区间比较算法计算H通道的中心值和差值
    h_values = masked_hsv[:, 0]
    h_min = int(np.min(h_values))
    h_max = int(np.max(h_values))

    # 计算线性区间长度：[min, max]
    linear_length = h_max - h_min

    # 计算环形区间长度：[max, min]
    circular_length = (180 - h_max) + h_min

    if linear_length <= circular_length:
        # 选择线性区间
        h_center = (h_min + h_max) // 2
        h_diff = linear_length // 2
    else:
        # 选择环形区间
        # 环形区间的中心计算：从max开始，加上环形长度的一半
        half_circular = circular_length // 2
        h_center = h_max + half_circular
        if h_center >= 180:
            h_center -= 180  # 转换为0-179范围
        h_diff = half_circular

    # S和V通道保持线性计算
    s_center = int((int(s_min) + int(s_max)) // 2)
    v_center = int((int(v_min) + int(v_max)) // 2)
    s_diff = int(s_max - s_min)
    v_diff = int(v_max - v_min)

    return {
        'center_hsv': (int(h_center), int(s_center), int(v_center)),
        'diff_hsv': (int(h_diff), int(s_diff), int(v_diff))
    }
