from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResult
from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.base.screen.screen_info import ScreenInfo
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_context import OneDragonContext


class OcrClickResultEnum(Enum):

    OCR_CLICK_SUCCESS = 1  # OCR并点击成功
    OCR_CLICK_FAIL = 0  # OCR成功但点击失败 基本不会出现
    OCR_CLICK_NOT_FOUND = -1  # OCR找不到目标
    AREA_NO_CONFIG = -2  # 区域配置找不到


class FindAreaResultEnum(Enum):

    TRUE = 1  # 找到了
    FALSE = 0  # 找不到
    AREA_NO_CONFIG = -2  # 区域配置找不到


def find_area(
    ctx: OneDragonContext,
    screen: MatLike,
    screen_name: str,
    area_name: str,
    crop_first: bool = True,
) -> FindAreaResultEnum:
    """
    游戏截图中 是否能找到对应的区域
    Args:
        ctx: 上下文
        screen: 游戏截图
        screen_name: 画面名称
        area_name: 区域名称
        crop_first: 在传入区域时 是否先裁剪再进行文本识别

    Returns:
        bool: 是否可以匹配到指定区域
    """
    area: ScreenArea = ctx.screen_loader.get_area(screen_name, area_name)
    return find_area_in_screen(ctx, screen, area, crop_first)


def find_area_binary(
    ctx: OneDragonContext,
    screen: MatLike,
    screen_name: str,
    area_name: str,
    binary_threshold: int = 127,
    crop_first: bool = True,
) -> FindAreaResultEnum:
    """
    使用二值化图像在游戏截图中查找区域
    Args:
        ctx: 上下文
        screen: 游戏截图
        screen_name: 画面名称
        area_name: 区域名称
        binary_threshold: 二值化阈值，默认为127
        crop_first: 在传入区域时 是否先裁剪再进行识别

    Returns:
        FindAreaResultEnum: 是否可以匹配到指定区域
    """
    area: ScreenArea = ctx.screen_loader.get_area(screen_name, area_name)
    return find_area_in_screen_binary(ctx, screen, area, binary_threshold, crop_first)


def find_area_in_screen_binary(
    ctx: OneDragonContext,
    screen: MatLike,
    area: ScreenArea,
    binary_threshold: int = 127,
    crop_first: bool = True,
) -> FindAreaResultEnum:
    """
    使用二值化图像在截图中查找区域
    Args:
        ctx: 上下文
        screen: 游戏截图
        area: 区域
        binary_threshold: 二值化阈值，默认为127
        crop_first: 在传入区域时 是否先裁剪再进行识别

    Returns:
        FindAreaResultEnum: 是否可以匹配到指定区域
    """
    if area is None:
        return FindAreaResultEnum.AREA_NO_CONFIG

    # 对屏幕进行二值化处理
    binary_screen = cv2_utils.to_binary(screen, threshold=binary_threshold)

    find: bool = False
    if area.is_text_area:
        ocr_result_list = ctx.ocr_service.get_ocr_result_list(
            image=binary_screen,
            rect=area.rect,
            color_range=area.color_range,
            crop_first=crop_first,
        )

        for ocr_result in ocr_result_list:
            if str_utils.find_by_lcs(gt(area.text, 'game'), ocr_result.data, percent=area.lcs_percent):
                find = True
                break
    elif area.is_template_area:
        # 裁剪区域
        rect = area.rect
        part = cv2_utils.crop_image_only(binary_screen, rect)

        # 使用二值化模板匹配
        mrl = ctx.tm.match_template_binary(
            part,
            area.template_sub_dir,
            area.template_id,
            threshold=area.template_match_threshold,
            binary_threshold=binary_threshold
        )
        find = mrl.max is not None

    return FindAreaResultEnum.TRUE if find else FindAreaResultEnum.FALSE


def find_area_in_screen(
    ctx: OneDragonContext,
    screen: MatLike,
    area: ScreenArea,
    crop_first: bool = True,
) -> FindAreaResultEnum:
    """
    游戏截图中 是否能找到对应的区域

    Args:
        ctx: 上下文
        screen: 游戏截图
        area: 区域
        crop_first: 在传入区域时 是否先裁剪再进行文本识别

    Returns:
        bool: 是否可以匹配到指定区域
    """
    if area is None:
        return FindAreaResultEnum.AREA_NO_CONFIG

    find: bool = False
    if area.is_text_area:
        ocr_result_list = ctx.ocr_service.get_ocr_result_list(
            image=screen,
            rect=area.rect,
            color_range=area.color_range,
            crop_first=crop_first,
        )

        for ocr_result in ocr_result_list:
            if str_utils.find_by_lcs(gt(area.text, 'game'), ocr_result.data, percent=area.lcs_percent):
                find = True
                break
    elif area.is_template_area:
        rect = area.rect
        part = cv2_utils.crop_image_only(screen, rect)

        mrl = ctx.tm.match_template(part, area.template_sub_dir, area.template_id,
                                    threshold=area.template_match_threshold)
        find = mrl.max is not None

    return FindAreaResultEnum.TRUE if find else FindAreaResultEnum.FALSE


def find_template_coord_in_area(
    ctx: OneDragonContext,
    screen: MatLike,
    screen_name: str,
    area_name: str,
) -> MatchResult | None:
    """
    在指定区域内进行模板匹配，返回匹配到的绝对坐标

    Args:
        ctx: 上下文
        screen: 游戏截图
        screen_name: 画面名称
        area_name: 区域名称

    Returns:
        MatchResult | None: 匹配结果（包含绝对坐标），如果未匹配到则返回 None
    """
    area: ScreenArea = ctx.screen_loader.get_area(screen_name, area_name)
    if area is None or not area.is_template_area:
        return None

    # 裁剪出指定区域
    part = cv2_utils.crop_image_only(screen, area.rect)

    # 在裁剪区域内进行模板匹配
    mrl = ctx.tm.match_template(
        part,
        area.template_sub_dir,
        area.template_id,
        threshold=area.template_match_threshold,
        only_best=True
    )

    if mrl.max is None:
        return None

    # 将相对坐标转换为绝对坐标
    result = MatchResult(
        mrl.max.confidence,
        mrl.max.x + area.rect.x1,
        mrl.max.y + area.rect.y1,
        mrl.max.w,
        mrl.max.h
    )

    return result


def find_and_click_area(
    ctx: OneDragonContext,
    screen: MatLike,
    screen_name: str,
    area_name: str,
    crop_first: bool = True,
) -> OcrClickResultEnum:
    """
    在一个区域匹配成功后进行点击

    Args:
        ctx: 运行上下文
        screen: 游戏截图
        screen_name: 画面名称
        area_name: 区域名称
        crop_first: 在传入区域时 是否先裁剪再进行文本识别

    Returns:
        OcrClickResultEnum: 点击结果
    """
    area: ScreenArea = ctx.screen_loader.get_area(screen_name, area_name)
    if area is None:
        return OcrClickResultEnum.AREA_NO_CONFIG
    if area.is_text_area:
        ocr_result_list = ctx.ocr_service.get_ocr_result_list(
            image=screen,
            rect=area.rect,
            color_range=area.color_range,
            crop_first=crop_first,
        )

        for ocr_result in ocr_result_list:
            if str_utils.find_by_lcs(gt(area.text, 'game'), ocr_result.data, percent=area.lcs_percent):
                if ctx.controller.click(ocr_result.center, pc_alt=area.pc_alt):
                    return OcrClickResultEnum.OCR_CLICK_SUCCESS
                else:
                    return OcrClickResultEnum.OCR_CLICK_FAIL

        return OcrClickResultEnum.OCR_CLICK_NOT_FOUND
    elif area.is_template_area:
        rect = area.rect
        part = cv2_utils.crop_image_only(screen, rect)

        mrl = ctx.tm.match_template(part, area.template_sub_dir, area.template_id,
                                    threshold=area.template_match_threshold)
        if mrl.max is None:
            return OcrClickResultEnum.OCR_CLICK_NOT_FOUND
        elif ctx.controller.click(mrl.max.center + rect.left_top, pc_alt=area.pc_alt):
            return OcrClickResultEnum.OCR_CLICK_SUCCESS
        else:
            return OcrClickResultEnum.OCR_CLICK_FAIL
    else:
        ctx.controller.click(area.center, pc_alt=area.pc_alt)
        return OcrClickResultEnum.OCR_CLICK_SUCCESS


def scroll_area(
    ctx: OneDragonContext,
    area: ScreenArea,
    direction: str = 'down',
    start_ratio: float = 0.9,
    end_ratio: float = 0.1,
) -> None:
    """
    在指定区域内滚动屏幕

    Args:
        ctx: 运行上下文
        area: 区域
        direction: 滚动方向，'down' 表示往下滚（从下往上滑），'up' 表示往上滚（从上往下滑）
        start_ratio: 起始位置比例（距顶部的比例）。默认0.9，即区域底部10%处
        end_ratio: 结束位置比例（距顶部的比例）。默认0.1，即区域顶部10%处
    """
    rect = area.rect
    height = rect.height

    # 统一按“距顶部比例”计算位置，避免 start/end 计算成同一点
    start_ratio = max(0.0, min(1.0, start_ratio))
    end_ratio = max(0.0, min(1.0, end_ratio))
    y_start = rect.y1 + int(height * start_ratio)
    y_end = rect.y1 + int(height * end_ratio)

    if direction == 'up':
        # 往上滚：手势从上往下划
        start = Point(rect.center.x, y_end)
        end = Point(rect.center.x, y_start)
    else:
        # 往下滚：手势从下往上划
        start = Point(rect.center.x, y_start)
        end = Point(rect.center.x, y_end)

    # 防止极端情况下 start/end 重合导致“看起来没有滚动”
    if start.y == end.y:
        if start.y >= rect.center.y:
            end = Point(end.x, max(rect.y1 + 1, end.y - 1))
        else:
            end = Point(end.x, min(rect.y2 - 1, end.y + 1))

    ctx.controller.drag_to(start=start, end=end)


def get_match_screen_name(
    ctx: OneDragonContext,
    screen: MatLike,
    screen_name_list: list[str] | None = None,
    crop_first: bool = True,
) -> str | None:
    """
    根据游戏截图 匹配一个最合适的画面

    Args:
        ctx: 上下文
        screen: 游戏截图
        screen_name_list: 画面列表 传入时 只判断这里的画面
        crop_first: 在传入区域时 是否先裁剪再进行文本识别

    Returns:
        str | None: 画面名称
    """
    if screen_name_list is not None:
        for screen_info in ctx.screen_loader.screen_info_list:
            if screen_info.screen_name not in screen_name_list:
                continue
            if is_target_screen(ctx, screen, screen_info=screen_info, crop_first=crop_first):
                return screen_info.screen_name
    elif ctx.screen_loader.current_screen_name is not None or ctx.screen_loader.last_screen_name is not None:
        return get_match_screen_name_from_last(ctx, screen, crop_first=crop_first)
    else:
        for screen_info in ctx.screen_loader.screen_info_list:
            if is_target_screen(ctx, screen, screen_info=screen_info, crop_first=crop_first):
                return screen_info.screen_name

    return None


def get_match_screen_name_from_last(
    ctx: OneDragonContext,
    screen: MatLike,
    crop_first: bool = True,
) -> str | None:
    """
    根据游戏截图 从上次记录的画面开始 匹配一个最合适的画面
    Args:
        ctx: 上下文
        screen: 游戏截图
        crop_first: 在传入区域时 是否先裁剪再进行文本识别

    Returns:
        str | None: 画面名称
    """
    bfs_list = []

    if ctx.screen_loader.current_screen_name is not None:  # 如果有记录上次所在画面 则从这个画面开始搜索
        bfs_list.append(ctx.screen_loader.current_screen_name)
    if ctx.screen_loader.last_screen_name is not None:
        bfs_list.append(ctx.screen_loader.last_screen_name)

    if len(bfs_list) == 0:
        return None

    bfs_idx = 0
    while bfs_idx < len(bfs_list):
        current_screen_name = bfs_list[bfs_idx]
        bfs_idx += 1

        if is_target_screen(ctx, screen, screen_name=current_screen_name, crop_first=crop_first):
            return current_screen_name

        screen_info = ctx.screen_loader.get_screen(current_screen_name)
        if screen_info is None:
            continue
        for area in screen_info.area_list:
            if area.goto_list is None or len(area.goto_list) == 0:
                continue
            for goto_screen in area.goto_list:
                if goto_screen not in bfs_list:
                    bfs_list.append(goto_screen)

    # 最后 尝试搜索中没有出现的画面
    for screen_info in ctx.screen_loader.screen_info_list:
        if screen_info.screen_name in bfs_list:
            continue
        if is_target_screen(ctx, screen, screen_info=screen_info, crop_first=crop_first):
            return screen_info.screen_name

    return None

def is_target_screen(
    ctx: OneDragonContext,
    screen: MatLike,
    screen_name: str | None = None,
    screen_info: ScreenInfo | None = None,
    crop_first: bool = True,
) -> bool:
    """
    根据游戏截图 判断是否目标画面

    Args:
        ctx: 上下文
        screen: 游戏截图
        screen_name: 目标画面名称
        screen_info: 目标画面信息 传入时优先使用
        crop_first: 在传入区域时 是否先裁剪再进行文本识别

    Returns:
        bool: 是否目标画面
    """
    if screen_info is None:
        if screen_name is None:
            return False
        screen_info = ctx.screen_loader.get_screen(screen_name)
        if screen_info is None:
            return False

    existed_id_mark: bool = False
    fit_id_mark: bool = True
    for screen_area in screen_info.area_list:
        if not screen_area.id_mark:
            continue
        existed_id_mark = True

        if find_area_in_screen(ctx, screen, screen_area, crop_first) != FindAreaResultEnum.TRUE:
            fit_id_mark = False
            break

    return existed_id_mark and fit_id_mark


def find_by_ocr(
    ctx: OneDragonContext,
    screen: MatLike,
    target_cn: str,
    area: ScreenArea | None = None,
    lcs_percent: float = 0.5,
    color_range: list[list[int]] | None = None,
    crop_first: bool = True,
) -> bool:
    """
    判断画面中是否有目标文本

    Args:
        ctx: 上下文
        screen: 游戏截图
        target_cn: 目标中文文本
        area: 指定区域
        lcs_percent: 文本匹配阈值
        color_range: 区域筛选的颜色范围
        crop_first: 在传入区域时 是否先裁剪再进行文本识别

    Returns:
        bool: 是否有目标文本
    """
    if lcs_percent is None:
        lcs_percent = area.lcs_percent

    if color_range is None and area is not None:
        color_range = area.color_range
    ocr_result_list = ctx.ocr_service.get_ocr_result_list(
        image=screen,
        rect=area.rect if area is not None else None,
        color_range=color_range,
        crop_first=crop_first,
    )

    to_click: Point | None = None
    for ocr_result in ocr_result_list:
        if str_utils.find_by_lcs(gt(target_cn, 'game'), ocr_result.data, percent=lcs_percent):
            to_click = ocr_result.center
            break

    return to_click is not None
