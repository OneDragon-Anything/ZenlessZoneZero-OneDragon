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


@dataclass(slots=True)
class ProjectRuntimeLoggingContext:
    """项目显式启用的运行时日志分流结果。"""

    project_logger: logging.Logger
    framework_logger: logging.Logger
    project_log_file_path: str
    framework_log_file_path: str


def get_log_formatter() -> logging.Formatter:
    return logging.Formatter(
        '[%(asctime)s.%(msecs)03d] [%(filename)s %(lineno)d] [%(levelname)s]: %(message)s',
        '%H:%M:%S',
    )


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
        logger.addHandler(_prepare_handler(logging.StreamHandler(), logger, config))
    return logger


def get_or_create_logger(name: str, config: LoggerConfig | None = None) -> logging.Logger:
    """获取指定名称的 logger。

    - 若框架尚未为该 logger 挂载默认 handler，则按给定配置初始化
    - 若已初始化过，则直接复用
    - 不会因为外部额外挂载了 handler 而跳过框架默认配置
    """
    logger = logging.getLogger(name)
    if any(_handler_belongs_to_logger(handler, logger) for handler in logger.handlers):
        return logger
    return configure_logger(logger, config or LoggerConfig())


def configure_project_runtime_logging(
    project_logger_name: str,
    project_log_file_path: str,
    framework_log_file_path: str,
    *,
    level: int = logging.INFO,
    project_add_console_handler: bool = False,
    framework_add_console_handler: bool = False,
    framework_logger_name: str = LOGGER_NAME,
) -> ProjectRuntimeLoggingContext:
    """为项目运行态显式启用项目日志与框架日志分流。

    默认的框架日志仍然写入 `log.txt`；只有项目主动调用本函数时，
    才会把项目 logger 和框架 logger 分别切到指定文件。
    """
    if project_logger_name == framework_logger_name:
        raise ValueError(
            'configure_project_runtime_logging 需要不同的 '
            'project_logger_name 和 framework_logger_name；否则 '
            '_configure_runtime_logger 会对同一个 logger 调用两次 '
            '_close_managed_handlers，导致 ProjectRuntimeLoggingContext '
            '静默丢失其中一套 handler 配置。'
        )

    project_logger = logging.getLogger(project_logger_name)
    framework_logger = logging.getLogger(framework_logger_name)

    framework_logger = _configure_runtime_logger(
        framework_logger,
        log_file_path=framework_log_file_path,
        level=level,
        add_console_handler=framework_add_console_handler,
    )
    project_logger = _configure_runtime_logger(
        project_logger,
        log_file_path=project_log_file_path,
        level=level,
        add_console_handler=project_add_console_handler,
    )
    return ProjectRuntimeLoggingContext(
        project_logger=project_logger,
        framework_logger=framework_logger,
        project_log_file_path=project_log_file_path,
        framework_log_file_path=framework_log_file_path,
    )


def _configure_runtime_logger(
    logger: logging.Logger,
    *,
    log_file_path: str,
    level: int,
    add_console_handler: bool,
) -> logging.Logger:
    return configure_logger(
        logger,
        LoggerConfig(
            level=level,
            log_file_path=log_file_path,
            add_console_handler=add_console_handler,
            propagate=False,
        ),
    )


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
        if not _handler_belongs_to_logger(handler, target):
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


def _close_managed_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        if not _handler_belongs_to_logger(handler, logger):
            continue
        logger.removeHandler(handler)
        with suppress(Exception):
            handler.close()


def _handler_belongs_to_logger(handler: logging.Handler, logger: logging.Logger) -> bool:
    return getattr(handler, _HANDLER_OWNER_ATTR, None) == logger.name


def _build_file_handler(logger: logging.Logger, config: LoggerConfig) -> logging.Handler:
    handler = TimedRotatingFileHandler(
        get_log_file_path(config.log_file_path, default_name=config.default_name),
        when='midnight',
        interval=1,
        backupCount=3,
        encoding='utf-8',
        delay=True,
    )
    return _prepare_handler(handler, logger, config)


def _prepare_handler(
    handler: logging.Handler,
    logger: logging.Logger,
    config: LoggerConfig,
) -> logging.Handler:
    setattr(handler, _HANDLER_OWNER_ATTR, logger.name)
    handler.setLevel(config.level)
    handler.setFormatter(get_log_formatter())
    return handler


log = get_logger()
