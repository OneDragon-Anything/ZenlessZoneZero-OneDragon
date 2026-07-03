from dataclasses import asdict

from one_dragon.base.screen.screen_match import AreaMatchDetail, AreaType, ScreenMatch
from zzz_od.backend.schemas import AnalyzeScreenResult, OcrText, WindowStatus


def test_ocr_text_fields() -> None:
    """校验 OcrText 各字段的取值与默认值。"""
    t = OcrText(text="体力", x=10, y=20, width=30, height=40)
    assert t.text == "体力"
    assert (t.x, t.y, t.width, t.height) == (10, 20, 30, 40)


def test_analyze_result_default_error_none() -> None:
    """校验 AnalyzeScreenResult 的 error 默认为 None、ocr_texts 透传。"""
    r = AnalyzeScreenResult(success=True, ocr_texts=[])
    assert r.error is None
    assert r.ocr_texts == []


def test_window_status_optional_rect() -> None:
    """校验 WindowStatus 的窗口矩形字段可选，缺省为 None。"""
    w = WindowStatus(win_title="绝区零", is_win_valid=True, is_win_active=True, is_win_scale=True)
    assert w.x is None
    assert w.width is None
    w2 = WindowStatus(win_title="t", is_win_valid=True, is_win_active=False, is_win_scale=True, x=1, y=2, width=3, height=4)
    assert (w2.x, w2.y, w2.width, w2.height) == (1, 2, 3, 4)


def test_analyze_result_has_screens_field() -> None:
    """AnalyzeScreenResult 含 screens 字段,可装 ScreenMatch 列表。"""
    detail = AreaMatchDetail(area_name='标题', area_type=AreaType.TEXT,
                             x=1, y=1, width=1, height=1, text='菜单')
    match = ScreenMatch(screen_name='菜单', is_precise=True, areas=[detail])
    r = AnalyzeScreenResult(success=True, ocr_texts=[], screens=[match], error=None)
    assert r.success is True
    assert len(r.screens) == 1
    assert r.screens[0].screen_name == '菜单'


def test_analyze_result_asdict_nested_serializable() -> None:
    """asdict 递归嵌套 dataclass + str Enum,可序列化(area_type 序列化为 'text')。"""
    detail = AreaMatchDetail(area_name='标题', area_type=AreaType.TEXT,
                             x=1, y=1, width=1, height=1, text='菜单')
    match = ScreenMatch(screen_name='菜单', is_precise=True, areas=[detail])
    r = AnalyzeScreenResult(success=True, ocr_texts=[], screens=[match], error=None)
    d = asdict(r)
    assert d['screens'][0]['areas'][0]['area_type'] == AreaType.TEXT  # str Enum 原值
