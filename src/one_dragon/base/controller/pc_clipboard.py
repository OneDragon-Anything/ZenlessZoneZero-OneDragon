import sys
import time
from contextlib import suppress

from pynput.keyboard import Controller, Key

if sys.platform == 'win32':
    import pywintypes
    import win32clipboard
    import win32con
elif sys.platform == 'darwin':
    from AppKit import NSPasteboard

from one_dragon.utils.log_utils import log, mask_text


class PcClipboard:

    @staticmethod
    def copy_and_paste(text: str) -> None:
        """
        将给定的文本复制到剪贴板，然后再从剪贴板粘贴出来。

        :param text: 要复制到剪贴板的文本
        :return: 无
        """
        PcClipboard.copy_string(text)
        PcClipboard.paste_text()
        PcClipboard.empty_clipboard()

    @staticmethod
    def empty_clipboard() -> None:
        """
        清空剪贴板的内容。

        :return: 无
        """
        if sys.platform == 'darwin':
            NSPasteboard.generalPasteboard().clearContents()
            return

        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
        finally:
            with suppress(Exception):
                win32clipboard.CloseClipboard()

    @staticmethod
    def copy_string(text: str) -> None:
        """
        将给定的文本复制到剪贴板。

        :param text: 要复制到剪贴板的文本
        :return: 无
        """
        if sys.platform == 'darwin':
            log.info(f'复制文字到剪切板:{mask_text(text)}')
            pasteboard = NSPasteboard.generalPasteboard()
            pasteboard.clearContents()
            pasteboard.setString_forType_(text, 'public.utf8-plain-text')
            return

        try:
            # 脱敏（前后10%的字符不加密）
            log.info(f'复制文字到剪切板:{mask_text(text)}')
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
            log.info('复制文字到剪切板成功')
        finally:
            with suppress(Exception):
                win32clipboard.CloseClipboard()

    @staticmethod
    def paste_text() -> str:
        """
        从剪贴板粘贴文本，并模拟按下 Ctrl+V 组合键。

        :return: 从剪贴板获取的文本，如果获取失败则返回空字符串
        """
        keyboard = Controller()

        if sys.platform == 'darwin':
            pasteboard = NSPasteboard.generalPasteboard()
            data = pasteboard.stringForType_('public.utf8-plain-text') or ''
            modifier = Key.cmd
        else:
            modifier = Key.ctrl
            try:
                log.info('粘贴文字, 查找剪切板')
                win32clipboard.OpenClipboard()
                data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                log.info(f'粘贴文字, 获取到:{mask_text(data)}')
            except pywintypes.error:
                data = ''
            finally:
                with suppress(Exception):
                    win32clipboard.CloseClipboard()

        # 使用 pynput 模拟粘贴操作
        log.info('粘贴文字, 按下粘贴快捷键')
        log.debug('粘贴文字, 按下修饰键')
        with keyboard.pressed(modifier):
            time.sleep(0.2)
            log.debug('粘贴文字, 按下 V')
            keyboard.press('v')
            time.sleep(0.2)
            log.debug('粘贴文字, 释放 V')
            keyboard.release('v')

        return data
