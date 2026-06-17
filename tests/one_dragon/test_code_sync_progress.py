from types import SimpleNamespace

import one_dragon.devtools.python_launcher as python_launcher
import one_dragon.envs.env_config as env_config_module
import one_dragon.envs.git_service as git_service_module
import one_dragon.envs.project_config as project_config_module
import one_dragon.utils.i18_utils as i18_utils_module
from one_dragon.launcher.runtime_launcher import RuntimeLauncher


def test_python_launcher_progress_callback_limits_transfer_messages(monkeypatch) -> None:
    messages: list[tuple[str, str]] = []
    callback = python_launcher.create_git_progress_callback()

    original_print_message = python_launcher.print_message
    python_launcher.print_message = lambda message, level='INFO': messages.append((level, message))
    timestamps = iter([0.0, 0.4, 1.5])
    monkeypatch.setattr(python_launcher.time, 'monotonic', lambda: next(timestamps))
    try:
        callback(0.421, '拉取对象 1/10')
        callback(0.424, '拉取对象 2/10')
        callback(0.500, '检查运行环境兼容性')
        callback(0.431, '拉取对象 3/10')
    finally:
        python_launcher.print_message = original_print_message

    assert messages == [
        ('INFO', '拉取对象 1/10 (10%)'),
        ('INFO', '检查运行环境兼容性'),
        ('INFO', '拉取对象 3/10 (30%)'),
    ]


def test_python_launcher_progress_callback_always_shows_final_100_percent(monkeypatch) -> None:
    messages: list[tuple[str, str]] = []
    callback = python_launcher.create_git_progress_callback()

    original_print_message = python_launcher.print_message
    python_launcher.print_message = lambda message, level='INFO': messages.append((level, message))
    timestamps = iter([0.0, 0.2])
    monkeypatch.setattr(python_launcher.time, 'monotonic', lambda: next(timestamps))
    try:
        callback(0.421, '拉取对象 1/10')
        callback(1.0, '拉取对象 10/10')
    finally:
        python_launcher.print_message = original_print_message

    assert messages == [
        ('INFO', '拉取对象 1/10 (10%)'),
        ('INFO', '拉取对象 10/10 (100%)'),
    ]


def test_python_launcher_fetch_latest_code_passes_progress_callback(
    monkeypatch,
) -> None:
    messages: list[tuple[str, str]] = []

    class FakeGitService:

        def __init__(self) -> None:
            self.progress_callback = None

        def fetch_latest_code(self, progress_callback=None):
            self.progress_callback = progress_callback
            progress_callback(0.421, '拉取对象 3/10')
            progress_callback(0.500, '检查运行环境兼容性')
            return True, ''

    git_service = FakeGitService()
    ctx = SimpleNamespace(
        env_config=SimpleNamespace(auto_update=True),
        git_service=git_service,
    )

    monkeypatch.setattr(
        python_launcher,
        'print_message',
        lambda message, level='INFO': messages.append((level, message)),
    )

    python_launcher.fetch_latest_code(ctx)

    assert git_service.progress_callback is not None
    assert ('INFO', '开始获取最新代码...') in messages
    assert ('INFO', '拉取对象 3/10 (30%)') in messages
    assert ('INFO', '检查运行环境兼容性') in messages
    assert ('PASS', '最新代码获取成功') in messages


def test_python_launcher_fetch_latest_code_silences_framework_console_log(
    monkeypatch,
) -> None:
    configured: list[tuple[object, str | None, bool, bool]] = []

    class FakeGitService:

        def fetch_latest_code(self, progress_callback=None):
            progress_callback(0.500, '检查运行环境兼容性')
            return True, ''

    messages: list[tuple[str, str]] = []
    ctx = SimpleNamespace(
        env_config=SimpleNamespace(auto_update=True),
        git_service=FakeGitService(),
    )

    def _fake_configure_logger(logger, config):
        configured.append(
            (
                logger,
                config.log_file_path,
                config.add_console_handler,
                config.propagate,
            )
        )
        return logger

    monkeypatch.setattr(
        python_launcher,
        'configure_logger',
        _fake_configure_logger,
    )
    monkeypatch.setattr(
        python_launcher,
        'print_message',
        lambda message, level='INFO': messages.append((level, message)),
    )

    python_launcher.fetch_latest_code(ctx)

    assert configured
    assert configured[0][0] is python_launcher.framework_log
    assert configured[0][1] is not None
    assert configured[0][2] is False
    assert configured[0][3] is False
    assert ('INFO', '检查运行环境兼容性') in messages


def test_python_launcher_progress_callback_passes_stage_messages_through() -> None:
    messages: list[tuple[str, str]] = []

    callback = python_launcher.create_git_progress_callback()
    original_print_message = python_launcher.print_message
    python_launcher.print_message = lambda message, level='INFO': messages.append((level, message))
    try:
        callback(0.2, '获取远程代码')
        callback(0.5, '检查工作区状态')
    finally:
        python_launcher.print_message = original_print_message

    assert messages == [
        ('INFO', '获取远程代码'),
        ('INFO', '检查工作区状态'),
    ]


def test_runtime_launcher_sync_code_uses_framework_log(monkeypatch) -> None:
    messages: list[str] = []

    class FakeEnvConfig:
        auto_update = True

    class FakeGitService:
        instances: list['FakeGitService'] = []

        def __init__(self, project_config, env_config) -> None:
            self.project_config = project_config
            self.env_config = env_config
            self.progress_callback = None
            FakeGitService.instances.append(self)

        def check_repo_exists(self) -> bool:
            return True

        def fetch_latest_code(self, progress_callback=None):
            self.progress_callback = progress_callback
            return True, ''

    monkeypatch.setattr(env_config_module, 'EnvConfig', FakeEnvConfig)
    monkeypatch.setattr(git_service_module, 'GitService', FakeGitService)
    monkeypatch.setattr(project_config_module, 'ProjectConfig', lambda: object())
    monkeypatch.setattr(i18_utils_module, 'gt', lambda message: message)
    monkeypatch.setattr('one_dragon.utils.log_utils.log.info', lambda message: messages.append(message))

    launcher = RuntimeLauncher('test', '1.0.0')
    launcher._sync_code()

    assert len(FakeGitService.instances) == 1
    assert FakeGitService.instances[0].progress_callback is None
    assert '正在检查代码更新...' in messages
    assert '代码已是最新' in messages
