import platform
import sys


def get_runtime_id() -> str:
    """返回内置源码快照绑定的 Python 运行时标识。"""
    python_version = f'{sys.version_info.major}.{sys.version_info.minor}'
    machine = platform.machine().lower() or 'unknown'
    return f'{sys.implementation.name}-{python_version}-{sys.platform}-{machine}'
