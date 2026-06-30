"""后端服务入口（``create_app`` 装配）的单元测试。

通过 ``MagicMock`` 伪造 backend（不真启动 uvicorn），只校验 ``create_app``
是否把 MCP ``/mcp`` 端点与 ``/game/*`` custom_route 同进程挂到同一 Starlette app。
``app.routes`` 可能含 ``Mount``，因此递归收集子路由的 ``path``。
"""

from unittest.mock import MagicMock

from zzz_od.backend.entry.server import create_app


def _collect_paths(routes) -> list[str]:
    """递归收集 Starlette 路由（含 ``Mount`` 子路由）的 ``path``。

    Args:
        routes: ``app.routes`` 或某 ``Mount`` 的 ``routes`` 列表。

    Returns:
        所有非空 ``path`` 字符串列表。
    """
    paths: list[str] = []
    for r in routes:
        p = getattr(r, "path", None)
        if p:
            paths.append(p)
        sub = getattr(r, "routes", None)
        if sub:
            paths.extend(_collect_paths(sub))
    return paths


def test_create_app_mounts_mcp_and_game_routes() -> None:
    """``create_app`` 应在同一 app 上同时挂载 ``/game/*`` 与 ``mcp`` 端点。"""
    backend = MagicMock()
    app = create_app(backend)
    paths = _collect_paths(app.routes)
    assert any("/game/window" in p for p in paths)
    assert any("mcp" in p for p in paths)
