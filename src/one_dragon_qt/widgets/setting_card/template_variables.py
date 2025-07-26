from qfluentwidgets import FluentIcon
from one_dragon.utils.i18_utils import gt


class TemplateVariables:
    """模板变量配置类"""

    VARIABLES = [
        {"key": "$title", "name": "标题变量", "icon": FluentIcon.TAG},
        {"key": "$content", "name": "内容变量", "icon": FluentIcon.DOCUMENT},
        {"key": "$image", "name": "图片变量", "icon": FluentIcon.PHOTO},
    ]

    @classmethod
    def get_variables(cls):
        """获取所有变量配置"""
        return cls.VARIABLES