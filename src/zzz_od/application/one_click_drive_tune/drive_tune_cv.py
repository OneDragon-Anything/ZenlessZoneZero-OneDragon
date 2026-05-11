"""驱动盘列表网格整理（来自 drive_disk_enhance_bundle 的 sort_grids 逻辑）。"""

from __future__ import annotations

import cv2
import numpy as np
from one_dragon.base.geometry.point import Point


def sort_grids(all_disks: list[Point]) -> list[list[Point]]:
    """将检测到的驱动盘中心点整理为按行、列排序的二维网格。"""
    if not all_disks:
        return []

    sorted_by_y = sorted(all_disks, key=lambda d: d.y)
    rows: list[list[Point]] = []
    current_row = [sorted_by_y[0]]
    y_tolerance = 20

    for i in range(1, len(sorted_by_y)):
        disk = sorted_by_y[i]
        if abs(disk.y - current_row[0].y) <= y_tolerance:
            current_row.append(disk)
        else:
            current_row.sort(key=lambda d: d.x)
            rows.append(current_row)
            current_row = [disk]

    if current_row:
        current_row.sort(key=lambda d: d.x)
        rows.append(current_row)

    filtered_rows: list[list[Point]] = []
    for i, row in enumerate(rows):
        if i < len(rows) - 1:
            if len(row) == 4:
                filtered_rows.append(row)
        elif 1 <= len(row) <= 4:
            filtered_rows.append(row)

    return filtered_rows


def contours_to_grid_centers(
    contours: list[np.ndarray], list_rect
) -> list[list[Point]]:
    """轮廓 → 绝对坐标中心点 → sort_grids。"""
    all_grids: list[Point] = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        gx = int(x + list_rect.x1 + w / 2)
        gy = int(y + list_rect.y1 + h / 2)
        all_grids.append(Point(gx, gy))
    return sort_grids(all_grids)
