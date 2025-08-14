"""
全局主题色管理模块
"""
from PySide6.QtGui import QColor
from qfluentwidgets import setThemeColor


class ThemeManager:
    """全局主题色管理器 - 配合自动提取机制"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._current_color = (0, 120, 215)  # 默认蓝色，与context_lazy_signal.py保持一致
            self._initialized = True

    @property
    def current_color(self) -> tuple:
        """获取当前主题色"""
        return self._current_color

    def set_theme_color(self, color: tuple) -> None:
        """
        设置全局主题色（通常由背景图片自动提取调用）
        :param color: RGB颜色元组 (R, G, B)
        """
        if not isinstance(color, tuple) or len(color) != 3:
            raise ValueError("颜色必须是包含3个整数的元组 (R, G, B)")

        # 验证颜色值范围
        if not all(0 <= c <= 255 for c in color):
            raise ValueError("颜色值必须在0-255范围内")

        self._current_color = color
        # 转换为QColor并设置全局主题色
        qcolor = QColor(color[0], color[1], color[2])
        setThemeColor(qcolor)

    def get_qcolor(self) -> QColor:
        """获取当前主题色的QColor对象"""
        return QColor(self._current_color[0], self._current_color[1], self._current_color[2])

    def get_hex_color(self) -> str:
        """获取当前主题色的十六进制字符串"""
        return f"#{self._current_color[0]:02x}{self._current_color[1]:02x}{self._current_color[2]:02x}"

    def get_rgb_string(self) -> str:
        """获取当前主题色的RGB字符串"""
        return f"rgb({self._current_color[0]}, {self._current_color[1]}, {self._current_color[2]})"


# 全局主题色管理器实例
theme_manager = ThemeManager()