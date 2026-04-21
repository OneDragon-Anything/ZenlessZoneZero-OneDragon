import logging
import os
from contextlib import suppress
from dataclasses import dataclass
from logging.handlers import TimedRotatingFileHandler

from one_dragon.utils import os_utils

LOGGER_NAME = 'OneDragon'
_HANDLER_OWNER_ATTR = '_one_dragon_logger_owner'


@dataclass(slots=True)
class LoggerConfig:
    level: int = logging.INFO
    log_file_path: str | None = None
    default_name: str = 'log.txt'
    add_console_handler: bool = True
    propagate: bool = False


def get_log_formatter() -> logging.Formatter:
    return logging.Formatter(
        '[%(asctime)s.%(msecs)03d] [%(filename)s %(lineno)d] [%(levelname)s]: %(message)s',
        '%H:%M:%S',
    )


def _mark_handler(handler: logging.Handler, logger_name: str) -> logging.Handler:
    setattr(handler, _HANDLER_OWNER_ATTR, logger_name)
    return handler


def _is_managed_handler(handler: logging.Handler, logger: logging.Logger) -> bool:
    return getattr(handler, _HANDLER_OWNER_ATTR, None) == logger.name


def _close_managed_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        if not _is_managed_handler(handler, logger):
            continue
        logger.removeHandler(handler)
        with suppress(Exception):
            handler.close()


def _has_managed_handlers(logger: logging.Logger) -> bool:
    return any(_is_managed_handler(handler, logger) for handler in logger.handlers)


def _build_file_handler(logger: logging.Logger, config: LoggerConfig) -> logging.Handler:
    handler = _mark_handler(
        TimedRotatingFileHandler(
            get_log_file_path(config.log_file_path, default_name=config.default_name),
            when='midnight',
            interval=1,
            backupCount=3,
            encoding='utf-8',
        ),
        logger.name,
    )
    handler.setLevel(config.level)
    handler.setFormatter(get_log_formatter())
    return handler


def _build_console_handler(logger: logging.Logger, config: LoggerConfig) -> logging.Handler:
    handler = _mark_handler(logging.StreamHandler(), logger.name)
    handler.setLevel(config.level)
    handler.setFormatter(get_log_formatter())
    return handler


def configure_logger(logger: logging.Logger, config: LoggerConfig) -> logging.Logger:
    """显式配置 logger。

    职责只有一个：将一个现成的 logger 调整到目标配置。
    仅会替换框架自己创建的 handler，不会移除外部追加的 handler。
    """
    _close_managed_handlers(logger)
    logger.setLevel(config.level)
    logger.propagate = config.propagate
    logger.addHandler(_build_file_handler(logger, config))
    if config.add_console_handler:
        logger.addHandler(_build_console_handler(logger, config))
    return logger


def get_or_create_logger(name: str, config: LoggerConfig | None = None) -> logging.Logger:
    """获取指定名称的 logger。

    - 若框架尚未为该 logger 挂载默认 handler，则按给定配置初始化
    - 若已初始化过，则直接复用
    - 不会因为外部额外挂载了 handler 而跳过框架默认配置
    """
    logger = logging.getLogger(name)
    if _has_managed_handlers(logger):
        return logger
    return configure_logger(logger, config or LoggerConfig())


def get_log_file_path(log_file_path: str | None = None, default_name: str = 'log.txt') -> str:
    """获取日志文件路径。

    - 未传 `log_file_path` 时，使用工作目录 `.log/` 下的默认文件名
    - 传相对路径/文件名时，仍然放在工作目录 `.log/` 下
    - 传绝对路径时，直接使用
    """
    configured = (log_file_path or '').strip()
    if not configured:
        configured = default_name
    if os.path.isabs(configured):
        return configured
    return os.path.join(os_utils.get_path_under_work_dir('.log'), configured)


def get_logger():
    """获取框架默认 logger。

    若尚未初始化，则按默认配置初始化一次；若已经存在框架默认 handler，则直接复用。
    """
    return get_or_create_logger(LOGGER_NAME, LoggerConfig())


def set_log_level(level: int, logger: logging.Logger | None = None) -> None:
    """
    显示日志等级
    :param level:
    :return:
    """
    target = logger or log
    target.setLevel(level)
    for handler in target.handlers:
        if not _is_managed_handler(handler, target):
            continue
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
