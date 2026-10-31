"""录制线程：把打点录制器放到后台线程，并把回调转成 Qt 信号。

录制核心在 ``bagel_route_recorder``，这里只做线程包装；界面层用它把
打点、撤销、定位位置与朝向的变化接到界面上。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal

from one_dragon.utils.log_utils import log

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

    from PySide6.QtWidgets import QWidget

    from zzz_od.application.bagel.bagel_route_model import BagelRoutePoint
    from zzz_od.application.bagel.bagel_route_recorder import BagelPointRecorder


class BagelRecordThread(QThread):
    """把录制器的回调转成 Qt 信号。"""

    point_ready = Signal(object)
    undo_happened = Signal()
    status_changed = Signal(str)
    layer_changed = Signal(str, object)
    position_changed = Signal(object)
    angles_changed = Signal(object, object)
    stats_changed = Signal(object)
    done = Signal(bool, str)
    """(是否成功, 结论文案)。"""

    def __init__(self, recorder: BagelPointRecorder, parent: QWidget | None = None) -> None:
        """
        Args:
            recorder: 已配置好的打点录制器。
            parent: Qt 父对象。
        """
        super().__init__(parent)
        self.recorder: BagelPointRecorder = recorder
        recorder.on_point = self._on_point
        recorder.on_undo = self._on_undo
        recorder.on_status = self._on_status
        recorder.on_layer = self._on_layer
        recorder.on_position = self._on_position
        recorder.on_angles = self._on_angles
        recorder.on_stats = self._on_stats

    def run(self) -> None:
        """执行录制并汇总结论。"""
        try:
            self.recorder.run()
        except Exception as error:
            log.error('贝果路线录制线程异常', exc_info=True)
            self.recorder.failure = f'录制异常：{error}'
        if self.recorder.failure is not None:
            self.done.emit(False, self.recorder.failure)
            return
        route = self.recorder.saved_route
        if route is None:
            self.done.emit(False, '未生成路线文件')
            return
        self.done.emit(
            True,
            f'{self.recorder.stop_reason}，已保存为「{route.name}」，{len(route.points)} 点',
        )

    def stop(self) -> None:
        """请求停止录制。"""
        self.recorder.request_stop()

    def _on_point(self, point: BagelRoutePoint) -> None:
        self.point_ready.emit(point)

    def _on_undo(self) -> None:
        self.undo_happened.emit()

    def _on_status(self, text: str) -> None:
        self.status_changed.emit(text)

    def _on_layer(self, layer_name: str, image_path: Path) -> None:
        self.layer_changed.emit(layer_name, image_path)

    def _on_position(self, local_xy: tuple[float, float] | None) -> None:
        self.position_changed.emit(local_xy)

    def _on_angles(self, sector: float | None, marker: float | None) -> None:
        self.angles_changed.emit(sector, marker)

    def _on_stats(self, stats: dict[str, Any]) -> None:
        self.stats_changed.emit(stats)
