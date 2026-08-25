from __future__ import annotations

import contextlib
import logging
import time

from PySide6.QtCore import QObject, QPoint, QTimer, Signal
from PySide6.QtGui import QGuiApplication

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.context_event_bus import ContextEventItem
from one_dragon.utils.log_utils import log
from one_dragon_qt.overlay.overlay_config import OverlayConfig
from one_dragon_qt.overlay.overlay_events import OverlayEventEnum, OverlayLogEvent
from one_dragon_qt.overlay.overlay_hud_window import OverlayHudWindow
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

    _instance: OverlayManager | None = None

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.config = OverlayConfig()

        self._supported = win32_utils.is_windows_build_supported(19041)
        self._warned_unsupported = False
        self._warned_waiting_game_window = False
        self._started = False
        self._overlay_window: OverlayWindow | None = None
        self._hud_window: OverlayHudWindow | None = None
        self._log_handler: OverlayLogHandler | None = None
        self._ctrl_interaction = False
        self._toggle_combo_pressed = False
        self._toast_until: float = 0
        # 各面板最近一次内容更新的时间戳，驱动 15 秒无更新淡出
        self._panel_last_active: dict[str, float] = {}

        self._signal_bridge = _OverlaySignalBridge()
        self._signal_bridge.log_received.connect(self._on_log_received_signal)

        self._follow_timer = QTimer(self)
        self._follow_timer.timeout.connect(self._safe_follow_window)

        self._input_timer = QTimer(self)
        self._input_timer.timeout.connect(self._safe_poll_input_mode)

        self._state_timer = QTimer(self)
        self._state_timer.timeout.connect(self._safe_refresh_state)

    @classmethod
    def create(cls, ctx, parent=None) -> OverlayManager:
        if cls._instance is None:
            cls._instance = OverlayManager(ctx, parent=parent)
        return cls._instance

    @classmethod
    def instance(cls) -> OverlayManager | None:
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

        if self._hud_window is not None:
            self._hud_window.close()
            self._hud_window = None

        OverlayManager._instance = None

    def reload_config(self) -> None:
        self.config = OverlayConfig()
        self._toggle_combo_pressed = False
        self._apply_timer_intervals()
        self._safe_follow_window()

    def toggle_visibility(self) -> None:
        if not self.config.enabled:
            return
        self.config.visible = not self.config.visible
        self._safe_follow_window()

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

    def _toggle_display_mode(self) -> None:
        """按调试热键（默认 F12）循环切换显示模式：关闭 -> 普通 -> debug。"""
        if not self.config.enabled:
            return
        order = ["off", "normal", "debug"]
        current = self.config.display_mode
        next_mode = order[(order.index(current) + 1) % len(order)]
        self.config.display_mode = next_mode
        toast_text = {"off": "HUD 已关闭", "normal": "HUD 开启", "debug": "HUD 调试"}[next_mode]
        self._toast_until = time.time() + 5.0
        self._safe_follow_window()
        if self._hud_window is not None:
            self._hud_window.set_toast(toast_text)
        log.info(f"Overlay 显示模式切换为 {next_mode}")

    def _on_log_received_signal(self, payload: object) -> None:
        if self._hud_window is None:
            return
        if not isinstance(payload, OverlayLogEvent):
            return
        self._panel_last_active["log_panel"] = time.time()
        import html

        source = f"{payload.filename}:{payload.lineno}"
        level_name = (payload.level_name or "").upper()
        level_color = {
            "DEBUG": "#8cb4ff",
            "INFO": "#6ad192",
            "WARNING": "#ffcb6b",
            "ERROR": "#ff7c7c",
            "CRITICAL": "#ff5f5f",
        }.get(level_name, "#d0d0d0")
        self._hud_window.append_log(
            {
                "created": payload.created,
                "time": time.strftime("%H:%M:%S", time.localtime(payload.created)),
                "level": level_name,
                "levelColor": level_color,
                "source": html.escape(source),
                "message": html.escape(payload.message),
            }
        )
        # 日志面板常驻，只按固定行数裁剪（样式写死，不读配置）
        self._hud_window.trim_log(100)

    def _ensure_overlay_window(self) -> OverlayWindow:
        if self._overlay_window is None:
            self._overlay_window = OverlayWindow()
            self._overlay_window.set_standard_resolution(
                int(self.ctx.project_config.screen_standard_width),
                int(self.ctx.project_config.screen_standard_height),
            )
        return self._overlay_window

    def _ensure_hud_window(self) -> OverlayHudWindow:
        if self._hud_window is None:
            self._hud_window = OverlayHudWindow()
            self._hud_window.ensure_created()
        return self._hud_window

    def _iter_panel_names(self):
        return [
            "log_panel",
            "state_panel",
            "decision_panel",
            "performance_panel",
        ]

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

        if not self._is_game_window_active():
            self._hide_overlay()
            return

        game_qt_rect = self._to_qt_rect(game_rect)

        overlay = self._ensure_overlay_window()
        overlay.update_with_game_rect(game_qt_rect)
        overlay.set_vision_layer_enabled(
            self.config.vision_layer_enabled and self.config.display_mode == "debug"
        )
        overlay.set_vision_transform(
            offset_x=self.config.vision_offset_x,
            offset_y=self.config.vision_offset_y,
            scale_x=self.config.vision_scale_x,
            scale_y=self.config.vision_scale_y,
        )
        overlay.set_anti_capture(self.config.display_mode != "debug")
        overlay.set_overlay_visible(self.config.visible)
        if self.config.visible:
            overlay.set_passthrough(not self._ctrl_interaction)

        hud = self._ensure_hud_window()
        hud.set_geometry(self._qt_rect_to_qrect(game_qt_rect))
        # off 模式下 toast 展示期（5 秒）窗口仍可见，展示结束自动隐藏
        toast_showing = time.time() < self._toast_until
        hud.set_visible(self.config.visible and (self.config.display_mode != "off" or toast_showing))
        if self.config.visible and (self.config.display_mode != "off" or toast_showing):
            hud.set_passthrough(True)
            hud.set_anti_capture(self.config.display_mode != "debug")

        self._sync_hud_panels(game_qt_rect)

    @staticmethod
    def _qt_rect_to_qrect(qt_rect: Rect):
        from PySide6.QtCore import QRect

        return QRect(
            int(getattr(qt_rect, "x1", 0)),
            int(getattr(qt_rect, "y1", 0)),
            int(getattr(qt_rect, "x2", 0)) - int(getattr(qt_rect, "x1", 0)),
            int(getattr(qt_rect, "y2", 0)) - int(getattr(qt_rect, "y1", 0)),
        )

    def _sync_hud_panels(self, game_qt_rect: Rect) -> None:
        mode = self.config.display_mode
        # off：全部隐藏；normal：顶部灵动岛 + 底部战斗状态 + 决策 + 日志；debug：全部显示
        panel_visible_map = {
            "log_panel": mode in ("normal", "debug"),
            "state_panel": mode in ("normal", "debug"),
            "decision_panel": mode in ("normal", "debug"),
            "performance_panel": mode == "debug",
        }

        # 面板位置由 QML anchors 相对 HUD 窗口固定（HUD 整体跟随游戏窗口），这里只同步可见性
        for panel_name in self._iter_panel_names():
            if self._hud_window is None:
                return
            show_panel = self.config.visible and panel_visible_map.get(panel_name, False)
            self._hud_window.set_panel_visible(panel_name, show_panel)

    def _hide_overlay(self) -> None:
        self._ctrl_interaction = False
        self._toggle_combo_pressed = False
        if self._overlay_window is not None:
            self._overlay_window.set_vision_items([])
            self._overlay_window.set_overlay_visible(False)
        if self._hud_window is not None:
            self._hud_window.set_visible(False)

    def _safe_poll_input_mode(self) -> None:
        try:
            self._poll_input_mode()
        except Exception:
            log.error("更新 Overlay 交互模式失败", exc_info=True)

    def _poll_input_mode(self) -> None:
        toggle_key = str(self.ctx.key_debug or "f12").lower()
        toggle_now = win32_utils.is_key_pressed(win32_utils.key_to_vk(toggle_key) or 0)
        if toggle_now and not self._toggle_combo_pressed:
            self._toggle_display_mode()
        self._toggle_combo_pressed = toggle_now

        if self._overlay_window is None or not self._overlay_window.isVisible():
            self._ctrl_interaction = False
            return

        ctrl_now = win32_utils.is_ctrl_pressed()
        if ctrl_now == self._ctrl_interaction:
            return

        self._ctrl_interaction = ctrl_now
        self._overlay_window.set_passthrough(not ctrl_now)

    def _safe_refresh_state(self) -> None:
        try:
            self._refresh_state_panel()
        except Exception:
            log.error("刷新 Overlay 状态面板失败", exc_info=True)

    def _refresh_state_panel(self) -> None:
        if self._overlay_window is None or not self._overlay_window.isVisible():
            return

        self._refresh_debug_panels()

        if self._hud_window is not None:
            self._hud_window.set_status_line(self._build_run_status_line())

        self._sync_panel_fade()

        if self._hud_window is None:
            return
        items = self._collect_auto_battle_items()
        if items:
            self._panel_last_active["state_panel"] = time.time()
        state_rows = self._build_state_rows(items)
        self._hud_window.sync_state_items(state_rows)

    def _sync_panel_fade(self) -> None:
        """按各面板最近内容更新时间驱动淡入淡出：15 秒无更新则淡出。"""
        if self._hud_window is None:
            return
        now = time.time()
        log_active = now - self._panel_last_active.get("log_panel", 0.0) <= 15.0
        self._hud_window.set_panel_fade("log_panel", 1.0 if log_active else 0.0)

        auto_running = self._is_auto_battle_running()
        self._hud_window.set_running(auto_running)
        self._sync_fairy_state()
        for name in ("state_panel", "decision_panel"):
            active = auto_running and now - self._panel_last_active.get(name, 0.0) <= 15.0
            self._hud_window.set_panel_fade(name, 1.0 if active else 0.0)

    def _sync_fairy_state(self) -> None:
        """按运行上下文三态推送 fairy 徽章：running=旋转 / pause=停转 / stop=消失。"""
        if self._hud_window is None:
            return
        try:
            run_ctx = self.ctx.run_context
            if run_ctx.is_context_running:
                state = "running"
            elif run_ctx.is_context_pause:
                state = "pause"
            else:
                state = "stop"
        except Exception:
            state = "stop"
        self._hud_window.set_fairy_state(state)

    def _is_auto_battle_running(self) -> bool:
        try:
            auto_op = self.ctx.auto_battle_context.auto_op
            return auto_op is not None and auto_op.is_running
        except Exception:
            return False

    def _build_state_rows(self, items: list[tuple[str, str, str]]) -> list[dict]:
        """把 (状态名, 秒数, 状态值) 转成 QML stateModel 行：首行黄块大号，其余青色竖条。"""
        rows: list[dict] = []
        for idx, (key, seconds, value) in enumerate(items):
            accent = "#ffd400" if idx == 0 else "#00e5ff"
            rows.append(
                {
                    "big": idx == 0,
                    "accent": accent,
                    "key": key,
                    "value": seconds,
                    "stateValue": value,
                    "valueColor": "#ffffff",
                }
            )
        return rows

    def _refresh_debug_panels(self) -> None:
        bus = getattr(self.ctx, "overlay_debug_bus", None)
        if bus is None:
            return

        snapshot = bus.snapshot()
        if snapshot.decision_items:
            # 以最新一条决策的时间为面板活跃基准
            self._panel_last_active["decision_panel"] = max(
                float(x.created) for x in snapshot.decision_items
            )
        if self._overlay_window is not None:
            self._overlay_window.set_vision_items(self._filter_vision_items(snapshot.vision_items))
        if self._hud_window is not None:
            self._hud_window.set_decision_items(self._build_decision_rows(snapshot.decision_items))
            self._hud_window.set_decision_title(self._build_decision_title(snapshot.decision_items))
            self._hud_window.set_perf_items(
                self._build_perf_rows(snapshot.performance_items)
            )

    def _build_decision_rows(self, items) -> list[dict]:
        import html
        import time

        rows: list[dict] = []
        for item in sorted(items, key=lambda x: x.created, reverse=True)[:24]:
            rows.append(
                {
                    "time": time.strftime("%H:%M:%S", time.localtime(item.created)),
                    "source": html.escape(item.source),
                    "trigger": html.escape(item.trigger),
                    "expr": html.escape(item.expression),
                    "action": html.escape(item.operation),
                    "status": html.escape(item.status),
                }
            )
        return rows

    @staticmethod
    def _build_decision_title(items) -> str:
        """取最新一条决策的正文（expr）作为标题栏文本。"""
        if not items:
            return ""
        latest = max(items, key=lambda x: x.created)
        expr = str(getattr(latest, "expression", "") or "").strip()
        if not expr:
            return ""
        return expr

    def _build_perf_rows(self, items) -> list[dict]:
        import time

        now = time.time()
        metric_keys = self._sorted_perf_metric_keys({item.metric for item in items})

        rows: list[dict] = []
        for key in metric_keys:
            # 取最近 10 秒内的样本，算平均与峰值
            samples = [
                float(item.value)
                for item in items
                if getattr(item, "metric", "") == key
                and now - float(getattr(item, "created", 0.0) or 0.0) <= 10.0
            ]
            if not samples:
                continue
            avg = sum(samples) / len(samples)
            peak = max(samples)
            rows.append(
                {
                    "name": self._perf_metric_display_name(key),
                    "avgText": f"{avg:.0f}",
                    "peakText": f"{peak:.0f}",
                }
            )
        return rows

    @staticmethod
    def _perf_metric_display_name(metric: str) -> str:
        return {
            "ocr_ms": "ocr",
            "yolo_ms": "yolo",
            "cv_pipeline_ms": "cvpipe",
        }.get(metric, metric)

    @staticmethod
    def _sorted_perf_metric_keys(metric_keys) -> list[str]:
        core_order = [
            "ocr_ms",
            "yolo_ms",
            "cv_pipeline_ms",
        ]
        core = [key for key in core_order if key in metric_keys]
        rest = sorted([key for key in metric_keys if key not in core_order])
        return core + rest

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
        filtered_items = self._dedupe_latest_by_label(filtered_items)
        return self._dedupe_yolo_vision_items(filtered_items)

    def _dedupe_latest_by_label(self, items):
        """template/ocr 是离散触发，同一目标多次识别只保留最新一个框。

        items 按时间先后排列（旧在前新在后），从最新开始遍历，
        同 source 同 label 只保留第一个遇到的（最新）。
        """
        kept_items = []
        seen_keys: set[tuple[str, str]] = set()
        for item in reversed(items):
            source = getattr(item, "source", "")
            if source not in ("template", "ocr"):
                kept_items.append(item)
                continue
            key = (source, str(getattr(item, "label", "") or ""))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            kept_items.append(item)
        kept_items.reverse()
        return kept_items

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
            # 外接圆圆心距近似：中心点 x/y 偏差各 ≤ 80px，视为同一目标
            # （不用 sqrt：只比大小，恒等变换下 Chebyshev 与欧氏同序）
            ax1 = float(getattr(item, "x1", 0))
            ay1 = float(getattr(item, "y1", 0))
            ax2 = float(getattr(item, "x2", 0))
            ay2 = float(getattr(item, "y2", 0))
            bx1 = float(getattr(recent_item, "x1", 0))
            by1 = float(getattr(recent_item, "y1", 0))
            bx2 = float(getattr(recent_item, "x2", 0))
            by2 = float(getattr(recent_item, "y2", 0))
            if abs((ax1 + ax2) - (bx1 + bx2)) / 2 > 80:
                continue
            if abs((ay1 + ay2) - (by1 + by2)) / 2 > 80:
                continue
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

    def _collect_auto_battle_items(self) -> list[tuple[str, str]]:
        """只显示游戏里看不到的信息：自定义状态 + 角色专属状态。

        常规信息（前台角色、技能可用、闪避、距离等）游戏 UI 本身可见，
        overlay 不重复显示。
        """
        auto_ctx = self.ctx.auto_battle_context
        auto_op = auto_ctx.auto_op
        if auto_op is None or not auto_op.is_running:
            return []

        try:
            from zzz_od.game_data.agent import AgentEnum
        except Exception:
            agent_prefixes: list[str] = []
        else:
            agent_prefixes = [
                agent_enum.value.agent_name + "-" for agent_enum in AgentEnum
            ]

        items: list[tuple[str, str]] = []
        for state_name in sorted(auto_op.usage_states):
            is_custom = state_name.startswith("自定义-")
            is_agent_state = any(
                state_name.startswith(prefix) for prefix in agent_prefixes
            )
            if not (is_custom or is_agent_state):
                continue
            recorder = auto_ctx.state_record_service.get_state_recorder(state_name)
            if recorder is None or recorder.last_record_time <= 0:
                continue
            # 显示距状态触发已过去的秒数（精确到 0.01）和上次记录的状态值
            seconds_text = f"{time.time() - recorder.last_record_time:.2f}s"
            value_text = str(recorder.last_value) if recorder.last_value is not None else "-"
            items.append((state_name, seconds_text, value_text))
        return items

    def _build_run_status_line(self) -> str:
        """运行状态精简为一行中文，左下角常驻显示。"""
        run_ctx = self.ctx.run_context
        parts = [str(run_ctx.run_status_text or "-")]
        app = getattr(run_ctx, "current_application", None)
        if app is not None:
            app_name = str(getattr(app, "display_name", None) or getattr(app, "op_name", "-"))
            if app_name and app_name != "-":
                parts.append(app_name)
            node = "-"
            with contextlib.suppress(Exception):
                node = str(app.current_node.name or "-")
            if node and node != "-":
                parts.append(node)
        return "｜".join(parts)

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

        with contextlib.suppress(Exception):
            log.removeHandler(self._log_handler)

        if yolo_log is not None:
            with contextlib.suppress(Exception):
                yolo_log.removeHandler(self._log_handler)

        self._log_handler = None
