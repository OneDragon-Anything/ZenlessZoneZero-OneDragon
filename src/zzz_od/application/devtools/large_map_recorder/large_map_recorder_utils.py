import os

import cv2
import numpy as np
from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResult, MatchResultList
from one_dragon.utils import cv2_utils, cal_utils
from zzz_od.application.devtools.large_map_recorder.large_map_recorder_wrapper import LargeMapSnapshot, MiniMapSnapshot
from zzz_od.application.world_patrol.world_patrol_area import WorldPatrolLargeMapIcon, WorldPatrolLargeMap
from zzz_od.context.zzz_context import ZContext
from zzz_od.application.world_patrol import cal_pos_utils
from zzz_od.application.world_patrol.mini_map_wrapper import MiniMapWrapper


def get_mini_map_circle_mask(d: int) -> MatLike:
    """
    Args:
        d: 直径

    Returns:
        MatLike: 圆形区域的掩码
    """
    r = d // 2
    circle_mask: MatLike = np.zeros((d, d), dtype=np.uint8)
    cv2.circle(circle_mask, [r, r], r - 7, [255], -1)
    cv2.circle(circle_mask, [207, 189], 50, [0], -1)
    return circle_mask


def get_mini_map_in_circle(mini_map: MiniMapSnapshot) -> MiniMapSnapshot:
    """
    获取圆形区域的小地图

    Args:
        mini_map: 小地图

    Returns:
        MiniMapSnapshot: 裁剪后的小地图
    """
    road_mask = mini_map.road_mask
    circle_mask: MatLike = get_mini_map_circle_mask(road_mask.shape[0])
    road_mask = cv2.bitwise_and(road_mask, circle_mask)
    road_mask = cv2_utils.connection_erase(road_mask, erase_white=False)  # 填补一些小黑点
    road_mask = cv2_utils.connection_erase(road_mask, erase_white=True)  # 清除小白点

    return MiniMapSnapshot(
        road_mask,
        [] + mini_map.icon_list
    )

def merge_large_map(
        large_map: LargeMapSnapshot,
        mini_map: MiniMapSnapshot,
        pos_mr: MatchResult,
) -> LargeMapSnapshot:
    """
    将图标合并到现有的大地图上

    Args:
        large_map: 大地图
        mini_map: 当前的道路掩码
        pos_mr: 坐标

    Returns:
        MatLike: 合并后的大地图
        Point: 拓展产生左上方的偏移量
    """
    to_use: MiniMapSnapshot = get_mini_map_in_circle(mini_map)

    # 如果大地图为空，初始化一个3x3小地图大小的大地图，将第一张小地图放在中心
    if large_map is None:
        return _initialize_large_map(to_use)

    # 没有传入匹配位置 不合并
    if pos_mr is None:
        return large_map

    # 将道路掩码合并到大地图上
    merged_map = _merge_at_position(large_map, to_use, pos_mr)

    # 检查并扩展边缘
    final_map = _expand_edges_if_needed(merged_map, (to_use.road_mask.shape[0], to_use.road_mask.shape[1]))

    return final_map


def _initialize_large_map(mini_map: MiniMapSnapshot) -> LargeMapSnapshot:
    """
    初始化大地图，创建3x3小地图大小的空间，将第一张小地图放在中心

    Args:
        mini_map: 小地图

    Returns:
        LargeMapSnapshot: 初始化的大地图
    """
    mask_height, mask_width = mini_map.road_mask.shape[:2]

    # 创建3x3大小的大地图
    large_height = mask_height * 3
    large_width = mask_width * 3

    # 初始化为全黑（0值）
    large_map = np.zeros((large_height, large_width), dtype=np.uint8)

    # 将第一张小地图放在中心位置
    center_y = mask_height  # 中心位置的y坐标
    center_x = mask_width   # 中心位置的x坐标

    large_map[center_y:center_y + mask_height, center_x:center_x + mask_width] = mini_map.road_mask

    icon_list = []
    for icon_name, icon_pos in mini_map.icon_list:
        adjusted_pos = icon_pos + Point(center_x, center_y)
        icon_list.append(WorldPatrolLargeMapIcon(
            icon_name='',
            template_id=icon_name,
            lm_pos=[adjusted_pos.x, adjusted_pos.y],
            tp_pos=None,
        ))

    # Create a temporary WorldPatrolLargeMap to pass to LargeMapSnapshot
    temp_world_patrol_map = WorldPatrolLargeMap(
        area_full_id="",  # Empty area_full_id for initialization
        road_mask=large_map,
        icon_list=icon_list
    )

    return LargeMapSnapshot(
        world_patrol_large_map=temp_world_patrol_map,
        pos_after_merge=Point(center_x, center_y) + Point(mask_width // 2, mask_height // 2),
    )


def _merge_at_position(
        large_map: LargeMapSnapshot,
        mini_map: MiniMapSnapshot,
        pos_mr: MatchResult,
        copy_road: bool = False,
) -> LargeMapSnapshot:
    """
    将道路掩码合并到大地图的指定位置

    Args:
        large_map: 大地图
        mini_map: 小地图
        pos_mr: 合并位置 (x, y)
        copy_road: 是否要复制道路

    Returns:
        LargeMapSnapshot: 合并后的大地图
    """
    x = pos_mr.x
    y = pos_mr.y

    # 创建大地图的副本
    merged_road_mask = large_map.road_mask.copy()

    if copy_road:
        mask_height, mask_width = mini_map.road_mask.shape[:2]

        # 使用按位或操作合并掩码，这样可以保留两个掩码的所有道路信息
        merged_road_mask[y:y + mask_height, x:x + mask_width] = cv2.bitwise_or(
            merged_road_mask[y:y + mask_height, x:x + mask_width],
            mini_map.road_mask,
        )

    icon_list: list[WorldPatrolLargeMapIcon] = [
        WorldPatrolLargeMapIcon(
            icon_name=icon.icon_name,
            template_id=icon.template_id,
            lm_pos=[icon.lm_pos.x, icon.lm_pos.y],
            tp_pos=[icon.tp_pos.x, icon.tp_pos.y] if icon.tp_pos else None,
        )
        for icon in large_map.icon_list
    ]

    for icon_name, icon_pos in mini_map.icon_list:
        new_icon_pos = icon_pos + Point(x, y)
        existed: bool = False
        for old_icon in icon_list:
            if icon_name != old_icon.template_id:
                continue
            if cal_utils.distance_between(old_icon.lm_pos, new_icon_pos) > 10:
                continue
            existed = True
            break

        if not existed:
            icon_list.append(WorldPatrolLargeMapIcon(
                icon_name='',
                template_id=icon_name,
                lm_pos=[new_icon_pos.x, new_icon_pos.y],
                tp_pos=None,
            ))

    # Create a temporary WorldPatrolLargeMap to pass to LargeMapSnapshot
    temp_world_patrol_map = WorldPatrolLargeMap(
        area_full_id=large_map.area_full_id,
        road_mask=merged_road_mask,
        icon_list=icon_list
    )

    return LargeMapSnapshot(
        world_patrol_large_map=temp_world_patrol_map,
        pos_after_merge=pos_mr.center,
    )


def _expand_edges_if_needed(
        large_map: LargeMapSnapshot,
        mask_shape: tuple[int, int]
) -> LargeMapSnapshot:
    """
    检查大地图边缘，如果边缘区域被占用，则扩展大地图以保持边缘有一个小地图长度的空白

    Args:
        large_map: 大地图
        mask_shape: 小地图的形状 (height, width)

    Returns:
        LargeMapSnapshot: 可能扩展后的大地图
    """
    road_mask = large_map.road_mask
    mask_height, mask_width = mask_shape
    large_height, large_width = road_mask.shape[0], road_mask.shape[1]

    # 检查边缘是否需要扩展，使用更精确的检测
    expand_top = expand_bottom = expand_left = expand_right = 0

    # 定义边缘检测的厚度（比一个小地图稍小，避免过度扩展）
    edge_thickness_h = mask_height // 2
    edge_thickness_w = mask_width // 2

    # 检查顶部边缘
    if np.any(road_mask[:edge_thickness_h, :] > 0):
        expand_top = mask_height

    # 检查底部边缘
    if np.any(road_mask[-edge_thickness_h:, :] > 0):
        expand_bottom = mask_height

    # 检查左侧边缘
    if np.any(road_mask[:, :edge_thickness_w] > 0):
        expand_left = mask_width

    # 检查右侧边缘
    if np.any(road_mask[:, -edge_thickness_w:] > 0):
        expand_right = mask_width

    # 如果不需要扩展，直接返回原地图
    if expand_top == 0 and expand_bottom == 0 and expand_left == 0 and expand_right == 0:
        return large_map

    # 计算新的地图尺寸
    new_height = large_height + expand_top + expand_bottom
    new_width = large_width + expand_left + expand_right

    # 创建扩展后的地图
    expanded_map = np.zeros((new_height, new_width), dtype=np.uint8)

    # 将原地图复制到新位置
    expanded_map[expand_top:expand_top + large_height,
                 expand_left:expand_left + large_width] = road_mask

    left_top = Point(expand_left, expand_top)
    new_icon_list = [
        WorldPatrolLargeMapIcon(
            icon_name=icon.icon_name,
            template_id=icon.template_id,
            lm_pos=[icon.lm_pos.x + left_top.x, icon.lm_pos.y + left_top.y],
            tp_pos=[icon.tp_pos.x + left_top.x, icon.tp_pos.y + left_top.y] if icon.tp_pos else None,
        )
        for icon in large_map.icon_list
    ]

    # Create a temporary WorldPatrolLargeMap to pass to LargeMapSnapshot
    temp_world_patrol_map = WorldPatrolLargeMap(
        area_full_id=large_map.area_full_id,
        road_mask=expanded_map,
        icon_list=new_icon_list
    )

    return LargeMapSnapshot(
        world_patrol_large_map=temp_world_patrol_map,
        pos_after_merge=large_map.pos_after_merge + left_top,
    )


def get_large_map_display(
        ctx: ZContext,
        large_map: LargeMapSnapshot | None,
) -> MatLike:
    """
    获取用于展示的小地图图片 RGB 包含图标

    Args:
        ctx: 上下文
        large_map: 大地图

    Returns:
        MatLike: 用于展示的图片
    """
    if large_map is None:
        return None
    to_display = cv2.cvtColor(large_map.road_mask, cv2.COLOR_GRAY2RGB)
    for icon in large_map.icon_list:
        template = ctx.template_loader.get_template('map', icon.template_id)
        if template is None:
            continue

        # 将中心点坐标转换为左上角坐标进行渲染
        left_top_x = icon.lm_pos.x - template.raw.shape[1] // 2
        left_top_y = icon.lm_pos.y - template.raw.shape[0] // 2

        # 定义目标图像中的感兴趣区域 (ROI)
        y_start, y_end = left_top_y, left_top_y + template.raw.shape[0]
        x_start, x_end = left_top_x, left_top_x + template.raw.shape[1]
        roi = to_display[y_start:y_end, x_start:x_end]

        mask_condition = template.mask > 0

        # 使用布尔索引，只将模板中掩码为 True 的像素复制到 ROI。
        # NumPy 会自动将这个二维的布尔掩码应用到三维的彩色图像上。
        roi[mask_condition] = template.raw[mask_condition]

    return to_display


def create_mini_map_snapshot(
        ctx: ZContext,
        new_mini_map: MiniMapWrapper,
        icon_threshold: float = 0.7,
) -> MiniMapSnapshot:
    """
    创建一个小地图快照

    Args:
        ctx: 上下文
        new_mini_map: 小地图截图
        icon_threshold: 图标匹配阈值，默认0.7

    Returns:
        MiniMapSnapshot: 小地图快照
    """
    icon_list: list[tuple[str, Point]] = []
    all_mrl = MatchResultList(only_best=False)
    for i in range(1, 100):
        template = ctx.template_loader.get_template('map', f'map_icon_{i:02d}')
        if template is None:
            break

        mrl = cv2_utils.match_template(
            source=new_mini_map.rgb,
            template=template.raw,
            mask=template.mask,
            threshold=icon_threshold,
            only_best=False,
            ignore_inf=True
        )
        for mr in mrl:
            mr.data = template.template_id
            all_mrl.append(mr)

    for mr in all_mrl:
        # 计算图标中心点坐标
        icon_list.append((mr.data, mr.rect.center))

    return MiniMapSnapshot(
        new_mini_map.road_mask,
        icon_list,
    )


def merge_mini_map(
        merge: MiniMapSnapshot,
        new_mini_map: MiniMapSnapshot,
) -> MiniMapSnapshot:
    """
    合并两个小地图，需要是同一个位置里转动视角获取的

    Args:
        merge: 原来已经合并的结果
        new_mini_map: 新的小地图截图

    Returns:
        MiniMapSnapshot: 合并后的小地图
    """
    icon_list: list[tuple[str, Point]] = []
    for new_icon_name, new_icon_point in (new_mini_map.icon_list + merge.icon_list):
        existed = False
        for old_icon_name, old_icon_point in icon_list:
            if new_icon_name != old_icon_name:
                continue
            if cal_utils.distance_between(new_icon_point, old_icon_point) > 10:
                continue
            existed = True
            break

        if existed:
            continue

        icon_list.append((new_icon_name, new_icon_point))

    return MiniMapSnapshot(
        cv2.bitwise_or(merge.road_mask, new_mini_map.road_mask),
        icon_list,
    )


def get_mini_map_display(
        ctx: ZContext,
        mini_map: MiniMapSnapshot,
) -> MatLike:
    """
    获取用于展示的小地图图片 RGB 包含图标

    Args:
        ctx: 上下文
        mini_map: 小地图

    Returns:
        MatLike: 用于展示的图片
    """
    to_display = cv2.cvtColor(mini_map.road_mask, cv2.COLOR_GRAY2RGB)
    for icon_name, icon_point in mini_map.icon_list:
        template = ctx.template_loader.get_template('map', icon_name)
        if template is None:
            continue

        # 将中心点坐标转换为左上角坐标进行渲染
        left_top_x = icon_point.x - template.raw.shape[1] // 2
        left_top_y = icon_point.y - template.raw.shape[0] // 2

        # 定义目标图像中的感兴趣区域 (ROI)
        y_start, y_end = left_top_y, left_top_y + template.raw.shape[0]
        x_start, x_end = left_top_x, left_top_x + template.raw.shape[1]
        roi = to_display[y_start:y_end, x_start:x_end]

        mask_condition = template.mask > 0

        # 使用布尔索引，只将模板中掩码为 True 的像素复制到 ROI。
        # NumPy 会自动将这个二维的布尔掩码应用到三维的彩色图像上。
        roi[mask_condition] = template.raw[mask_condition]

    return to_display


def cal_pos(
        ctx: ZContext,
        large_map: LargeMapSnapshot,
        mini_map: MiniMapSnapshot,
        last_pos: Point,
        use_icon: bool,
) -> MatchResult | None:
    """
    计算小地图在大地图上的坐标

    Args:
        ctx: 上下文
        large_map: 大地图
        mini_map: 小地图
        last_pos: 上次所在的位置
        use_icon: 是否使用图标进行计算

    Returns:
        MatchResult: 匹配结果
    """
    if use_icon:
        result = cal_pos_by_icon(ctx, large_map, mini_map, last_pos)
        if result is not None:
            return result
    return cal_pos_by_road(ctx, large_map, mini_map, last_pos)


def cal_pos_by_icon(
        ctx: ZContext,
        large_map: LargeMapSnapshot,
        mini_map: MiniMapSnapshot,
        last_pos: Point,
) -> MatchResult | None:
    """
    通过图标计算小地图在大地图上的坐标

    Args:
        ctx: 上下文
        large_map: 大地图
        mini_map: 小地图
        last_pos: 上次所在的位置

    Returns:
        MatchResult: 匹配结果
    """
    x1 = last_pos.x - mini_map.road_mask.shape[1] * 2
    x2 = last_pos.x + mini_map.road_mask.shape[1] * 2
    y1 = last_pos.y - mini_map.road_mask.shape[0] * 2
    y2 = last_pos.y + mini_map.road_mask.shape[0] * 2

    match_list: list[MatchResult] = []
    for large_map_icon in large_map.icon_list:
        if large_map_icon.lm_pos.x < x1 or large_map_icon.lm_pos.x > x2:
            continue
        if large_map_icon.lm_pos.y < y1 or large_map_icon.lm_pos.y > y2:
            continue

        for mini_map_icon_name, mini_map_icon_point in mini_map.icon_list:
            if mini_map_icon_name != large_map_icon.template_id:
                continue
            new_point = large_map_icon.lm_pos - mini_map_icon_point
            new_mr = MatchResult(
                1,
                new_point.x,
                new_point.y,
                mini_map.road_mask.shape[1],
                mini_map.road_mask.shape[0],
            )

            merged = False
            for old_mr in match_list:
                if cal_utils.distance_between(new_mr.left_top, old_mr.left_top) < 10:
                    old_mr.confidence += 1
                    merged = True
                    break
            if not merged:
                match_list.append(new_mr)

    if len(match_list) == 0:
        return None

    match_list.sort(key=lambda x: x.confidence, reverse=True)
    max_confidence_list = [x for x in match_list if x.confidence == match_list[0].confidence]
    if len(max_confidence_list) == 1:
        return max_confidence_list[0]

    # 多个候选结果时 比较和原图的相似度
    template = get_mini_map_in_circle(mini_map)
    for mr in max_confidence_list:
        source_part = large_map.road_mask[
                   mr.left_top.y:mr.left_top.y + template.road_mask.shape[0],
                   mr.left_top.x:mr.left_top.x + template.road_mask.shape[1]
                   ]
        # 置信度=差异的负数
        mr.confidence = -cv2.absdiff(source_part, template.road_mask).sum()

    # 返回置信度最高的
    return max(max_confidence_list, key=lambda x: x.confidence)


def cal_pos_by_road(
        ctx: ZContext,
        large_map: LargeMapSnapshot,
        mini_map: MiniMapSnapshot,
        last_pos: Point,
) -> MatchResult | None:
    """
    通过图标计算小地图在大地图上的坐标

    Args:
        ctx: 上下文
        large_map: 大地图
        mini_map: 小地图
        last_pos: 上次所在的位置

    Returns:
        MatchResult: 匹配结果
    """
    return cal_pos_utils.cal_pos(
        large_map.road_mask,
        mini_map.road_mask,
        last_pos,
    )


def __debug():
    from zzz_od.context.zzz_context import ZContext
    ctx = ZContext()
    ctx.init_by_config()

    from one_dragon.utils import debug_utils
    screen1 = debug_utils.get_debug_image('_1753027579068')
    mm1 = ctx.world_patrol_service.cut_mini_map(screen1)
    mm1 = get_mini_map_in_circle(mm1.road_mask)
    from one_dragon.utils import cv2_utils
    cv2_utils.show_image(mm1, win_name='mm', wait=0)
    large_map = merge_large_map(None, mm1, None)
    cv2_utils.show_image(large_map, win_name='large_map', wait=0)


def __debug_read_extract():
    from one_dragon.utils import os_utils
    base_dir = os_utils.get_path_under_work_dir('.debug', 'extract')
    for file_name in os.listdir(base_dir):
        if not file_name.endswith('.png'):
            continue
        if file_name.endswith('_gray.png'):
            continue

        image = cv2.imread(os.path.join(base_dir, file_name), cv2.IMREAD_UNCHANGED)
        gray = image[:, :, 0]
        alpha = image[:, :, 3]
        road_mask = cv2.bitwise_and(gray, alpha)

        temp_world_patrol_map = WorldPatrolLargeMap("", road_mask, [])
        lm = LargeMapSnapshot(temp_world_patrol_map, Point(0, 0))
        new_file_name = f'{os.path.splitext(file_name)[0]}_gray.png'
        cv2_utils.save_image(lm.road_mask, os.path.join(base_dir, new_file_name))


if __name__ == '__main__':
    __debug_read_extract()