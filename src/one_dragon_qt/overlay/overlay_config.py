from __future__ import annotations

import re
from copy import deepcopy
from enum import Enum
from typing import Any

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_config import YamlConfig


class HudFontSizeEnum(Enum):
    """HUD 字号档位，对应 QML 里的字号缩放系数。"""

    LARGE = ConfigItem('大', 'large')
    MEDIUM = ConfigItem('中', 'medium')
    SMALL = ConfigItem('小', 'small')


_HUD_FONT_SCALE_MAP: dict[str, float] = {
    'large': 1.0,
    'medium': 0.9,
    'small': 0.8,
}

# 主题色默认值与校验：标题条、状态行流光都用它
_DEFAULT_HUD_THEME_COLOR = '#ffd400'
_HEX_COLOR_PATTERN = re.compile(r'#[0-9a-fA-F]{6}')

_DEFAULT_OVERLAY_CONFIG: dict[str, Any] = {
    "vision_layer_enabled": True,
    "vision_yolo_enabled": True,
    "vision_ocr_enabled": True,
    "vision_template_enabled": True,
    "vision_cv_enabled": True,
    "vision_offset_x": 0,
    "vision_offset_y": 0,
    "vision_scale_x": 1.0,
    "vision_scale_y": 1.0,
    "patched_capture_enabled": False,
    "patched_capture_suffix": "_patched",
    # 档位键换过一次名：旧键 display_mode 默认 off，老配置里残留的关闭状态会让
    # overlay 永远不显示，因此改用新键，老用户与新用户都从 normal 起。
    "overlay_display_mode": "normal",
    "hud_opacity": 100,
    "hud_font_size": "large",
    "hud_font_bold": True,
    "hud_theme_color": _DEFAULT_HUD_THEME_COLOR,
    "follow_interval_ms": 120,
    "input_poll_interval_ms": 50,
    "state_poll_interval_ms": 200,
}

_OVERLAY_SCALAR_KEYS = {
    "overlay_display_mode",
    "hud_opacity",
    "hud_font_size",
    "hud_font_bold",
    "hud_theme_color",
    "vision_layer_enabled",
    "vision_yolo_enabled",
    "vision_ocr_enabled",
    "vision_template_enabled",
    "vision_cv_enabled",
    "vision_offset_x",
    "vision_offset_y",
    "vision_scale_x",
    "vision_scale_y",
    "patched_capture_enabled",
    "patched_capture_suffix",
    "follow_interval_ms",
    "input_poll_interval_ms",
    "state_poll_interval_ms",
}


class OverlayConfig(YamlConfig):
    """Overlay debug HUD configuration persisted at config/overlay.yml."""

    def __init__(self):
        YamlConfig.__init__(self, module_name="overlay")

    def _overlay_data(self) -> dict[str, Any]:
        data = self.get("overlay", {})
        if not isinstance(data, dict):
            data = {}
        merged = deepcopy(_DEFAULT_OVERLAY_CONFIG)
        merged.update(data)
        return merged

    def _update_overlay_data(self, key: str, value: Any) -> None:
        data = self._overlay_data()
        data[key] = value
        self.update("overlay", data)

    def update(self, key: str, value, save: bool = True):
        """
        Override update so YamlConfigAdapter can still write overlay.* fields.
        """
        if key in _OVERLAY_SCALAR_KEYS:
            data = self._overlay_data()
            data[key] = value
            return YamlConfig.update(self, "overlay", data, save=save)
        return YamlConfig.update(self, key, value, save=save)

    @property
    def display_mode(self) -> str:
        mode = str(self._overlay_data()["overlay_display_mode"] or "normal")
        if mode not in ("off", "normal", "debug"):
            return "normal"
        return mode

    @display_mode.setter
    def display_mode(self, value: str) -> None:
        mode = str(value or "normal")
        if mode not in ("off", "normal", "debug"):
            mode = "normal"
        self._update_overlay_data("overlay_display_mode", mode)

    @property
    def hud_opacity(self) -> int:
        """面板底色不透明度百分比，100 为纯黑不透明。"""
        return max(10, min(100, int(self._overlay_data()["hud_opacity"])))

    @hud_opacity.setter
    def hud_opacity(self, value: int) -> None:
        self._update_overlay_data("hud_opacity", max(10, min(100, int(value))))

    @property
    def hud_font_size(self) -> str:
        size = str(self._overlay_data()["hud_font_size"] or "large")
        if size not in _HUD_FONT_SCALE_MAP:
            return "large"
        return size

    @hud_font_size.setter
    def hud_font_size(self, value: str) -> None:
        size = str(value or "large")
        if size not in _HUD_FONT_SCALE_MAP:
            size = "large"
        self._update_overlay_data("hud_font_size", size)

    @property
    def hud_font_scale(self) -> float:
        """字号缩放系数，由档位换算，不下发到配置。"""
        return _HUD_FONT_SCALE_MAP[self.hud_font_size]

    @property
    def hud_font_bold(self) -> bool:
        return bool(self._overlay_data()["hud_font_bold"])

    @hud_font_bold.setter
    def hud_font_bold(self, value: bool) -> None:
        self._update_overlay_data("hud_font_bold", bool(value))

    @property
    def hud_theme_color(self) -> str:
        """主题色 hex 字符串，标题条与状态行流光共用。"""
        color = str(self._overlay_data()["hud_theme_color"] or _DEFAULT_HUD_THEME_COLOR)
        if _HEX_COLOR_PATTERN.fullmatch(color) is None:
            return _DEFAULT_HUD_THEME_COLOR
        return color.lower()

    @hud_theme_color.setter
    def hud_theme_color(self, value: str) -> None:
        color = str(value or _DEFAULT_HUD_THEME_COLOR).strip()
        if _HEX_COLOR_PATTERN.fullmatch(color) is None:
            color = _DEFAULT_HUD_THEME_COLOR
        self._update_overlay_data("hud_theme_color", color.lower())

    @property
    def patched_capture_enabled(self) -> bool:
        return bool(self._overlay_data()["patched_capture_enabled"])

    @patched_capture_enabled.setter
    def patched_capture_enabled(self, value: bool) -> None:
        self._update_overlay_data("patched_capture_enabled", bool(value))

    @property
    def patched_capture_suffix(self) -> str:
        suffix = str(self._overlay_data()["patched_capture_suffix"] or "").strip()
        if not suffix:
            suffix = "_patched"
        if not suffix.startswith("_"):
            suffix = "_" + suffix
        return suffix

    @patched_capture_suffix.setter
    def patched_capture_suffix(self, value: str) -> None:
        suffix = str(value or "").strip()
        if not suffix:
            suffix = "_patched"
        if not suffix.startswith("_"):
            suffix = "_" + suffix
        self._update_overlay_data("patched_capture_suffix", suffix[:40])

    @property
    def vision_layer_enabled(self) -> bool:
        return bool(self._overlay_data()["vision_layer_enabled"])

    @vision_layer_enabled.setter
    def vision_layer_enabled(self, value: bool) -> None:
        self._update_overlay_data("vision_layer_enabled", bool(value))

    @property
    def vision_yolo_enabled(self) -> bool:
        return bool(self._overlay_data()["vision_yolo_enabled"])

    @vision_yolo_enabled.setter
    def vision_yolo_enabled(self, value: bool) -> None:
        self._update_overlay_data("vision_yolo_enabled", bool(value))

    @property
    def vision_ocr_enabled(self) -> bool:
        return bool(self._overlay_data()["vision_ocr_enabled"])

    @vision_ocr_enabled.setter
    def vision_ocr_enabled(self, value: bool) -> None:
        self._update_overlay_data("vision_ocr_enabled", bool(value))

    @property
    def vision_template_enabled(self) -> bool:
        return bool(self._overlay_data()["vision_template_enabled"])

    @vision_template_enabled.setter
    def vision_template_enabled(self, value: bool) -> None:
        self._update_overlay_data("vision_template_enabled", bool(value))

    @property
    def vision_cv_enabled(self) -> bool:
        return bool(self._overlay_data()["vision_cv_enabled"])

    @vision_cv_enabled.setter
    def vision_cv_enabled(self, value: bool) -> None:
        self._update_overlay_data("vision_cv_enabled", bool(value))

    @property
    def vision_offset_x(self) -> int:
        return int(self._overlay_data()["vision_offset_x"])

    @vision_offset_x.setter
    def vision_offset_x(self, value: int) -> None:
        self._update_overlay_data("vision_offset_x", int(value))

    @property
    def vision_offset_y(self) -> int:
        return int(self._overlay_data()["vision_offset_y"])

    @vision_offset_y.setter
    def vision_offset_y(self, value: int) -> None:
        self._update_overlay_data("vision_offset_y", int(value))

    @property
    def vision_scale_x(self) -> float:
        return max(0.5, min(1.5, float(self._overlay_data()["vision_scale_x"])))

    @vision_scale_x.setter
    def vision_scale_x(self, value: float) -> None:
        self._update_overlay_data("vision_scale_x", max(0.5, min(1.5, float(value))))

    @property
    def vision_scale_y(self) -> float:
        return max(0.5, min(1.5, float(self._overlay_data()["vision_scale_y"])))

    @vision_scale_y.setter
    def vision_scale_y(self, value: float) -> None:
        self._update_overlay_data("vision_scale_y", max(0.5, min(1.5, float(value))))

    @property
    def follow_interval_ms(self) -> int:
        return max(30, int(self._overlay_data()["follow_interval_ms"]))

    @follow_interval_ms.setter
    def follow_interval_ms(self, value: int) -> None:
        self._update_overlay_data("follow_interval_ms", max(30, int(value)))

    @property
    def input_poll_interval_ms(self) -> int:
        return max(20, int(self._overlay_data()["input_poll_interval_ms"]))

    @input_poll_interval_ms.setter
    def input_poll_interval_ms(self, value: int) -> None:
        self._update_overlay_data("input_poll_interval_ms", max(20, int(value)))

    @property
    def state_poll_interval_ms(self) -> int:
        return max(80, int(self._overlay_data()["state_poll_interval_ms"]))

    @state_poll_interval_ms.setter
    def state_poll_interval_ms(self, value: int) -> None:
        self._update_overlay_data("state_poll_interval_ms", max(80, int(value)))
