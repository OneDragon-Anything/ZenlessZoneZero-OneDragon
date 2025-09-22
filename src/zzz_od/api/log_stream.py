from __future__ import annotations

"""WebSocket 日志流支持。

设计:
1. WSLogHandler 捕获 Root Logger 及子 logger 的记录, 异步入队.
2. 后台协程 _broadcast_worker 从队列读取, 向 channel 'logs' 广播 JSON:
   {"type":"log","data":{ level, message, time, logger }}
3. 在 FastAPI lifespan 启动/关闭时 start / stop.

注意:
 - 队列满时丢弃最旧/或直接丢弃当前, 这里选择 try_put (丢弃当前并统计 dropped)。
 - 仅发送 INFO 及以上级别; 可按需调整。
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .ws import manager  # 复用现有连接管理

_queue: asyncio.Queue[Dict[str, Any]] | None = None
_worker_task: asyncio.Task | None = None
_handler: logging.Handler | None = None
_dropped: int = 0  # 统计丢弃数量


class WSLogHandler(logging.Handler):
    def __init__(self, level: int = logging.INFO, queue_size: int = 256) -> None:
        super().__init__(level=level)
        self.queue_size = queue_size

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        global _dropped
        if _queue is None:
            return

        # 只保留OneDragon相关的业务日志
        # 允许的logger名称前缀
        allowed_prefixes = ['OneDragon', 'zzz_od', 'one_dragon']

        # 检查是否是允许的logger
        is_allowed = any(record.name.startswith(prefix) for prefix in allowed_prefixes)
        if not is_allowed:
            # 如果不是OneDragon相关的logger，直接跳过
            return

        # 过滤掉监控系统和底层框架的日志
        excluded_names = [
            'unified_api_monitor',
            'unified_event_bridge',
            'websockets',
            'websockets.server',
            'numba',
            'byteflow',
            'interpreter',
            'auto_battle_target_context',
            'auto_battle_dodge_context'
        ]

        for excluded in excluded_names:
            if excluded in record.name.lower():
                return

        # 过滤掉特定的消息内容
        message = record.getMessage()
        excluded_messages = [
            'WebSocket事件',
            'WebSocket广播',
            'bytecode dump',
            'LOAD_FAST',
            'LOAD_CONST',
            'stack:',
            'block_infos',
            'deque('
        ]

        for excluded in excluded_messages:
            if excluded in message:
                return

        # GUI 的 LogDisplayCard 期待已经带方括号的完整行, 再进行着色处理
        try:
            formatted_line = self.format(record)  # 与普通控制台 handler 一致的完整行
        except Exception:  # pragma: no cover - 防御
            return
        payload = {
            # 原始完整文本 (含时间/文件/级别)；前端直接显示后再局部上色
            "line": formatted_line,
            # 结构化字段，方便前端条件格式化
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "time": datetime.now(timezone.utc).isoformat(),
        }
        if _queue.full():
            _dropped += 1
            return
        try:
            _queue.put_nowait(payload)
        except Exception:  # pragma: no cover
            _dropped += 1


async def _broadcast_worker() -> None:
    """后台协程: 从队列取出日志并广播."""
    assert _queue is not None

    while True:
        item = await _queue.get()
        try:
            await manager.broadcast_json("logs", {"type": "log", "data": item})
        except Exception:
            # 忽略广播异常
            pass




def start_log_stream(queue_size: int = 256, level: int = logging.DEBUG) -> None:
    """初始化日志流: 安装 Handler 并启动广播任务 (幂等)."""
    global _queue, _worker_task, _handler
    if _handler is not None:
        return  # 已启动
    loop = asyncio.get_running_loop()
    _queue = asyncio.Queue(maxsize=queue_size)
    _handler = WSLogHandler(level=logging.DEBUG, queue_size=queue_size)
    # 采用简单格式, 去除多余前缀, 前端可自行再格式化
    # 采用较通用的格式, 尽量贴近 GUI 原生格式
    # GUI 主 logger 格式: [%(asctime)s.%(msecs)03d] [%(filename)s %(lineno)d] [%(levelname)s]: %(message)s
    # 为减少差异, 这里复刻 (包含毫秒)
    _handler.setFormatter(logging.Formatter('[%(asctime)s.%(msecs)03d] [%(filename)s %(lineno)d] [%(levelname)s]: %(message)s', '%H:%M:%S'))
    # 添加到根logger
    logging.getLogger().addHandler(_handler)

    # 重要：确保OneDragon logger已经被初始化（触发log_utils.get_logger）
    # 这会清除handlers，所以需要在之后重新添加
    try:
        # 尝试导入以触发logger初始化
        from one_dragon.utils.log_utils import log as onedragon_log_instance
        # 现在OneDragon logger已经被初始化，重新添加我们的handler
        onedragon_logger = logging.getLogger('OneDragon')
        # 检查是否已经有WSLogHandler，避免重复添加
        has_ws_handler = any(isinstance(h, WSLogHandler) for h in onedragon_logger.handlers)
        if not has_ws_handler:
            onedragon_logger.addHandler(_handler)

        # 不改变OneDragon logger的级别，保持其原有配置

        # 同时为所有OneDragon子logger添加handler，但不改变级别
        for logger_name in ['OneDragon.onnx_ocr_matcher', 'OneDragon-YOLO']:
            sub_logger = logging.getLogger(logger_name)
            if not any(isinstance(h, WSLogHandler) for h in sub_logger.handlers):
                sub_logger.addHandler(_handler)

    except Exception as e:
        # 如果导入失败，至少添加到已知的logger
        logging.getLogger('OneDragon').addHandler(_handler)
        logging.getLogger('OneDragon-YOLO').addHandler(_handler)
        logging.getLogger('OneDragon.onnx_ocr_matcher').addHandler(_handler)

    # 可选: 也确保根 logger 级别不高于我们需要
    root = logging.getLogger()
    if root.level > level:
        root.setLevel(level)
    _worker_task = loop.create_task(_broadcast_worker(), name="ws-log-broadcast")


async def stop_log_stream() -> None:
    """停止日志流(移除 handler 并取消任务)."""
    global _queue, _worker_task, _handler
    if _handler is not None:
        try:
            # 从根logger移除handler
            logging.getLogger().removeHandler(_handler)
            # 从OneDragon业务logger移除handler
            logging.getLogger('OneDragon').removeHandler(_handler)
            logging.getLogger('OneDragon-YOLO').removeHandler(_handler)
        except Exception:
            pass
    _handler = None
    if _worker_task is not None:
        _worker_task.cancel()
        try:
            await _worker_task
        except Exception:  # pragma: no cover
            pass
    _worker_task = None
    _queue = None


def ensure_handler_attached() -> None:
    """确保WSLogHandler已附加到OneDragon logger"""
    global _handler
    if _handler is None:
        return

    try:
        onedragon_logger = logging.getLogger('OneDragon')
        # 检查是否有我们的特定handler实例（而不是类型）
        if _handler not in onedragon_logger.handlers:
            onedragon_logger.addHandler(_handler)

        # 同时检查YOLO logger
        yolo_logger = logging.getLogger('OneDragon-YOLO')
        if _handler not in yolo_logger.handlers:
            yolo_logger.addHandler(_handler)
    except Exception:
        pass


def get_dropped_count() -> int:
    return _dropped
