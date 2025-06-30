import math
from random import random

from typing import List, Union

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect


def distance_between(pos1: Point, pos2: Point) -> float:
    """
    计算两点之间的距离
    :param pos1:
    :param pos2:
    :return:
    """
    x1, y1 = pos1.x, pos1.y
    x2, y2 = pos2.x, pos2.y
    return math.sqrt(((x1 - x2) ** 2) + ((y1 - y2) ** 2))


def get_angle_by_pts(from_pos: Point, to_pos: Point) -> float:
    """
    计算两点形成向量的角度
    :param from_pos: 起始点
    :param to_pos: 结束点
    :return: 角度 正右方为0 顺时针为正
    """
    x1, y1 = from_pos.x, from_pos.y
    x2, y2 = to_pos.x, to_pos.y
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0:
        if dy > 0:
            return 90
        elif dy == 0:
            return 0
        else:
            return 270
    if dy == 0:
        if dx >= 0:
            return 0
        else:
            return 180
    angle = math.degrees(math.atan(dy / dx))
    if angle > 0 and (dy < 0 and dx < 0):
        angle += 180
    elif angle < 0 and (dx < 0 and dy > 0):
        angle += 180
    elif angle < 0 and (dx > 0 and dy < 0):
        angle += 360
    return angle


def angle_delta(from_angle: float, to_angle: float) -> float:
    """
    从一个角度转到另一个角度需要的角度 正数向右转
    :param from_angle:
    :param to_angle:
    :return:
    """
    delta_angle = to_angle - from_angle if to_angle >= from_angle else to_angle + 360 - from_angle
    # 正方向转太远的话就用负方向转
    if delta_angle > 180:
        delta_angle -= 360
    return delta_angle


def angle_add(current_angle: float, delta_angle: float) -> float:
    """
    一个角度加上一个偏移角度
    :param current_angle: 当前角度 正右方为0 顺时针为正
    :param delta_angle: 偏移角度 正数往右转 负数往左转
    :return: 偏移后的角度 正右方为0 顺时针为正
    """
    result_angle = current_angle + delta_angle
    while result_angle >= 360:
        result_angle -= 360
    while result_angle < 0:
        result_angle += 360
    return result_angle


def in_rect(point: Point, rect: Rect) -> bool:
    """
    点是否在矩阵内
    :param point:
    :param rect:
    :return:
    """
    return rect.x1 <= point.x <= rect.x2 and rect.y1 <= point.y <= rect.y2


def calculate_overlap_area(r1: Rect, r2: Rect) -> float:
    """
    计算两个矩形的重叠面积
    Args:
        r1: 矩形1
        r2: 矩形2

    Returns:
        overlap: 重叠面积
    """
    if r1.x1 > r2.x2 or r1.x2 < r2.x1 or r1.y1 > r2.y2 or r1.y2 < r2.y1:
        # 两个矩形不相交，重叠面积为0
        return 0
    else:
        # 计算重叠矩形的左上角坐标和右下角坐标
        overlap_x1 = max(r1.x1, r2.x1)
        overlap_y1 = max(r1.y1, r2.y1)
        overlap_x2 = min(r1.x2, r2.x2)
        overlap_y2 = min(r1.y2, r2.y2)

        # 计算重叠矩形的宽度和高度
        width = overlap_x2 - overlap_x1
        height = overlap_y2 - overlap_y1

        # 计算重叠矩形的面积
        overlap_area = width * height
        return overlap_area


def cal_overlap_percent(r1: Rect, r2: Rect) -> float:
    """
    计算两个矩形的重叠面积百分比 = 重叠面积 / 两者较小的面积
    Args:
        r1: 矩形1
        r2: 矩形2

    Returns:
        percent: 重叠面积百分比
    """
    overlap = calculate_overlap_area(r1, r2)
    min_area = min(r1.area, r2.area)
    if min_area <= 0:
        return 0
    else:
        return overlap * 1.0 / min_area


def coalesce(*args):
    """
    返回第一个非空元素
    :param args:
    :return:
    """
    return next((arg for arg in args if arg is not None), None)


def distance_to_line(target: Point, p1: Point, p2: Point) -> float:
    """
    目标点到直线的距离
    :param target: 目标点
    :param p1: 连线点1
    :param p2: 连线点2
    :return:
    """
    x1, y1 = p1.x, p1.y
    x2, y2 = p2.x, p2.y
    x0, y0 = target.x, target.y

    if x1 == x2:  # 处理垂直于 y 轴的情况
        distance = abs(x0 - x1)
    elif y1 == y2:  # 处理垂直于 x 轴的情况
        distance = abs(y0 - y1)
    else:
        # 计算直线的方程 Ax + By + C = 0
        A = y2 - y1
        B = x1 - x2
        C = x2 * y1 - x1 * y2
        distance = abs(A * x0 + B * y0 + C) / (A ** 2 + B ** 2) ** 0.5

    return distance


def random_in_range(r: Union[List[float], float]) -> float:
    """
    在范围内随机一个数
    :param r:
    :return:
    """
    if r is None:
        return 0
    elif not isinstance(r, list):
        return r
    elif len(r) == 0:
        return 0
    elif len(r) == 1:
        return r[0]
    elif len(r) > 1 and r[0] == r[1]:
        return r[0]
    else:
        return r[0] + (r[1] - r[0]) * random()
