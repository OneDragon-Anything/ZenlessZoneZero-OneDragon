from __future__ import annotations

import logging
import time
from typing import Optional

from PySide6.QtCore import QObject, QPoint, QTimer, Signal, Qt
from PySide6.QtGui import QGuiApplication

from one_dragon.base.operation.context_event_bus import ContextEventItem
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils.log_utils import log
from one_dragon_qt.overlay.overlay_config import OverlayConfig
from one_dragon_qt.overlay.overlay_events import OverlayEventEnum, OverlayLogEvent
from one_dragon_qt.overlay.overlay_log_handler import OverlayLogHandler
from one_dragon_qt.overlay.overlay_window import OverlayWindow
from one_dragon_qt.overlay.panels.decision_panel import DecisionPanel
from one_dragon_qt.overlay.panels.log_panel import LogPanel
from one_dragon_qt.overlay.panels.performance_panel import PerformancePanel
from one_dragon_qt.overlay.panels.state_panel import StatePanel
from one_dragon_qt.overlay.panels.timeline_panel import TimelinePanel
from one_dragon_qt.overlay.utils import win32_utils

try:
    from one_dragon.yolo.log_utils import log as yolo_log
except Exception:
    yolo_log = None


class _OverlaySignalBridge(QObject):
    log_received = Signal(object)


class OverlayManager(QObject):
    """Singleton manager for overlay lifecycle and runtime behavior."""

    _instance: Optional["OverlayManager"] = None

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.config = OverlayConfig()

        self._supported = win32_utils.is_windows_build_supported(19041)
        self._warned_unsupported = False
        self._warned_waiting_game_window = False
        self._started = False
        self._overlay_window: Optional[OverlayWindow] = None
        self._log_panel: Optional["LogPanel"] = None
        self._state_panel: Optional["StatePanel"] = None
        self._decision_panel: Optional["DecisionPanel"] = None
        self._timeline_panel: Optional["TimelinePanel"] = None
        self._performance_panel: Optional["PerformancePanel"] = None
        self._log_handler: Optional[OverlayLogHandler] = None
        self._ctrl_interaction = False
        self._toggle_combo_pressed = False
        self._last_toggle_hotkey_time = 0.0
        self._last_game_qt_rect: Rect | None = None

        self._signal_bridge = _OverlaySignalBridge()
        self._signal_bridge.log_received.connect(self._on_log_received_signal)

        self._follow_timer = QTimer(self)
        self._follow_timer.timeout.connect(self._safe_follow_window)

        self._input_timer = QTimer(self)
        self._input_timer.timeout.connect(self._safe_poll_input_mode)

        self._state_timer = QTimer(self)
        self._state_timer.timeout.connect(self._safe_refresh_state)

    @classmethod
    def create(cls, ctx, parent=None) -> "OverlayManager":
        if cls._instance is None:
            cls._instance = OverlayManager(ctx, parent=parent)
        return cls._instance

    @classmethod
    def instance(cls) -> Optional["OverlayManager"]:
        return cls._instance

    def start(self) -> None:
        if self._started:
            return
        self._started = True

        self._bind_context_events()
        self._install_log_handler()
        self._apply_timer_intervals()
        self._follow_timer.start()
        self._input_timer.start()
        self._state_timer.start()
        self._safe_follow_window()

    def shutdown(self) -> None:
        if not self._started:
            return
        self._started = False

        self._follow_timer.stop()
        self._input_timer.stop()
        self._state_timer.stop()

        self._uninstall_log_handler()
        self.ctx.unlisten_all_event(self)

        if self._overlay_window is not None:
            self._overlay_window.close()
            self._overlay_window.deleteLater()
            self._overlay_window = None

        if self._log_panel is not None:
            self._log_panel.close()
            self._log_panel.deleteLater()
            self._log_panel = None
        if self._state_panel is not None:
            self._state_panel.close()
            self._state_panel.deleteLater()
            self._state_panel = None
        if self._decision_panel is not None:
            self._decision_panel.close()
            self._decision_panel.deleteLater()
            self._decision_panel = None
        if self._timeline_panel is not None:
            self._timeline_panel.close()
            self._timeline_panel.deleteLater()
            self._timeline_panel = None
        if self._performance_panel is not None:
            self._performance_panel.close()
            self._performance_panel.deleteLater()
            self._performance_panel = None

        OverlayManager._instance = None

    def reload_config(self) -> None:
        self.config = OverlayConfig()
        self._toggle_combo_pressed = False
        self._apply_timer_intervals()
        for panel_name, panel in self._iter_side_panels():
            if panel is None:
                continue
            geo = self._panel_geometry_with_fallback(panel_name)
            panel.setGeometry(geo["x"], geo["y"], geo["w"], geo["h"])
        self._safe_follow_window()

    def toggle_visibility(self) -> None:
        if not self.config.enabled:
            return
        self.config.visible = not self.config.visible
        self._safe_follow_window()

    def reset_panel_geometry(self) -> None:
        self.config.reset_panel_geometry()
        for panel_name, _panel in self._iter_side_panels():
            geo = self._panel_geometry_with_fallback(panel_name)
            self.config.set_panel_geometry(panel_name, geo)

        for panel_name, panel in self._iter_side_panels():
            if panel is None:
                continue
            geo = self.config.get_panel_geometry(panel_name)
            panel.setGeometry(geo["x"], geo["y"], geo["w"], geo["h"])

    def capture_overlay_rgba(self):
        if self._overlay_window is None or not self._overlay_window.isVisible():
            return None
        try:
            return self._overlay_window.capture_overlay_rgba()
        except Exception:
            log.error("捕获 Overlay 图像失败", exc_info=True)
            return None

    def _apply_timer_intervals(self) -> None:
        self._follow_timer.setInterval(self.config.follow_interval_ms)
        self._input_timer.setInterval(self.config.input_poll_interval_ms)
        self._state_timer.setInterval(self.config.state_poll_interval_ms)

    def _bind_context_events(self) -> None:
        self.ctx.listen_event(OverlayEventEnum.OVERLAY_LOG.value, self._on_context_log_event)

    def _on_context_log_event(self, event: ContextEventItem) -> None:
        if event is None or event.data is None:
            return
        self._signal_bridge.log_received.emit(event.data)

    def _toggle_hotkey_if_allowed(self) -> None:
        if not self.config.enabled:
            return
        if not self._is_game_window_active():
            return
        now = time.time()
        if now - self._last_toggle_hotkey_time < 0.35:
            return
        self._last_toggle_hotkey_time = now
        self.toggle_visibility()

    def _on_log_received_signal(self, payload: object) -> None:
        if self._log_panel is None:
            return
        if not isinstance(payload, OverlayLogEvent):
            return
        if not self.config.log_panel_enabled:
            return
        self._log_panel.append_log(payload)

    def _ensure_overlay_window(self) -> OverlayWindow:
        if self._overlay_window is None:
            self._overlay_window = OverlayWindow()
            self._overlay_window.set_standard_resolution(
                int(self.ctx.project_config.screen_standard_width),
                int(self.ctx.project_config.screen_standard_height),
            )
        if self._log_panel is None:
            self._log_panel = LogPanel(parent=None)
            self._init_top_panel("log_panel", self._log_panel)
            self._log_panel.geometry_changed.connect(
                lambda g: self._on_panel_geometry_changed("log_panel", g)
            )
            self._log_panel.appearance_changed.connect(
                self._on_panel_appearance_changed
            )
            self._log_panel.free_mode_changed.connect(
                self._on_panel_free_mode_changed
            )
            self._log_panel.edit_mode_changed.connect(
                self._on_panel_edit_mode_changed
            )
            geo = self._panel_geometry_with_fallback("log_panel")
            self._log_panel.setGeometry(geo["x"], geo["y"], geo["w"], geo["h"])
        if self._state_panel is None:
            self._state_panel = StatePanel(parent=None)
            self._init_top_panel("state_panel", self._state_panel)
            self._state_panel.geometry_changed.connect(
                lambda g: self._on_panel_geometry_changed("state_panel", g)
            )
            self._state_panel.appearance_changed.connect(self._on_panel_appearance_changed)
            self._state_panel.free_mode_changed.connect(self._on_panel_free_mode_changed)
            self._state_panel.edit_mode_changed.connect(self._on_panel_edit_mode_changed)
            geo = self._panel_geometry_with_fallback("state_panel")
            self._state_panel.setGeometry(geo["x"], geo["y"], geo["w"], geo["h"])
        if self._decision_panel is None:
            self._decision_panel = DecisionPanel(parent=None)
            self._init_top_panel("decision_panel", self._decision_panel)
            self._decision_panel.geometry_changed.connect(
                lambda g: self._on_panel_geometry_changed("decision_panel", g)
            )
            self._decision_panel.appearance_changed.connect(self._on_panel_appearance_changed)
            self._decision_panel.free_mode_changed.connect(self._on_panel_free_mode_changed)
            self._decision_panel.edit_mode_changed.connect(self._on_panel_edit_mode_changed)
            geo = self._panel_geometry_with_fallback("decision_panel")
            self._decision_panel.setGeometry(geo["x"], geo["y"], geo["w"], geo["h"])
        if self._timeline_panel is None:
            self._timeline_panel = TimelinePanel(parent=None)
            self._init_top_panel("timeline_panel", self._timeline_panel)
            self._timeline_panel.geometry_changed.connect(
                lambda g: self._on_panel_geometry_changed("timeline_panel", g)
            )
            self._timeline_panel.appearance_changed.connect(self._on_panel_appearance_changed)
            self._timeline_panel.free_mode_changed.connect(self._on_panel_free_mode_changed)
            self._timeline_panel.edit_mode_changed.connect(self._on_panel_edit_mode_changed)
            geo = self._panel_geometry_with_fallback("timeline_panel")
            self._timeline_panel.setGeometry(geo["x"], geo["y"], geo["w"], geo["h"])
        if self._performance_panel is None:
            self._performance_panel = PerformancePanel(parent=None)
            self._init_top_panel("performance_panel", self._performance_panel)
            self._performance_panel.geometry_changed.connect(
                lambda g: self._on_panel_geometry_changed("performance_panel", g)
            )
            self._performance_panel.appearance_changed.connect(self._on_panel_appearance_changed)
            self._performance_panel.free_mode_changed.connect(self._on_panel_free_mode_changed)
            self._performance_panel.edit_mode_changed.connect(self._on_panel_edit_mode_changed)
            geo = self._panel_geometry_with_fallback("performance_panel")
            self._performance_panel.setGeometry(geo["x"], geo["y"], geo["w"], geo["h"])
        return self._overlay_window

    def _init_top_panel(self, panel_name: str, panel) -> None:
        panel.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        panel.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        panel.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        panel.set_title_visible(False)
        panel.set_drag_anywhere(False)
        panel.set_passthrough_on_body(True)
        panel.set_free_mode(self.config.is_panel_free_mode(panel_name))
        panel.set_edit_mode(self.config.panel_edit_mode)

    def _iter_side_panels(self):
        return [
            ("log_panel", self._log_panel),
            ("state_panel", self._state_panel),
            ("decision_panel", self._decision_panel),
            ("timeline_panel", self._timeline_panel),
            ("performance_panel", self._performance_panel),
        ]

    def _panel_geometry_with_fallback(self, panel_name: str) -> dict[str, int]:
        geometry = self.config.get_panel_geometry(panel_name)
        if panel_name == "log_panel" and self._is_log_panel_factory_geometry(geometry):
            resolved = self._resolve_panel_geometry_for_game(panel_name)
            if resolved is not None:
                return resolved

        if panel_name in ("state_panel", "decision_panel", "timeline_panel", "performance_panel"):
            if int(geometry.get("x", 0)) == 0 and int(geometry.get("y", 0)) == 0:
                resolved = self._resolve_panel_geometry_for_game(panel_name)
                if resolved is not None:
                    return resolved

        return geometry

    @staticmethod
    def _is_log_panel_factory_geometry(geometry: dict[str, int]) -> bool:
        return (
            int(geometry.get("x", 0)) == 100
            and int(geometry.get("y", 0)) == 100
            and int(geometry.get("w", 0)) == 480
            and int(geometry.get("h", 0)) == 200
        )

    def _resolve_panel_geometry_for_game(self, panel_name: str) -> dict[str, int] | None:
        base_geo = self.config.get_panel_geometry(panel_name)
        game_rect = self._get_game_rect()
        if game_rect is None:
            return base_geo

        qt_rect = self._to_qt_rect(game_rect)
        margin = 16
        qr_x1 = int(getattr(qt_rect, "x1", 0))
        qr_y1 = int(getattr(qt_rect, "y1", 0))
        qr_x2 = int(getattr(qt_rect, "x2", 0))
        qr_y2 = int(getattr(qt_rect, "y2", 0))
        game_w = max(100, qr_x2 - qr_x1)
        game_h = max(100, qr_y2 - qr_y1)

        w = max(180, min(int(base_geo.get("w", 320)), game_w - margin * 2))
        h = max(90, min(int(base_geo.get("h", 180)), game_h - margin * 2))

        if panel_name == "log_panel":
            x = qr_x1 + margin
            y = qr_y1 + margin
        else:
            right_x = qr_x2 - margin - w
            top_start = qr_y1 + margin
            vertical_gap = 8
            index = {
                "state_panel": 0,
                "decision_panel": 1,
                "timeline_panel": 2,
                "performance_panel": 3,
            }.get(panel_name, 0)
            x = right_x
            y = top_start + index * (h + vertical_gap)
            if y + h > qr_y2 - margin:
                y = max(qr_y1 + margin, qr_y2 - margin - h)

        return {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}

    def _on_panel_geometry_changed(self, panel_name: str, geometry: dict[str, int]) -> None:
        try:
            if not self.config.is_panel_free_mode(panel_name):
                game_rect = self._get_game_rect()
                if game_rect is not None:
                    qt_rect = self._to_qt_rect(game_rect)
                    geometry = self._clamp_geometry_dict_to_game_rect(geometry, qt_rect)
            self.config.set_panel_geometry(panel_name, geometry)
        except Exception:
            log.error("保存 Overlay 面板位置失败", exc_info=True)

    def _on_panel_appearance_changed(
        self, panel_name: str, font_size: int, panel_opacity: int
    ) -> None:
        try:
            self.config.set_panel_appearance(panel_name, font_size=font_size, opacity=panel_opacity)
        except Exception:
            log.error(f"保存 Overlay {panel_name} 样式失败", exc_info=True)

    def _on_panel_edit_mode_changed(self, enabled: bool) -> None:
        try:
            self.config.panel_edit_mode = bool(enabled)
            self._safe_follow_window()
        except Exception:
            log.error("保存 Overlay 编辑模式失败", exc_info=True)

    def _on_panel_free_mode_changed(self, panel_name: str, enabled: bool) -> None:
        try:
            self.config.set_panel_free_mode(panel_name, bool(enabled))
            self._safe_follow_window()
        except Exception:
            log.error(f"保存 Overlay {panel_name} 窗口模式失败", exc_info=True)

    def _safe_follow_window(self) -> None:
        try:
            self._follow_window()
        except Exception:
            log.error("更新 Overlay 窗口失败", exc_info=True)

    def _follow_window(self) -> None:
        if not self.config.enabled:
            self._hide_overlay()
            return
        if not self._supported:
            self._hide_overlay()
            if not self._warned_unsupported:
                log.warning("Overlay 已禁用：系统版本低于 Windows 10 2004（build 19041）")
                self._warned_unsupported = True
            return

        game_rect = self._get_game_rect()
        if game_rect is None:
            self._hide_overlay()
            if not self._warned_waiting_game_window:
                log.info("Overlay 已启用，等待游戏窗口可用后显示")
                self._warned_waiting_game_window = True
            return
        self._warned_waiting_game_window = False

        if not self._is_game_window_active() and not self.config.panel_edit_mode:
            self._hide_overlay()
            return

        overlay = self._ensure_overlay_window()
        game_qt_rect = self._to_qt_rect(game_rect)
        overlay.update_with_game_rect(game_qt_rect)
        # State/decision/timeline/perf now render as independent windows.
        overlay.set_info_hud_enabled(False)
        overlay.set_vision_layer_enabled(self.config.vision_layer_enabled)
        overlay.set_vision_transform(
            offset_x=self.config.vision_offset_x,
            offset_y=self.config.vision_offset_y,
            scale_x=self.config.vision_scale_x,
            scale_y=self.config.vision_scale_y,
        )
        overlay.set_anti_capture(self.config.anti_capture)
        overlay.set_overlay_visible(self.config.visible)
        if self.config.visible:
            overlay.set_passthrough(not self._ctrl_interaction)

        self._sync_side_panels(game_qt_rect)
        self._last_game_qt_rect = game_qt_rect

    def _sync_side_panels(self, game_qt_rect: Rect) -> None:
        edit_mode = self.config.panel_edit_mode
        panel_visible_map = {
            "log_panel": self.config.log_panel_enabled,
            "state_panel": self.config.state_panel_enabled,
            "decision_panel": self.config.decision_panel_enabled,
            "timeline_panel": self.config.timeline_panel_enabled,
            "performance_panel": self.config.performance_panel_enabled,
        }

        # If game window moved, shift panel windows with it before clamping.
        delta_x = 0
        delta_y = 0
        if self._last_game_qt_rect is not None:
            delta_x = int(getattr(game_qt_rect, "x1", 0)) - int(getattr(self._last_game_qt_rect, "x1", 0))
            delta_y = int(getattr(game_qt_rect, "y1", 0)) - int(getattr(self._last_game_qt_rect, "y1", 0))

        for panel_name, panel in self._iter_side_panels():
            if panel is None:
                continue
            lock_in_game = not self.config.is_panel_free_mode(panel_name)

            if panel_name == "log_panel":
                panel.set_limits(self.config.log_max_lines, self.config.log_fade_seconds)
            pa = self.config.get_panel_appearance(panel_name)
            panel.set_free_mode(not lock_in_game)
            panel.set_appearance(pa["font_size"], pa["opacity"])
            if edit_mode:
                panel.setWindowOpacity(1.0)
            else:
                panel.setWindowOpacity(pa["opacity"] / 100.0)
            if hasattr(panel, "set_text_color"):
                panel.set_text_color(self.config.panel_text_color)
            # set_edit_mode last so placeholder is not overwritten by set_appearance/set_text_color
            panel.set_edit_mode(edit_mode)
            panel.set_passthrough_on_body(False)

            show_panel = self.config.visible and panel_visible_map.get(panel_name, True)
            if not show_panel:
                if panel.isVisible():
                    panel.hide()
                continue

            if lock_in_game and (delta_x != 0 or delta_y != 0):
                g = panel.geometry()
                panel.setGeometry(g.x() + delta_x, g.y() + delta_y, g.width(), g.height())

            if lock_in_game:
                self._clamp_panel_to_game_rect(panel, game_qt_rect)

            if not panel.isVisible():
                panel.show()
                panel.raise_()

            panel_hwnd = int(panel.winId())
            win32_utils.set_window_display_affinity(panel_hwnd, self.config.anti_capture)
            # Non-edit mode: all clicks pass through to underlying game window.
            win32_utils.set_window_click_through(panel_hwnd, not edit_mode)

    @staticmethod
    def _clamp_panel_to_game_rect(panel, game_qt_rect: Rect) -> None:
        g = panel.geometry()
        left = int(getattr(game_qt_rect, "x1", 0))
        top = int(getattr(game_qt_rect, "y1", 0))
        right = int(getattr(game_qt_rect, "x2", 0))
        bottom = int(getattr(game_qt_rect, "y2", 0))
        margin = 4

        max_w = max(120, right - left - margin * 2)
        max_h = max(80, bottom - top - margin * 2)
        w = min(g.width(), max_w)
        h = min(g.height(), max_h)

        min_x = left + margin
        min_y = top + margin
        max_x = right - margin - w
        max_y = bottom - margin - h

        x = min(max(g.x(), min_x), max_x)
        y = min(max(g.y(), min_y), max_y)

        if x != g.x() or y != g.y() or w != g.width() or h != g.height():
            panel.setGeometry(int(x), int(y), int(w), int(h))

    @staticmethod
    def _clamp_geometry_dict_to_game_rect(geometry: dict[str, int], game_qt_rect: Rect) -> dict[str, int]:
        g_x = int(geometry.get("x", 0))
        g_y = int(geometry.get("y", 0))
        g_w = max(80, int(geometry.get("w", 0)))
        g_h = max(60, int(geometry.get("h", 0)))

        left = int(getattr(game_qt_rect, "x1", 0))
        top = int(getattr(game_qt_rect, "y1", 0))
        right = int(getattr(game_qt_rect, "x2", 0))
        bottom = int(getattr(game_qt_rect, "y2", 0))
        margin = 4

        max_w = max(120, right - left - margin * 2)
        max_h = max(80, bottom - top - margin * 2)
        w = min(g_w, max_w)
        h = min(g_h, max_h)

        min_x = left + margin
        min_y = top + margin
        max_x = right - margin - w
        max_y = bottom - margin - h
        x = min(max(g_x, min_x), max_x)
        y = min(max(g_y, min_y), max_y)

        return {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}

    def _hide_overlay(self) -> None:
        self._ctrl_interaction = False
        self._toggle_combo_pressed = False
        self._last_game_qt_rect = None
        if self._overlay_window is not None:
            self._overlay_window.set_vision_items([])
            self._overlay_window.set_overlay_visible(False)
        for _panel_name, panel in self._iter_side_panels():
            if panel is not None and panel.isVisible():
                panel.hide()

    def _safe_poll_input_mode(self) -> None:
        try:
            self._poll_input_mode()
        except Exception:
            log.error("更新 Overlay 交互模式失败", exc_info=True)

    def _poll_input_mode(self) -> None:
        toggle_combo_now = win32_utils.is_hotkey_combo_pressed(self.config.toggle_hotkey)
        if toggle_combo_now and not self._toggle_combo_pressed:
            self._toggle_hotkey_if_allowed()
        self._toggle_combo_pressed = toggle_combo_now

        if self._overlay_window is None or not self._overlay_window.isVisible():
            self._ctrl_interaction = False
            return

        ctrl_now = win32_utils.is_ctrl_pressed()
        if ctrl_now == self._ctrl_interaction:
            return

        self._ctrl_interaction = ctrl_now
        self._overlay_window.set_passthrough(not ctrl_now)

    def _safe_refresh_state(self) -> None:
        start = time.time()
        try:
            self._refresh_state_panel()
        except Exception:
            log.error("刷新 Overlay 状态面板失败", exc_info=True)
        finally:
            self._emit_overlay_refresh_perf(start)

    def _refresh_state_panel(self) -> None:
        if self._overlay_window is None or not self._overlay_window.isVisible():
            return

        self._refresh_debug_panels()

        if not self.config.state_panel_enabled or self._state_panel is None:
            return
        items = self._collect_state_items()
        self._state_panel.update_snapshot(items)

    def _refresh_debug_panels(self) -> None:
        bus = getattr(self.ctx, "overlay_debug_bus", None)
        if bus is None:
            return

        snapshot = bus.snapshot()
        if self._overlay_window is not None:
            self._overlay_window.set_vision_items(self._filter_vision_items(snapshot.vision_items))
        if self._decision_panel is not None:
            self._decision_panel.update_items(snapshot.decision_items)
        if self._timeline_panel is not None:
            self._timeline_panel.update_items(snapshot.timeline_items)
        if self._performance_panel is not None:
            self._performance_panel.set_enabled_metric_map(self.config.performance_metric_enabled_map)
            self._performance_panel.update_items(snapshot.performance_items)

    def _emit_overlay_refresh_perf(self, start_time: float) -> None:
        bus = getattr(self.ctx, "overlay_debug_bus", None)
        if bus is None:
            return
        try:
            from one_dragon.base.operation.overlay_debug_bus import PerfMetricSample
        except Exception:
            return
        elapsed_ms = (time.time() - start_time) * 1000.0
        bus.add_performance(
            PerfMetricSample(
                metric="overlay_refresh_ms",
                value=elapsed_ms,
                unit="ms",
                ttl_seconds=20.0,
            )
        )

    def _filter_vision_items(self, items):
        if not self.config.vision_layer_enabled:
            return []

        source_enabled = {
            "yolo": self.config.vision_yolo_enabled,
            "ocr": self.config.vision_ocr_enabled,
            "template": self.config.vision_template_enabled,
            "cv": self.config.vision_cv_enabled,
        }
        filtered_items = [
            item
            for item in items
            if source_enabled.get(getattr(item, "source", ""), True)
        ]
        return self._dedupe_yolo_vision_items(filtered_items)

    def _dedupe_yolo_vision_items(self, items):
        kept_items = []
        latest_yolo_items = []

        for item in reversed(items):
            if getattr(item, "source", "") != "yolo":
                kept_items.append(item)
                continue
            if self._matches_recent_yolo_item(item, latest_yolo_items):
                continue
            latest_yolo_items.append(item)
            kept_items.append(item)

        kept_items.reverse()
        return kept_items

    def _matches_recent_yolo_item(self, item, recent_items) -> bool:
        item_label = str(getattr(item, "label", "") or "")
        for recent_item in recent_items:
            if item_label != str(getattr(recent_item, "label", "") or ""):
                continue
            if self._vision_item_iou(item, recent_item) >= 0.3:
                return True
        return False

    @staticmethod
    def _vision_item_iou(a, b) -> float:
        ax1 = float(getattr(a, "x1", 0))
        ay1 = float(getattr(a, "y1", 0))
        ax2 = float(getattr(a, "x2", 0))
        ay2 = float(getattr(a, "y2", 0))
        bx1 = float(getattr(b, "x1", 0))
        by1 = float(getattr(b, "y1", 0))
        bx2 = float(getattr(b, "x2", 0))
        by2 = float(getattr(b, "y2", 0))

        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)
        inter_w = max(0.0, inter_x2 - inter_x1)
        inter_h = max(0.0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h
        if inter_area <= 0:
            return 0.0

        a_area = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
        b_area = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
        union_area = a_area + b_area - inter_area
        if union_area <= 0:
            return 0.0

        return inter_area / union_area

    def _collect_state_items(self) -> list[tuple[str, str]]:
        run_ctx = self.ctx.run_context
        items: list[tuple[str, str]] = [
            ("RunState", run_ctx.run_status_text),
            ("CurrentAppId", str(run_ctx.current_app_id or "-")),
        ]

        app = getattr(run_ctx, "current_application", None)
        app_name = "-"
        current_node = "-"
        previous_node = "-"
        retry_times = "0"
        if app is not None:
            app_name = str(getattr(app, "display_name", None) or getattr(app, "op_name", "-"))
            try:
                current_node = str(app.current_node.name or "-")
                previous_node = str(app.previous_node.name or "-")
            except Exception:
                current_node = "-"
                previous_node = "-"
            retry_times = str(getattr(app, "node_retry_times", 0))

        items.extend(
            [
                ("CurrentApp", app_name),
                ("CurrentNode", current_node),
                ("PreviousNode", previous_node),
                ("NodeRetry", retry_times),
            ]
        )

        if hasattr(self.ctx, "auto_battle_context"):
            items.extend(self._collect_auto_battle_items())

        return items

    def _collect_auto_battle_items(self) -> list[tuple[str, str]]:
        auto_ctx = self.ctx.auto_battle_context
        auto_op = auto_ctx.auto_op
        is_running = auto_op is not None and auto_op.is_running

        items: list[tuple[str, str]] = [("AutoBattle", "RUNNING" if is_running else "STOP")]
        if not is_running:
            return items

        front_agent_name = "-"
        front_special = "-"
        front_ultimate = "-"

        team_info = auto_ctx.agent_context.team_info
        if team_info.agent_list:
            front_agent = team_info.agent_list[0]
            if front_agent.agent is not None:
                front_agent_name = front_agent.agent.agent_name
            front_special = "Y" if front_agent.special_ready else "N"
            front_ultimate = "Y" if front_agent.ultimate_ready else "N"

        distance = "-"
        if auto_ctx.last_check_distance >= 0:
            distance = f"{auto_ctx.last_check_distance:.1f}m"

        dodge_text = self._latest_dodge_state_text()
        chain_text = "READY" if self._is_state_recent("连携技-准备", 1.2) else "-"
        quick_text = self._latest_quick_assist_text(team_info)

        items.extend(
            [
                ("FrontAgent", front_agent_name),
                ("FrontSpecial", front_special),
                ("FrontUltimate", front_ultimate),
                ("Dodge", dodge_text),
                ("Chain", chain_text),
                ("QuickAssist", quick_text),
                ("Distance", distance),
            ]
        )
        return items

    def _latest_dodge_state_text(self) -> str:
        candidates = ["闪避识别-黄光", "闪避识别-红光", "闪避识别-声音"]
        latest_name = "-"
        latest_time = 0.0
        now = time.time()
        for name in candidates:
            recorder = self.ctx.auto_battle_context.state_record_service.get_state_recorder(name)
            if recorder is None:
                continue
            ts = recorder.last_record_time
            if ts <= 0 or now - ts > 2.0:
                continue
            if ts > latest_time:
                latest_time = ts
                latest_name = name
        return latest_name

    def _latest_quick_assist_text(self, team_info) -> str:
        now = time.time()
        latest_name = "-"
        latest_time = 0.0
        if not team_info.agent_list:
            return latest_name

        for agent_info in team_info.agent_list:
            if agent_info.agent is None:
                continue
            state_name = f"快速支援-{agent_info.agent.agent_name}"
            recorder = self.ctx.auto_battle_context.state_record_service.get_state_recorder(state_name)
            if recorder is None:
                continue
            ts = recorder.last_record_time
            if ts <= 0 or now - ts > 2.0:
                continue
            if ts > latest_time:
                latest_time = ts
                latest_name = agent_info.agent.agent_name
        return latest_name

    def _is_state_recent(self, state_name: str, seconds: float) -> bool:
        recorder = self.ctx.auto_battle_context.state_record_service.get_state_recorder(state_name)
        if recorder is None or recorder.last_record_time <= 0:
            return False
        return time.time() - recorder.last_record_time <= seconds

    def _get_game_rect(self):
        if self.ctx.controller is None:
            return None
        game_win = getattr(self.ctx.controller, "game_win", None)
        if game_win is None:
            return None
        rect = self._resolve_game_rect_once(game_win)
        if rect is not None:
            return rect

        refresh = getattr(game_win, "refresh_win", None)
        if callable(refresh):
            refresh()
            return self._resolve_game_rect_once(game_win)
        return None

    @staticmethod
    def _resolve_game_rect_once(game_win):
        if not game_win.is_win_valid:
            return None
        hwnd = game_win.get_hwnd() if hasattr(game_win, "get_hwnd") else None
        if hwnd is None:
            return None
        if win32_utils.is_window_minimized(hwnd):
            return None
        win = game_win.get_win() if hasattr(game_win, "get_win") else None
        if win is not None:
            if bool(getattr(win, "isMinimized", False)):
                return None
            win_visible = getattr(win, "isVisible", None)
            if isinstance(win_visible, bool) and not win_visible:
                return None
            # pygetwindow may still expose parked coords after minimize.
            left = getattr(win, "left", None)
            top = getattr(win, "top", None)
            width = getattr(win, "width", None)
            height = getattr(win, "height", None)
            if left is not None and top is not None and int(left) <= -30000 and int(top) <= -30000:
                return None
            if width is not None and height is not None:
                if int(width) <= 0 or int(height) <= 0:
                    return None
        if not win32_utils.is_window_visible(hwnd):
            return None

        rect = game_win.win_rect
        if rect is None:
            return None
        # Minimized windows can report parked coordinates such as (-32000, -32000).
        if int(getattr(rect, "x1", 0)) <= -30000 and int(getattr(rect, "y1", 0)) <= -30000:
            return None
        if int(getattr(rect, "width", 0)) <= 0 or int(getattr(rect, "height", 0)) <= 0:
            return None
        return rect

    def _to_qt_rect(self, rect: Rect) -> Rect:
        """
        Convert native/physical window coordinates to Qt logical coordinates.
        This prevents overlay misalignment on high-DPI scaling.
        """
        x = int(getattr(rect, "x1", 0))
        y = int(getattr(rect, "y1", 0))
        w = int(getattr(rect, "width", 0))
        h = int(getattr(rect, "height", 0))

        if w <= 0 or h <= 0:
            return rect

        screen = QGuiApplication.screenAt(QPoint(x, y))
        if screen is None:
            return rect

        # For DPI-unaware processes, Windows may already virtualize coordinates.
        # In that case, dividing by DPR again causes severe offset.
        if not win32_utils.is_process_dpi_aware():
            return rect

        dpr = float(screen.devicePixelRatio() or 1.0)
        if dpr <= 1.01:
            return rect

        return Rect(
            round(x / dpr),
            round(y / dpr),
            round((x + w) / dpr),
            round((y + h) / dpr),
        )

    def _is_game_window_active(self) -> bool:
        if self.ctx.controller is None:
            return False
        game_win = getattr(self.ctx.controller, "game_win", None)
        if game_win is None:
            return False
        return bool(game_win.is_win_active)

    def _install_log_handler(self) -> None:
        if self._log_handler is not None:
            return

        self._log_handler = OverlayLogHandler(self.ctx)
        self._log_handler.setLevel(logging.DEBUG)
        log.addHandler(self._log_handler)
        if yolo_log is not None:
            yolo_log.addHandler(self._log_handler)

    def _uninstall_log_handler(self) -> None:
        if self._log_handler is None:
            return

        try:
            log.removeHandler(self._log_handler)
        except Exception:
            pass

        if yolo_log is not None:
            try:
                yolo_log.removeHandler(self._log_handler)
            except Exception:
                pass

        self._log_handler = None
