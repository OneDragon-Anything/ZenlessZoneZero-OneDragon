"""测试 GitService 的拉取进度回调。"""

from types import SimpleNamespace

import pytest

from one_dragon.envs.git_service import GitService, _FetchProgressRemoteCallbacks


class FakeRemote:

    def __init__(self, progress_stats: SimpleNamespace):
        self.name: str = 'origin'
        self.progress_stats: SimpleNamespace = progress_stats
        self.fetch_calls: list[dict[str, object]] = []

    def fetch(
        self,
        refspecs: list[str] | None = None,
        message: str | None = None,
        callbacks: object | None = None,
        prune: object | None = None,
        proxy: bool | str | None = None,
        depth: int = 0,
    ) -> SimpleNamespace:
        self.fetch_calls.append(
            {
                'refspecs': refspecs,
                'message': message,
                'callbacks': callbacks,
                'prune': prune,
                'proxy': proxy,
                'depth': depth,
            }
        )
        if callbacks is not None:
            callbacks.transfer_progress(self.progress_stats)
        return self.progress_stats


class TestFetchProgressRemoteCallbacks:

    def test_transfer_progress_maps_to_stage_range(self) -> None:
        events: list[tuple[float, str]] = []
        callbacks = _FetchProgressRemoteCallbacks(
            lambda progress, message: events.append((progress, message)),
            0.4,
            0.6,
        )

        stats = SimpleNamespace(received_objects=3, total_objects=10, received_bytes=4096)
        callbacks.transfer_progress(stats)

        assert len(events) == 1
        progress, message = events[0]
        assert progress == pytest.approx(0.46)
        assert message == '拉取对象 3/10'

    def test_transfer_progress_falls_back_to_received_bytes(self) -> None:
        events: list[tuple[float, str]] = []
        callbacks = _FetchProgressRemoteCallbacks(
            lambda progress, message: events.append((progress, message)),
            0.2,
            0.4,
        )

        stats = SimpleNamespace(received_objects=0, total_objects=0, received_bytes=3 * 1024 * 1024)
        callbacks.transfer_progress(stats)

        assert len(events) == 1
        progress, message = events[0]
        assert progress == pytest.approx(0.2)
        assert message == '拉取对象 3.00 MB'

    def test_transfer_progress_deduplicates_identical_messages(self) -> None:
        events: list[tuple[float, str]] = []
        callbacks = _FetchProgressRemoteCallbacks(
            lambda progress, message: events.append((progress, message)),
            0.2,
            0.4,
        )

        stats = SimpleNamespace(received_objects=12, total_objects=12, received_bytes=2048)
        callbacks.transfer_progress(stats)
        callbacks.transfer_progress(stats)

        assert events == [
            (0.4, '拉取对象 12/12'),
        ]


class TestGitServiceFetchRemote:

    @pytest.fixture
    def git_service(self) -> GitService:
        project_config = SimpleNamespace(
            github_https_repository='https://example.com/repo.git',
            gitee_https_repository='https://example.com/repo.git',
        )
        env_config = SimpleNamespace(
            git_branch='main',
            git_remote='origin',
            is_personal_proxy=False,
            personal_proxy='',
        )
        return GitService(project_config, env_config, repo_dir='.')

    def test_fetch_remote_reports_progress_and_success(
        self,
        git_service: GitService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo = SimpleNamespace(references={})
        remote = FakeRemote(SimpleNamespace(received_objects=2, total_objects=4, received_bytes=2048))
        events: list[tuple[float, str]] = []

        monkeypatch.setattr(git_service, '_open_repo', lambda: repo)
        monkeypatch.setattr(git_service, '_ensure_remote', lambda: remote)

        success = git_service._fetch_remote(
            lambda progress, message: events.append((progress, message)),
            0.2,
            0.4,
        )

        assert success is True
        assert remote.fetch_calls[0]['depth'] == 1
        assert remote.fetch_calls[0]['refspecs'] == ['+refs/heads/main:refs/remotes/origin/main']
        assert events[0][0] == pytest.approx(0.3)
        assert events[0][1] == '拉取对象 2/4'
        assert events[-1] == (0.4, '获取远程代码成功')
