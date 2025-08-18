from PySide6.QtGui import QColor
from qfluentwidgets import setThemeColor


class ThemeManager:
    """全局主题色管理器"""

    _current_color = (0, 120, 215)  # 默认蓝色

    @classmethod
    def get_current_color(cls) -> tuple:
        """获取当前主题色"""
        return cls._current_color

    @classmethod
    def set_theme_color(cls, color: tuple, ctx=None) -> None:
        """
        设置全局主题色（通常由背景图片自动提取调用）
        :param color: RGB颜色元组 (R, G, B)
        :param ctx: 上下文对象，用于持久化存储
        """
        if not isinstance(color, tuple) or len(color) != 3:
            raise ValueError("颜色必须是包含3个整数的元组 (R, G, B)")

        # 验证颜色值范围
        if not all(0 <= c <= 255 for c in color):
            raise ValueError("颜色值必须在0-255范围内")

        cls._current_color = color

        # 转换为QColor并设置全局主题色
        qcolor = QColor(color[0], color[1], color[2])
        setThemeColor(qcolor)

        # 如果提供了context，同时保存到配置文件并触发信号
        if ctx:
            ctx.custom_config.global_theme_color = color
            ctx.signal.theme_color_changed = True

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
        if ctx.custom_config.has_custom_theme_color:
            saved_color = ctx.custom_config.global_theme_color
            cls._current_color = saved_color
            # 设置到qfluentwidgets但不触发信号
            qcolor = QColor(saved_color[0], saved_color[1], saved_color[2])
            setThemeColor(qcolor)
