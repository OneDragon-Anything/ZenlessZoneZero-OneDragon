from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    QRect,
    Qt,
    QUrl,
)
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow

from one_dragon.utils import os_utils
from one_dragon_qt.overlay.utils import win32_utils

# 面板固定尺寸（与 overlay_hud.qml 中面板宽高一致，样式写死不读配置）
_PANEL_SIZE: dict[str, tuple[int, int]] = {
    "log_panel": (460, 300),
    "state_panel": (320, 260),
    "decision_panel": (640, 160),
    "performance_panel": (280, 150),
}

# QML 根属性名映射：面板名 -> visible 属性
_PANEL_VISIBLE_MAP: dict[str, str] = {
    "log_panel": "logVisible",
    "state_panel": "stateVisible",
    "decision_panel": "decisionVisible",
    "performance_panel": "perfVisible",
}

# QML 根属性名映射：面板名 -> 淡入淡出透明度属性
_PANEL_FADE_MAP: dict[str, str] = {
    "log_panel": "logFade",
    "state_panel": "stateFade",
    "decision_panel": "decisionFade",
}


class OverlayListModel(QAbstractListModel):
    """通用 overlay 列表模型，字段名即 QML role 名。

    日志等增量场景用 append_item / drop_expired / trim_to，
    状态等全量场景用 set_items。
    """

    def __init__(self, fields: list[str], parent: QObject | None = None):
        super().__init__(parent)
        self._fields = list(fields)
        self._items: list[dict] = []
        self._role_names: dict[int, QByteArray] = {}
        for i, field in enumerate(self._fields):
            self._role_names[Qt.ItemDataRole.UserRole + i] = QByteArray(field.encode("utf-8"))

    def roleNames(self) -> dict[int, QByteArray]:
        return self._role_names

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        if parent.isValid():
            return 0
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None
        field_index = role - Qt.ItemDataRole.UserRole
        if not (0 <= field_index < len(self._fields)):
            return None
        return self._items[index.row()].get(self._fields[field_index])

    def set_items(self, items: list[dict]) -> None:
        """全量替换数据（state/decision/perf 每 200ms 刷新用）。"""
        self.beginResetModel()
        self._items = list(items)
        self.endResetModel()

    def sync_items(self, items: list[dict], key_field: str = "key") -> None:
        """按 key 增量同步：只增删改变化行，触发 QML add/remove Transition。

        用于状态面板等需要插入/移除动画的全量刷新场景。
        """
        new_rows = list(items)
        old_keys = [row.get(key_field) for row in self._items]

        # 删除已消失的行（从后往前删，避免索引错乱）
        for idx in range(len(old_keys) - 1, -1, -1):
            key = old_keys[idx]
            if key not in {row.get(key_field) for row in new_rows}:
                self.beginRemoveRows(QModelIndex(), idx, idx)
                del self._items[idx]
                self.endRemoveRows()

        # 插入新行、更新变化行（保持新列表顺序）
        target = 0
        while target < len(new_rows):
            key = new_rows[target].get(key_field)
            cur_idx = next(
                (i for i, row in enumerate(self._items) if row.get(key_field) == key),
                None,
            )
            if cur_idx is None:
                self.beginInsertRows(QModelIndex(), target, target)
                self._items.insert(target, new_rows[target])
                self.endInsertRows()
            elif cur_idx != target:
                # 顺序变化：先删除再插入到目标位
                self.beginRemoveRows(QModelIndex(), cur_idx, cur_idx)
                row = self._items.pop(cur_idx)
                self.endRemoveRows()
                self.beginInsertRows(QModelIndex(), target, target)
                self._items.insert(target, row)
                self.endInsertRows()
            elif self._items[cur_idx] != new_rows[target]:
                self._items[cur_idx] = new_rows[target]
                top_left = self.index(target, 0)
                self.dataChanged.emit(
                    top_left, top_left, list(self._role_names.keys())
                )
            target += 1

        # 删除多余的尾部行（理论上不会发生，防御）
        while len(self._items) > len(new_rows):
            last = len(self._items) - 1
            self.beginRemoveRows(QModelIndex(), last, last)
            del self._items[last]
            self.endRemoveRows()

    def append_item(self, item: dict) -> None:
        """尾部追加一行（日志事件驱动用）。"""
        row = len(self._items)
        self.beginInsertRows(QModelIndex(), row, row)
        self._items.append(item)
        self.endInsertRows()

    def drop_expired(self, now: float, ttl_seconds: float) -> None:
        """从队头丢弃超过存活时间的行（日志 12 秒淡出）。"""
        removed = 0
        while removed < len(self._items) and now - float(
            self._items[removed].get("created", 0.0) or 0.0
        ) > ttl_seconds:
            removed += 1
        if removed:
            self.beginRemoveRows(QModelIndex(), 0, removed - 1)
            del self._items[:removed]
            self.endRemoveRows()

    def trim_to(self, max_rows: int) -> None:
        """超过行数上限时从队头裁剪。"""
        excess = len(self._items) - max_rows
        if excess > 0:
            self.beginRemoveRows(QModelIndex(), 0, excess - 1)
            del self._items[:excess]
            self.endRemoveRows()

    def clear(self) -> None:
        self.set_items([])


class OverlayHudWindow:
    """Qt Quick overlay HUD 窗口。

    加载 overlay_hud.qml，把 Python 侧数据经 setContextProperty 注入 QML，
    负责窗口跟随游戏与点击穿透。
    """

    def __init__(self):
        self._engine: QQmlApplicationEngine | None = None
        self._window: QQuickWindow | None = None
        self._models: dict[str, OverlayListModel] = {}
        self._qml_path = Path(__file__).parent / "overlay_hud.qml"

    def ensure_created(self) -> QQuickWindow:
        """创建 QML 引擎与窗口（幂等）。"""
        if self._window is not None:
            return self._window

        self._engine = QQmlApplicationEngine()

        self._models = {
            "logModel": OverlayListModel(
                ["levelColor", "time", "level", "source", "message"]
            ),
            "stateModel": OverlayListModel(
                ["big", "accent", "key", "value", "stateValue", "valueColor"]
            ),
            "decisionModel": OverlayListModel(
                ["time", "source", "trigger", "expr", "action", "status"]
            ),
            "perfModel": OverlayListModel(["name", "avgText", "peakText"]),
        }

        ctx = self._engine.rootContext()
        for name, model in self._models.items():
            ctx.setContextProperty(name, model)
        ctx.setContextProperty(
            "fairyBadgeUrl",
            QUrl.fromLocalFile(
                os_utils.get_resource_path(
                    "assets", "ui", "fairy_badge", "q_badge.svg"
                )
            ),
        )
        ctx.setContextProperty(
            "fairyTriUrl",
            QUrl.fromLocalFile(
                os_utils.get_resource_path(
                    "assets", "ui", "fairy_badge", "triangles.svg"
                )
            ),
        )

        self._engine.load(QUrl.fromLocalFile(str(self._qml_path)))
        roots = self._engine.rootObjects()
        if not roots:
            raise RuntimeError("overlay_hud.qml 加载失败，无 root 对象")
        self._window = roots[0]
        if not isinstance(self._window, QQuickWindow):
            raise RuntimeError(
                f"overlay_hud.qml 根对象类型异常: {type(self._window).__name__}"
            )
        return self._window

    def _set(self, name: str, value) -> None:
        if self._window is not None:
            self._window.setProperty(name, value)

    def set_visible(self, visible: bool) -> None:
        if self._window is None:
            return
        if visible and not self._window.isVisible():
            self._window.show()
            self._window.raise_()
        elif not visible and self._window.isVisible():
            self._window.hide()

    def set_geometry(self, rect: QRect) -> None:
        """整个 HUD 窗口对齐游戏窗口区域。"""
        if self._window is not None:
            self._window.setGeometry(rect)

    def set_status_line(self, text: str) -> None:
        self._set("statusLine", str(text or ""))

    def set_running(self, running: bool) -> None:
        """设置自动战斗运行状态，控制灵动岛流光动画。"""
        self._set("isRunning", bool(running))

    def set_fairy_state(self, state: str) -> None:
        """设置 fairy 徽章状态：running=三角旋转 / pause=停转 / stop=消失。"""
        self._set("fairyState", str(state))

    def set_toast(self, text: str) -> None:
        """显示模式切换提示（中间偏下，iOS 风格，5 秒后自动消失）。"""
        self._set("toastText", str(text or ""))

    def set_panel_visible(self, panel_name: str, visible: bool) -> None:
        """设置单个面板的可见性（位置由 QML anchors 固定）。"""
        prop = _PANEL_VISIBLE_MAP.get(panel_name)
        if prop is None:
            return
        self._set(prop, bool(visible))

    def set_panel_fade(self, panel_name: str, opacity: float) -> None:
        """设置面板淡入淡出透明度（0 隐藏，1 全显，QML 侧动画过渡）。"""
        prop = _PANEL_FADE_MAP.get(panel_name)
        if prop is None:
            return
        self._set(prop, float(opacity))

    def append_log(self, item: dict) -> None:
        self._models["logModel"].append_item(item)

    def drop_expired_log(self, now: float, ttl_seconds: float) -> None:
        self._models["logModel"].drop_expired(now, ttl_seconds)

    def trim_log(self, max_rows: int) -> None:
        self._models["logModel"].trim_to(max_rows)

    def set_state_items(self, items: list[dict]) -> None:
        self._models["stateModel"].set_items(items)

    def sync_state_items(self, items: list[dict]) -> None:
        """增量同步状态行，触发 QML 插入/移除动画。"""
        self._models["stateModel"].sync_items(items, key_field="key")

    def set_state_title(self, text: str) -> None:
        """设置状态面板标题栏文本（当前前台角色名）。"""
        self._set("stateTitle", str(text or ""))

    def set_decision_items(self, items: list[dict]) -> None:
        self._models["decisionModel"].set_items(items)

    def set_decision_title(self, text: str) -> None:
        """设置决策面板黄色标题栏文本（最新一条决策的状态）。"""
        self._set("decisionTitle", str(text or ""))

    def set_perf_items(self, items: list[dict]) -> None:
        self._models["perfModel"].set_items(items)

    def set_passthrough(self, enabled: bool) -> None:
        """win32 点击穿透（复用现有逻辑，与渲染框架无关）。"""
        if self._window is None or not self._window.isVisible():
            return
        hwnd = int(self._window.winId())
        win32_utils.set_window_click_through(hwnd, enabled)

    def set_anti_capture(self, enabled: bool) -> None:
        if self._window is None or not self._window.isVisible():
            return
        hwnd = int(self._window.winId())
        win32_utils.set_window_display_affinity(hwnd, enabled)

    def close(self) -> None:
        if self._window is not None:
            self._window.close()
            self._window = None
        if self._engine is not None:
            self._engine.deleteLater()
            self._engine = None
        self._models.clear()
