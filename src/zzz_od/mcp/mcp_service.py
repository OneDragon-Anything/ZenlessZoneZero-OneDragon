import os
import socket
import threading
import time
import json
import logging
from typing import Any

import anyio
from mcp.server.fastmcp import FastMCP
from one_dragon.base.geometry.point import Point
from one_dragon.utils import cv2_utils
from one_dragon.utils.log_utils import log
from zzz_od.operation.zzz_operation import ZOperation


class _IgnoreMcpClosedResourceErrorFilter(logging.Filter):
    """过滤 MCP 连接关闭时的已知噪声日志。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name != "mcp.server.streamable_http":
            return True
        if "Error in message router" not in record.getMessage():
            return True
        if not record.exc_info or len(record.exc_info) < 2:
            return True
        exc = record.exc_info[1]
        return not isinstance(exc, anyio.ClosedResourceError)


class _McpBridgeOperation(ZOperation):
    """
    MCP工具桥接操作：复用 Operation 层封装（截图/坐标体系）。
    """

    def __init__(self, ctx):
        ZOperation.__init__(self, ctx=ctx, op_name="MCP工具桥接", need_check_game_win=False)

    def capture_screen(self):
        image = self.screenshot()
        return self.last_screenshot_time, image


class GuiMcpService:
    """在 GUI 进程内启动/停止的 MCP 服务。"""

    def __init__(self, ctx):
        self.ctx = ctx
        self.host = os.environ.get("OD_MCP_HOST", "127.0.0.1")
        self._click_trace = os.environ.get("OD_MCP_CLICK_TRACE", "0") in ("1", "true", "True")
        self._port_start = int(os.environ.get("OD_MCP_PORT_START", "9850"))
        self._port_max = int(os.environ.get("OD_MCP_PORT_MAX", "9999"))
        self.port = self._find_available_port()
        self.path = os.environ.get("OD_MCP_PATH", "/mcp")

        self._mcp = FastMCP(
            "ZZZ OneDragon MCP",
            instructions=(
                "Tools for Zenless Zone Zero (ZZZ): watch game screen, click in game, "
                "and start/stop auto battle with optional delayed screenshot return."
            ),
            stateless_http=True,
            json_response=True,
            host=self.host,
            port=self.port,
            streamable_http_path=self.path,
        )
        self._server = None
        self._thread: threading.Thread | None = None
        self._stop_lock = threading.Lock()
        self._auto_battle_loop_thread: threading.Thread | None = None
        self._auto_battle_loop_stop = threading.Event()
        self._auto_battle_loop_lock = threading.Lock()
        self._auto_battle_exec_lock = threading.Lock()
        self._bridge_op = _McpBridgeOperation(ctx)

        self._install_mcp_log_filter()
        self._register_tools()

    def _log_click_trace(self, message: str, **kwargs) -> None:
        if not self._click_trace:
            return
        detail = " ".join([f"{k}={v}" for k, v in kwargs.items()])
        log.info("[MCP_CLICK_TRACE] %s %s", message, detail)

    def _install_mcp_log_filter(self) -> None:
        logger = logging.getLogger("mcp.server.streamable_http")
        for f in logger.filters:
            if isinstance(f, _IgnoreMcpClosedResourceErrorFilter):
                return
        logger.addFilter(_IgnoreMcpClosedResourceErrorFilter())

    def _find_available_port(self) -> int:
        if self._port_max < self._port_start:
            self._port_max = self._port_start

        for port in range(self._port_start, self._port_max + 1):
            if self._is_port_available(port):
                return port

        raise RuntimeError(
            f"未找到可用MCP端口，搜索范围: {self._port_start}-{self._port_max}"
        )

    def _is_port_available(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((self.host, port))
                return True
            except OSError:
                return False

    def _capture_screen(self):
        """
        复用 Operation 层封装截图，返回标准分辨率坐标系下的图像。
        """
        self._require_controller()
        screenshot_time, image = self._bridge_op.capture_screen()
        if image is None:
            raise RuntimeError("截图失败，未获取到图像")
        return screenshot_time, image

    def _capture_image_payload(self):
        screenshot_time, image = self._capture_screen()
        image_base64 = cv2_utils.to_base64(image)
        return screenshot_time, image_base64, image

    def _build_screenshot_payload(
        self,
        timestamp: float,
        width: int,
        height: int,
        image_base64: str,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": True,
            "width": int(width),
            "height": int(height),
            "elapsedMs": 0,
            "imageMime": "image/png",
            "imageBase64": image_base64,
            "response": {
                "ok": True,
                "width": int(width),
                "height": int(height),
                "imageMime": "image/png",
                "elapsedMs": 0,
            },
            "timestamp": float(timestamp),
        }
        if extra:
            payload.update(extra)
        return payload

    def _extract_ocr_result(self, image, max_entries: int = 300) -> dict[str, Any]:
        """
        OCR优先，返回可直接点击的中心坐标（标准分辨率坐标系）。
        """
        ocr_list = self.ctx.ocr_service.get_ocr_result_list(
            image=image,
            crop_first=False,
        )
        entries: list[dict[str, Any]] = []
        for mr in ocr_list:
            text = (mr.data or "").strip()
            if len(text) == 0:
                continue
            entries.append(
                {
                    "text": text,
                    "center_x": int(mr.center.x),
                    "center_y": int(mr.center.y),
                }
            )

        entries.sort(key=lambda i: (i["center_y"], i["center_x"]))
        total = len(entries)
        if max_entries > 0 and len(entries) > max_entries:
            entries = entries[:max_entries]

        return {
            "count": total,
            "returned_count": len(entries),
            "truncated": total > len(entries),
            "entries": entries,
        }

    def _register_tools(self) -> None:
        @self._mcp.tool(
            name="watch_zzz",
            description=(
                "查看绝区零当前画面。"
                "先进行OCR并返回可点击坐标（center_x/center_y），"
                "同时返回截图图片内容。"
            ),
        )
        def watch_zzz(predelay_seconds: float = 1.0) -> dict[str, Any]:
            if predelay_seconds < 0:
                predelay_seconds = 0.0
            time.sleep(predelay_seconds)
            screenshot_time, image_base64, image = self._capture_image_payload()
            ocr = self._extract_ocr_result(image)
            extra = {
                "predelay_seconds": float(predelay_seconds),
                "ocr": ocr,
            }
            return self._build_screenshot_payload(
                timestamp=screenshot_time,
                width=int(image.shape[1]),
                height=int(image.shape[0]),
                image_base64=image_base64,
                extra=extra,
            )

        @self._mcp.tool(
            name="click_zzz",
            description=(
                "点击绝区零画面坐标（标准分辨率坐标系）。"
                "x/y 可直接使用 watch_zzz 返回的 center_x/center_y。"
                "predelay_seconds: 可选，点击前等待时间（秒），默认1秒，一般不需要传。"
            ),
        )
        def click(
            x: int,
            y: int,
            predelay_seconds: float = 1.0,
        ):
            """
            点击游戏窗口中的坐标点（基于标准分辨率坐标系）。
            使用 ALT 键点击以确保光标能正确进入游戏窗口。
            """
            controller = self._require_controller()
            if predelay_seconds < 0:
                predelay_seconds = 0.0

            start = time.time()
            self._log_click_trace(
                "enter",
                x=int(x),
                y=int(y),
                predelay_seconds=float(predelay_seconds),
            )
            time.sleep(predelay_seconds)

            # 普通点击，使用 ALT 键解锁光标
            ok = bool(controller.click(
                pos=Point(x, y),
                pc_alt=True,
            ))

            self._log_click_trace(
                "click_return",
                elapsed=round(time.time() - start, 4),
                ok=ok,
            )
            return {
                "ok": ok,
                "x": int(x),
                "y": int(y),
                "predelay_seconds": float(predelay_seconds),
                "elapsed_seconds": round(time.time() - start, 3),
            }

        @self._mcp.tool(
            name="auto_battle_zzz",
            description=(
                "控制绝区零自动战斗。"
                "action: 必填，传 'start' 启动或 'stop' 停止自动战斗。"
                "wait_seconds: 可选，启动/停止后等待时间（秒），默认0，范围0-180。"
            ),
        )
        def auto_battle_zzz(
            action: str,
            wait_seconds: int = 0,
        ) -> dict[str, Any]:
            """
            启动/停止自动战斗，并可在等待后返回截图。
            使用默认的自动战斗配置。
            """
            self._require_controller()
            action = (action or "").strip().lower()
            if action not in ("start", "stop"):
                raise ValueError("action 仅支持 'start' 或 'stop'")

            # 固定参数
            startup_timeout_seconds = 180
            sub_dir = "auto_battle"

            if wait_seconds < 0:
                wait_seconds = 0
            if wait_seconds > 180:
                wait_seconds = 180

            started = False
            start_elapsed = 0.0
            if action == "start":
                if self._is_auto_battle_running():
                    return {
                        "action": action,
                        "running": True,
                        "wait_seconds": wait_seconds,
                        "started": False,
                        "error": "duplicate start forbidden: auto battle already running",
                    }
                # 使用默认配置
                op_name = self.ctx.battle_assistant_config.auto_battle_config

                # 对齐「自动战斗」页面: 先加载指令，再启动
                try:
                    self.ctx.auto_battle_context.init_auto_op(op_name=op_name, sub_dir=sub_dir)
                    self.ctx.auto_battle_context.auto_ultimate_enabled = (
                        self.ctx.battle_assistant_config.auto_ultimate_enabled
                    )
                except Exception as e:
                    return {
                        "action": action,
                        "running": False,
                        "wait_seconds": wait_seconds,
                        "started": False,
                        "error": f"init_auto_op failed: {e}",
                    }

                self.ctx.auto_battle_context.start_auto_battle()
                # 与 AutoBattleApp 行为一致: 启动后再覆盖一次配置值
                self.ctx.auto_battle_context.auto_ultimate_enabled = (
                    self.ctx.battle_assistant_config.auto_ultimate_enabled
                )
                self._start_auto_battle_loop()

                start = time.time()
                while time.time() - start <= startup_timeout_seconds:
                    auto_op = self.ctx.auto_battle_context.auto_op
                    if auto_op is not None and auto_op.is_running:
                        started = True
                        break
                    time.sleep(0.1)
                start_elapsed = round(time.time() - start, 3)
                if not started:
                    self._stop_auto_battle_loop()
                    self.ctx.auto_battle_context.stop_auto_battle()
            else:
                if not self._is_auto_battle_running():
                    return {
                        "action": action,
                        "running": False,
                        "wait_seconds": wait_seconds,
                        "error": "duplicate stop forbidden: auto battle already stopped",
                    }
                # stop_auto_battle 内部会 stop_context，并释放相关按键
                self._stop_auto_battle_loop()
                self.ctx.auto_battle_context.stop_auto_battle()

            if wait_seconds > 0:
                time.sleep(wait_seconds)

            auto_op = self.ctx.auto_battle_context.auto_op
            running = bool(auto_op is not None and auto_op.is_running)

            result: dict[str, Any] = {
                "action": action,
                "running": running,
                "wait_seconds": wait_seconds,
            }

            if action == "start":
                result["started"] = started
                result["startup_elapsed_seconds"] = start_elapsed
                if not started:
                    result["error"] = "start_auto_battle timeout (180s)"
            return result

    def _require_controller(self):
        if not self.ctx.ready_for_application:
            raise RuntimeError("上下文尚未完成初始化，请稍后重试")
        if self.ctx.controller is None:
            raise RuntimeError("控制器未初始化")
        if not self.ctx.controller.is_game_window_ready:
            raise RuntimeError("游戏窗口未就绪")
        return self.ctx.controller

    def _start_auto_battle_loop(self) -> None:
        with self._auto_battle_loop_lock:
            if self._auto_battle_loop_thread is not None and self._auto_battle_loop_thread.is_alive():
                return
            self._auto_battle_loop_stop.clear()
            self._auto_battle_loop_thread = threading.Thread(
                target=self._run_auto_battle_loop,
                name="zzz_mcp_auto_battle_loop",
                daemon=True,
            )
            self._auto_battle_loop_thread.start()
            log.info("MCP自动战斗识别循环已启动")

    def _stop_auto_battle_loop(self) -> None:
        with self._auto_battle_loop_lock:
            self._auto_battle_loop_stop.set()
            if self._auto_battle_loop_thread is not None:
                self._auto_battle_loop_thread.join(timeout=2)
                self._auto_battle_loop_thread = None
            log.info("MCP自动战斗识别循环已停止")

    def _run_auto_battle_loop(self) -> None:
        while not self._auto_battle_loop_stop.is_set():
            try:
                auto_op = self.ctx.auto_battle_context.auto_op
                if auto_op is None or not auto_op.is_running:
                    time.sleep(0.05)
                    continue

                with self._auto_battle_exec_lock:
                    screenshot_time, image = self._capture_screen()
                    self.ctx.auto_battle_context.check_battle_state(image, screenshot_time)

                interval = float(self.ctx.battle_assistant_config.screenshot_interval)
                if interval < 0.02:
                    interval = 0.02
                time.sleep(interval)
            except Exception:
                log.error("MCP自动战斗识别循环异常", exc_info=True)
                time.sleep(0.1)

    def _is_auto_battle_running(self) -> bool:
        auto_op = self.ctx.auto_battle_context.auto_op
        return bool(auto_op is not None and auto_op.is_running)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        self._thread = threading.Thread(
            target=self._run_server,
            name="zzz_gui_mcp_server",
            daemon=True,
        )
        self._thread.start()
        log.info("MCP服务启动中 http://%s:%d%s", self.host, self.port, self.path)

    def _run_server(self) -> None:
        try:
            import uvicorn

            app = self._mcp.streamable_http_app()
            config = uvicorn.Config(
                app=app,
                host=self.host,
                port=self.port,
                log_level="info",
            )
            self._server = uvicorn.Server(config)
            # 线程内运行时禁用 signal handlers
            self._server.install_signal_handlers = lambda: None  # type: ignore[method-assign]
            self._server.run()
        except Exception:
            log.error("MCP服务运行失败", exc_info=True)
        finally:
            self._server = None
            log.info("MCP服务已停止")

    def stop(self) -> None:
        with self._stop_lock:
            self._stop_auto_battle_loop()
            server = self._server
            if server is not None:
                server.should_exit = True

            if self._thread is not None:
                self._thread.join(timeout=5)
                self._thread = None

    def get_server_url(self) -> str:
        return f"http://{self.host}:{self.port}{self.path}"

    def build_client_config(self) -> dict[str, Any]:
        return {
            "mcpServers": {
                "zzz-onedragon": {
                    "transport": "streamable-http",
                    "url": self.get_server_url(),
                }
            }
        }

    def build_client_config_json(self) -> str:
        return json.dumps(self.build_client_config(), ensure_ascii=False, indent=2)
