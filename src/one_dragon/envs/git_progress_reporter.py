import re
import time
from collections.abc import Callable

_TRANSFER_PROGRESS_PATTERN = re.compile(r'^拉取对象\s+(\d+)/(\d+)$')


def create_git_progress_reporter(
    emit: Callable[[str], None],
    transfer_log_interval_seconds: float = 1.0,
    time_source: Callable[[], float] = time.monotonic,
) -> Callable[[float, str], None]:
    """创建 Git 拉取进度的输出回调。"""
    last_transfer_log_at: float | None = None

    def _report(progress: float, message: str) -> None:
        nonlocal last_transfer_log_at

        del progress

        transfer_message = _format_transfer_message(message)
        if transfer_message is None:
            emit(message)
            return

        now = time_source()
        is_complete = transfer_message.endswith('(100%)')
        if (
            last_transfer_log_at is not None
            and now - last_transfer_log_at < transfer_log_interval_seconds
            and not is_complete
        ):
            return

        last_transfer_log_at = now
        emit(transfer_message)

    return _report


def _format_transfer_message(message: str) -> str | None:
    match = _TRANSFER_PROGRESS_PATTERN.match(message)
    if match is None:
        return None

    received_objects = int(match.group(1))
    total_objects = int(match.group(2))
    if total_objects <= 0:
        return message

    percent = max(0, min(100, round(received_objects / total_objects * 100)))
    return f'拉取对象 {received_objects}/{total_objects} ({percent}%)'
