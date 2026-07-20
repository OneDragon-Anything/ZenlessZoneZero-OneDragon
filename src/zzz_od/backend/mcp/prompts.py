"""MCP prompt 与帮助工具注册。

MCP prompt 属于协议中的独立能力，但部分客户端不会主动展示或使用 prompts。
因此同一份模板也通过普通 tool 暴露，给 agent 一个类似 ``--help`` 的入口。
"""

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations


def render_check_status_guide() -> str:
    """生成状态检查提示词。"""
    return """请按以下顺序检查绝区零一条龙当前状态：

1. 调用 `get_run_status`，确认是否已有后台任务正在运行。
2. 调用 `check_game_window`，确认游戏窗口是否存在、是否激活、缩放是否正常。
3. 如需要判断当前画面，再调用 `analyze_screen` 获取 OCR 与画面匹配结果。
4. 汇总时明确说明：运行状态、窗口状态、当前画面判断，以及下一步建议。
"""


def render_run_one_dragon_guide() -> str:
    """生成一条龙运行提示词。"""
    return """请按以下顺序运行绝区零一条龙：

1. 调用 `get_run_status`，如果已有任务在 running，先向用户说明当前任务，不要重复启动。
2. 调用 `check_game_window`。如果游戏窗口不可用，调用 `open_game(enter=True, block=True)` 进入游戏。
3. 调用 `run_one_dragon(block=False)`，按 GUI 当前配置启动完整一条龙。
4. 周期性调用 `get_run_status`，直到状态不再是 running，或用户要求停止。
5. 只有用户明确要求中断时，才调用 `stop_run`。
6. 最终汇总应用名、最终状态、失败节点或结果文本、耗时。
"""


def render_run_standalone_app_guide(app_id: str | None = None) -> str:
    """生成独立应用运行提示词。

    Args:
        app_id: 要运行的应用 ID；为空时使用 GUI 当前选中的独立应用。
    """
    target = "`run_standalone_app(app_id=None, block=False)`，使用 GUI 当前选中项"
    if app_id:
        target = f"`run_standalone_app(app_id={app_id!r}, block=False)`"
    return f"""请按以下顺序运行绝区零独立应用：

1. 调用 `get_run_status`，如果已有任务在 running，先向用户说明当前任务，不要重复启动。
2. 调用 `list_applications`，确认当前实例可运行的独立应用列表。
3. 如果用户没有指定应用，使用 GUI 当前在「应用运行」中选中的应用。
4. 调用 {target} 启动独立应用。
5. 周期性调用 `get_run_status`，直到状态不再是 running，或用户要求停止。
6. 只有用户明确要求中断时，才调用 `stop_run`。
7. 最终汇总应用名、最终状态、失败节点或结果文本、耗时。
"""


def list_prompt_guides() -> list[dict[str, str]]:
    """列出可通过 prompt 或 help tool 获取的操作指南。"""
    return [
        {
            "name": "zzz_check_status",
            "title": "绝区零状态检查",
            "description": "检查运行状态、游戏窗口和当前画面。",
            "arguments": "",
        },
        {
            "name": "zzz_run_one_dragon",
            "title": "运行绝区零一条龙",
            "description": "按 GUI 当前配置启动一条龙并轮询状态。",
            "arguments": "",
        },
        {
            "name": "zzz_run_standalone_app",
            "title": "运行绝区零独立应用",
            "description": "选择或使用 GUI 当前选中独立应用，启动后轮询状态。",
            "arguments": "app_id: str | None",
        },
    ]


def render_prompt_guide(name: str, app_id: str | None = None) -> str:
    """按名称渲染操作指南。

    Args:
        name: 指南名称。
        app_id: 独立应用 ID，仅 ``zzz_run_standalone_app`` 使用。

    Returns:
        操作指南文本；未知名称返回可用名称提示。
    """
    if name == "zzz_check_status":
        return render_check_status_guide()
    if name == "zzz_run_one_dragon":
        return render_run_one_dragon_guide()
    if name == "zzz_run_standalone_app":
        return render_run_standalone_app_guide(app_id)
    names = ", ".join(item["name"] for item in list_prompt_guides())
    return f"未知指南: {name}。可用指南: {names}"


def register_prompts(mcp: FastMCP) -> None:
    """把绝区零一条龙常用操作 prompt 注册到 FastMCP。"""

    @mcp.prompt(
        name="zzz_check_status",
        title="绝区零状态检查",
        description="检查游戏窗口、画面识别与当前后台运行状态。",
    )
    def zzz_check_status() -> str:
        """生成状态检查提示词。"""
        return render_check_status_guide()

    @mcp.prompt(
        name="zzz_run_one_dragon",
        title="运行绝区零一条龙",
        description="按当前实例配置启动一条龙，并持续查询运行状态。",
    )
    def zzz_run_one_dragon() -> str:
        """生成一条龙运行提示词。"""
        return render_run_one_dragon_guide()

    @mcp.prompt(
        name="zzz_run_standalone_app",
        title="运行绝区零独立应用",
        description="选择或使用当前选中独立应用，启动后持续查询运行状态。",
    )
    def zzz_run_standalone_app(app_id: str | None = None) -> str:
        """生成独立应用运行提示词。"""
        return render_run_standalone_app_guide(app_id)


def register_prompt_tools(mcp: FastMCP) -> None:
    """把 prompt 模板以普通 MCP tool 形式暴露，便于客户端发现。"""

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="列出操作指南"))
    def list_mcp_usage_guides() -> list[dict[str, str]]:
        """列出 zzz_od MCP 可用操作指南，相当于帮助目录。观察类。"""
        return list_prompt_guides()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="读取操作指南"))
    def get_mcp_usage_guide(name: str, app_id: str | None = None) -> str:
        """读取 zzz_od MCP 操作指南，相当于某个任务的 --help。观察类。

        Args:
            name: 指南名称，可先调用 ``list_mcp_usage_guides`` 查看。
            app_id: 独立应用 ID，仅 ``zzz_run_standalone_app`` 使用。
        """
        return render_prompt_guide(name, app_id)
