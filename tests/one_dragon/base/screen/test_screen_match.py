"""screen_match 框架强化匹配测试。"""
from one_dragon.base.screen.screen_match import AreaType, AreaMatchDetail, ScreenMatch


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
