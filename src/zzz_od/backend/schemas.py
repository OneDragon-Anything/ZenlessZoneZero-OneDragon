from dataclasses import dataclass, field

from one_dragon.base.screen.screen_match import ScreenMatch


@dataclass
class OcrText:
    """OCR 识别的单条文本。

    Attributes:
        text: 识别出的文本内容。
        x: 文本框左上角横坐标（像素）。
        y: 文本框左上角纵坐标（像素）。
        width: 文本框宽度（像素）。
        height: 文本框高度（像素）。
    """

    text: str
    x: int
    y: int
    width: int
    height: int


@dataclass
class AnalyzeScreenResult:
    """分析游戏画面结果(截图 + OCR + 画面匹配)。

    Attributes:
        success: 是否成功截图并完成分析。
        ocr_texts: 全图原始 OCR 文本列表(含未归类到任何 area 的散落文本)。
        error: 失败时的错误描述。
        screens: 画面匹配结果(精准命中=[1 个 is_precise=True];否则 top_n 个
            is_precise=False 候选)。决策优先看 screens;需看散落文本再看 ocr_texts。
        screenshot_path: 本次 analyze 新存的截图绝对路径;实时+save_image=True 时有值,
            其余 None。**有值 ⟺ 这次实时模式新存了张图**(离线模式不存)。
    """

    success: bool
    ocr_texts: list[OcrText]
    error: str | None = None
    screens: list[ScreenMatch] = field(default_factory=list)
    screenshot_path: str | None = None


@dataclass
class WindowStatus:
    """游戏窗口状态。

    Attributes:
        win_title: 窗口标题；获取不到时为 None。
        is_win_valid: 窗口句柄是否有效。
        is_win_active: 窗口当前是否处于激活状态。
        is_win_scale: 窗口缩放比例是否符合基准（1.0）。
        x: 窗口左上角横坐标；不可用时为 None。
        y: 窗口左上角纵坐标；不可用时为 None。
        width: 窗口客户区宽度；不可用时为 None。
        height: 窗口客户区高度；不可用时为 None。
    """

    win_title: str | None
    is_win_valid: bool
    is_win_active: bool
    is_win_scale: bool
    x: int | None = None
    y: int | None = None
    width: int | None = None
    height: int | None = None


@dataclass
class RunStatusResult:
    """运行状态查询结果(MCP/HTTP 共享,传输无关)。

    Attributes:
        state: idle/running/success/failed/stopped。
        source: 触发方 "mcp"/"http";终态后保留,反映最近一次来源。
        app: operation 类名(如 "OpenAndEnterGame");终态后保留。
        started_at: ISO 时间戳,可作 tail 日志锚点;不可用时 None。
        duration_seconds: 截至查询时的耗时;不可用时 None。
        current_node: 运行中当前节点名;终态 None。
        retry_count: 运行中当前节点重试次数;终态 None。
        last_status: OperationResult.status(失败原因 / "人工结束" / 成功描述);运行中 None。
        failed_node: 仅 failed:失败停在哪一步;否则 None。
    """
    state: str
    source: str | None = None
    app: str | None = None
    started_at: str | None = None
    duration_seconds: float | None = None
    current_node: str | None = None
    retry_count: int | None = None
    last_status: str | None = None
    failed_node: str | None = None


@dataclass
class ApplicationInfo:
    """可通过 backend 触发运行的应用信息。

    字段同时描述「一条龙组里是否启用」和「独立应用列表里是否出现」，
    这样 MCP/HTTP 客户端能区分完整一条龙运行与单个应用运行。
    """

    app_id: str
    app_name: str
    enabled_in_one_dragon: bool = False
    in_standalone_list: bool = False
    is_active_standalone: bool = False


@dataclass
class ApplicationListResult:
    """应用运行配置概览。

    用于 ``list_applications`` / ``GET /game/applications`` 返回当前实例下
    可运行应用、GUI 当前选中的独立应用，以及各应用在不同运行模式中的状态。
    """

    current_instance_idx: int
    active_standalone_app_id: str | None
    applications: list[ApplicationInfo]
