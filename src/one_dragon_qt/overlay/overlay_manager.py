from __future__ import annotations

import logging
import time
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

from one_dragon.base.operation.context_event_bus import ContextEventItem
from one_dragon.utils.log_utils import log
from one_dragon_qt.overlay.overlay_config import OverlayConfig
from one_dragon_qt.overlay.overlay_events import OverlayEventEnum, OverlayLogEvent
from one_dragon_qt.overlay.overlay_log_handler import OverlayLogHandler
from one_dragon_qt.overlay.overlay_window import OverlayWindow
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
        self._log_handler: Optional[OverlayLogHandler] = None
        self._ctrl_interaction = False
        self._toggle_combo_pressed = False
        self._last_toggle_hotkey_time = 0.0

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

        OverlayManager._instance = None

    def reload_config(self) -> None:
        self.config = OverlayConfig()
        self._toggle_combo_pressed = False
        self._apply_timer_intervals()
        if self._overlay_window is not None:
            self._overlay_window.apply_panel_geometry(
                "log_panel", self._panel_geometry_with_fallback("log_panel")
            )
            self._overlay_window.apply_panel_geometry(
                "state_panel", self._panel_geometry_with_fallback("state_panel")
            )
            self._overlay_window.apply_panel_geometry(
                "decision_panel", self._panel_geometry_with_fallback("decision_panel")
            )
            self._overlay_window.apply_panel_geometry(
                "timeline_panel", self._panel_geometry_with_fallback("timeline_panel")
            )
            self._overlay_window.apply_panel_geometry(
                "performance_panel", self._panel_geometry_with_fallback("performance_panel")
            )
        self._safe_follow_window()

    def toggle_visibility(self) -> None:
        if not self.config.enabled:
            return
        self.config.visible = not self.config.visible
        self._safe_follow_window()

    def reset_panel_geometry(self) -> None:
        self.config.reset_panel_geometry()
        if self._overlay_window is None:
            return
        self._overlay_window.apply_panel_geometry(
            "log_panel", self._panel_geometry_with_fallback("log_panel")
        )
        self._overlay_window.apply_panel_geometry(
            "state_panel", self._panel_geometry_with_fallback("state_panel")
        )
        self._overlay_window.apply_panel_geometry(
            "decision_panel", self._panel_geometry_with_fallback("decision_panel")
        )
        self._overlay_window.apply_panel_geometry(
            "timeline_panel", self._panel_geometry_with_fallback("timeline_panel")
        )
        self._overlay_window.apply_panel_geometry(
            "performance_panel", self._panel_geometry_with_fallback("performance_panel")
        )

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
        if self._overlay_window is None:
            return
        if not isinstance(payload, OverlayLogEvent):
            return
        if not self.config.log_panel_enabled:
            return
        self._overlay_window.log_panel.append_log(payload)

    def _ensure_overlay_window(self) -> OverlayWindow:
        if self._overlay_window is None:
            self._overlay_window = OverlayWindow()
            self._overlay_window.set_standard_resolution(
                int(self.ctx.project_config.screen_standard_width),
                int(self.ctx.project_config.screen_standard_height),
            )
            self._overlay_window.panel_geometry_changed.connect(self._on_panel_geometry_changed)
            self._overlay_window.apply_panel_geometry(
                "log_panel", self._panel_geometry_with_fallback("log_panel")
            )
            self._overlay_window.apply_panel_geometry(
                "state_panel", self._panel_geometry_with_fallback("state_panel")
            )
            self._overlay_window.apply_panel_geometry(
                "decision_panel", self._panel_geometry_with_fallback("decision_panel")
            )
            self._overlay_window.apply_panel_geometry(
                "timeline_panel", self._panel_geometry_with_fallback("timeline_panel")
            )
            self._overlay_window.apply_panel_geometry(
                "performance_panel", self._panel_geometry_with_fallback("performance_panel")
            )
        return self._overlay_window

    def _panel_geometry_with_fallback(self, panel_name: str) -> dict[str, int]:
        geometry = self.config.get_panel_geometry(panel_name)
        if not (
            geometry.get("x", 0) == 0
            and geometry.get("y", 0) == 0
            and geometry.get("w", 320) == 320
            and geometry.get("h", 200) == 200
        ):
            return geometry

        defaults = {
            "decision_panel": {"x": 620, "y": 20, "w": 620, "h": 220},
            "timeline_panel": {"x": 620, "y": 260, "w": 620, "h": 220},
            "performance_panel": {"x": 620, "y": 500, "w": 420, "h": 180},
        }
        return defaults.get(panel_name, geometry)

    def _on_panel_geometry_changed(self, panel_name: str, geometry: dict[str, int]) -> None:
        try:
            self.config.set_panel_geometry(panel_name, geometry)
        except Exception:
            log.error("保存 Overlay 面板位置失败", exc_info=True)

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

        overlay = self._ensure_overlay_window()
        overlay.update_with_game_rect(game_rect)
        overlay.log_panel.set_limits(self.config.log_max_lines, self.config.log_fade_seconds)
        overlay.set_log_panel_enabled(self.config.log_panel_enabled)
        overlay.set_state_panel_enabled(self.config.state_panel_enabled)
        overlay.set_decision_panel_enabled(self.config.decision_panel_enabled)
        overlay.set_timeline_panel_enabled(self.config.timeline_panel_enabled)
        overlay.set_performance_panel_enabled(self.config.performance_panel_enabled)
        overlay.set_vision_layer_enabled(self.config.vision_layer_enabled)
        overlay.set_performance_metric_enabled_map(self.config.performance_metric_enabled_map)
        overlay.set_panel_appearance(
            self.config.font_size, self.config.text_opacity, self.config.panel_opacity
        )
        overlay.set_anti_capture(self.config.anti_capture)
        overlay.set_overlay_visible(self.config.visible)
        if self.config.visible:
            overlay.set_passthrough(not self._ctrl_interaction)

    def _hide_overlay(self) -> None:
        self._ctrl_interaction = False
        self._toggle_combo_pressed = False
        if self._overlay_window is not None:
            self._overlay_window.set_vision_items([])
            self._overlay_window.set_overlay_visible(False)

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

        if not self.config.state_panel_enabled:
            return
        items = self._collect_state_items()
        self._overlay_window.state_panel.update_snapshot(items)

    def _refresh_debug_panels(self) -> None:
        bus = getattr(self.ctx, "overlay_debug_bus", None)
        if bus is None:
            return

        snapshot = bus.snapshot()
        self._overlay_window.set_vision_items(self._filter_vision_items(snapshot.vision_items))
        self._overlay_window.set_decision_items(snapshot.decision_items)
        self._overlay_window.set_timeline_items(snapshot.timeline_items)
        self._overlay_window.set_performance_items(snapshot.performance_items)

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
        return [
            item
            for item in items
            if source_enabled.get(getattr(item, "source", ""), True)
        ]

    def _collect_state_items(self) -> list[tuple[str, str]]:
        run_ctx = self.ctx.run_context
        items: list[tuple[str, str]] = [
            ("RunState", str(run_ctx._run_state.value)),
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
        if not game_win.is_win_valid:
            return None
        hwnd = game_win.get_hwnd() if hasattr(game_win, "get_hwnd") else None
        if win32_utils.is_window_minimized(hwnd):
            return None

        rect = game_win.win_rect
        if rect is None:
            return None
        if int(getattr(rect, "width", 0)) <= 0 or int(getattr(rect, "height", 0)) <= 0:
            return None
        return rect

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
