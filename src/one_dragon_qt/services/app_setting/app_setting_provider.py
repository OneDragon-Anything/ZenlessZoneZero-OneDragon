from abc import ABC, abstractmethod
from enum import Enum

from one_dragon.base.operation.application.application_const import DEFAULT_GROUP_ID


class SettingType(Enum):
    """设置界面显示方式。"""

    INTERFACE = "interface"  # 推入二级界面
    FLYOUT = "flyout"  # 弹窗


class GroupIdMixin:
    """为需要 group_id 的设置界面提供统一属性。"""

    group_id: str = DEFAULT_GROUP_ID


class AppSettingProvider(ABC):
    """应用设置提供者基类。

    通过文件名约定 (*_app_setting.py) 被自动发现。
    每个文件中应有且仅有一个 AppSettingProvider 子类。

    子类需声明:
        - ``app_id``: 必须匹配对应 app 的 APP_ID
        - ``setting_type``: ``SettingType.INTERFACE`` 或 ``SettingType.FLYOUT``
        - ``get_setting_cls()``: 惰性返回设置界面类
    """

    app_id: str
    setting_type: SettingType

    @staticmethod
    @abstractmethod
    def get_setting_cls() -> type:
        """返回设置界面类（懒加载导入）。

        - setting_type == SettingType.INTERFACE: 返回 BaseInterface 子类
        - setting_type == SettingType.FLYOUT: 返回 AppSettingFlyout 子类
        """
        ...
