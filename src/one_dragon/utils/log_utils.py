import logging
import os
import time
from logging.handlers import TimedRotatingFileHandler

from one_dragon.utils import os_utils


class SafeTimedRotatingFileHandler(TimedRotatingFileHandler):
    def doRollover(self):
        try:
            super().doRollover()
        except PermissionError:
            if self.stream is None:
                self.stream = self._open()

            current_time = int(time.time())
            rollover_at = self.computeRollover(current_time)
            while rollover_at <= current_time:
                rollover_at += self.interval
            self.rolloverAt = rollover_at


def get_logger():
    logger = logging.getLogger('OneDragon')
    logger.handlers.clear()
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('[%(asctime)s.%(msecs)03d] [%(filename)s %(lineno)d] [%(levelname)s]: %(message)s', '%H:%M:%S')

    log_file_path = os.path.join(os_utils.get_path_under_work_dir('.log'), 'log.txt')
    archive_handler = SafeTimedRotatingFileHandler(log_file_path, when='midnight', interval=1, backupCount=3, encoding='utf-8')
    archive_handler.setLevel(logging.INFO)
    archive_handler.setFormatter(formatter)
    logger.addHandler(archive_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def set_log_level(level: int) -> None:
    """
    显示日志等级
    :param level:
    :return:
    """
    log.setLevel(level)
    for handler in log.handlers:
        handler.setLevel(level)


def mask_text(text: str) -> str:
    """
    对给定的文本进行脱敏处理，保留首尾部分字符，其余用 * 替换。
    如果字符数少于5个，则只保留首字符不脱敏。

    :param text: 需要脱敏的文本
    :return: 脱敏后的文本
    """
    if len(text) < 5:
        return text[0] + '*' * (len(text) - 1)
    else:
        return text[:2] + '*' * (len(text) - 4) + text[-2:]


log = get_logger()
