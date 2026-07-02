from dataclasses import dataclass


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
    """画面分析结果。

    传输无关的返回结构，Task 3 将在 game 切片中消费。

    Attributes:
        success: 本次分析是否成功。
        ocr_texts: 命中的 OCR 文本列表。
        error: 失败时的错误描述；成功时为 None。
    """

    success: bool
    ocr_texts: list[OcrText]
    error: str | None = None


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
