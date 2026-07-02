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
