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


def test_enter_game_success(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.run_context.start_running.return_value = True
    ctx.current_instance_idx = 0
    backend = ZzzBackendContext(ctx)

    fake_op = MagicMock()
    fake_op.execute.return_value = MagicMock(success=True, status="OK")
    import zzz_od.operation.enter_game.open_and_enter_game as eg_mod
    monkeypatch.setattr(eg_mod, "OpenAndEnterGame", lambda c: fake_op)

    msg = backend.enter_game()
    assert "成功" in msg
    ctx.run_context.stop_running.assert_called_once()


def test_enter_game_start_running_failed() -> None:
    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.run_context.start_running.return_value = False
    backend = ZzzBackendContext(ctx)
    with pytest.raises(BackendNotReadyError):
        backend.enter_game()
