"""screen_match 框架强化匹配测试。"""
from unittest.mock import MagicMock

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.base.screen.screen_match import AreaType, AreaMatchDetail, ScreenMatch, find_area_with_detail


def test_area_type_is_str_enum():
    """AreaType 是 str Enum,值 'text'/'template',可直接当字符串用。"""
    assert AreaType.TEXT == 'text'
    assert AreaType.TEMPLATE == 'template'
    assert isinstance(AreaType.TEXT, str)


def test_area_match_detail_text():
    """文本命中详情构造(text 字段、置信度)。"""
    d = AreaMatchDetail(area_name='菜单标题', area_type=AreaType.TEXT,
                        x=120, y=40, width=280, height=50, text='菜单', confidence=0.95)
    assert d.area_name == '菜单标题'
    assert d.area_type == AreaType.TEXT
    assert d.text == '菜单'
    assert d.confidence == 0.95


def test_area_match_detail_template_optional_text():
    """模板命中详情 text 默认 None。"""
    d = AreaMatchDetail(area_name='邮箱', area_type=AreaType.TEMPLATE,
                        x=1700, y=40, width=60, height=60, confidence=0.92)
    assert d.text is None
    assert d.confidence == 0.92


def test_screen_match_construction():
    """ScreenMatch 构造(is_precise / areas 列表)。"""
    d = AreaMatchDetail(area_name='标题', area_type=AreaType.TEXT,
                        x=1, y=1, width=1, height=1)
    m = ScreenMatch(screen_name='菜单', is_precise=True, areas=[d])
    assert m.screen_name == '菜单'
    assert m.is_precise is True
    assert len(m.areas) == 1


def _text_area(text: str = '战斗') -> ScreenArea:
    return ScreenArea(area_name=f'按钮-{text}', pc_rect=Rect(300, 800, 500, 880),
                      text=text, lcs_percent=0.5)


def _template_area() -> ScreenArea:
    return ScreenArea(area_name='邮箱图标', pc_rect=Rect(1700, 40, 1760, 100),
                      template_id='mail', template_sub_dir='menu',
                      template_match_threshold=0.7)


def _plain_area() -> ScreenArea:
    return ScreenArea(area_name='点击区', pc_rect=Rect(0, 0, 100, 100))


def test_find_area_text_match_returns_detail():
    ctx = MagicMock()
    ocr = MagicMock(data='战斗', confidence=0.95, x=300, y=800, w=200, h=80)
    ctx.ocr_service.get_ocr_result_list.return_value = [ocr]
    d = find_area_with_detail(ctx, MagicMock(), _text_area())
    assert d is not None
    assert d.area_type == AreaType.TEXT
    assert d.text == '战斗'
    assert d.confidence == 0.95
    assert (d.x, d.y, d.width, d.height) == (300, 800, 200, 80)


def test_find_area_text_no_match_returns_none():
    ctx = MagicMock()
    ocr = MagicMock(data='设置')
    ctx.ocr_service.get_ocr_result_list.return_value = [ocr]
    assert find_area_with_detail(ctx, MagicMock(), _text_area()) is None


def test_find_area_template_match_absolute_coord():
    """模板命中返回绝对坐标(mrl.max + area.rect 偏移)。"""
    ctx = MagicMock()
    mrl = MagicMock()
    mrl.max = MagicMock(x=10, y=20, w=50, h=60, confidence=0.92)
    ctx.tm.crop_and_match_template.return_value = mrl
    d = find_area_with_detail(ctx, MagicMock(), _template_area())
    assert d is not None
    assert d.area_type == AreaType.TEMPLATE
    assert d.confidence == 0.92
    assert (d.x, d.y) == (1710, 60)      # 1700+10, 40+20
    assert (d.width, d.height) == (50, 60)


def test_find_area_template_no_match_returns_none():
    ctx = MagicMock()
    mrl = MagicMock()
    mrl.max = None
    ctx.tm.crop_and_match_template.return_value = mrl
    assert find_area_with_detail(ctx, MagicMock(), _template_area()) is None


def test_find_area_plain_returns_none():
    """纯定位区域(无 text/template)返 None,不参与识别。"""
    ctx = MagicMock()
    assert find_area_with_detail(ctx, MagicMock(), _plain_area()) is None


def test_find_area_default_crop_first_false():
    """默认 crop_first=False(全图 OCR 缓存复用,与 find_area_in_screen 默认 True 相反)。"""
    ctx = MagicMock()
    ctx.ocr_service.get_ocr_result_list.return_value = []
    find_area_with_detail(ctx, MagicMock(), _text_area())
    _args, kwargs = ctx.ocr_service.get_ocr_result_list.call_args
    assert kwargs.get('crop_first') is False
