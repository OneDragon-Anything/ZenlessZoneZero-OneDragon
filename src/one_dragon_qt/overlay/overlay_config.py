from __future__ import annotations

from copy import deepcopy
from typing import Any

from one_dragon.base.config.yaml_config import YamlConfig


_DEFAULT_PANEL_GEOMETRY: dict[str, dict[str, int]] = {
    "log_panel": {"x": 20, "y": 20, "w": 560, "h": 220},
    "state_panel": {"x": 20, "y": 260, "w": 360, "h": 320},
}

_DEFAULT_OVERLAY_CONFIG: dict[str, Any] = {
    "enabled": False,
    "visible": True,
    "anti_capture": True,
    "toggle_hotkey": "o",
    "font_size": 12,
    "text_opacity": 100,
    "panel_opacity": 70,
    "log_panel_enabled": True,
    "state_panel_enabled": True,
    "log_max_lines": 120,
    "log_fade_seconds": 12,
    "follow_interval_ms": 120,
    "input_poll_interval_ms": 50,
    "state_poll_interval_ms": 200,
    "panel_geometry": deepcopy(_DEFAULT_PANEL_GEOMETRY),
}

_OVERLAY_SCALAR_KEYS = {
    "enabled",
    "visible",
    "anti_capture",
    "toggle_hotkey",
    "font_size",
    "text_opacity",
    "panel_opacity",
    "log_panel_enabled",
    "state_panel_enabled",
    "log_max_lines",
    "log_fade_seconds",
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

        panel_geometry = merged.get("panel_geometry", {})
        if not isinstance(panel_geometry, dict):
            panel_geometry = {}
        default_geometry = deepcopy(_DEFAULT_PANEL_GEOMETRY)
        for panel_name, geometry in panel_geometry.items():
            if panel_name not in default_geometry:
                continue
            if not isinstance(geometry, dict):
                continue
            default_geometry[panel_name].update(
                {
                    "x": int(geometry.get("x", default_geometry[panel_name]["x"])),
                    "y": int(geometry.get("y", default_geometry[panel_name]["y"])),
                    "w": int(geometry.get("w", default_geometry[panel_name]["w"])),
                    "h": int(geometry.get("h", default_geometry[panel_name]["h"])),
                }
            )
        merged["panel_geometry"] = default_geometry
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

    @staticmethod
    def _normalize_hotkey_key(value: str) -> str:
        key = str(value or "").strip().lower()
        if not key:
            return "o"
        if key.startswith("vk_"):
            num_text = key.replace("vk_", "", 1)
            if num_text.isdigit():
                vk = int(num_text)
                if 65 <= vk <= 90 or 48 <= vk <= 57:
                    return chr(vk).lower()
        if key.startswith("numpad_"):
            suffix = key.replace("numpad_", "", 1)
            if suffix.isdigit():
                return key
        return key

    @property
    def enabled(self) -> bool:
        return bool(self._overlay_data()["enabled"])

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._update_overlay_data("enabled", bool(value))

    @property
    def visible(self) -> bool:
        return bool(self._overlay_data()["visible"])

    @visible.setter
    def visible(self, value: bool) -> None:
        self._update_overlay_data("visible", bool(value))

    @property
    def anti_capture(self) -> bool:
        return bool(self._overlay_data()["anti_capture"])

    @anti_capture.setter
    def anti_capture(self, value: bool) -> None:
        self._update_overlay_data("anti_capture", bool(value))

    @property
    def toggle_hotkey(self) -> str:
        return self._normalize_hotkey_key(self._overlay_data()["toggle_hotkey"])

    @toggle_hotkey.setter
    def toggle_hotkey(self, value: str) -> None:
        self._update_overlay_data("toggle_hotkey", self._normalize_hotkey_key(value))

    @property
    def font_size(self) -> int:
        return max(10, min(28, int(self._overlay_data()["font_size"])))

    @font_size.setter
    def font_size(self, value: int) -> None:
        self._update_overlay_data("font_size", max(10, min(28, int(value))))

    @property
    def text_opacity(self) -> int:
        return max(20, min(100, int(self._overlay_data()["text_opacity"])))

    @text_opacity.setter
    def text_opacity(self, value: int) -> None:
        self._update_overlay_data("text_opacity", max(20, min(100, int(value))))

    @property
    def panel_opacity(self) -> int:
        return max(20, min(100, int(self._overlay_data()["panel_opacity"])))

    @panel_opacity.setter
    def panel_opacity(self, value: int) -> None:
        self._update_overlay_data("panel_opacity", max(20, min(100, int(value))))

    @property
    def log_panel_enabled(self) -> bool:
        return bool(self._overlay_data()["log_panel_enabled"])

    @log_panel_enabled.setter
    def log_panel_enabled(self, value: bool) -> None:
        self._update_overlay_data("log_panel_enabled", bool(value))

    @property
    def state_panel_enabled(self) -> bool:
        return bool(self._overlay_data()["state_panel_enabled"])

    @state_panel_enabled.setter
    def state_panel_enabled(self, value: bool) -> None:
        self._update_overlay_data("state_panel_enabled", bool(value))

    @property
    def log_max_lines(self) -> int:
        return max(20, int(self._overlay_data()["log_max_lines"]))

    @log_max_lines.setter
    def log_max_lines(self, value: int) -> None:
        self._update_overlay_data("log_max_lines", max(20, int(value)))

    @property
    def log_fade_seconds(self) -> int:
        return max(3, int(self._overlay_data()["log_fade_seconds"]))

    @log_fade_seconds.setter
    def log_fade_seconds(self, value: int) -> None:
        self._update_overlay_data("log_fade_seconds", max(3, int(value)))

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

    def get_panel_geometry(self, panel_name: str) -> dict[str, int]:
        geometry = self._overlay_data()["panel_geometry"].get(panel_name, {})
        return {
            "x": int(geometry.get("x", 0)),
            "y": int(geometry.get("y", 0)),
            "w": int(geometry.get("w", 320)),
            "h": int(geometry.get("h", 200)),
        }

    def set_panel_geometry(self, panel_name: str, geometry: dict[str, int]) -> None:
        if panel_name not in _DEFAULT_PANEL_GEOMETRY:
            return
        all_geometry = self._overlay_data()["panel_geometry"]
        all_geometry[panel_name] = {
            "x": int(geometry.get("x", all_geometry[panel_name]["x"])),
            "y": int(geometry.get("y", all_geometry[panel_name]["y"])),
            "w": int(geometry.get("w", all_geometry[panel_name]["w"])),
            "h": int(geometry.get("h", all_geometry[panel_name]["h"])),
        }
        self._update_overlay_data("panel_geometry", all_geometry)

    def reset_panel_geometry(self) -> None:
        self._update_overlay_data("panel_geometry", deepcopy(_DEFAULT_PANEL_GEOMETRY))
