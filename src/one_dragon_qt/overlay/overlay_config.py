from __future__ import annotations

from copy import deepcopy
from typing import Any

from one_dragon.base.config.yaml_config import YamlConfig

_DEFAULT_OVERLAY_CONFIG: dict[str, Any] = {
    "enabled": False,
    "visible": True,
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
    "display_mode": "normal",
    "follow_interval_ms": 120,
    "input_poll_interval_ms": 50,
    "state_poll_interval_ms": 200,
}

_OVERLAY_SCALAR_KEYS = {
    "enabled",
    "visible",
    "display_mode",
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
    def display_mode(self) -> str:
        mode = str(self._overlay_data()["display_mode"] or "normal")
        if mode not in ("off", "normal", "debug"):
            return "normal"
        return mode

    @display_mode.setter
    def display_mode(self, value: str) -> None:
        mode = str(value or "normal")
        if mode not in ("off", "normal", "debug"):
            mode = "normal"
        self._update_overlay_data("display_mode", mode)

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
