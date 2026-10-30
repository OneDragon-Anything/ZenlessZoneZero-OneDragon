from enum import Enum
from qfluentwidgets import StyleSheetBase, Theme, qconfig
from .._rc import resource


def fake_init() -> bool:
    """
    一段不会被调用的代码
    用于避免 resource 的引入被自动格式化删除掉
    必须引入 resource 才能正确加载样式
    """
    return resource is not None


class OdQtStyleSheet(StyleSheetBase, Enum):
    """样式表类型枚举"""

    NONE = "none"
    DIALOG = "dialog"
    SAMPLE_CARD = "sample_card"
    LINK_CARD = "link_card"
    GAME_DIALOG = "game_dialog"
    SHARED_BATTLE_DIALOG = "shared_battle_dialog"
    NOTICE_CARD = "notice_card"
    PIVOT = "pivot"
    MULTI_SELECTION_COMBO_BOX = "multi_selection_combo_box"

    # 窗口配置样式
    STACKED_WIDGET = "stacked_widget"
    TITLE_BAR = "title_bar"
    NAVIGATION_INTERFACE = "navigation_interface"
    AREA_WIDGET = "area_widget"

    def path(self, theme=Theme.AUTO):
        """获取样式表的路径

        根据主题设置获取相应的 `.qss` 文件路径。

        Args:
            theme (Theme): 主题设置，默认为 Theme.AUTO

        Returns:
            str: 样式表文件的路径
        """
        theme = qconfig.theme if theme == Theme.AUTO else theme
        return f":/one_dragon_qt/qss/{theme.value.lower()}/{self.value}.qss"
