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
