"""MCP 引导内容注册:instructions(server 级)+ prompts(user-controlled)+ help tool(prompt 的 tool 镜像)。

三通道分工(MCP 协议对应):
- ``instructions``:server 级「用户手册」,握手时注入客户端 system prompt,**常驻**(智能体一定有)。
  放两边共通的操作哲学(三件套 / scope / 安全);详细步骤不进,保持精炼。
- ``prompts``(``@mcp.prompt()``):协议设计给**终端用户在 UI 手动选**(user-controlled)。
  Claude Code 等客户端把它映射成 slash command,智能体平时看不到。
- help tool(``list_mcp_usage_guides`` / ``get_mcp_usage_guide``):prompt 模板的 tool 镜像,
  给智能体一个 ``--help`` 入口(协议保证 tool 一定进模型上下文,弥补 prompts 对智能体不可见)。

模式差异(开发者 / 使用者)走 guide item 的 ``mode`` 字段分流,不进 instructions
(instructions 是 server 级全局、启动时定,不支持运行时按消费者切;且两套会膨胀违背精炼)。

设计依据:docs/superpowers/specs/2026-07-22-mcp-instructions-design.md。
"""

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations


def render_instructions() -> str:
    """生成 server 级 instructions(共通操作哲学,握手时注入客户端 system prompt)。

    放所有消费者(使用者/开发者)每次交互都适用的共通核心;模式差异走 guide(mode 分流),不进此处。
    保持精炼(MCP spec blog:instructions 过长是反模式),只放原则 + 指针,不放详细步骤。
    """
    return """绝区零一条龙 MCP:操作一台 Windows 上的绝区零实机(1080p)。

工具分两类(非穷尽,完整列表见各 tool 描述):
- 观察(不改游戏状态):analyze_screen / capture_game_screen / check_game_window / get_run_status / list_*
- 操作(改游戏状态):click_game / key_tap / drag / input_text / open_game / run_operation / run_one_dragon / run_standalone_app / close_game / stop_run

操作三件套(任何改状态的动作都按这个循环):
1. 先看:analyze_screen 截当前画面 → 看 screens 命中 + ocr_texts 判断在哪。
2. 再动:click_game(点 UI)/ key_tap(按键)/ run_operation(跑预设流程)。
3. 后验:操作后画面常变,等 ~1s 再 analyze_screen / 视觉验证是否到达预期,别假设点击一定成功。

约束:
- 输入注入到活跃游戏窗口,需游戏在线(先 check_game_window);大世界等锁光标画面,click_game 传 pc_alt=True。
- 出错别猜:画面不对 / op 失败 → 先 analyze_screen 看现状 + 查 log(.debug/zzz_od_mcp/main_server.log),再决定。
- 安全:不主动改用户配置(yml);消耗周限的玩法(防卫战/恶名狩猎等)先向用户确认再跑。

开发者场景(验证 op / 画面建档 / 调试):调 get_mcp_usage_guide('zzz_dev_validate_op')。"""


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


def render_dev_validate_op_guide() -> str:
    """生成开发者 op 实操验证指南(dev 模式;走 tool,不做 prompt)。"""
    return """验证一个 operation(如战斗 op)的实操流程:

1. 经 daemon 启动 MCP server(必须在交互桌面会话,否则输入注入失败)→ 客户端 /mcp 重连。
2. 导航到目标画面(大世界 → 对应入口),用 analyze_screen 确认到达。
3. list_operations / describe_operation 确认 op_id 与参数。
4. run_operation(op_id=..., args=..., block=True) 跑;跑完看返回 status。
5. 战斗 op 边界:op 只到「判断战斗结束返回 status」,结束后操作(领奖/撤退/进下一层)交外层 —— op 返回后看 status 决定下一步,别以为跑完就全完事。
6. 验证:op 返回后 analyze_screen / 视觉看画面是否符合预期;失败查 log(.debug/zzz_od_mcp/main_server.log)看节点流转卡哪。
7. 改了 op 代码 → 经 daemon 重启 server(清 Python import 缓存)+ 重连,否则跑的是旧代码。"""


def list_prompt_guides() -> list[dict[str, str]]:
    """列出可通过 help tool 获取的操作指南(help 目录;user 模式项也有对应 prompt,dev 模式项只走 tool)。"""
    return [
        {
            "name": "zzz_check_status",
            "title": "绝区零状态检查",
            "description": "检查运行状态、游戏窗口和当前画面。",
            "mode": "user",
            "arguments": "",
        },
        {
            "name": "zzz_run_one_dragon",
            "title": "运行绝区零一条龙",
            "description": "按 GUI 当前配置启动一条龙并轮询状态。",
            "mode": "user",
            "arguments": "",
        },
        {
            "name": "zzz_run_standalone_app",
            "title": "运行绝区零独立应用",
            "description": "选择或使用 GUI 当前选中独立应用,启动后轮询状态。",
            "mode": "user",
            "arguments": "app_id: str | None",
        },
        {
            "name": "zzz_dev_validate_op",
            "title": "开发者-op 实操验证",
            "description": "用 run_operation 实操验证 op、看节点流转、视觉验证、战斗 op 边界。",
            "mode": "dev",
            "arguments": "",
        },
    ]


def render_prompt_guide(name: str, app_id: str | None = None) -> str:
    """按名称渲染操作指南。

    Args:
        name: 指南名称。
        app_id: 独立应用 ID,仅 ``zzz_run_standalone_app`` 使用。

    Returns:
        操作指南文本;未知名称返回可用名称提示。
    """
    if name == "zzz_check_status":
        return render_check_status_guide()
    if name == "zzz_run_one_dragon":
        return render_run_one_dragon_guide()
    if name == "zzz_run_standalone_app":
        return render_run_standalone_app_guide(app_id)
    if name == "zzz_dev_validate_op":
        return render_dev_validate_op_guide()
    names = ", ".join(item["name"] for item in list_prompt_guides())
    return f"未知指南: {name}。可用指南: {names}"


def register_prompts(mcp: FastMCP) -> None:
    """把绝区零一条龙常用操作 prompt 注册到 FastMCP(仅 user 模式项;dev 走 tool)。

    prompts 协议上 user-controlled(给人手动选),智能体平时看不到;
    对应内容同时由 ``register_prompt_tools`` 做 tool 镜像供智能体主动取。
    """

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
    """把 prompt 模板以普通 MCP tool 形式暴露,便于智能体发现(含 dev 模式项)。"""

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="列出操作指南"))
    def list_mcp_usage_guides() -> list[dict[str, str]]:
        """列出 zzz_od MCP 可用操作指南,相当于帮助目录。观察类。

        每项含 ``mode``(user/dev):user 项面向普通使用者(跑龙/独立应用),dev 项面向开发者(验证 op/调试)。
        """
        return list_prompt_guides()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="读取操作指南"))
    def get_mcp_usage_guide(name: str, app_id: str | None = None) -> str:
        """读取 zzz_od MCP 操作指南,相当于某个任务的 --help。观察类。

        Args:
            name: 指南名称,可先调用 ``list_mcp_usage_guides`` 查看。
            app_id: 独立应用 ID,仅 ``zzz_run_standalone_app`` 使用。
        """
        return render_prompt_guide(name, app_id)
