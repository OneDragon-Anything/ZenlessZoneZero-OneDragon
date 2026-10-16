from __future__ import annotations

import re
from typing import TYPE_CHECKING

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.screen import screen_utils
from one_dragon.utils import cal_utils
from zzz_od.application.bagel.bagel_const import MAP_TITLE, RECOMMENDED_VALUE

if TYPE_CHECKING:
    from cv2.typing import MatLike

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


def _plain_value(texts: list[str], label: str | None) -> str:
    """标题条里恰好一个纯数字才采用。面板识别还要求标题文字在同一区域。"""
    if label is not None and label not in texts:
        return ''
    numbers = [text for text in texts if re.fullmatch(r'[0-9]+', text)]
    if len(numbers) == 1:
        return numbers[0]
    return ''


def _glued_value(texts: list[str]) -> str:
    """金币图标粘在数字前时，整段类似「@0」。只接受一段这样的结果。"""
    if any(re.fullmatch(r'[0-9]+', text) for text in texts):
        return ''
    found: list[str] = []
    for text in texts:
        match = re.fullmatch(r'[^0-9]{1,2}([0-9]+)', text.strip())
        if match is not None:
            found.append(match.group(1))
    if len(found) == 1:
        return found[0]
    return ''


def read_loadout(ctx: ZContext, screen: MatLike) -> dict[str, str]:
    """先识别备战右侧面板，小数字漏识别时再单独裁完整标题条。"""
    values: dict[str, str] = {}
    labels = (
        ('武备价值', '代理人武备'), ('装备价值', '装备'), ('道具价值', '道具'),
    )
    regions: list[Rect] = []
    for area, _ in labels:
        region = ctx.screen_loader.get_area('贝果-备战', area)
        if region is None:
            raise ValueError(f'缺少贝果画面区域：贝果-备战/{area}')
        regions.append(region.pc_rect)
    # 保留完整标题与价值的上下文，但不识别无关的左侧仓储库存列表。
    bounds = Rect(max(0, min(rect.x1 for rect in regions) - 20), 0, screen.shape[1], screen.shape[0])
    all_matches = ctx.ocr_service.get_ocr_result_list(screen, rect=bounds, crop_first=True)
    for (area, label), rect in zip(labels, regions, strict=True):
        matches = [match for match in all_matches
                   if cal_utils.cal_overlap_percent(match.rect, rect, base=match.rect) > 0.7]
        texts = [match.data for match in matches]
        value = _plain_value(texts, label)
        if not value:
            cropped = ctx.ocr_service.get_ocr_result_list(
                screen, rect=rect, crop_first=True,
            )
            crop_texts = [match.data for match in cropped]
            value = _plain_value(crop_texts, None) or _glued_value(crop_texts)
            texts.extend(crop_texts)
        if not value:
            # 裁图有时把标题和金额粘成一段；仅在仍无法解析时回退到整屏识别。
            full = ctx.ocr_service.get_ocr_result_list(screen, rect=rect, crop_first=False)
            full_texts = [match.data for match in full]
            value = _plain_value(full_texts, label)
            texts.extend(full_texts)
        # 金币图标可能被识别为 0；单条裁剪漏字不能抹掉合并区域已读到的非零证据。
        if value == '0' and any(re.search(r'[1-9]', text) for text in texts):
            value = ''
        values[area] = value
    for area in ('背包数量', '安全箱数量'):
        values[area] = read_area(ctx, screen, '贝果-备战', area)
    return values


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
    return all(values.get(name, '').strip() == '0' for name in ('武备价值', '装备价值', '道具价值')) and all(
        empty_capacity(values.get(name, '')) for name in ('背包数量', '安全箱数量')
    )


def complete_loadout(values: dict[str, str]) -> bool:
    """五项全部合法才允许清空；识别缺失、冲突或非法容量不能算非零。"""
    for name in ('武备价值', '装备价值', '道具价值'):
        if re.fullmatch(r'[0-9]+', values.get(name, '').strip()) is None:
            return False
    for name in ('背包数量', '安全箱数量'):
        text = values.get(name, '').replace(' ', '')
        if re.fullmatch(r'[0-9]+/[1-9][0-9]*', text) is None:
            return False
        if parse_capacity_pair(text) is None:
            return False
    return True


def entry_warning(text: str) -> str | None:
    """区分三个已实拍的入场弹窗；其他确认框不能自动确认。

    提示区可能只 OCR 到第一行，因此用关键片段匹配，不用整句全等。
    """
    compact = re.sub(r'[\s，,。？?：:（）()、]', '', text)
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
