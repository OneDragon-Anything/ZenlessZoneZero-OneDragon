from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.envs.git_service import GitSyncStatus
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log


def sync_external_source(launcher_version: str) -> bool:
    """按绝区零配置同步外部源码，返回源码是否发生变化。"""
    log.info(f'OneDragon 集成启动器 {launcher_version}')
    env_context = OneDragonEnvContext()
    git_service = env_context.git_service
    first_run = git_service.is_initial_checkout_pending()
    if not first_run and not env_context.env_config.auto_update_code:
        log.info(gt('未开启代码自动更新，跳过'))
        return False

    log.info(
        gt('首次运行，正在同步代码仓库...')
        if first_run
        else gt('正在检查代码更新...')
    )
    status, message = git_service.fetch_latest_code(
        _log_progress,
        initial_tag=_initial_tag(launcher_version, first_run),
    )
    return _handle_sync_status(status, message, first_run)


def _initial_tag(launcher_version: str, first_run: bool) -> str | None:
    """首次运行时返回可用来建立仓库的版本标签。"""
    if (
        first_run
        and launcher_version.startswith('v')
        and launcher_version != 'v0.0.0'
    ):
        return launcher_version
    return None


def _handle_sync_status(
    status: GitSyncStatus,
    message: str,
    first_run: bool,
) -> bool:
    """按同步结果决定继续启动、记录警告或中断启动。"""
    if status is GitSyncStatus.SUCCESS:
        log.info(message)
        return True
    if status in (
        GitSyncStatus.UP_TO_DATE,
        GitSyncStatus.RUNTIME_INCOMPATIBLE,
        GitSyncStatus.BUILTIN_TAG_UNAVAILABLE,
        GitSyncStatus.LOCAL_CHANGES,
    ) or (status is GitSyncStatus.REMOTE_UNAVAILABLE and not first_run):
        warning = _continue_message(status)
        log.info(message) if warning is None else log.warning(f'{message}, {gt(warning)}')
        return False
    if status is GitSyncStatus.REMOTE_UNAVAILABLE:
        raise RuntimeError(f'{message}, {gt("请稍后重试或切换代码源")}')
    if status is GitSyncStatus.LOCAL_UPDATE_FAILED:
        raise RuntimeError(
            f'{message}, {gt("请重新运行启动器；仍然失败时请重新安装")}'
        )
    raise RuntimeError(f'{message}, {gt("请查看日志后重试")}')


def _continue_message(status: GitSyncStatus) -> str | None:
    """返回可以继续使用当前源码时附加的提示。"""
    if status is GitSyncStatus.BUILTIN_TAG_UNAVAILABLE:
        return '继续使用内置版本'
    if status is GitSyncStatus.UP_TO_DATE:
        return None
    return '继续使用当前版本'


_progress_line_active = False


def _log_progress(_progress: float, message: str) -> None:
    """把百分比进度刷新在同一行，其余消息写入日志。"""
    global _progress_line_active
    refresh = '%' in message and 'done' not in message.lower()
    if refresh:
        print(message, end='\r', flush=True)
        _progress_line_active = True
        return
    if _progress_line_active:
        print(' ' * 120, end='\r', flush=True)
        _progress_line_active = False
    log.info(message)
