import io
import os
import time
from functools import lru_cache
from typing import Optional

import cv2
import win32clipboard
import win32con
from cv2.typing import MatLike
from PIL import Image

from one_dragon.utils import cv2_utils, os_utils
from one_dragon.utils.log_utils import log


@lru_cache
def get_debug_dir_path() -> str:
    return os_utils.get_path_under_work_dir('.debug')


@lru_cache()
def get_debug_image_dir_path() -> str:
    return os_utils.get_path_under_work_dir('.debug', 'images')


def get_debug_image_path(filename, suffix: str = '.png') -> str:
    return os.path.join(get_debug_image_dir_path(), filename + suffix)


def get_debug_image(filename, suffix: str = '.png') -> MatLike:
    return cv2_utils.read_image(get_debug_image_path(filename, suffix))


def copy_image_to_clipboard(image) -> bool:
    """将图片复制到剪贴板"""
    try:
        pil_image = Image.fromarray(image)
        with io.BytesIO() as output:
            pil_image.save(output, "BMP")
            data = output.getvalue()[14:]  # 跳过BMP文件头，获取DIB数据

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_DIB, data)
            log.debug('图片已复制到剪贴板')
            return True
        finally:
            win32clipboard.CloseClipboard()
    except Exception as e:
        log.error('无法将图片复制到剪贴板: %s', e)
        return False


DEBUG_IMAGE_KEEP_COUNT = 300
"""调试图目录保留的最新图片数量，超出的旧图片会被删掉。"""

_PRUNE_INTERVAL_SECONDS = 30.0
"""两次清理之间的最小间隔，避免每存一张都扫目录。"""

_last_prune_time: float = 0.0


def prune_debug_images(keep_count: int = DEBUG_IMAGE_KEEP_COUNT) -> int:
    """只保留最新的若干张调试图。

    运行时间长了调试图会越堆越多（快捷键截图、识别失败截图都往里写）。这里按修改
    时间保留最新的若干张，避免占满磁盘。

    Args:
        keep_count: 保留的图片数量。

    Returns:
        删除的图片数量。
    """
    image_dir = get_debug_image_dir_path()
    if not os.path.isdir(image_dir):
        return 0

    entries: list[tuple[float, str]] = []
    try:
        scan = os.scandir(image_dir)
    except OSError:
        return 0

    with scan:
        for entry in scan:
            try:
                if not entry.is_file():
                    continue
                entries.append((entry.stat().st_mtime, entry.path))
            except OSError:
                continue

    if len(entries) <= keep_count:
        return 0

    entries.sort(key=lambda item: item[0], reverse=True)
    removed = 0
    for _, path in entries[keep_count:]:
        try:
            os.remove(path)
            removed += 1
        except OSError:
            continue

    if removed > 0:
        log.info('清理调试图 %d 张，保留最新 %d 张', removed, keep_count)
    return removed


def _maybe_prune_debug_images() -> None:
    """按时间间隔触发一次调试图清理。"""
    global _last_prune_time
    now = time.time()
    if now - _last_prune_time < _PRUNE_INTERVAL_SECONDS:
        return
    _last_prune_time = now
    prune_debug_images()


def save_debug_image(image, file_name: Optional[str] = None, prefix: str = '', copy_screenshot: bool = False) -> str:
    """保存调试图片到文件，可选择是否同时复制到剪贴板"""
    if file_name is None:
        file_name = '%s_%d' % (prefix, round(time.time() * 1000))
    path = get_debug_image_path(file_name)
    log.debug('临时图片保存 %s', path)

    bgr_image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    cv2.imwrite(path, bgr_image)

    _maybe_prune_debug_images()

    if copy_screenshot:
        copy_image_to_clipboard(image)

    return file_name
