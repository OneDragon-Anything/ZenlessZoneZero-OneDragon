from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, List, Optional

import cv2
import numpy as np
from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.base.screen.screen_info import ScreenInfo
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_context import OneDragonContext


class OcrClickResultEnum(Enum):

    OCR_CLICK_SUCCESS: int = 1  # OCR并点击成功
    OCR_CLICK_FAIL: int = 0  # OCR成功但点击失败 基本不会出现
    OCR_CLICK_NOT_FOUND: int = -1  # OCR找不到目标
    AREA_NO_CONFIG: int = -2  # 区域配置找不到


class FindAreaResultEnum(Enum):

    TRUE: int = 1  # 找到了
    FALSE: int = 0  # 找不到
    AREA_NO_CONFIG: int = -2  # 区域配置找不到


def find_area(ctx: OneDragonContext, screen: MatLike, screen_name: str, area_name: str) -> FindAreaResultEnum:
    """
    游戏截图中 是否能找到对应的区域
    :param ctx: 上下文
    :param screen: 游戏截图
    :param screen_name: 画面名称
    :param area_name: 区域名称
    :return: 结果
    """
    area: ScreenArea = ctx.screen_loader.get_area(screen_name, area_name)
    return find_area_in_screen(ctx, screen, area)


def find_area_in_screen(ctx: OneDragonContext, screen: MatLike, area: ScreenArea) -> FindAreaResultEnum:
    """
    游戏截图中 是否能找到对应的区域
    :param ctx: 上下文
    :param screen: 游戏截图
    :param area: 区域
    :return: 结果
    """
    if area is None:
        return FindAreaResultEnum.AREA_NO_CONFIG

    find: bool = False
    if area.is_text_area:
        if ctx.env_config.ocr_cache:
            ocr_result_map = ctx.ocr_service.get_ocr_result_map(
                image=screen,
                color_range=area.color_range,
                rect=area.rect
            )
        else:
            rect = area.rect
            part = cv2_utils.crop_image_only(screen, rect)

            if area.color_range is None:
                to_ocr = part
            else:
                mask = cv2.inRange(part,
                                   np.array(area.color_range[0], dtype=np.uint8),
                                   np.array(area.color_range[1], dtype=np.uint8))
                mask = cv2_utils.dilate(mask, 2)
                to_ocr = cv2.bitwise_and(part, part, mask=mask)

            ocr_result_map = ctx.ocr.run_ocr(to_ocr)

        for ocr_result, mrl in ocr_result_map.items():
            if str_utils.find_by_lcs(gt(area.text, 'game'), ocr_result, percent=area.lcs_percent):
                find = True
                break
    elif area.is_template_area:
        rect = area.rect
        part = cv2_utils.crop_image_only(screen, rect)

        mrl = ctx.tm.match_template(part, area.template_sub_dir, area.template_id,
                                    threshold=area.template_match_threshold)
        find = mrl.max is not None

    return FindAreaResultEnum.TRUE if find else FindAreaResultEnum.FALSE


def find_and_click_area(ctx: OneDragonContext, screen: MatLike, screen_name: str, area_name: str) -> OcrClickResultEnum:
    """
    在一个区域匹配成功后进行点击
    :param ctx: 运行上下文
    :param screen: 屏幕截图
    :param screen_name: 画面名称
    :param area_name: 区域名称
    :return:
    """
    area: ScreenArea = ctx.screen_loader.get_area(screen_name, area_name)
    if area is None:
        return OcrClickResultEnum.AREA_NO_CONFIG
    if area.is_text_area:
        rect = area.rect
        to_ocr_part = cv2_utils.crop_image_only(screen, rect)
        if area.color_range is not None:
            mask = cv2.inRange(to_ocr_part, area.color_range_lower, area.color_range_upper)
            mask = cv2_utils.dilate(mask, 5)
            to_ocr_part = cv2.bitwise_and(to_ocr_part, to_ocr_part, mask=mask)
        # cv2_utils.show_image(to_ocr_part, win_name='debug', wait=1)

        ocr_result_map = ctx.ocr.run_ocr(to_ocr_part)
        for ocr_result, mrl in ocr_result_map.items():
            if str_utils.find_by_lcs(gt(area.text, 'game'), ocr_result, percent=area.lcs_percent):
                to_click = mrl.max.center + area.left_top
                if ctx.controller.click(to_click, pc_alt=area.pc_alt):
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


def get_match_screen_name(ctx: OneDragonContext, screen: MatLike, screen_name_list: Optional[List[str]] = None) -> Optional[str]:
    """
    根据游戏截图 匹配一个最合适的画面
    :param ctx: 上下文
    :param screen: 游戏截图
    :param screen_name_list: 传入时 只判断这里的画面
    :return: 画面名字
    """
    if screen_name_list is not None:
        for screen_info in ctx.screen_loader.screen_info_list:
            if screen_info.screen_name not in screen_name_list:
                continue
            if is_target_screen(ctx, screen, screen_info=screen_info):
                return screen_info.screen_name
    elif ctx.screen_loader.current_screen_name is not None or ctx.screen_loader.last_screen_name is not None:
        return get_match_screen_name_from_last(ctx, screen)
    else:
        for screen_info in ctx.screen_loader.screen_info_list:
            if is_target_screen(ctx, screen, screen_info=screen_info):
                return screen_info.screen_name

    return None


def get_match_screen_name_from_last(ctx: OneDragonContext, screen: MatLike) -> str | None:
    """
    根据游戏截图 从上次记录的画面开始 匹配一个最合适的画面
    :param ctx: 上下文
    :param screen: 游戏截图
    :return: 画面名字
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

        if is_target_screen(ctx, screen, screen_name=current_screen_name):
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
        if is_target_screen(ctx, screen, screen_info=screen_info):
            return screen_info.screen_name

    return None

def is_target_screen(ctx: OneDragonContext, screen: MatLike,
                     screen_name: Optional[str] = None,
                     screen_info: Optional[ScreenInfo] = None) -> bool:
    """
    根据游戏截图 判断是否目标画面
    :param ctx: 上下文
    :param screen: 游戏截图
    :param screen_name: 目标画面名称
    :param screen_info: 目标画面信息 传入时优先使用
    :return: 结果
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

        if find_area_in_screen(ctx, screen, screen_area) != FindAreaResultEnum.TRUE:
            fit_id_mark = False
            break

    return existed_id_mark and fit_id_mark


def find_by_ocr(ctx: OneDragonContext, screen: MatLike, target_cn: str,
                area: Optional[ScreenArea] = None, lcs_percent: float = 0.5,
                color_range: Optional[List] = None) -> bool:
    """

    @param ctx:
    @param screen:
    @param target_cn:
    @param area:
    @param lcs_percent:
    @param color_range:
    @return:
    """
    if lcs_percent is None:
        lcs_percent = area.lcs_percent

    # 优先使用OCR缓存服务
    if ctx.env_config.ocr_cache:
        return ctx.ocr_service.find_text_in_area(
            image=screen,
            rect=area.rect,
            color_range=color_range,
            target_text=target_cn,
            threshold=lcs_percent,
        )

    # 回退到原有方法
    to_ocr_part = screen if area is None else cv2_utils.crop_image_only(screen, area.rect)
    if color_range is not None:
        mask = cv2.inRange(to_ocr_part, color_range[0], color_range[1])
        to_ocr_part = cv2.bitwise_and(to_ocr_part, to_ocr_part, mask=mask)
    ocr_result_map = ctx.ocr.run_ocr(to_ocr_part)

    to_click: Optional[Point] = None
    for ocr_result, mrl in ocr_result_map.items():
        if mrl.max is None:
            continue
        if str_utils.find_by_lcs(gt(target_cn, 'game'), ocr_result, percent=lcs_percent):
            to_click = mrl.max.center
            break

    return to_click is not None
