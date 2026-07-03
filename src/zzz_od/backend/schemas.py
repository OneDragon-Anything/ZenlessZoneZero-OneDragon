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
    """

    success: bool
    ocr_texts: list[OcrText]
    error: str | None = None
    screens: list[ScreenMatch] = field(default_factory=list)


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
