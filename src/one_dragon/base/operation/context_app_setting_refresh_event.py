from dataclasses import dataclass
from typing import ClassVar


@dataclass(slots=True)
class ContextAppSettingRefreshEvent:
    """应用注册刷新后 请求前端重扫应用设置入口的事件体。

    后端 refresh_application_registration() 完成后 dispatch；
    前端收到后在主线程重新执行 AppSettingManager.discover()，
    使插件安装/卸载后的设置入口及时更新。
    """

    EVENT_ID: ClassVar[str] = 'context_app_setting_refresh'
