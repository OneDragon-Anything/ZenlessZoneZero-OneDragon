import os
from pathlib import Path
from typing import Literal

from one_dragon.utils import os_utils

SourceMode = Literal['external', 'recovery']
_SOURCE_ROOT_ENV = 'ONE_DRAGON_SOURCE_ROOT'
_SOURCE_MODE_ENV = 'ONE_DRAGON_RUNTIME_MODE'


def get_source_root() -> Path:
    """返回当前进程唯一启用的业务源码根目录。"""
    configured = os.environ.get(_SOURCE_ROOT_ENV, '').strip()
    if configured:
        return Path(configured).resolve()
    return (Path(os_utils.get_work_dir()) / 'src').resolve()


def get_source_mode() -> SourceMode:
    """返回当前进程使用外部源码还是内置恢复源码。"""
    mode = os.environ.get(_SOURCE_MODE_ENV, 'external')
    return 'recovery' if mode == 'recovery' else 'external'


def is_recovery_mode() -> bool:
    """当前进程是否处于内置源码恢复模式。"""
    return get_source_mode() == 'recovery'
