from types import SimpleNamespace

import one_dragon.devtools.python_launcher as python_launcher
import one_dragon.envs.env_config as env_config_module
import one_dragon.envs.git_service as git_service_module
import one_dragon.envs.project_config as project_config_module
import one_dragon.utils.i18_utils as i18_utils_module
import one_dragon.utils.log_utils as log_utils_module
from one_dragon.envs.git_progress_reporter import create_git_progress_reporter
from one_dragon.launcher.runtime_launcher import RuntimeLauncher


def test_create_git_progress_reporter_deduplicates_transfer_messages() -> None:
    messages: list[str] = []
    timestamps = iter([0.0, 0.4, 1.5])
    callback = create_git_progress_reporter(
        messages.append,
        time_source=lambda: next(timestamps),
    )

    callback(0.421, '拉取对象 1/10')
    callback(0.424, '拉取对象 2/10')
    callback(0.500, '检查运行环境兼容性')
    callback(0.431, '拉取对象 3/10')

    assert messages == [
        '拉取对象 1/10 (10%)',
        '检查运行环境兼容性',
        '拉取对象 3/10 (30%)',
    ]


def test_python_launcher_fetch_latest_code_passes_progress_callback(
    monkeypatch,
) -> None:
    messages: list[tuple[str, str]] = []
    logs: list[str] = []

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
    monkeypatch.setattr(python_launcher, 'log', SimpleNamespace(info=logs.append))

    python_launcher.fetch_latest_code(ctx)

    assert git_service.progress_callback is not None
    assert ('INFO', '开始获取最新代码...') in messages
    assert ('PASS', '最新代码获取成功') in messages
    assert '拉取对象 3/10 (30%)' in logs
    assert '检查运行环境兼容性' in logs


def test_runtime_launcher_sync_code_passes_progress_callback(monkeypatch) -> None:
    logs: list[str] = []
    timestamps = iter([0.0, 0.2])

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
            progress_callback(0.251, '拉取对象 1/4')
            progress_callback(0.500, '检查工作区状态')
            return True, ''

    monkeypatch.setattr(env_config_module, 'EnvConfig', FakeEnvConfig)
    monkeypatch.setattr(git_service_module, 'GitService', FakeGitService)
    monkeypatch.setattr(project_config_module, 'ProjectConfig', lambda: object())
    monkeypatch.setattr(i18_utils_module, 'gt', lambda message: message)
    monkeypatch.setattr(log_utils_module, 'log', SimpleNamespace(info=logs.append))
    monkeypatch.setattr(
        'one_dragon.envs.git_progress_reporter.time.monotonic',
        lambda: next(timestamps),
    )

    launcher = RuntimeLauncher('test', '1.0.0')
    launcher._sync_code()

    assert len(FakeGitService.instances) == 1
    assert FakeGitService.instances[0].progress_callback is not None
    assert '正在检查代码更新...' in logs
    assert '拉取对象 1/4 (25%)' in logs
    assert '检查工作区状态' in logs
    assert '代码已是最新' in logs
