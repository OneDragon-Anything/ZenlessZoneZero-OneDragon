"""
截图工具模块

提供游戏截图相关的 MCP 工具。
"""

import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log
from zzz_mcp.context import get_zzz_context


def get_screenshot_dir() -> Path:
    """
    获取截图保存目录
    如果目录不存在则自动创建

    Returns:
        Path: 截图保存目录的绝对路径
    """
    dir_path = os_utils.get_path_under_work_dir(".debug", "zzz_od_mcp", "screenshot")
    return Path(dir_path).absolute()


def register_screenshot_tools(mcp: FastMCP) -> None:
    """注册截图相关工具"""

    @mcp.tool()
    def capture_game_screen() -> str:
        """
        捕获绝区零游戏当前画面

        Returns:
            str: 截图保存的绝对路径
        """
        zzz = get_zzz_context()
        if zzz is None:
            return "错误: ZContext 未初始化"

        if zzz.controller is None:
            return "错误: 控制器未初始化"

        if not zzz.controller.is_game_window_ready:
            return "错误: 游戏窗口未就绪"

        try:
            # 执行截图 - 使用正确的 API
            image = zzz.controller.get_screenshot(independent=False)

            if image is None:
                return "错误: 截图失败，返回值为 None"

            # 生成带时间戳的文件名
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"

            # 确保目录存在
            screenshot_dir = get_screenshot_dir()
            screenshot_dir.mkdir(parents=True, exist_ok=True)

            # 保存截图
            img_path = screenshot_dir / filename

            # 将 OpenCV 图像（RGB）保存为 PNG
            import cv2

            # image 是 RGB 格式，需要转为 BGR 格式才能被 cv2.imwrite 正确保存
            bgr_image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            cv2.imwrite(str(img_path), bgr_image)

            log.info(f"截图已保存到: {img_path}")

            # 返回绝对路径
            return str(img_path)

        except Exception as e:
            log.error(f"截图失败: {e}", exc_info=True)
            return f"错误: 截图失败 - {str(e)}"
