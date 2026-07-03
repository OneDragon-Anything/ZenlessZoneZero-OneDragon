"""MCP 适配器：把 ``ZzzBackendContext`` 以 MCP tool 的形式对外暴露。

本模块在后端 game 切片（``ZzzBackendContext``）之上架设一层传输适配：
- ``create_mcp_server`` 创建一个 ``FastMCP`` 实例，并通过闭包将 backend 注入到
  工具函数中，使工具调用最终落到 backend 的 game 切片方法上。
- 工具返回值尽量保持「可直接读」的字符串或传输无关结构，便于上层（CLI/Agent）消费。

注意：
    - 同步工具（check/capture/analyze）直接调用 backend 的同步方法；
    - ``open_and_enter_game`` 当前为临时占位，Task 6 将改造为基于
      ``backend.start_run`` 的异步适配。
"""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from mcp.server.fastmcp import FastMCP

from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log
from zzz_od.backend.backend_context import ZzzBackendContext
from zzz_od.backend.schemas import AnalyzeScreenResult

if TYPE_CHECKING:
    from cv2.typing import MatLike


def _save_screenshot(image: 'MatLike') -> str:
    """将 RGB 截图以 BGR 写盘，返回绝对路径。

    Args:
        image: backend ``capture`` 返回的 RGB ``ndarray``。

    Returns:
        保存后的截图文件绝对路径。
    """
    import cv2

    screenshot_dir = Path(os_utils.get_path_under_work_dir(".debug", "zzz_od_mcp", "screenshot"))
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    img_path = screenshot_dir / f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
    bgr_image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    if not cv2.imwrite(str(img_path), bgr_image):
        raise RuntimeError(f"截图写盘失败: {img_path}")
    return str(img_path)


def create_mcp_server(backend: ZzzBackendContext, name: str = "zzz_od") -> FastMCP:
    """创建 MCP 服务器并注册 game 工具。

    通过闭包将 ``backend`` 注入到各工具函数中，使工具调用最终落到 backend 的
    game 切片方法（``check_window``/``capture``/``analyze``）；``open_and_enter_game``
    当前为临时占位（Task 6 改造）。

    Args:
        backend: 已就绪的 ``ZzzBackendContext``，提供 game 切片能力。
        name: MCP 服务器名称，默认 ``zzz_od``。

    Returns:
        注册好 4 个工具的 ``FastMCP`` 实例。
    """
    mcp = FastMCP(name)

    @mcp.tool()
    def check_game_window() -> str:
        """检查绝区零游戏窗口状态。

        读取窗口标题、有效性、激活态、缩放比例及客户区矩形，格式化为可读字符串。

        Returns:
            窗口状态描述字符串；backend 抛错时返回 ``错误: <原因>``。
        """
        try:
            s = backend.check_window()
        except Exception as e:  # noqa: BLE001 工具层统一兜底，避免异常透传到 MCP 框架
            return f"错误: {e}"
        lines = [
            "游戏窗口状态:",
            f"  窗口标题: {s.win_title}",
            f"  窗口有效: {s.is_win_valid}",
            f"  窗口激活: {s.is_win_active}",
            f"  窗口缩放: {s.is_win_scale}",
        ]
        if s.x is not None:
            lines.append(f"  窗口位置: x={s.x}, y={s.y}, 宽={s.width}, 高={s.height}")
        return "\n".join(lines)

    @mcp.tool()
    def capture_game_screen() -> str:
        """捕获游戏画面并保存截图，返回截图绝对路径。

        Returns:
            截图文件的绝对路径；backend 抛错时返回 ``错误: <原因>``。
        """
        try:
            image = backend.capture()
            path = _save_screenshot(image)
        except Exception as e:  # noqa: BLE001 工具层统一兜底
            return f"错误: {e}"
        log.info(f"截图已保存到: {path}")
        return path

    @mcp.tool()
    def analyze_screen() -> AnalyzeScreenResult:
        """分析画面（截图 + OCR），返回结构化结果。

        Returns:
            ``AnalyzeScreenResult``（成功标志、OCR 文本列表、错误描述）。
        """
        try:
            return backend.analyze()
        except Exception as e:  # noqa: BLE001 工具层统一兜底
            return AnalyzeScreenResult(success=False, ocr_texts=[], error=str(e))

    @mcp.tool()
    async def open_and_enter_game() -> str:
        """打开并进入绝区零游戏。

        这是一个长阻塞流程，需要本地交互式桌面会话。

        Returns:
            执行结果描述字符串；backend 抛错时返回 ``错误: <原因>``。
        """
        # 临时占位:backend.enter_game 已移除,Task 6 将改为基于 start_run 的异步适配。
        raise RuntimeError('Task 6 改造中')

    return mcp
