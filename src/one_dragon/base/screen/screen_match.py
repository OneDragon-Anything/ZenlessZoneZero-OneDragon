"""画面匹配的强化版匹配函数与返回结构。

本模块在框架现有 ``find_area_in_screen``(返回布尔枚举)之上,新增强化版:
- ``find_area_with_detail``:单 area 匹配,返回命中详情(坐标/文本/置信度),
  默认 ``crop_first=False`` 走全图 OCR 缓存复用(与 ``find_area_in_screen`` 默认相反)。
- ``find_screen_matches``:一次遍历分级匹配画面(精准早停 / top_n)。

数据结构 ``AreaType`` / ``AreaMatchDetail`` / ``ScreenMatch`` 为纯 dataclass,
供 backend 层 ``AnalyzeScreenResult`` 跨层引用(``zzz_od`` 依赖 ``one_dragon``)。
"""
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from one_dragon.base.matcher.match_result import MatchResultList
from one_dragon.base.matcher.ocr.ocr_match_result import OcrMatchResult
from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.utils import str_utils
from one_dragon.utils.i18_utils import gt

if TYPE_CHECKING:
    from cv2.typing import MatLike

    from one_dragon.base.operation.one_dragon_context import OneDragonContext
    from one_dragon.base.screen.screen_info import ScreenInfo


class AreaType(str, Enum):
    """画面区域类型(str Enum,序列化为 'text'/'template')。

    Attributes:
        TEXT: 文本区域(OCR 识别)。
        TEMPLATE: 模板区域(模板匹配)。
    """

    TEXT = 'text'
    TEMPLATE = 'template'


@dataclass
class AreaMatchDetail:
    """单个 area 的命中详情。

    Attributes:
        area_name: 区域名称(中文,如「菜单标题」)。
        area_type: 区域类型(文本/模板)。
        x: 命中左上角 x(绝对坐标)。
        y: 命中左上角 y(绝对坐标)。
        width: 命中宽度。
        height: 命中高度。
        text: 文本区域实际命中文本(模板区域为 None)。
        confidence: 置信度(文本=ocr score,模板=匹配度)。
    """

    area_name: str
    area_type: AreaType
    x: int
    y: int
    width: int
    height: int
    text: str | None = None
    confidence: float | None = None


@dataclass
class ScreenMatch:
    """单个画面的匹配结果。

    Attributes:
        screen_name: 画面名称(中文,关联 ``screen_info.screen_name``)。
        is_precise: True=精准命中(``id_mark`` 全中);False=模糊 top_n 候选。
        areas: 命中的 area 详情(只返命中的;是结果层,非 ``ScreenArea`` 配置)。
    """

    screen_name: str
    is_precise: bool
    areas: list[AreaMatchDetail]


def find_area_with_detail(
    ctx: 'OneDragonContext',
    screen: 'MatLike',
    area: ScreenArea,
    crop_first: bool = False,
) -> AreaMatchDetail | None:
    """单 area 强化匹配,返回命中详情;纯定位区域或未命中返 None。

    与 ``find_area_in_screen`` 的差异:默认 ``crop_first=False`` 走全图 OCR 缓存
    复用(性能,见 spec §2.5);返回 ``AreaMatchDetail`` 详情而非布尔枚举。

    Args:
        ctx: 运行上下文(提供 ``ocr_service`` / ``tm``)。
        screen: 游戏截图。
        area: 待匹配的区域。
        crop_first: 是否先裁剪再 OCR,默认 False(全图缓存复用)。

    Returns:
        命中详情;纯定位区域或未命中返 None。
    """
    if area.is_text_area:
        ocr_result_list: list[OcrMatchResult] = ctx.ocr_service.get_ocr_result_list(
            image=screen,
            rect=area.rect,
            color_range=area.color_range,
            crop_first=crop_first,
        )
        for ocr_result in ocr_result_list:
            if str_utils.find_by_lcs(gt(area.text, 'game'), ocr_result.data, percent=area.lcs_percent):
                return AreaMatchDetail(
                    area_name=area.area_name,
                    area_type=AreaType.TEXT,
                    x=int(ocr_result.x),
                    y=int(ocr_result.y),
                    width=int(ocr_result.w),
                    height=int(ocr_result.h),
                    text=ocr_result.data,
                    confidence=float(ocr_result.confidence),
                )
        return None
    if area.is_template_area:
        mrl: MatchResultList = ctx.tm.crop_and_match_template(
            screen,
            area.rect,
            area.template_sub_dir,
            area.template_id,
            threshold=area.template_match_threshold,
        )
        if mrl.max is None:
            return None
        # mrl.max 坐标是相对 area.rect 左上角的局部坐标,转绝对坐标
        return AreaMatchDetail(
            area_name=area.area_name,
            area_type=AreaType.TEMPLATE,
            x=int(mrl.max.x + area.rect.x1),
            y=int(mrl.max.y + area.rect.y1),
            width=int(mrl.max.w),
            height=int(mrl.max.h),
            confidence=float(mrl.max.confidence),
        )
    return None


def find_screen_matches(
    ctx: 'OneDragonContext',
    screen: 'MatLike',
    top_n: int = 5,
) -> list[ScreenMatch]:
    """一次遍历分级匹配画面:精准早停 / 否则命中数 top_n。

    本函数纯匹配,**无副作用**(可独立测试);精准命中后的 ``current_screen_name``
    回写由 backend ``analyze`` 层负责。

    每个画面算所有 area(同时得 ``id_mark`` 全中标志 + 命中数),精准判定与命中数
    在同一次遍历得到,无独立「模糊阶段」重复遍历(见 spec §2.1.2)。

    遍历顺序:``current``/``last`` 有值 → BFS 扩散(+ 兜底全量);均 None → 全量。
    精准早停:遇 ``id_mark`` 全中画面即返、停止。无精准 → 按命中数 top_n(命中数
    相同按 ``screen_info_list`` 顺序 tie-break,稳定可复现)。

    Args:
        ctx: 运行上下文。
        screen: 游戏截图。
        top_n: 模糊候选返回数,默认 5。

    Returns:
        精准命中 → ``[1 个 ScreenMatch(is_precise=True)]``;否则 top_n 个
        ``ScreenMatch(is_precise=False)``。
    """
    loader = ctx.screen_loader
    active_names = loader.active_screen_names  # None 或 set[str]
    order = {s.screen_name: i for i, s in enumerate(loader.screen_info_list)}

    # 1) 确定遍历顺序:BFS(若有起点)+ 兜底全量
    # BFS 起点集合:current 在前、last 在后(遍历顺序为 current 全树 → last 全树,
    # 非并行双起点;精准早停使共享 id_mark 时 current 子树先命中)
    bfs_seeds: list[str] = []
    if loader.current_screen_name is not None:
        bfs_seeds.append(loader.current_screen_name)
    if loader.last_screen_name is not None and loader.last_screen_name not in bfs_seeds:
        bfs_seeds.append(loader.last_screen_name)

    visited: set[str] = set(bfs_seeds)   # seed 标 visited,避免稠密 goto 图重复入队
    ordered_names: list[str] = []

    def _expand_goto(screen_info: 'ScreenInfo') -> None:
        for area in screen_info.area_list:
            for goto in area.goto_list or []:
                if goto not in visited:
                    visited.add(goto)
                    bfs_seeds.append(goto)

    # BFS 扩散(scope 模式下非 active 候选跳过匹配但展开邻居;backend 恒全量不触发)
    if bfs_seeds:
        while bfs_seeds:
            name = bfs_seeds.pop(0)
            if name in ordered_names:
                continue
            screen_info = loader.screen_info_map.get(name)
            if screen_info is None:
                continue
            if active_names is not None and name not in active_names:
                _expand_goto(screen_info)
                continue
            ordered_names.append(name)
            _expand_goto(screen_info)

    # 兜底全量:未在 BFS 集合中的 active 画面
    for screen_info in loader.active_screen_info_list:
        if screen_info.screen_name not in ordered_names:
            ordered_names.append(screen_info.screen_name)

    # 2) 一次遍历:每画面算所有 area + 精准早停 / 积累命中数
    fuzzy: list[tuple[str, list[AreaMatchDetail], int]] = []   # (name, areas, 命中数)
    for name in ordered_names:
        screen_info = loader.screen_info_map.get(name)
        if screen_info is None:
            continue
        hit_details: list[AreaMatchDetail] = []
        hit_names: set[str] = set()
        for area in screen_info.area_list:
            # 模块级引用调用(测试用 monkeypatch.setattr(_sm, ...)patch 模块属性)
            detail = find_area_with_detail(ctx, screen, area)
            if detail is not None:
                hit_details.append(detail)
                hit_names.add(area.area_name)
        id_mark_names = {a.area_name for a in screen_info.area_list if a.id_mark}
        is_precise = len(id_mark_names) > 0 and id_mark_names.issubset(hit_names)
        if is_precise:
            return [ScreenMatch(screen_name=name, is_precise=True, areas=hit_details)]
        fuzzy.append((name, hit_details, len(hit_details)))

    # 3) 无精准 → 命中数 top_n(tie-break 用 screen_info_list 顺序)
    fuzzy.sort(key=lambda item: (-item[2], order.get(item[0], len(order))))
    return [ScreenMatch(screen_name=name, is_precise=False, areas=areas)
            for name, areas, _ in fuzzy[:top_n] if areas]
