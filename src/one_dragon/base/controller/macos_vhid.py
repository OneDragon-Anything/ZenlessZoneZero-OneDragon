from __future__ import annotations

import selectors
import subprocess
import threading
from pathlib import Path


class MacVirtualHIDMouse:
    """通过 Karabiner 虚拟 HID 发送鼠标输入。"""

    READY_TIMEOUT: float = 10
    RESPONSE_TIMEOUT: float = 10

    def __init__(self) -> None:
        project_dir = Path(__file__).resolve().parents[4]
        client_path = project_dir / '.install' / 'macos-vhid' / 'vhid-click-client'
        if not client_path.is_file():
            raise FileNotFoundError(
                f'找不到虚拟 HID 点击客户端：{client_path}。'
                '请先双击仓库根目录的启动一条龙.command'
            )

        self._process = subprocess.Popen(
            ['/usr/bin/sudo', '-n', str(client_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding='utf-8',
            errors='replace',
        )
        self._lock = threading.Lock()
        try:
            response = self._read_line(self.READY_TIMEOUT)
            if response != 'READY':
                if 'password is required' in response.lower():
                    raise RuntimeError(
                        '启动虚拟 HID 客户端需要管理员授权；'
                        '请通过启动一条龙.command 重新启动并完成一次密码验证'
                    )
                raise RuntimeError(response.removeprefix('ERROR ').strip() or
                                   '虚拟鼠标设备未就绪')
        except Exception:
            self.close()
            raise

    def click(self, press_time: float = 0.1, button: str = 'left') -> None:
        """发送一次鼠标点击。"""
        duration_ms = min(60000, max(1, round(press_time * 1000)))
        self._send_command('click', button, duration_ms)

    def press(self, button: str = 'left') -> None:
        """按住鼠标按键。"""
        self._send_command('press', button, 0)

    def release(self, button: str = 'left') -> None:
        """释放鼠标按键。"""
        self._send_command('release', button, 0)

    def _send_command(self, command: str, button: str, duration_ms: int) -> None:
        button_id = {'left': 1, 'right': 2, 'middle': 3}.get(button)
        if button_id is None:
            raise ValueError(f'不支持的 macOS 虚拟鼠标按键：{button}')

        with self._lock:
            if self._process.poll() is not None:
                raise RuntimeError('虚拟 HID 点击客户端已退出')
            if self._process.stdin is None:
                raise RuntimeError('虚拟 HID 点击客户端输入通道不可用')
            self._process.stdin.write(
                f'{command} {button_id} {duration_ms}\n'
            )
            self._process.stdin.flush()
            timeout = max(self.RESPONSE_TIMEOUT, duration_ms / 1000 + 5)
            response = self._read_line(timeout)
            if response != 'OK':
                raise RuntimeError(response.removeprefix('ERROR ').strip() or
                                   '虚拟 HID 鼠标操作失败')

    def close(self) -> None:
        """释放鼠标按键并关闭客户端进程。"""
        process = getattr(self, '_process', None)
        if process is None:
            return
        with self._lock:
            if process.poll() is not None:
                return

            if process.stdin is not None:
                try:
                    process.stdin.write('quit\n')
                    process.stdin.flush()
                except BrokenPipeError:
                    pass

            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=2)

    def _read_line(self, timeout: float) -> str:
        if self._process.stdout is None:
            raise RuntimeError('虚拟 HID 点击客户端输出通道不可用')

        with selectors.DefaultSelector() as selector:
            selector.register(self._process.stdout, selectors.EVENT_READ)
            if not selector.select(timeout):
                raise TimeoutError('等待虚拟 HID 点击客户端响应超时')
            response = self._process.stdout.readline()

        if not response:
            return_code = self._process.poll()
            raise RuntimeError(
                f'虚拟 HID 点击客户端意外退出，退出码：{return_code}'
            )
        return response.strip()
