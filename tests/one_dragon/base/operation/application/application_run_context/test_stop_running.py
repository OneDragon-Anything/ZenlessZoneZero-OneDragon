from types import SimpleNamespace

import pytest

from one_dragon.base.operation.application.application_run_context import (
    ApplicationRunContext,
)


class FakeController:
    """用于测试运行上下文启动流程的控制器。"""

    def __init__(self) -> None:
        """初始化测试控制器。"""
        self.init_count: int = 0

    def init_before_context_run(self) -> bool:
        """模拟运行前初始化成功。"""
        self.init_count += 1
        return True


class TestStopRunning:
    """测试运行上下文停止来源记录。"""

    @pytest.fixture
    def run_context(self) -> ApplicationRunContext:
        """创建应用运行上下文。"""
        ctx = SimpleNamespace(controller=FakeController())
        return ApplicationRunContext(ctx)

    def test_stop_running_by_user_records_source(
        self,
        run_context: ApplicationRunContext,
    ) -> None:
        """测试用户主动停止会记录停止来源。"""
        assert run_context.start_running()

        run_context.stop_running(by_user=True)

        assert run_context.is_context_stop
        assert run_context.is_last_stop_by_user

    def test_stop_running_without_by_user_records_natural_stop(
        self,
        run_context: ApplicationRunContext,
    ) -> None:
        """测试默认停止会记录为非用户主动停止。"""
        assert run_context.start_running()

        run_context.stop_running()

        assert run_context.is_context_stop
        assert not run_context.is_last_stop_by_user

    def test_start_running_resets_last_stop_source(
        self,
        run_context: ApplicationRunContext,
    ) -> None:
        """测试重新开始运行会清理上一次用户停止标记。"""
        assert run_context.start_running()
        run_context.stop_running(by_user=True)

        assert run_context.start_running()

        assert not run_context.is_last_stop_by_user
