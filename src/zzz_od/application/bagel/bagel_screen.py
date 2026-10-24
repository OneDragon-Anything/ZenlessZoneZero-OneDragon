from __future__ import annotations

import re
from typing import TYPE_CHECKING

import cv2
import numpy as np

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.matcher.ocr import ocr_utils
from one_dragon.base.screen import screen_utils
from one_dragon.utils import cal_utils, cv2_utils
from one_dragon.utils.log_utils import log
from zzz_od.application.bagel.bagel_const import MAP_TITLE, RECOMMENDED_VALUE

if TYPE_CHECKING:
    from cv2.typing import MatLike

    from one_dragon.base.matcher.ocr.ocr_match_result import OcrMatchResult
    from zzz_od.context.zzz_context import ZContext


def read_area(ctx: ZContext, screen: MatLike, screen_name: str, area_name: str) -> str:
    """读取已建档区域的完整文字，不把空识别结果替换为零。"""
    area = ctx.screen_loader.get_area(screen_name, area_name)
    if area is None:
        raise ValueError(f'缺少贝果画面区域：{screen_name}/{area_name}')
    matches = ctx.ocr_service.get_ocr_result_list(
        screen, rect=area.pc_rect, crop_first=True, color_range=area.color_range,
    )
    return ''.join(match.data for match in sorted(matches, key=lambda match: (match.y, match.x)))


def warehouse_sale_state(ctx: ZContext, screen: MatLike) -> str | None:
    """识别仓库出售底栏和出售相关弹窗，供启动清空拒绝继续操作。"""
    for name in ('取消出售', '快速选择标题', '出售确认标题'):
        if screen_utils.find_area(ctx, screen, '贝果-仓库', name) == screen_utils.FindAreaResultEnum.TRUE:
            return name
    if all(screen_utils.find_area(ctx, screen, '贝果-仓库', name) == screen_utils.FindAreaResultEnum.TRUE
           for name in ('出售获得标题', '出售获得货币')):
        return '出售获得货币'
    return None


def _parse_loadout_value(text: str) -> int | None:
    """完整 ASCII 数字才转为数值，空值和异常文字保留为未知。"""
    text = text.strip()
    return int(text) if re.fullmatch(r'[0-9]+', text) is not None else None


def _loadout_coin_rect(crop: MatLike) -> Rect | None:
    """借鉴投资页定位唯一金币，扩边必须留在标题条内且不碰到白字。"""
    if crop is None or crop.ndim != 3 or crop.shape[2] != 3 or crop.size == 0:
        return None
    yellow = cv2.inRange(
        cv2.cvtColor(crop, cv2.COLOR_RGB2HSV),
        np.array([10, 100, 120]), np.array([40, 255, 255]),
    )
    _, _, stats, _ = cv2.connectedComponentsWithStats(yellow)
    candidates = [
        Rect(x, y, x + width, y + height)
        for x, y, width, height, area in stats[1:]
        if area >= 100 and 18 <= width <= 45 and 18 <= height <= 45
    ]
    if len(candidates) != 1:
        return None
    coin = candidates[0]
    # 遮掉图标边缘与白色高光，金额仍使用原像素，不对整条做亮白过滤。
    if coin.x1 < 4 or coin.y1 < 2 or coin.x2 + 4 >= crop.shape[1] or coin.y2 + 2 >= crop.shape[0]:
        return None
    white = np.all(crop >= 180, axis=2)
    # 紧贴黄色主体的白点也属于图标；在扩边之外检查分隔，不能把高光误当标题或金额。
    if np.any(white[:, coin.x1 - 4:coin.x1 - 2]) or np.any(white[:, coin.x2:coin.x2 + 4]):
        return None
    return Rect(coin.x1 - 2, coin.y1 - 2, coin.x2 + 2, coin.y2 + 2)


def _loadout_value_candidate(
    matches: list[OcrMatchResult], label: str, coin: Rect, masked: MatLike,
) -> str:
    """按遮挡后的白色像素核对金额位置，文字框内的空白不算数字。"""
    titles = [match for match in matches if match.rect.x2 <= coin.x1]
    if not any(match.data.strip() == label for match in titles):
        return ''
    remaining = [match for match in matches if match.rect.x2 > coin.x1]
    if len(remaining) != 1 or remaining[0].rect.x1 < coin.x1:
        return ''
    amount = remaining[0]
    text = amount.data.strip()
    if _parse_loadout_value(text) is None:
        return ''
    # 检测框会向外包含空白，可伸入已遮挡区；可见数字仍须全部在金币右侧。
    crop, rect = cv2_utils.crop_image(masked, amount.rect)
    white_columns = np.flatnonzero(np.any(np.all(crop >= 180, axis=2), axis=0))
    if white_columns.size == 0 or rect.x1 + int(white_columns[0]) < coin.x2:
        return ''
    return text


def read_loadout(ctx: ZContext, screen: MatLike) -> dict[str, str]:
    """先遮挡金币，再分开核对标题和完整金额；所有回退均使用遮挡后的像素。"""
    values: dict[str, str] = {}
    labels = (
        ('武备价值', '代理人武备'), ('装备价值', '装备'), ('道具价值', '道具'),
    )
    regions: list[Rect] = []
    coins: list[Rect | None] = []
    masked = screen.copy()
    for area, _ in labels:
        region = ctx.screen_loader.get_area('贝果-备战', area)
        if region is None:
            raise ValueError(f'缺少贝果画面区域：贝果-备战/{area}')
        rect = region.pc_rect
        regions.append(rect)
        coin = _loadout_coin_rect(cv2_utils.crop_image_only(screen, rect))
        if coin is not None:
            coin.add_offset(rect.left_top)
            masked[coin.y1:coin.y2, coin.x1:coin.x2] = 0
        coins.append(coin)
    bounds = Rect(max(0, min(rect.x1 for rect in regions) - 20), 0, screen.shape[1], screen.shape[0])
    all_matches = ctx.ocr_service.get_ocr_result_list(masked, rect=bounds, crop_first=True)
    for (area, label), rect, coin in zip(labels, regions, coins, strict=True):
        if coin is None:
            values[area] = ''
            log.info('贝果价值识别未知：%s，金币缺失、多候选、边界不完整或邻接白字', area)
            continue
        observations: list[str] = []
        amount_texts: list[str] = []
        value = ''
        for stage in ('面板', '标题条', '整屏'):
            if stage == '面板':
                matches = [match for match in all_matches
                           if cal_utils.cal_overlap_percent(match.rect, rect, base=match.rect) > 0.7]
            else:
                matches = ctx.ocr_service.get_ocr_result_list(
                    masked, rect=rect, crop_first=stage == '标题条',
                )
            observations.append(f'{stage}：{[(match.data, match.rect) for match in matches]}')
            # 不忽略跨边界或未能成为候选的数字，防止重读只剩尾部零。
            amount_texts.extend(match.data for match in matches if re.search(r'[0-9]', match.data))
            value = _loadout_value_candidate(matches, label, coin, masked)
            if value:
                break
        conflict = _parse_loadout_value(value) == 0 and any(re.search(r'[1-9]', text) for text in amount_texts)
        if conflict:
            value = ''
        if not value:
            reason = '零值与非零证据冲突' if conflict else '标题、金额或位置关系不明确'
            log.info('贝果价值识别未知：%s，金币=%s，原因=%s，%s', area, coin, reason, '；'.join(observations))
        values[area] = value
    for area in ('背包数量', '安全箱数量'):
        values[area] = read_area(ctx, screen, '贝果-备战', area)
    return values


def prepare_detail_state(ctx: ZContext, screen: MatLike) -> bool | None:
    """识别备战详情；仅三个分区标题均在原位时确认无遮挡，其余保留未知。"""
    areas = (
        ('武备价值', '代理人武备'), ('装备价值', '装备'), ('道具价值', '道具'),
    )
    regions: list[tuple[Rect, str]] = []
    for area, label in areas:
        region = ctx.screen_loader.get_area('贝果-备战', area)
        if region is None:
            raise ValueError(f'缺少贝果画面区域：贝果-备战/{area}')
        regions.append((region.pc_rect, label))
    bounds = Rect(min(rect.x1 for rect, _ in regions) - 20, 0, screen.shape[1], screen.shape[0])
    matches = ctx.ocr_service.get_ocr_result_list(screen, rect=bounds, crop_first=True)
    text = ''.join(re.sub(r'\s', '', match.data) for match in matches)
    if any(label in text for label in ('放入背包', '放入安全箱', '放入仓储枢纽')):
        return True
    for rect, label in regions:
        title = ''.join(re.sub(r'\s', '', match.data) for match in matches
                        if cal_utils.cal_overlap_percent(match.rect, rect, base=match.rect) > 0.7)
        if label not in title:
            return None
    return False


def empty_capacity(text: str) -> bool:
    """仅接受已识别的零占用和正容量，不接受空字符串或锁定容量。"""
    return re.fullmatch(r'0/[1-9][0-9]*', text.replace(' ', '')) is not None


def parse_capacity_pair(text: str) -> tuple[int, int] | None:
    """从“全部(235/280)”一类文字读取占用与容量；识别不清返回 None。"""
    match = re.search(r'(\d+)\s*/\s*(\d+)', text.replace(' ', ''))
    if match is None:
        return None
    used = int(match.group(1))
    total = int(match.group(2))
    if total <= 0 or used > total:
        return None
    return used, total


def parse_filter_count(text: str) -> int | None:
    """读取快速选择「符合以上条件的道具数量」。"""
    compact = text.replace(' ', '')
    match = re.search(r'数量[:：]?(\d+)', compact)
    if match is not None:
        return int(match.group(1))
    match = re.search(r'(\d+)$', compact)
    if match is not None and '符合' in compact:
        return int(match.group(1))
    return None


def zero_loadout(values: dict[str, str]) -> bool:
    """三个价值区和两个占用区均明确为空才允许零携带入场。"""
    return all(_parse_loadout_value(values.get(name, '')) == 0 for name in ('武备价值', '装备价值', '道具价值')) and all(
        empty_capacity(values.get(name, '')) for name in ('背包数量', '安全箱数量')
    )


def complete_loadout(values: dict[str, str]) -> bool:
    """五项全部合法才允许清空；识别缺失、冲突或非法容量不能算非零。"""
    for name in ('武备价值', '装备价值', '道具价值'):
        if _parse_loadout_value(values.get(name, '')) is None:
            return False
    for name in ('背包数量', '安全箱数量'):
        text = values.get(name, '').replace(' ', '')
        if re.fullmatch(r'[0-9]+/[1-9][0-9]*', text) is None:
            return False
        if parse_capacity_pair(text) is None:
            return False
    return True


def read_entry_warning_text(ctx: ZContext, screen: MatLike) -> str:
    """按行读取入场提示，避免同一行识别框的高度偏差颠倒文字顺序。"""
    area = ctx.screen_loader.get_area('贝果-入场确认', '提示')
    if area is None:
        raise ValueError('缺少贝果画面区域：贝果-入场确认/提示')
    matches = ctx.ocr_service.get_ocr_result_list(
        screen, rect=area.pc_rect, crop_first=True, color_range=area.color_range,
    )
    # 先按行的中心高度排列，再复用合行规则从左到右拼接；不丢弃任何提示文字。
    ordered = sorted(matches, key=lambda match: (match.center.y, match.x))
    ocr_map = ctx.ocr_service.convert_list_to_map(ordered)
    return ocr_utils.merge_ocr_result_to_single_line(ocr_map, join_space=False)


def entry_warning(text: str) -> str | None:
    """区分已知入场弹窗；其他确认框不能自动确认。

    装备提示可能只识别到第一行，沿用关键片段匹配；未满编提示要求完整文案。
    """
    compact = re.sub(r'[\s，,。？?：:（）()、]', '', text)
    if compact == '代理人队伍未满编是否继续出战':
        return '代理人队伍未满编'
    if (
        '当前装备价值为0' in compact
        and '未达到推荐价值' in compact
        and str(RECOMMENDED_VALUE) in compact
    ):
        return '零装备价值'
    if '存在未装备武备的代理人' in compact:
        return '未装备武备'
    if '未穿戴队伍装备' in compact and ('异体刃' in compact or '抗蚀器' in compact):
        return '未穿戴队伍装备'
    return None


def expected_map(text: str) -> bool:
    """只接受完整高危雅努斯标题，拒绝其他难度与相似名称。"""
    return re.sub(r'[\s\[\]【】]', '', text) == MAP_TITLE
