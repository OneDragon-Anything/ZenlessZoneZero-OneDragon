"""
画面分析工具模块

提供游戏画面分析相关的 MCP 工具。
"""

from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP

from one_dragon.utils.log_utils import log
from zzz_mcp.context import get_zzz_context


@dataclass
class OcrText:
    """OCR 识别的文本"""
    text: str  # 识别的文本内容
    x: int  # 文本区域左上角 X 坐标
    y: int  # 文本区域左上角 Y 坐标
    width: int  # 文本区域宽度
    height: int  # 文本区域高度


@dataclass
class AnalyzeScreenResult:
    """画面分析结果"""
    success: bool  # 是否成功
    ocr_texts: list[OcrText]  # OCR 识别的文本列表
    error: str | None = None  # 错误信息


def register_screen_analysis_tools(mcp: FastMCP) -> None:
    """注册画面分析相关工具"""

    @mcp.tool()
    def analyze_screen() -> AnalyzeScreenResult:
        """
        分析绝区零游戏当前画面

        返回当前画面的详细信息，包括 OCR 识别结果。
        后续会扩展到模板匹配、屏幕识别等内容。

        Returns:
            AnalyzeScreenResult: 画面分析结果
        """
        zzz = get_zzz_context()
        if zzz is None:
            return AnalyzeScreenResult(
                success=False,
                ocr_texts=[],
                error="ZContext 未初始化"
            )

        if zzz.controller is None:
            return AnalyzeScreenResult(
                success=False,
                ocr_texts=[],
                error="控制器未初始化"
            )

        if not zzz.controller.is_game_window_ready:
            return AnalyzeScreenResult(
                success=False,
                ocr_texts=[],
                error="游戏窗口未就绪"
            )

        if zzz.ocr_service is None:
            return AnalyzeScreenResult(
                success=False,
                ocr_texts=[],
                error="OCR 服务未初始化"
            )

        try:
            # 1. 截图
            image = zzz.controller.get_screenshot(independent=False)
            if image is None:
                return AnalyzeScreenResult(
                    success=False,
                    ocr_texts=[],
                    error="截图失败"
                )

            # 2. OCR 识别
            ocr_result_list = zzz.ocr_service.get_ocr_result_list(
                image=image,
            )

            # 3. 构建返回结果
            ocr_texts = []
            for ocr_result in ocr_result_list:
                ocr_texts.append(OcrText(
                    text=ocr_result.data,
                    x=int(ocr_result.x),
                    y=int(ocr_result.y),
                    width=int(ocr_result.w),
                    height=int(ocr_result.h),
                ))

            log.info(f"画面分析完成，识别到 {len(ocr_texts)} 个文本")

            return AnalyzeScreenResult(
                success=True,
                ocr_texts=ocr_texts,
                error=None,
            )

        except Exception as e:
            log.error(f"画面分析失败: {e}", exc_info=True)
            return AnalyzeScreenResult(
                success=False,
                ocr_texts=[],
                error=f"画面分析失败 - {str(e)}"
            )
