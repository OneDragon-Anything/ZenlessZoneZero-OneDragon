"""应用常量模块的字段规范

定义每个应用的 *_const.py 模块中必须定义的字段。
插件加载时会验证 const 模块是否包含所有必需字段，缺少则抛出 ImportError。

使用示例（*_const.py）::

    APP_ID = "my_app"
    APP_NAME = "我的应用"
    DEFAULT_GROUP = False
    NEED_NOTIFY = True

    # 以下为可选字段（仅第三方插件需要）
    PLUGIN_AUTHOR = "作者"
    PLUGIN_HOMEPAGE = "https://github.com/..."
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_DESCRIPTION = "插件描述"
"""

# 每个应用的 const 模块必须定义的字段
REQUIRED_CONST_FIELDS: tuple[str, ...] = (
    'APP_ID',
    'APP_NAME',
    'DEFAULT_GROUP',
    'NEED_NOTIFY',
)

# 可选的插件元数据字段（仅第三方插件需要）
OPTIONAL_PLUGIN_FIELDS: tuple[str, ...] = (
    'PLUGIN_AUTHOR',
    'PLUGIN_HOMEPAGE',
    'PLUGIN_VERSION',
    'PLUGIN_DESCRIPTION',
)
