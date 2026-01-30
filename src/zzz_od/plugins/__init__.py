"""ZZZ OneDragon 第三方插件目录

此目录用于存放用户安装的第三方应用插件。
该目录被 .gitignore 忽略，不会被版本控制。

插件结构示例：
    plugins/
    └── my_plugin/
        ├── my_plugin_const.py   # 应用常量和元数据
        └── my_plugin_factory.py  # 应用工厂

元数据格式 (const 文件)：
    APP_ID = 'my_plugin'
    APP_NAME = '我的插件'
    DEFAULT_GROUP = True

    # 插件元数据（可选）
    PLUGIN_AUTHOR = '作者名'
    PLUGIN_HOMEPAGE = 'https://github.com/...'
    PLUGIN_VERSION = '1.0.0'
    PLUGIN_DESCRIPTION = '插件描述'
"""
