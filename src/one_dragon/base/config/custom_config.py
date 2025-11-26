from enum import Enum

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_config import YamlConfig


class UILanguageEnum(Enum):

    AUTO = ConfigItem('跟随系统', 'auto')
    ZH = ConfigItem('简体中文', 'zh')
    EN = ConfigItem('English', 'en')

class ThemeEnum(Enum):

    AUTO = ConfigItem('跟随系统', 'Auto')
    LIGHT = ConfigItem('浅色', 'Light')
    DARK = ConfigItem('深色', 'Dark')


class ThemeColorModeEnum(Enum):

    AUTO = ConfigItem('自动', 'auto')
    CUSTOM = ConfigItem('自定义', 'custom')


class BackgroundTypeEnum(Enum):

    VERSION_POSTER = ConfigItem('版本海报', 'version_poster')
    STATIC = ConfigItem('静态背景', 'static_background')
    DYNAMIC = ConfigItem('动态背景', 'dynamic_background')
    NONE = ConfigItem('无', 'none')


class CustomConfig(YamlConfig):

    def __init__(self):
        YamlConfig.__init__(self, module_name='custom')

    @property
    def ui_language(self) -> str:
        """
        界面语言
        :return:
        """
        return self.get('ui_language', UILanguageEnum.AUTO.value.value)

    @ui_language.setter
    def ui_language(self, new_value: str) -> None:
        """
        界面语言
        :return:
        """
        self.update('ui_language', new_value)

    @property
    def theme(self) -> str:
        """
        主题
        :return:
        """
        return self.get('theme', ThemeEnum.AUTO.value.value)

    @theme.setter
    def theme(self, new_value: str) -> None:
        """
        主题
        :return:
        """
        self.update('theme', new_value)

    @property
    def custom_banner(self) -> bool:
        """
        自定义主页背景
        :return:
        """
        return self.get('custom_banner', False)

    @custom_banner.setter
    def custom_banner(self, new_value: bool) -> None:
        """
        自定义主页背景
        :return:
        """
        self.update('custom_banner', new_value)

    @property
    def background_type(self) -> str:
        """
        主页背景类型（版本海报/静态背景/动态背景/无）
        """
        return self.get('background_type', BackgroundTypeEnum.STATIC.value.value)

    @background_type.setter
    def background_type(self, new_value: str) -> None:
        self.update('background_type', new_value)

    @property
    def last_version_poster_fetch_time(self) -> str:
        """
        上次获取版本海报的时间
        """
        return self.get('last_version_poster_fetch_time', '')

    @last_version_poster_fetch_time.setter
    def last_version_poster_fetch_time(self, new_value: str) -> None:
        self.update('last_version_poster_fetch_time', new_value)

    @property
    def last_static_background_fetch_time(self) -> str:
        """
        上次获取静态背景的时间
        """
        return self.get('last_static_background_fetch_time', '')

    @last_static_background_fetch_time.setter
    def last_static_background_fetch_time(self, new_value: str) -> None:
        self.update('last_static_background_fetch_time', new_value)

    @property
    def last_dynamic_background_fetch_time(self) -> str:
        """
        上次获取动态背景的时间
        """
        return self.get('last_dynamic_background_fetch_time', '')

    @last_dynamic_background_fetch_time.setter
    def last_dynamic_background_fetch_time(self, new_value: str) -> None:
        self.update('last_dynamic_background_fetch_time', new_value)

    @property
    def theme_color_mode(self) -> str:
        """
        主题色模式
        """
        return self.get('theme_color_mode', ThemeColorModeEnum.AUTO.value.value)

    @theme_color_mode.setter
    def theme_color_mode(self, new_value: str) -> None:
        """
        主题色模式
        """
        self.update('theme_color_mode', new_value)

    @property
    def is_custom_theme_color(self) -> bool:
        """
        是否使用自定义主题色
        """
        return self.theme_color_mode == ThemeColorModeEnum.CUSTOM.value.value

    @property
    def theme_color_str(self) -> str:
        """
        全局主题色，格式为 "r,g,b"
        """
        return self.get('global_theme_color', '')

    @property
    def theme_color(self) -> tuple[int, int, int]:
        """
        全局主题色 (r, g, b)
        """
        color_str = self.theme_color_str
        if color_str:
            parts = [p.strip() for p in color_str.split(',')]
            if len(parts) == 3 and all(p.isdigit() for p in parts):
                r, g, b = map(int, parts)
                if all(0 <= c <= 255 for c in (r, g, b)):
                    return r, g, b

        # 默认值
        return 0, 120, 215

    @theme_color.setter
    def theme_color(self, new_value: tuple) -> None:
        """
        全局主题色 (r, g, b)
        """
        color_str = f"{new_value[0]},{new_value[1]},{new_value[2]}"
        self.update('global_theme_color', color_str)

    @property
    def theme_color_banner_path(self) -> str:
        """
        当前主题色对应的背景图片路径
        """
        return self.get('theme_color_banner_path', '')

    @theme_color_banner_path.setter
    def theme_color_banner_path(self, new_value: str) -> None:
        """
        当前主题色对应的背景图片路径
        """
        self.update('theme_color_banner_path', new_value)

    @property
    def theme_color_banner_mtime(self) -> float:
        """
        当前主题色对应的背景图片修改时间戳
        """
        return self.get('theme_color_banner_mtime', 0.0)

    @theme_color_banner_mtime.setter
    def theme_color_banner_mtime(self, new_value: float) -> None:
        """
        当前主题色对应的背景图片修改时间戳
        """
        self.update('theme_color_banner_mtime', new_value)
