from PySide6.QtGui import QColor
from qfluentwidgets import setThemeColor


class ThemeManager:
    """全局主题色管理器"""

    _current_color = (0, 120, 215)  # 默认蓝色

    @classmethod
    def get_current_color(cls) -> tuple[int, int, int]:
        """获取当前主题色"""
        return cls._current_color

    @classmethod
    def set_theme_color(cls, color: tuple[int, int, int]) -> None:
        """
        设置全局主题色（通常由背景图片自动提取调用）
        :param color: RGB颜色元组 (R, G, B)
        """
        if not isinstance(color, tuple) or len(color) != 3:
            raise ValueError("颜色必须是包含3个整数的元组 (R, G, B)")

        # 显式转换并验证范围
        try:
            r, g, b = (int(color[0]), int(color[1]), int(color[2]))
        except (ValueError, TypeError, IndexError):
            raise ValueError("颜色必须是包含3个整数的元组 (R, G, B)")
        if not all(0 <= c <= 255 for c in (r, g, b)):
            raise ValueError("颜色值必须在0-255范围内")

        # 如果颜色没有变化，直接返回，避免不必要的样式刷新
        if cls._current_color == (r, g, b):
            return

        cls._current_color = (r, g, b)

        # 转换为QColor并设置全局主题色
        qcolor = QColor(r, g, b)
        setThemeColor(qcolor)

    @classmethod
    def get_qcolor(cls) -> QColor:
        """获取当前主题色的QColor对象"""
        return QColor(cls._current_color[0], cls._current_color[1], cls._current_color[2])

    @classmethod
    def get_hex_color(cls) -> str:
        """获取当前主题色的十六进制字符串"""
        return f"#{cls._current_color[0]:02x}{cls._current_color[1]:02x}{cls._current_color[2]:02x}"

    @classmethod
    def get_rgb_string(cls) -> str:
        """获取当前主题色的RGB字符串"""
        return f"rgb({cls._current_color[0]}, {cls._current_color[1]}, {cls._current_color[2]})"

    @classmethod
    def load_from_config(cls, ctx) -> None:
        """
        从配置文件加载主题色（应用启动时调用）
        :param ctx: 上下文对象
        """
        saved_color = ctx.custom_config.theme_color
        cls._current_color = saved_color
        # 设置到qfluentwidgets但不触发信号
        qcolor = QColor(saved_color[0], saved_color[1], saved_color[2])
        setThemeColor(qcolor)
