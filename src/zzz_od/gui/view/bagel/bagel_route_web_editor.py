"""贝果路线编辑器：顶部是 Python 按钮栏，下面是网页。

网页负责显示底图、出生点、路线与节点草稿，并收集用户操作；Python 负责
路线文件与开启选择的写入、录制、试跑和定位。网页通过 ``bagelBridge.send``
把命令交给 Python，Python 校验并执行后用 ``onResult`` 回复，再用 ``setData``
推送最新数据。默认路线只读、自定义路线的保存与开启互斥都在 Python 侧
（``BagelRouteStore``）再检查一次，不依赖网页隐藏按钮。

页面用 ``setHtml`` 加载并把 baseUrl 指向工作目录，这样页面里的相对路径
能直接读到 ``assets/game_data/map_locator`` 下的底图与清单。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import PySide6.QtWebChannel as QtWebChannel
import PySide6.QtWebEngineCore as QtWebEngineCore
import PySide6.QtWebEngineWidgets as QtWebEngineWidgets
from PySide6 import QtCore
from PySide6.QtCore import QObject, QRect, Qt, QTimer, QUrl, Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    PrimaryPushButton,
    PushButton,
    Theme,
)

from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log
from zzz_od.application.bagel.bagel_route_model import (
    KIND_COLORS,
    POINT_KINDS,
    BagelRoute,
    BagelRoutePoint,
    BagelRouteRef,
    BagelSpawnPoint,
)
from zzz_od.application.bagel.bagel_route_recorder import (
    BagelPointRecorder,
    is_foreground,
)
from zzz_od.application.bagel.bagel_route_store import (
    BagelRouteConfigError,
    BagelRouteStore,
)
from zzz_od.gui.view.bagel.bagel_light_theme import (
    apply_light_palette,
    enter_light_theme,
    restore_theme,
)
from zzz_od.gui.view.bagel.bagel_record_overlay import BagelRecordOverlay
from zzz_od.gui.view.bagel.bagel_run_overlay import BagelRunOverlay

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext

WEB_DIR = Path(__file__).parent / 'web'
"""网页资源目录。"""

OVERLAY_INTERVAL_MS = 150
"""悬浮窗跟随游戏窗口位置与显隐的刷新间隔。"""

UNDO_KEY_LABEL = '退格'
"""删除键在界面上的显示名。"""


class _KeyCap(QLabel):
    """单个按键的键帽样式标签，形状按内容宽度自适应。"""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        """
        Args:
            text: 键名，如 1、退格。
            parent: 父窗口。
        """
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(24)
        self.setStyleSheet(
            'QLabel {'
            ' color: #3b3b3b;'
            ' background: #ffffff;'
            ' border: 1px solid #c8ccd2;'
            ' border-bottom: 2px solid #a8adb5;'
            ' border-radius: 4px;'
            ' padding: 0 7px;'
            ' font-size: 13px;'
            '}'
        )


class _KeyName(QLabel):
    """键帽右侧的类型名，用普通正文色。"""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        """
        Args:
            text: 类型名，如 途径点。
            parent: 父窗口。
        """
        super().__init__(text, parent)
        self.setStyleSheet('QLabel { color: #4a4a4a; font-size: 12px; }')


class _KindDot(QLabel):
    """类型名前面的圆点，颜色与网页画该类型点的颜色一致。"""

    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        """
        Args:
            color: 圆点颜色，取自 KIND_COLORS。
            parent: 父窗口。
        """
        super().__init__('', parent)
        self.setFixedSize(8, 8)
        self.setStyleSheet(
            f'QLabel {{ background: {color}; border-radius: 4px; }}'
        )


class BagelEditorBridge(QObject):
    """网页调用 Python 的唯一入口。

    网页把命令名与 JSON 参数交给 ``send``，这里只转成信号，由编辑器在界面线程里
    校验并执行，避免在网页通道的调用栈里做文件操作。
    """

    command = Signal(str, str)
    """(命令名, JSON 参数)。"""

    @QtCore.Slot(str, str)
    def send(self, cmd: str, payload: str) -> None:
        """网页发来一条命令。

        Args:
            cmd: 命令名，见 ``BagelRouteEditor._on_command``。
            payload: JSON 参数，含 ``request_id``。
        """
        self.command.emit(cmd, payload)


class BagelRouteEditor(QDialog):
    """路线编辑器；写盘、录制、试跑在 Python，显示与编辑草稿在网页。"""

    def __init__(self, ctx: ZContext, parent: QWidget | None = None) -> None:
        """
        Args:
            ctx: 已初始化的上下文，录制复用其截图与定位服务。
            parent: 父窗口。
        """
        super().__init__(parent)
        self.ctx: ZContext = ctx
        self.store: BagelRouteStore = BagelRouteStore()
        self.recorder: BagelPointRecorder | None = None
        self.thread: Any = None
        self.test_thread: Any = None
        self.locate_thread: Any = None
        self._locate_index: int = -1
        """正在定位替换的点序号；-1 表示没有进行中的定位。"""
        self.run_overlay: BagelRunOverlay | None = None
        self._page_ready: bool = False
        self._close_confirmed: bool = False
        """网页已确认没有未保存修改，可以真正关闭。"""
        self._closing: bool = False
        """已请求关闭，正在等录制、试跑、定位线程退出；期间拒绝新命令。"""
        self._shown_layer: str | None = None
        self._layer_origins: dict[str, tuple[int, int]] = _layer_origins()
        self.overlay: BagelRecordOverlay | None = None
        self._overlay_timer: QTimer = QTimer(self)
        self._overlay_timer.setInterval(OVERLAY_INTERVAL_MS)
        self._overlay_timer.timeout.connect(self._sync_overlay)
        self._run_overlay_timer: QTimer = QTimer(self)
        self._run_overlay_timer.setInterval(OVERLAY_INTERVAL_MS)
        self._run_overlay_timer.timeout.connect(self._sync_run_overlay)

        self._previous_theme: Theme = enter_light_theme()
        apply_light_palette(self)
        self.setWindowTitle('贝果路线编辑器')
        self.resize(1360, 820)
        self._build_ui()

    def _build_key_hint(self, bar: QWidget) -> QWidget:
        """把打点键位做成键帽加名字的一行，供顶部栏右侧显示。

        Args:
            bar: 顶部按钮栏，作为控件的父窗口。

        Returns:
            装好全部键位说明的容器。
        """
        holder = QWidget(bar)
        layout = QHBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        # 颜色圆点跟在键帽后面、名字前面，和网页画点用的是同一套颜色。
        items = [(key, kind, label) for key, (kind, label) in POINT_KINDS.items()]
        for index, (key, kind, label) in enumerate(items):
            if index > 0:
                layout.addSpacing(8)
            layout.addWidget(_KeyCap(key, holder))
            layout.addSpacing(2)
            layout.addWidget(
                _KindDot(KIND_COLORS[kind], holder), 0,
                Qt.AlignmentFlag.AlignVCenter,
            )
            layout.addWidget(_KeyName(label, holder))
        layout.addSpacing(8)
        layout.addWidget(_KeyCap(UNDO_KEY_LABEL, holder))
        layout.addWidget(_KeyName('删上一个点', holder))
        return holder

    def _build_ui(self) -> None:
        """顶部按钮栏加网页视图。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        bar = QWidget(self)
        bar.setFixedHeight(52)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(16, 8, 16, 8)
        bar_layout.setSpacing(8)

        self.create_button: PrimaryPushButton = PrimaryPushButton('新增路线', bar)
        self.create_button.clicked.connect(lambda: self._run_js('window.bagelEditor.openCreate();'))
        bar_layout.addWidget(self.create_button)
        self.start_button: PushButton = PushButton('录制路线', bar)
        self.start_button.clicked.connect(lambda: self._run_js('window.bagelEditor.openRecord();'))
        bar_layout.addWidget(self.start_button)
        self.manage_button: PushButton = PushButton('路线管理', bar)
        self.manage_button.clicked.connect(lambda: self._run_js('window.bagelEditor.openManage();'))
        bar_layout.addWidget(self.manage_button)
        self.stop_button: PushButton = PushButton('停止录制', bar)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_recording)
        bar_layout.addWidget(self.stop_button)
        bar_layout.addSpacing(12)
        self.status_label: BodyLabel = BodyLabel('就绪', bar)
        bar_layout.addWidget(self.status_label, 1)
        bar_layout.addWidget(self._build_key_hint(bar))
        layout.addWidget(bar)

        self.view: QtWebEngineWidgets.QWebEngineView = QtWebEngineWidgets.QWebEngineView(self)
        settings = self.view.settings()
        settings.setAttribute(
            QtWebEngineCore.QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True,
        )
        settings.setAttribute(
            QtWebEngineCore.QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False,
        )
        self.view.loadFinished.connect(self._on_page_loaded)
        layout.addWidget(self.view, 1)

        self.bridge: BagelEditorBridge = BagelEditorBridge(self)
        self.bridge.command.connect(self._on_command)
        self.channel: QtWebChannel.QWebChannel = QtWebChannel.QWebChannel(self.view.page())
        self.channel.registerObject('bagelBridge', self.bridge)
        self.view.page().setWebChannel(self.channel)

        self._load_page()

    def _load_page(self) -> None:
        """把页面载入并指定 baseUrl，让页面能读到工作目录下的底图。"""
        html = (WEB_DIR / 'index.html').read_text(encoding='utf-8')
        base = QUrl.fromLocalFile(str(Path(os_utils.get_work_dir())) + '/')
        self.view.setHtml(html, base)

    def _on_page_loaded(self, ok: bool) -> None:
        """页面载入完成后推一次数据。"""
        if not ok:
            self.status_label.setText('页面载入失败')
            return
        self._page_ready = True
        self._push_data()

    def _run_js(self, script: str) -> None:
        """页面没准备好时直接丢弃，避免刷一堆控制台报错。"""
        if self._page_ready:
            self.view.page().runJavaScript(script)

    def _call_js(self, name: str, *args: Any) -> None:
        """调用网页 ``window.bagelEditor`` 上的方法，参数按 JSON 传入。"""
        params = ', '.join(json.dumps(arg, ensure_ascii=False) for arg in args)
        self._run_js(f'window.bagelEditor.{name}({params});')

    def _set_buttons(self) -> None:
        """按录制、试跑状态切换顶栏按钮。"""
        busy = self.recorder is not None or self.test_thread is not None
        for button in (self.create_button, self.start_button, self.manage_button):
            button.setEnabled(not busy)
        self.stop_button.setEnabled(self.recorder is not None)

    # ---------- 数据推送与命令 ----------

    def _push_data(self) -> None:
        """把出生点、路线与开启状态推给网页。

        配置损坏时仍推送出生点和路线供查看，开启状态全部显示为关闭，写入命令会报告错误。
        """
        problems: dict[str, str] = {}
        try:
            catalog = self.store.load_catalog()
            spawns = catalog.spawns
            routes = catalog.routes
            active = {route.ref for route in routes if catalog.is_active(route)}
            for spawn in spawns:
                problem = catalog.selection_problem(spawn.spawn_id)
                if problem is not None:
                    problems[spawn.spawn_id] = problem
            if catalog.errors:
                self.status_label.setText('；'.join(catalog.errors))
        except BagelRouteConfigError as error:
            log.error('读取贝果路线配置失败：%s', error)
            self.status_label.setText(f'路线配置无法使用：{error}')
            try:
                spawns = self.store.load_spawns()
            except BagelRouteConfigError:
                spawns = []
            routes = self.store.load_routes()[0]
            active = set()
        payload = {
            'spawns': [
                dict(spawn.to_json(), problem=problems.get(spawn.spawn_id, '')) for spawn in spawns
            ],
            'routes': [route.to_json(route.ref in active) for route in routes],
        }
        self._call_js('setData', payload)

    def _reply(self, request_id: Any, ok: bool, message: str, data: Any = None) -> None:
        """回复网页的一条命令，并同步到状态栏。"""
        if message:
            self.status_label.setText(message)
        self._call_js('onResult', request_id, ok, message, data)

    def _busy_reason(self) -> str | None:
        """录制、试跑、定位进行中时拒绝会改变数据或占用游戏的命令。"""
        if self._closing:
            return '正在关闭编辑器'
        if self.recorder is not None:
            return '正在录制，请先停止录制'
        if self.test_thread is not None:
            return '正在试跑，请等试跑结束'
        if self.locate_thread is not None:
            return '定位还在进行'
        return None

    def _on_command(self, cmd: str, payload: str) -> None:
        """执行网页发来的命令并回复结果。

        Args:
            cmd: 命令名。
            payload: JSON 参数。
        """
        try:
            args = json.loads(payload)
        except json.JSONDecodeError:
            log.error('贝果路线编辑器收到无法解析的命令 %s', cmd)
            return
        request_id = args.get('request_id')
        if cmd == 'close':
            self._reply(request_id, True, '')
            self._close_confirmed = True
            self.close()
            return
        busy = self._busy_reason()
        if busy is not None:
            self._reply(request_id, False, busy)
            return
        handlers = {
            'save': self._cmd_save,
            'activate': self._cmd_activate,
            'create': self._cmd_create,
            'copy': self._cmd_copy,
            'rename': self._cmd_rename,
            'delete': self._cmd_delete,
            'record': self._cmd_record,
            'test': self._cmd_test,
            'locate': self._cmd_locate,
        }
        handler = handlers.get(cmd)
        if handler is None:
            self._reply(request_id, False, f'不支持的命令：{cmd}')
            return
        try:
            message, data = handler(args)
        except (BagelRouteConfigError, ValueError, KeyError, TypeError) as error:
            log.warning('贝果路线编辑器命令 %s 失败：%s', cmd, error)
            self._push_data()
            self._reply(request_id, False, str(error))
            return
        self._push_data()
        self._reply(request_id, True, message, data)

    def _cmd_save(self, args: dict[str, Any]) -> tuple[str, Any]:
        """保存自定义路线的节点草稿；默认路线由存储模块拒绝。"""
        raw = args['points']
        if not isinstance(raw, list):
            raise ValueError('点位不是数组')
        points = [BagelRoutePoint.from_dict(item) for item in raw]
        route = self.store.save_custom_route(str(args['route_id']), points)
        log.info('贝果路线「%s」已保存 %s 点', route.name, len(points))
        return f'已保存「{route.name}」· {len(points)} 点', None

    def _cmd_activate(self, args: dict[str, Any]) -> tuple[str, Any]:
        """设置出生点当前开启的路线；ref 为 null 表示关闭。"""
        spawn_id = str(args['spawn_id'])
        ref = None if args.get('ref') is None else BagelRouteRef.from_json(args['ref'])
        self.store.set_active_route(spawn_id, ref)
        catalog = self.store.load_catalog()
        spawn = catalog.spawn(spawn_id)
        name = spawn.name if spawn is not None else spawn_id
        if ref is None:
            log.info('贝果出生点 %s 已关闭全部路线', name)
            return f'{name}已关闭路线，抽到时退出重开', None
        route = catalog.route(ref)
        log.info('贝果出生点 %s 开启路线 %s', name, ref)
        return f'{name}已开启「{route.name if route else ref.route_id}」', None

    def _cmd_create(self, args: dict[str, Any]) -> tuple[str, Any]:
        """新增一条自定义路线，首点取出生点坐标。"""
        route = self.store.create_custom_route(
            str(args['name']), str(args['spawn_id']), activate=bool(args.get('activate')),
        )
        log.info('贝果新增自定义路线「%s」（%s）', route.name, route.ref)
        return f'已新增「{route.name}」', route.ref.to_json()

    def _cmd_copy(self, args: dict[str, Any]) -> tuple[str, Any]:
        """复制路线为新的自定义路线，副本关闭。"""
        source = BagelRouteRef.from_json(args['ref'])
        route = self.store.copy_route(source, str(args['name']))
        log.info('贝果路线 %s 已复制为「%s」（%s）', source, route.name, route.ref)
        return f'已复制为「{route.name}」，副本未开启', route.ref.to_json()

    def _cmd_rename(self, args: dict[str, Any]) -> tuple[str, Any]:
        """修改自定义路线的显示名称。"""
        route = self.store.rename_custom_route(str(args['route_id']), str(args['name']))
        log.info('贝果路线 %s 改名为「%s」', route.ref, route.name)
        return f'已改名为「{route.name}」', None

    def _cmd_delete(self, args: dict[str, Any]) -> tuple[str, Any]:
        """删除自定义路线；开启中的先关闭。"""
        route_id = str(args['route_id'])
        self.store.delete_custom_route(route_id)
        log.info('贝果自定义路线 %s 已删除', route_id)
        return '已删除路线', None

    def _cmd_record(self, args: dict[str, Any]) -> tuple[str, Any]:
        """开始录制一条绑定出生点的自定义路线。"""
        name = str(args['name']).strip()
        catalog = self.store.load_catalog()
        spawn = catalog.spawn(str(args['spawn_id']))
        if spawn is None:
            raise ValueError('请选择出生点')
        if not name:
            raise ValueError('路线名称不能为空')
        if any(route.name == name for route in catalog.routes):
            raise ValueError(f'已经有同名路线：{name}')
        self._start_recording(name, spawn, bool(args.get('activate')))
        return f'正在准备录制「{name}」', None

    def _cmd_test(self, args: dict[str, Any]) -> tuple[str, Any]:
        """试跑一条路线；关闭的路线也可以试跑。"""
        ref = BagelRouteRef.from_json(args['ref'])
        route = self.store.load_route(ref)
        self._start_test(route)
        return f'正在切到游戏，准备试跑「{route.name}」', None

    def _cmd_locate(self, args: dict[str, Any]) -> tuple[str, Any]:
        """切到游戏定位一次，结果写进网页草稿。"""
        index = int(args['index'])
        self._start_locate(index)
        return f'正在切到游戏定位第 {index + 1} 点…', None

    # ---------- 定位 ----------

    def _start_locate(self, index: int) -> None:
        """切到游戏定位一次，把结果写到第 index 个点。

        Args:
            index: 要替换坐标的点序号，从 0 开始。
        """
        from zzz_od.gui.view.bagel.bagel_locate_thread import BagelLocateThread

        thread = BagelLocateThread(self.ctx, self)
        self.locate_thread = thread
        self._locate_index = index
        thread.status_changed.connect(self.status_label.setText)
        thread.done.connect(self._on_locate_done)
        thread.finished.connect(self._clear_locate_thread)
        thread.start()

    def _clear_locate_thread(self) -> None:
        """定位线程结束后放开引用。"""
        self.locate_thread = None
        self._close_if_pending()

    def _on_locate_done(
        self, ok: bool, message: str, layer_name: str, global_xy: object,
    ) -> None:
        """把定位结果写进网页草稿；保存后才写入文件。

        Args:
            ok: 是否定位成功。
            message: 结论文案。
            layer_name: 命中的分层名。
            global_xy: 全局坐标；失败时为 None。
        """
        index = self._locate_index
        self._locate_index = -1
        self.status_label.setText(message)
        if not ok or not isinstance(global_xy, tuple):
            return
        self._call_js(
            'setPointPosition', index, layer_name, [round(global_xy[0]), round(global_xy[1])],
        )

    # ---------- 试跑 ----------

    def _start_test(self, route: BagelRoute) -> None:
        """在游戏里试跑一条路线：角色站在绑定出生点附近，按节点顺序走一遍。

        Args:
            route: 要试跑的已保存路线。
        """
        from zzz_od.gui.view.bagel.bagel_route_test_thread import BagelRouteTestThread

        thread = BagelRouteTestThread(self.ctx, route.ref, self)
        self.test_thread = thread
        thread.status_changed.connect(self._on_test_status)
        thread.overlay_state.connect(self._on_run_state)
        thread.done.connect(self._on_test_done)
        thread.finished.connect(self._clear_test_thread)
        self._set_buttons()
        self._call_js('setBusy', {'trial': True})
        thread.start()

    def _on_run_state(self, snapshot: object) -> None:
        """试跑状态同步到执行态悬浮窗；None 表示收起。

        Args:
            snapshot: 执行器状态字典，或 None。
        """
        if snapshot is None:
            # 先停跟随计时器：计时器发现游戏在前台会重新显示悬浮窗。
            self._run_overlay_timer.stop()
            if self.run_overlay is not None:
                self.run_overlay.hide()
            return
        if not isinstance(snapshot, dict):
            return
        if self.run_overlay is None:
            self.run_overlay = BagelRunOverlay()
        if not self._run_overlay_timer.isActive():
            self._run_overlay_timer.start()
        from zzz_od.gui.view.bagel.bagel_route_test_thread import decision_lines

        self.run_overlay.set_lines(decision_lines(snapshot))
        layer = str(snapshot.get('layer') or '')
        layer_image = snapshot.get('layer_image')
        if layer and isinstance(layer_image, Path):
            self.run_overlay.set_layer(layer, layer_image)
        position = snapshot.get('position')
        if isinstance(position, tuple) and len(position) == 2:
            self.run_overlay.set_position(position)
        else:
            self.run_overlay.set_position(None)
        self.run_overlay.set_route(
            list(snapshot.get('points') or []), int(snapshot.get('cursor') or 0),
        )
        self.run_overlay.show()

    def _sync_run_overlay(self) -> None:
        """执行态悬浮窗跟随游戏窗口位置与显隐。"""
        overlay = self.run_overlay
        if overlay is None:
            return
        overlay.set_game_rect(_game_window_rect(self.ctx))

    def _on_test_status(self, text: str) -> None:
        """试跑阶段文案同步到状态栏。"""
        self.status_label.setText(text)

    def _on_test_done(self, success: bool, message: str) -> None:
        """试跑结束显示结论。"""
        self.status_label.setText(message)
        log.info('贝果路线试跑结束：%s', message)

    def _clear_test_thread(self) -> None:
        """线程退出后清引用，允许再次试跑。"""
        if self.test_thread is not None:
            self.test_thread.wait()
        self.test_thread = None
        self._set_buttons()
        self._call_js('setBusy', {'trial': False})
        self._close_if_pending()

    # ---------- 录制 ----------

    def _start_recording(self, name: str, spawn: BagelSpawnPoint, activate: bool) -> None:
        """开始录制；停止后保存为绑定出生点的自定义路线。

        Args:
            name: 路线显示名称。
            spawn: 绑定的出生点。
            activate: 保存后是否开启。
        """
        recorder = BagelPointRecorder(
            self.ctx,
            name,
            spawn,
            activate=activate,
            on_point=self._on_point,
            on_undo=self._on_undo,
            on_status=self._on_status,
            on_layer=self._on_layer,
            on_position=self._on_position,
        )
        self.recorder = recorder
        self._set_buttons()
        self._call_js('startRecording', name)
        self.overlay = BagelRecordOverlay()
        self.overlay.set_lines(['定位中...'])
        self.overlay.set_recording(True)
        self._overlay_timer.start()

        from zzz_od.gui.view.bagel.bagel_record_thread import BagelRecordThread

        self.thread = BagelRecordThread(recorder, self)
        self.thread.point_ready.connect(self._on_point)
        self.thread.undo_happened.connect(self._on_undo)
        self.thread.status_changed.connect(self._on_status)
        self.thread.layer_changed.connect(self._on_layer)
        self.thread.position_changed.connect(self._on_position)
        self.thread.angles_changed.connect(self._on_angles)
        self.thread.stats_changed.connect(self._on_stats)
        self.thread.done.connect(self._on_recording_done)
        self.thread.start()

    def _stop_recording(self) -> None:
        """请求停止，保存由录制线程收尾。"""
        if self.recorder is None:
            return
        self.stop_button.setEnabled(False)
        self.status_label.setText('正在停止并保存…')
        self.recorder.request_stop()

    def _on_point(self, point: BagelRoutePoint) -> None:
        """把一个点推给网页，同时画到悬浮窗上。"""
        self._call_js('addPoint', point.to_dict())
        if self.overlay is not None:
            layer = self._layer_origins.get(point.layer)
            if layer is not None:
                self.overlay.add_point(
                    (point.x - layer[0], point.y - layer[1]), point.kind,
                )

    def _on_undo(self) -> None:
        """删掉上一个点后让网页同步移除，悬浮窗按剩余点重画。"""
        self._call_js('popPoint')
        if self.overlay is not None and self.recorder is not None:
            self.overlay.clear_points()
            for point in self.recorder.route.points:
                layer = self._layer_origins.get(point.layer)
                if layer is not None:
                    self.overlay.add_point(
                        (point.x - layer[0], point.y - layer[1]), point.kind,
                    )

    def _on_status(self, text: str) -> None:
        """线程报告的阶段变化。"""
        self.status_label.setText(text)

    def _on_layer(self, layer_name: str, image_path: Path) -> None:
        """命中层变化：记下层名、让悬浮窗换底图。"""
        self._shown_layer = layer_name
        if self.overlay is not None:
            self.overlay.set_layer(layer_name, image_path)
            self.overlay.clear_points()
            if self.recorder is not None:
                for point in self.recorder.route.points:
                    origin = self._layer_origins.get(point.layer)
                    if origin is not None and point.layer == layer_name:
                        self.overlay.add_point(
                            (point.x - origin[0], point.y - origin[1]), point.kind,
                        )
        log.info('贝果路线录制命中分层 %s（%s）', layer_name, image_path.name)

    def _on_position(self, local_xy: tuple[float, float] | None) -> None:
        """把当前位置推给网页与悬浮窗；层名用最近一次命中层。"""
        if self.overlay is not None:
            self.overlay.set_position(local_xy)
        if local_xy is None:
            self._call_js('setPosition', None, None)
            return
        self._call_js(
            'setPosition', self._shown_layer, [round(local_xy[0], 1), round(local_xy[1], 1)],
        )

    def _on_angles(self, sector: float | None, marker: float | None) -> None:
        """把朝向推给悬浮窗的罗盘。"""
        if self.overlay is not None:
            self.overlay.set_angles(sector, marker)

    def _on_stats(self, stats: dict[str, Any]) -> None:
        """按插件原样拼出悬浮窗的定位详情行。

        Args:
            stats: 录制器每帧汇总的统计，字段见 ``BagelPointRecorder._build_stats``。
        """
        if self.overlay is None:
            return
        center = stats.get('center')
        score = stats.get('score')
        layer = stats.get('layer')
        if center is None or score is None or layer is None:
            self.overlay.set_lines([
                '未找到匹配地图',
                f'定位 {stats.get("locate_ms", 0.0):.1f}ms',
            ])
            return
        sector = self.overlay.sector_angle
        marker = self.overlay.marker_angle
        self.overlay.set_lines([
            f'{layer}  ({center[0]}, {center[1]})',
            f'扇形 {_fmt_angle(sector)}  菱形 {_fmt_angle(marker)}',
            f'匹配分 {score:.3f}  {stats.get("fps", 0.0):.0f} FPS',
            f'单帧最大偏移 {stats.get("step_max", 0.0):.0f}px'
            f'/{stats.get("window_span", 0.0):.2f}s',
            f'延迟 {stats.get("total_ms", 0.0):.0f}ms'
            f'  定位 {stats.get("locate_ms", 0.0):.1f}ms'
            f'  朝向 {stats.get("angle_ms", 0.0):.1f}ms',
        ])

    def _sync_overlay(self) -> None:
        """把悬浮窗贴到游戏窗口上；游戏不在前台就隐藏。"""
        if self.overlay is None:
            return
        self.overlay.set_game_rect(_game_window_rect(self.ctx))

    def _on_recording_done(self, success: bool, message: str) -> None:
        """收尾：撤掉悬浮窗、恢复按钮、刷新数据并选中新路线。"""
        self._overlay_timer.stop()
        if self.overlay is not None:
            self.overlay.hide()
            self.overlay.deleteLater()
            self.overlay = None
        self.status_label.setText(message)
        if self.thread is not None:
            self.thread.wait(3000)
        self.thread = None
        saved = self.recorder.saved_route if self.recorder is not None else None
        self.recorder = None
        self._set_buttons()
        self._push_data()
        self._call_js('stopRecording', saved.ref.to_json() if saved is not None else None)
        if saved is not None:
            log.info('贝果路线录制保存为「%s」（%s），%s 点', saved.name, saved.ref, len(saved.points))
        else:
            log.info('贝果路线录制未保存：%s', message)
        self._close_if_pending()

    def closeEvent(self, event: Any) -> None:
        """关窗前让网页确认未保存的修改；确认后先停后台线程，全部退出后才真正关闭。

        录制、试跑、定位线程都以本窗口为父对象。窗口关闭后会被销毁，
        线程还在运行时一起销毁会让整个程序崩溃，所以要等线程退出再关。
        """
        if self._page_ready and not self._close_confirmed:
            event.ignore()
            self.view.page().runJavaScript(
                'window.bagelEditor.requestClose()', 0, self._on_close_requested,
            )
            return
        if self._stop_background_threads():
            event.ignore()
            return
        self._run_overlay_timer.stop()
        if self.run_overlay is not None:
            self.run_overlay.close()
            self.run_overlay.deleteLater()
            self.run_overlay = None
        restore_theme(self._previous_theme)
        super().closeEvent(event)

    def keyPressEvent(self, event: Any) -> None:
        """Esc 走与关窗相同的流程；对话框默认的 Esc 处理会绕过 closeEvent。"""
        if event.key() == Qt.Key.Key_Escape:
            event.accept()
            self.close()
            return
        super().keyPressEvent(event)

    def _stop_background_threads(self) -> bool:
        """请求停止录制、试跑；定位无法中断，只等它结束。

        Returns:
            仍有线程在运行时返回 True，调用方应推迟关闭。
        """
        running = [
            thread for thread in (self.thread, self.test_thread, self.locate_thread)
            if thread is not None and thread.isRunning()
        ]
        if not running:
            return False
        if not self._closing:
            self._closing = True
            self.status_label.setText('正在停止后台任务，结束后自动关闭编辑器…')
            if self.recorder is not None:
                self.recorder.request_stop()
            if self.test_thread is not None:
                self.test_thread.stop()
        return True

    def _close_if_pending(self) -> None:
        """已请求关闭且后台线程都已退出时，完成关闭。

        放到下一轮事件循环执行：线程的结束信号处理完之后再关窗。
        """
        if self._closing:
            QTimer.singleShot(0, self.close)

    def _on_close_requested(self, result: object) -> None:
        """网页脚本出错没有接手关闭时直接关闭，避免窗口关不掉。"""
        if result is not True:
            log.warning('贝果路线编辑器网页未响应关闭请求，直接关闭')
            self._close_confirmed = True
            self.close()


def _fmt_angle(value: float | None) -> str:
    """朝向角度的显示格式，识别不出时显示 --。

    Args:
        value: 角度值。

    Returns:
        带度数符号的文本。
    """
    return '--' if value is None else f'{value:.0f}°'


def _layer_origins() -> dict[str, tuple[int, int]]:
    """读出各层的画布偏移，用于把全局坐标换算成层内坐标。

    Returns:
        分层名到 origin 的映射；读取失败时返回空映射。
    """
    try:
        from zzz_od.game_data.map_locator.map_locator import load_map_locators

        return {
            locator.name: locator.origin for locator in load_map_locators()
        }
    except (OSError, ValueError) as error:
        log.warning('读取分层偏移失败，悬浮窗不画点：%s', error)
        return {}


def _game_window_rect(ctx: ZContext) -> QRect | None:
    """取游戏窗口矩形；窗口不在前台时返回 None，让悬浮窗隐藏。

    Args:
        ctx: 运行上下文。

    Returns:
        游戏窗口在屏幕上的矩形，不可用时为 None。
    """
    controller = ctx.controller
    if controller is None:
        return None
    game_win = controller.game_win
    hwnd = game_win.get_hwnd()
    if hwnd is None or not is_foreground(hwnd):
        return None
    rect = game_win.win_rect
    if rect is None:
        return None
    return QRect(rect.x1, rect.y1, rect.width, rect.height)
