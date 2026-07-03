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
