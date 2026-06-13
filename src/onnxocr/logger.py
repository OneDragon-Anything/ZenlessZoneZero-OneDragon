"""OnnxOCR 统一日志模块，基于 OneDragon logger。

用法:
    from onnxocr.logger import get_logger
    log = get_logger("predict_det")
    log.info("检测模型加载完成")
"""

from typing import Any

from one_dragon.utils.log_utils import log as od_log


class _LoggerShim:
    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    def _format(self, msg: str) -> str:
        return f"[{self.name}] {msg}"

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if args or kwargs:
            msg = str(msg).format(*args, **kwargs)
        od_log.info(self._format(msg))

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if args or kwargs:
            msg = str(msg).format(*args, **kwargs)
        od_log.debug(self._format(msg))

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if args or kwargs:
            msg = str(msg).format(*args, **kwargs)
        od_log.warning(self._format(msg))

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if args or kwargs:
            msg = str(msg).format(*args, **kwargs)
        od_log.error(self._format(msg))


def get_logger(name: str = "OnnxOCR") -> _LoggerShim:
    """获取带模块标识的 logger。"""
    return _LoggerShim(name)


def add_file_sink(path: str, level: str = "DEBUG", rotation: str = "10 MB") -> None:
    raise NotImplementedError("add_file_sink is not implemented")
