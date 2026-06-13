from collections.abc import Callable


def create_git_progress_reporter(
    emit: Callable[[str], None],
    prefix: str = '代码同步进度',
) -> Callable[[float, str], None]:
    """创建 Git 拉取进度的输出回调。"""
    last_transfer_percent: int | None = None
    last_message: str | None = None

    def _report(progress: float, message: str) -> None:
        nonlocal last_transfer_percent, last_message

        percent = max(0, min(100, round(progress * 100)))
        is_transfer_message = message.startswith('拉取对象')

        if is_transfer_message:
            if percent == last_transfer_percent:
                return
            last_transfer_percent = percent
        elif message == last_message:
            return

        last_message = message
        emit(f'{prefix} {percent}% - {message}')

    return _report
