"""开发工具里的 MCP server 管理页。

本页面只管理本机 ``zzz_od.backend.entry.server`` 子进程，不把 MCP server
嵌进 GUI 主进程。运行状态通过 HTTP `/game/status` 轮询，日志通过读取
server 日志文件展示，避免把大段日志返回给 MCP agent 消耗上下文。
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import psutil
from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import (
    FluentIcon,
    PlainTextEdit,
    PrimaryPushButton,
    PushButton,
    SettingCardGroup,
)

from one_dragon.utils import os_utils
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import (
    MultiPushSettingCard,
)
from one_dragon_qt.widgets.setting_card.push_setting_card import PushSettingCard
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.context.zzz_context import ZContext

DEFAULT_MCP_PORT = 23001
# 首次打开页面时只读取日志尾部，避免历史日志过大导致 UI 卡顿。
LOG_TAIL_BYTES = 4096
LOG_TAIL_MAX_LINES = 30
STATUS_POLL_INTERVAL_MS = 5000
LOG_POLL_INTERVAL_MS = 5000
MESSAGE_MAX_BLOCKS = 300
RUNNER_WAIT_TIMEOUT_MS = 5000
NOISY_ACCESS_LOG_PARTS = (
    '"GET /health HTTP/1.1" 200 OK',
    '"GET /game/status HTTP/1.1" 200 OK',
    '"GET /mcp HTTP/1.1" 404 Not Found',
)
NOISY_CONNECTION_RESET_START = 'Exception in callback _ProactorBasePipeTransport._call_connection_lost'
NOISY_CONNECTION_RESET_END = 'ConnectionResetError:'


def _project_root() -> Path:
    """返回当前项目根目录。"""
    return Path(os_utils.get_work_dir())


def _server_url(port: int) -> str:
    """拼接 MCP streamable-http 地址。"""
    return f'http://127.0.0.1:{port}/mcp'


def _health_url(port: int) -> str:
    """拼接 GUI 探测用健康检查地址。"""
    return f'http://127.0.0.1:{port}/health'


def _status_url(port: int) -> str:
    """拼接运行状态查询地址。"""
    return f'http://127.0.0.1:{port}/game/status'


def _server_log_path() -> Path:
    """返回 MCP server 子进程 stdout/stderr 日志路径。"""
    return _project_root() / '.debug' / 'zzz_od_mcp' / 'main_server.log'


def _find_server_process() -> psutil.Process | None:
    """查找当前机器上由本项目入口启动的 MCP server 进程。"""
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and any('zzz_od.backend.entry.server' in arg for arg in cmdline):
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def _server_command(root: Path, port: int) -> list[str]:
    """构造启动命令；项目根目录存在 .env 时才追加 --env-file。"""
    cmd = ['uv', 'run']
    if (root / '.env').is_file():
        cmd.extend(['--env-file', '.env'])
    cmd.extend(['python', '-m', 'zzz_od.backend.entry.server', '--port', str(port)])
    return cmd


def _probe_server(port: int) -> tuple[bool, str]:
    """探测指定端口是否已经是 zzz_od MCP server。"""
    try:
        with urllib.request.urlopen(_health_url(port), timeout=2) as resp:
            body = resp.read().decode('utf-8', errors='ignore')
            if resp.status == 200 and 'zzz_od' in body:
                return True, f'已启动: {_server_url(port)}'
            return False, f'端口 {port} 有响应,但不是 zzz_od MCP 服务'
    except urllib.error.URLError:
        proc = _find_server_process()
        if proc is not None:
            return False, f'发现 MCP server 进程 PID={proc.pid},但 /health 暂不可用'
        return False, f'未启动: {_server_url(port)}'
    except Exception as e:  # noqa: BLE001 GUI 探测兜底
        return False, f'探测失败: {e}'


def _query_run_status(port: int) -> str:
    """读取 server 当前运行状态，格式化成适合 SettingCard 展示的一行文本。"""
    try:
        with urllib.request.urlopen(_status_url(port), timeout=2) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except urllib.error.URLError:
        return '服务未连接'
    except Exception as e:  # noqa: BLE001 GUI 状态兜底
        return f'状态读取失败: {e}'

    state = data.get('state', 'unknown')
    source = data.get('source') or '-'
    app = data.get('app') or '-'
    node = data.get('current_node') or data.get('last_status') or '-'
    duration = data.get('duration_seconds')
    duration_text = f'{duration:.1f}s' if isinstance(duration, int | float) else '-'
    return f'{state}; 来源={source}; 应用={app}; 节点/结果={node}; 耗时={duration_text}'


def _run_status_change_key(run_status: str) -> str:
    """生成用于判断状态是否变化的 key；忽略持续变化的耗时字段。"""
    return run_status.rsplit('; 耗时=', 1)[0]


def _decode_log_bytes(data: bytes) -> str:
    """解码 server 日志字节，兼容 Windows 重定向输出可能使用的 GBK。"""
    if not data:
        return ''
    candidates = [
        data.decode('utf-8', errors='replace'),
        data.decode('gbk', errors='replace'),
    ]
    return min(candidates, key=lambda text: text.count('\ufffd'))


def _is_noisy_access_log(line: str) -> bool:
    """判断是否为 GUI 轮询或 MCP GET 探测产生的无意义访问日志。"""
    return line.startswith('INFO:') and any(part in line for part in NOISY_ACCESS_LOG_PARTS)


def _is_log_record_start(line: str) -> bool:
    """判断一行是否像新的日志记录，用于异常堆栈过滤时恢复状态。"""
    return line.startswith(('DEBUG:', 'INFO:', 'WARNING:', 'ERROR:', 'CRITICAL:'))


def _start_server(port: int) -> str:
    """启动本机 MCP server 子进程，并把 stdout/stderr 写入日志文件。"""
    ok, msg = _probe_server(port)
    if ok:
        return msg

    root = _project_root()
    log_path = _server_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = _server_command(root, port)
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    # GUI 不直接持有 server 对象，只保留子进程日志供页面尾读展示。
    with open(log_path, 'w', encoding='utf-8') as log_file:
        process = subprocess.Popen(
            cmd,
            cwd=str(root),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=flags,
        )
    time.sleep(2)
    if process.poll() is None:
        ok, status = _probe_server(port)
        if ok:
            return f'{status}; PID={process.pid}; 日志: {log_path}'
        return f'进程已启动 PID={process.pid},等待服务就绪; 日志: {log_path}'
    return f'启动失败,返回码 {process.returncode}; 日志: {log_path}'


def _stop_server() -> str:
    """停止已发现的 MCP server 进程及其子进程。"""
    proc = _find_server_process()
    if proc is None:
        return 'MCP server 未运行'
    try:
        children = proc.children(recursive=True)
        for child in children:
            child.terminate()
        proc.terminate()
        _, alive = psutil.wait_procs([proc] + children, timeout=5)
        for item in alive:
            item.kill()
        return f'MCP server 已停止 PID={proc.pid}'
    except psutil.NoSuchProcess:
        return 'MCP server 已停止'
    except Exception as e:  # noqa: BLE001 GUI 操作兜底
        return f'停止失败: {e}'


class McpServiceRunner(QThread):
    """把启动/停止/重启这类慢操作放到后台线程，避免阻塞 Qt UI。"""

    finished = Signal(str, str)

    def __init__(self, action: str, port: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.action: str = action
        self.port: int = port

    def run(self) -> None:
        """执行服务操作，完成后顺带读取一次运行状态。"""
        if self.action == 'probe':
            _, msg = _probe_server(self.port)
        elif self.action == 'start':
            msg = _start_server(self.port)
        elif self.action == 'stop':
            msg = _stop_server()
        elif self.action == 'restart':
            stop_msg = _stop_server()
            start_msg = _start_server(self.port)
            msg = f'{stop_msg}; {start_msg}'
        elif self.action == 'status':
            msg = '状态已刷新'
        else:
            msg = f'未知操作: {self.action}'
        self.finished.emit(msg, _query_run_status(self.port))


class McpServiceInterface(VerticalScrollInterface):
    """开发工具中的 MCP 服务管理页。"""

    def __init__(self, ctx: ZContext, parent: QWidget | None = None) -> None:
        self.ctx: ZContext = ctx
        self._runner: McpServiceRunner | None = None
        self._last_run_status: str = ''
        self._last_run_status_key: str = ''
        # None 表示第一次尾读日志；之后保存文件 offset，只追加新日志。
        self._log_offset: int | None = None
        # Windows 上客户端断开连接偶发 Proactor traceback；这里只用于跳过这段噪音。
        self._skip_noisy_traceback: bool = False
        VerticalScrollInterface.__init__(
            self,
            content_widget=None,
            object_name='mcp_service_interface',
            nav_text_cn='MCP 服务',
            nav_icon=FluentIcon.DEVELOPER_TOOLS,
            parent=parent,
        )
        # 服务状态低频轮询，避免用户启动 MCP 后还要手动刷新当前运行状态。
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(STATUS_POLL_INTERVAL_MS)
        self._status_timer.timeout.connect(self._refresh_live_status)
        # 日志尾读只读新增内容，不走 MCP tool 返回给 agent。
        self._log_timer = QTimer(self)
        self._log_timer.setInterval(LOG_POLL_INTERVAL_MS)
        self._log_timer.timeout.connect(self._poll_server_log)

    def get_content_widget(self) -> QWidget:
        """构造 MCP 服务页内容。"""
        content = Column(spacing=8)
        group = SettingCardGroup('MCP 服务')
        content.add_widget(group)

        self.port_card = TextSettingCard(icon=FluentIcon.GLOBE, title='端口', content='仅监听 127.0.0.1')
        self.port_card.setValue(str(DEFAULT_MCP_PORT), emit_signal=False)
        group.addSettingCard(self.port_card)

        self.status_card = PushSettingCard(icon=FluentIcon.INFO, title='服务状态', content='尚未探测', text='刷新')
        self.status_card.clicked.connect(lambda: self._run_action('probe'))
        group.addSettingCard(self.status_card)

        self.copy_card = PushSettingCard(icon=FluentIcon.COPY, title='MCP 地址', content=_server_url(DEFAULT_MCP_PORT), text='复制')
        self.copy_card.clicked.connect(self._copy_url)
        group.addSettingCard(self.copy_card)

        action_group = SettingCardGroup('服务操作')
        content.add_widget(action_group)

        self.start_btn = PrimaryPushButton(text='启动 F9', icon=FluentIcon.PLAY)
        self.start_btn.setShortcut(QKeySequence('F9'))
        self.start_btn.clicked.connect(lambda: self._run_action('start'))
        self.stop_btn = PushButton(text='停止 F10', icon=FluentIcon.POWER_BUTTON)
        self.stop_btn.setShortcut(QKeySequence('F10'))
        self.stop_btn.clicked.connect(lambda: self._run_action('stop'))
        self.restart_btn = PushButton(text='重启 F11', icon=FluentIcon.SYNC)
        self.restart_btn.setShortcut(QKeySequence('F11'))
        self.restart_btn.clicked.connect(lambda: self._run_action('restart'))
        self.action_card = MultiPushSettingCard(
            icon=FluentIcon.COMMAND_PROMPT,
            title='服务控制',
            content='按当前端口管理本机 zzz_od.backend.entry.server 进程',
            btn_list=[self.start_btn, self.stop_btn, self.restart_btn],
        )
        action_group.addSettingCard(self.action_card)

        status_group = SettingCardGroup('当前运行状态')
        content.add_widget(status_group)
        self.run_status_card = PushSettingCard(icon=FluentIcon.SPEED_HIGH, title='当前运行状态', content='尚未读取', text='刷新')
        self.run_status_card.clicked.connect(lambda: self._run_action('status'))
        status_group.addSettingCard(self.run_status_card)

        log_group = SettingCardGroup('运行消息')
        content.add_widget(log_group)
        self.message_box = PlainTextEdit()
        self.message_box.setReadOnly(True)
        self.message_box.setMaximumBlockCount(MESSAGE_MAX_BLOCKS)
        self.message_box.setMinimumHeight(180)
        self.message_box.setPlaceholderText('MCP 服务操作和运行状态消息会显示在这里')
        log_group.addSettingCard(self.message_box)

        return content

    def on_interface_shown(self) -> None:
        """页面显示时启动状态/日志轮询，并立即探测一次服务。"""
        super().on_interface_shown()
        self._status_timer.start()
        self._log_timer.start()
        self._run_action('probe')

    def on_interface_hidden(self) -> None:
        """页面隐藏时停止轮询，避免后台无意义刷新 UI。"""
        super().on_interface_hidden()
        self._status_timer.stop()
        self._log_timer.stop()
        self._wait_runner_finished()

    def _wait_runner_finished(self) -> None:
        """等待正在执行的服务操作线程退出，避免页面销毁时线程仍在运行。"""
        if self._runner is None or not self._runner.isRunning():
            return
        if not self._runner.wait(RUNNER_WAIT_TIMEOUT_MS):
            self._append_message('MCP 服务操作仍在执行，将在后台继续完成')

    def _port(self) -> int:
        """读取端口输入框；非法输入时回退默认端口。"""
        try:
            return int(self.port_card.getValue())
        except Exception:
            return DEFAULT_MCP_PORT

    def _run_action(self, action: str) -> None:
        """提交服务操作到后台线程。"""
        if self._runner is not None and self._runner.isRunning():
            self._append_message('已有 MCP 服务操作正在执行')
            return
        port = self._port()
        self.status_card.setContent('执行中...')
        self.run_status_card.setContent('读取中...')
        self.copy_card.setContent(_server_url(port))
        self._set_buttons_enabled(False)
        self._append_message(f'开始执行: {self._action_name(action)}')
        self._runner = McpServiceRunner(action, port, self)
        self._runner.finished.connect(self._on_action_finished)
        self._runner.start()

    def _on_action_finished(self, msg: str, run_status: str) -> None:
        """服务操作结束后刷新卡片状态并写入消息框。"""
        self.status_card.setContent(msg)
        self.run_status_card.setContent(run_status)
        self._last_run_status = run_status
        self._last_run_status_key = _run_status_change_key(run_status)
        self._append_message(f'服务消息: {msg}')
        self._append_message(f'当前运行状态: {run_status}')
        self._set_buttons_enabled(True)

    def _copy_url(self) -> None:
        """复制当前端口对应的 MCP 地址。"""
        url = _server_url(self._port())
        QApplication.clipboard().setText(url)
        self.copy_card.setContent(f'已复制: {url}')
        self._append_message(f'已复制 MCP 地址: {url}')

    def _append_message(self, message: str) -> None:
        """向消息框追加带时间戳的 GUI 操作消息。"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.message_box.appendPlainText(f'[{timestamp}] {message}')
        self._scroll_message_to_bottom()

    def _append_log_line(self, line: str) -> None:
        """向消息框追加 server 日志原文。"""
        self.message_box.appendPlainText(line)
        self._scroll_message_to_bottom()

    def _scroll_message_to_bottom(self) -> None:
        """保持消息框滚动到底部，方便观察最新状态。"""
        scrollbar = self.message_box.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _set_buttons_enabled(self, enabled: bool) -> None:
        """统一启停三个服务控制按钮。"""
        self.start_btn.setEnabled(enabled)
        self.stop_btn.setEnabled(enabled)
        self.restart_btn.setEnabled(enabled)

    def _action_name(self, action: str) -> str:
        """把内部动作名转换为用户可读文本。"""
        names = {
            'probe': '探测服务',
            'start': '启动服务',
            'stop': '停止服务',
            'restart': '重启服务',
            'status': '刷新当前运行状态',
        }
        return names.get(action, action)

    def _refresh_live_status(self) -> None:
        """定时刷新运行状态；有服务操作进行中时让后台线程统一回写。"""
        if self._runner is not None and self._runner.isRunning():
            return
        run_status = _query_run_status(self._port())
        self.run_status_card.setContent(run_status)
        run_status_key = _run_status_change_key(run_status)
        if run_status_key != self._last_run_status_key:
            self._last_run_status = run_status
            self._last_run_status_key = run_status_key
            self._append_message(f'当前运行状态: {run_status}')

    def _poll_server_log(self) -> None:
        """尾读 MCP server 日志文件，把新增行追加到消息框。"""
        path = _server_log_path()
        if not path.is_file():
            return
        try:
            size = path.stat().st_size
            if self._log_offset is None:
                # 首次读取只从文件尾部开始，防止打开页面时灌入大量历史日志。
                self._log_offset = max(0, size - LOG_TAIL_BYTES)
            elif size < self._log_offset:
                # 日志被重新创建或截断时，从头开始读新文件。
                self._log_offset = 0
            if size == self._log_offset:
                return
            with open(path, 'rb') as log_file:
                log_file.seek(self._log_offset)
                text = _decode_log_bytes(log_file.read())
                self._log_offset = log_file.tell()
        except OSError as e:
            self._append_message(f'读取 MCP 日志失败: {e}')
            return
        lines = self._filter_server_log_lines([line for line in text.splitlines() if line.strip()])
        if not lines:
            return
        # 单次最多追加固定行数，避免服务短时间刷屏导致 UI 卡顿。
        for line in lines[-LOG_TAIL_MAX_LINES:]:
            self._append_log_line(line)

    def _filter_server_log_lines(self, lines: list[str]) -> list[str]:
        """过滤 GUI 自身轮询和 Windows 连接重置产生的日志噪音。"""
        filtered: list[str] = []
        for line in lines:
            if self._skip_noisy_traceback:
                if NOISY_CONNECTION_RESET_END in line:
                    self._skip_noisy_traceback = False
                    continue
                if _is_log_record_start(line):
                    self._skip_noisy_traceback = False
                else:
                    continue

            if _is_noisy_access_log(line):
                continue
            if line.startswith(NOISY_CONNECTION_RESET_START):
                self._skip_noisy_traceback = True
                continue
            filtered.append(line)
        return filtered
