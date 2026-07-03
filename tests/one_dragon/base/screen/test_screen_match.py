"""screen_match 框架强化匹配测试。"""
from unittest.mock import MagicMock

import one_dragon.base.screen.screen_match as _sm
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.base.screen.screen_info import ScreenInfo
from one_dragon.base.screen.screen_match import (
    AreaMatchDetail,
    AreaType,
    ScreenMatch,
    find_area_with_detail,
    find_screen_matches,
)


def test_area_type_is_str_enum() -> None:
    """AreaType 是 str Enum,值 'text'/'template',可直接当字符串用。"""
    assert AreaType.TEXT == 'text'
    assert AreaType.TEMPLATE == 'template'
    assert isinstance(AreaType.TEXT, str)


def test_area_match_detail_text() -> None:
    """文本命中详情构造(text 字段、置信度)。"""
    d = AreaMatchDetail(area_name='菜单标题', area_type=AreaType.TEXT,
                        x=120, y=40, width=280, height=50, text='菜单', confidence=0.95)
    assert d.area_name == '菜单标题'
    assert d.area_type == AreaType.TEXT
    assert d.text == '菜单'
    assert d.confidence == 0.95


def test_area_match_detail_template_optional_text() -> None:
    """模板命中详情 text 默认 None。"""
    d = AreaMatchDetail(area_name='邮箱', area_type=AreaType.TEMPLATE,
                        x=1700, y=40, width=60, height=60, confidence=0.92)
    assert d.text is None
    assert d.confidence == 0.92


def test_screen_match_construction() -> None:
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


def test_find_area_text_match_returns_detail() -> None:
    ctx = MagicMock()
    ocr = MagicMock(data='战斗', confidence=0.95, x=300, y=800, w=200, h=80)
    ctx.ocr_service.get_ocr_result_list.return_value = [ocr]
    d = find_area_with_detail(ctx, MagicMock(), _text_area())
    assert d is not None
    assert d.area_type == AreaType.TEXT
    assert d.text == '战斗'
    assert d.confidence == 0.95
    assert (d.x, d.y, d.width, d.height) == (300, 800, 200, 80)


def test_find_area_text_no_match_returns_none() -> None:
    ctx = MagicMock()
    ocr = MagicMock(data='设置')
    ctx.ocr_service.get_ocr_result_list.return_value = [ocr]
    assert find_area_with_detail(ctx, MagicMock(), _text_area()) is None


def test_find_area_template_match_absolute_coord() -> None:
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


def test_find_area_template_no_match_returns_none() -> None:
    ctx = MagicMock()
    mrl = MagicMock()
    mrl.max = None
    ctx.tm.crop_and_match_template.return_value = mrl
    assert find_area_with_detail(ctx, MagicMock(), _template_area()) is None


def test_find_area_plain_returns_none() -> None:
    """纯定位区域(无 text/template)返 None,不参与识别。"""
    ctx = MagicMock()
    assert find_area_with_detail(ctx, MagicMock(), _plain_area()) is None


def test_find_area_default_crop_first_false() -> None:
    """默认 crop_first=False(全图 OCR 缓存复用,与 find_area_in_screen 默认 True 相反)。"""
    ctx = MagicMock()
    ctx.ocr_service.get_ocr_result_list.return_value = []
    find_area_with_detail(ctx, MagicMock(), _text_area())
    _args, kwargs = ctx.ocr_service.get_ocr_result_list.call_args
    assert kwargs.get('crop_first') is False


# --- find_screen_matches 测试(find_screen_matches 一次遍历分级匹配)---


def _screen_info(name: str, areas: list[ScreenArea]) -> ScreenInfo:
    """用 ScreenInfo 构造一个画面(area_list 来自入参)。"""
    data = {'screen_id': name, 'screen_name': name, 'app_id': '',
            'area_list': [a.to_dict() for a in areas]}
    return ScreenInfo(data)


def _id_mark_text_area(name: str, text: str) -> ScreenArea:
    a = ScreenArea(area_name=name, pc_rect=Rect(0, 0, 100, 50), text=text, lcs_percent=0.5)
    a.id_mark = True
    return a


def _make_loader(screens: list[ScreenInfo], current: str | None = None,
                 last: str | None = None) -> MagicMock:
    """构造 mock screen_loader。"""
    loader = MagicMock()
    loader.screen_info_list = screens
    loader.active_screen_info_list = screens
    loader.screen_info_map = {s.screen_name: s for s in screens}
    loader.active_screen_names = None   # backend 语境 scope 不激活
    loader.current_screen_name = current
    loader.last_screen_name = last
    return loader


def _patch_find(monkeypatch, hit_map: dict) -> None:
    """patch 模块级 find_area_with_detail:按 area_name 决定命中(走 text 分支语义)。

    必须用 monkeypatch.setattr(_sm, ...)patch 模块属性 —— find_screen_matches 内部以
    模块级引用调用 find_area_with_detail(见实现注),patch 模块属性才生效。
    """
    def fake_find(ctx, screen, area, crop_first=False):
        if area.area_name in hit_map and hit_map[area.area_name]:
            return AreaMatchDetail(area_name=area.area_name, area_type=AreaType.TEXT,
                                   x=0, y=0, width=10, height=10, text=area.text or '')
        return None
    monkeypatch.setattr(_sm, 'find_area_with_detail', fake_find)


def test_precise_early_stop_when_current_set(monkeypatch) -> None:
    """current 有值 + 该画面 id_mark 全中 → 精准早停返 1 个 is_precise=True。"""
    menu = _screen_info('菜单', [_id_mark_text_area('菜单标题', '菜单')])
    ctx = MagicMock()
    ctx.screen_loader = _make_loader([menu], current='菜单')
    _patch_find(monkeypatch, {'菜单标题': True})
    result = find_screen_matches(ctx, MagicMock())
    assert len(result) == 1
    assert result[0].screen_name == '菜单'
    assert result[0].is_precise is True


def test_no_precise_returns_topn_by_hit_count(monkeypatch) -> None:
    """无 id_mark 全中 → 按命中数 top_n(is_precise=False)。"""
    a = _screen_info('画面A', [ScreenArea(area_name='a1', pc_rect=Rect(0, 0, 10, 10), text='x'),
                               ScreenArea(area_name='a2', pc_rect=Rect(0, 0, 10, 10), text='y')])
    b = _screen_info('画面B', [ScreenArea(area_name='b1', pc_rect=Rect(0, 0, 10, 10), text='z')])
    ctx = MagicMock()
    ctx.screen_loader = _make_loader([a, b])
    _patch_find(monkeypatch, {'a1': True, 'a2': True, 'b1': True})
    result = find_screen_matches(ctx, MagicMock(), top_n=5)
    assert len(result) == 2
    assert result[0].screen_name == '画面A'   # 命中 2 个,排前
    assert result[0].is_precise is False
    assert result[1].screen_name == '画面B'


def test_current_last_none_full_traversal(monkeypatch) -> None:
    """current/last 均 None → 直接全量遍历(无 BFS)。"""
    menu = _screen_info('菜单', [_id_mark_text_area('标题', '菜单')])
    ctx = MagicMock()
    ctx.screen_loader = _make_loader([menu], current=None, last=None)
    _patch_find(monkeypatch, {'标题': True})
    result = find_screen_matches(ctx, MagicMock())
    assert len(result) == 1
    assert result[0].is_precise is True


def test_no_id_mark_screen_only_enters_topn(monkeypatch) -> None:
    """无 id_mark 画面精准永假,但参与命中数(可进 top_n)。"""
    plain = _screen_info('无标识画面', [ScreenArea(area_name='p1', pc_rect=Rect(0, 0, 10, 10), text='p')])
    ctx = MagicMock()
    ctx.screen_loader = _make_loader([plain])
    _patch_find(monkeypatch, {'p1': True})
    result = find_screen_matches(ctx, MagicMock())
    assert len(result) == 1
    assert result[0].is_precise is False


def test_bfs_traverses_goto_neighbors(monkeypatch) -> None:
    """BFS 从 current 沿 goto_list 扩散到邻接画面(图不连通时兜底全量覆盖)。"""
    a = _screen_info('A', [_id_mark_text_area('a_mark', 'a')])
    a_area = ScreenArea(area_name='a_goto', pc_rect=Rect(0, 0, 10, 10), text='goto')
    a_area.goto_list = ['B']
    a.area_list.append(a_area)
    b = _screen_info('B', [_id_mark_text_area('b_mark', 'b')])
    ctx = MagicMock()
    ctx.screen_loader = _make_loader([a, b], current='A')
    _patch_find(monkeypatch, {'b_mark': True})   # A 的 a_mark 未中 → 沿 goto 到 B
    result = find_screen_matches(ctx, MagicMock())
    assert len(result) == 1
    assert result[0].screen_name == 'B'
    assert result[0].is_precise is True


def test_precise_early_stop_returns_first_processed(monkeypatch) -> None:
    """current 起的精准早停:两画面共享 id_mark 时,current 先处理即返(B 不会进 BFS)。

    (精准早停使「共享 id_mark tie-break」实际不可达 —— 首个精准即返,不存在多精准排序。)
    """
    a = _screen_info('A', [_id_mark_text_area('shared', 'x')])
    b = _screen_info('B', [_id_mark_text_area('shared', 'x')])
    ctx = MagicMock()
    ctx.screen_loader = _make_loader([a, b], current='A')
    _patch_find(monkeypatch, {'shared': True})
    result = find_screen_matches(ctx, MagicMock())
    assert len(result) == 1
    assert result[0].screen_name == 'A'   # current=A,BFS 从 A 起,A 首个精准即返


def test_color_range_distinct_ocr_called_per_range(monkeypatch) -> None:
    """两个不同 color_range 的 text area → OCR 各调一次(不同 color_range 缓存不复用)。

    spec §2.5 性能论据:find_area_with_detail 默认 crop_first=False 走全图 OCR 缓存
    复用,但缓存键含 color_range;不同 color_range 各触发一次全图 OCR。
    """
    area_a = ScreenArea(area_name='a', pc_rect=Rect(0, 0, 100, 50), text='x', lcs_percent=0.5,
                        color_range=[[0, 0, 0], [100, 100, 100]])
    area_b = ScreenArea(area_name='b', pc_rect=Rect(0, 0, 100, 50), text='y', lcs_percent=0.5,
                        color_range=[[200, 200, 200], [255, 255, 255]])
    screen = _screen_info('S', [area_a, area_b])
    ctx = MagicMock()
    ctx.screen_loader = _make_loader([screen])
    ctx.ocr_service.get_ocr_result_list.return_value = []

    find_screen_matches(ctx, MagicMock())

    assert ctx.ocr_service.get_ocr_result_list.call_count == 2   # 不同 color_range 各一次


def test_color_range_none_ocr_reuses_cache(monkeypatch) -> None:
    """两个 color_range=None(相同)的 text area → OCR 只调一次(全图缓存复用契约)。

    spec §2.5 性能论据根基:同 color_range + crop_first=False 时,ocr_service 内部
    缓存命中、不重复全图 OCR。本测试用 side_effect 模拟该缓存:以 (color_range, crop_first)
    为键,首次"实际跑 OCR"(计 1 次),同键后续命中缓存(不再计)。find_screen_matches
    两次 find_area_with_detail 因 color_range 一致 → 真实 OCR 只 1 次。
    """
    area_a = ScreenArea(area_name='a', pc_rect=Rect(0, 0, 100, 50), text='x', lcs_percent=0.5)
    area_b = ScreenArea(area_name='b', pc_rect=Rect(0, 0, 100, 50), text='y', lcs_percent=0.5)
    screen = _screen_info('S', [area_a, area_b])
    ctx = MagicMock()
    ctx.screen_loader = _make_loader([screen])

    real_call_keys: list[tuple] = []
    cache: dict[tuple, list] = {}

    def _ocr_with_cache(image, rect=None, color_range=None, crop_first=True):
        key = (repr(color_range), crop_first)
        if key not in cache:
            real_call_keys.append(key)   # 仅首次"实际跑 OCR"计数
            cache[key] = []
        return cache[key]

    ctx.ocr_service.get_ocr_result_list.side_effect = _ocr_with_cache

    find_screen_matches(ctx, MagicMock())

    assert len(real_call_keys) == 1   # 同 color_range=None → 缓存复用,真实 OCR 仅 1 次


def test_scope_inactive_traverses_all_screens(monkeypatch) -> None:
    """scope 未激活(active_screen_names=None)→ 全量遍历所有画面,均进候选。

    spec ⑧:backend 语境 scope 恒不激活(loader.active_screen_names=None),
    find_screen_matches 应遍历 loader.active_screen_info_list 全部画面。设多画面、
    无 id_mark 命中(均进 top_n),断言全部进候选。
    """
    a = _screen_info('画面A', [ScreenArea(area_name='a1', pc_rect=Rect(0, 0, 10, 10), text='a')])
    b = _screen_info('画面B', [ScreenArea(area_name='b1', pc_rect=Rect(0, 0, 10, 10), text='b')])
    c = _screen_info('画面C', [ScreenArea(area_name='c1', pc_rect=Rect(0, 0, 10, 10), text='c')])
    ctx = MagicMock()
    ctx.screen_loader = _make_loader([a, b, c], current=None, last=None)
    assert ctx.screen_loader.active_screen_names is None   # scope 未激活
    _patch_find(monkeypatch, {'a1': True, 'b1': True, 'c1': True})

    result = find_screen_matches(ctx, MagicMock(), top_n=10)

    # 三画面均进候选(全量遍历,无 scope 过滤)
    names = {m.screen_name for m in result}
    assert names == {'画面A', '画面B', '画面C'}
