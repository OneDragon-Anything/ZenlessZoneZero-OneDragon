"""ZzzBackendContext 生命周期与就绪校验的单元测试。

测试使用 MagicMock 伪造 ZContext，避免触发真实的 onnx 模型加载。
"""

from unittest.mock import MagicMock

import pytest

from zzz_od.backend.backend_context import BackendNotReadyError, ZzzBackendContext


def _backend(ready: bool = True, controller: MagicMock | None = None) -> ZzzBackendContext:
    """构造一个使用伪造 ctx 的 ZzzBackendContext。

    Args:
        ready: ctx.ready_for_application 的取值，默认 True。
        controller: ctx.controller 的取值，默认 None。

    Returns:
        绑定了伪造 ctx 的 ZzzBackendContext 实例。
    """
    ctx = MagicMock()
    ctx.ready_for_application = ready
    ctx.controller = controller
    return ZzzBackendContext(ctx)


@pytest.mark.asyncio
async def test_start_runs_init_in_thread() -> None:
    """start() 应当在线程池中调用 ctx.init() 完成初始化。"""
    ctx = MagicMock()
    backend = ZzzBackendContext(ctx)
    await backend.start()
    ctx.init.assert_called_once()


@pytest.mark.asyncio
async def test_shutdown_runs_after_app_shutdown_in_thread() -> None:
    """shutdown() 应当在线程池中调用 ctx.after_app_shutdown() 释放资源。"""
    ctx = MagicMock()
    backend = ZzzBackendContext(ctx)
    await backend.shutdown()
    ctx.after_app_shutdown.assert_called_once()


def test_ensure_ready_raises_when_not_ready() -> None:
    """ctx 未就绪时，_ensure_ready() 应抛出 BackendNotReadyError。"""
    backend = _backend(ready=False)
    with pytest.raises(BackendNotReadyError):
        backend._ensure_ready()


def test_check_window_returns_status_no_rect() -> None:
    game_win = MagicMock(
        win_title="绝区零", is_win_valid=True, is_win_active=False, is_win_scale=True, win_rect=None
    )
    backend = _backend(ready=True, controller=MagicMock(game_win=game_win))
    status = backend.check_window()
    assert status.win_title == "绝区零"
    assert status.is_win_valid is True
    assert status.x is None


def test_check_window_with_rect() -> None:
    rect = MagicMock(x1=1, y1=2, width=3, height=4)
    game_win = MagicMock(win_title="t", is_win_valid=True, is_win_active=True, is_win_scale=True, win_rect=rect)
    backend = _backend(ready=True, controller=MagicMock(game_win=game_win))
    status = backend.check_window()
    assert (status.x, status.y, status.width, status.height) == (1, 2, 3, 4)


def test_capture_returns_image() -> None:
    controller = MagicMock()
    controller.is_game_window_ready = True
    fake_img = object()
    controller.get_screenshot.return_value = fake_img
    backend = _backend(ready=True, controller=controller)
    assert backend.capture() is fake_img
    controller.get_screenshot.assert_called_once_with(independent=False)


def test_capture_raises_when_window_not_ready() -> None:
    controller = MagicMock()
    controller.is_game_window_ready = False
    backend = _backend(ready=True, controller=controller)
    with pytest.raises(BackendNotReadyError):
        backend.capture()


def test_analyze_maps_ocr_results() -> None:
    r1 = MagicMock(data="体力", x=1, y=2, w=3, h=4)
    r2 = MagicMock(data="设定", x=5, y=6, w=7, h=8)
    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = object()
    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.controller = controller
    ctx.ocr_service.get_ocr_result_list.return_value = [r1, r2]
    backend = ZzzBackendContext(ctx)
    result = backend.analyze()
    assert result.success is True
    assert [t.text for t in result.ocr_texts] == ["体力", "设定"]
    assert result.ocr_texts[0].width == 3


def test_analyze_returns_error_when_screenshot_none() -> None:
    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = None
    backend = _backend(ready=True, controller=controller)
    result = backend.analyze()
    assert result.success is False
    assert "截图失败" in (result.error or "")


def test_analyze_returns_screens_and_writes_back_on_precise(monkeypatch) -> None:
    """analyze 精准命中 → 返回 screens[0].is_precise=True,并回写 current_screen_name。"""
    import zzz_od.backend.backend_context as bc
    from one_dragon.base.screen.screen_match import ScreenMatch

    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = MagicMock()
    backend = _backend(ready=True, controller=controller)

    # mock find_screen_matches 返精准
    precise = ScreenMatch(screen_name='菜单', is_precise=True, areas=[])
    monkeypatch.setattr(bc, 'find_screen_matches', lambda ctx, screen, top_n=5: [precise])
    # mock ocr_service 返空(ocr_texts 走全图 OCR)
    backend.ctx.ocr_service.get_ocr_result_list.return_value = []

    result = backend.analyze()
    assert result.success is True
    assert len(result.screens) == 1
    assert result.screens[0].is_precise is True
    # 回写
    backend.ctx.screen_loader.update_current_screen_name.assert_called_once_with('菜单')


def test_analyze_no_precise_does_not_write_back(monkeypatch) -> None:
    """analyze 无精准(模糊 top_n)→ 不回写 current_screen_name。"""
    import zzz_od.backend.backend_context as bc
    from one_dragon.base.screen.screen_match import ScreenMatch

    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = MagicMock()
    backend = _backend(ready=True, controller=controller)

    fuzzy = ScreenMatch(screen_name='某画面', is_precise=False, areas=[])
    monkeypatch.setattr(bc, 'find_screen_matches', lambda ctx, screen, top_n=5: [fuzzy])
    backend.ctx.ocr_service.get_ocr_result_list.return_value = []

    result = backend.analyze()
    assert result.success is True
    assert result.screens[0].is_precise is False
    backend.ctx.screen_loader.update_current_screen_name.assert_not_called()


def test_analyze_exception_no_writeback(monkeypatch) -> None:
    """匹配中途异常 → success=False, screens=[], 不回写。"""
    import zzz_od.backend.backend_context as bc

    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = MagicMock()
    backend = _backend(ready=True, controller=controller)

    def boom(ctx, screen, top_n=5):
        raise RuntimeError('ocr boom')
    monkeypatch.setattr(bc, 'find_screen_matches', boom)

    result = backend.analyze()
    assert result.success is False
    assert result.screens == []
    assert result.error is not None
    backend.ctx.screen_loader.update_current_screen_name.assert_not_called()


def test_start_run_delegates_to_run_slot() -> None:
    """start_run 应委托 run_slot._start_run，返回 (ok, future) 元组。

    覆盖旧的 enter_game 用例：不再有同步 enter_game 方法，运行由
    run_slot 异步派发；此处直接 mock run_slot，验证透传与返回结构。
    """
    from concurrent.futures import Future

    backend = _backend(ready=True)
    fut: Future = Future()
    fut.set_result(object())
    backend.run_slot = MagicMock()
    backend.run_slot._start_run.return_value = (True, fut)

    def _factory(_ctx: object) -> object:
        return object()

    ok, future = backend.start_run("mcp", _factory)
    assert ok is True
    assert future is fut
    backend.run_slot._start_run.assert_called_once_with("mcp", _factory)


def test_query_status_delegates_to_run_slot() -> None:
    """query_status 应委托 run_slot._query_status 返回 RunStatusResult。"""
    from zzz_od.backend.schemas import RunStatusResult

    expected = RunStatusResult(state="idle", source=None, app=None,
                               started_at=None, duration_seconds=None)
    backend = _backend(ready=True)
    backend.run_slot = MagicMock()
    backend.run_slot._query_status.return_value = expected

    assert backend.query_status() is expected
    backend.run_slot._query_status.assert_called_once()


def test_stop_delegates_to_run_slot() -> None:
    """stop 应封装 run_slot._stop，无运行时返回 {stopped: False, error}。"""
    backend = _backend(ready=True)
    backend.run_slot = MagicMock()
    backend.run_slot._stop.return_value = (False, None)

    assert backend.stop() == {"stopped": False, "error": "当前无运行"}
    backend.run_slot._stop.assert_called_once()


def test_close_game_delegates() -> None:
    """close_game 应委托 controller.close_game()。"""
    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.close_game.return_value = None
    backend = _backend(ready=True, controller=controller)
    msg = backend.close_game()
    controller.close_game.assert_called_once()
    assert msg == '已发送关闭游戏信号,可用 check_game_window 验证'
