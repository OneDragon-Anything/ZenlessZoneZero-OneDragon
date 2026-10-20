import threading
from typing import TYPE_CHECKING

from one_dragon.utils.log_utils import log

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_context import OneDragonContext


class UpdateCheckService:
    """代码更新后台检查服务

    运行期间定时对远程仓库做 fetch（只把远程对象下载到本地仓库，不改工作区文件），
    发现有新版本时按远程 commit 去重，先做模块清单兼容性检查，再打信号给主页并推送通知。
    工作区落盘（reset）仍由启动器在下次启动时完成，运行期间绝不 checkout。
    """

    FIRST_CHECK_DELAY_SECONDS: float = 60
    """启动后的首次检查延迟 避开启动初始化高峰"""

    CHECK_INTERVAL_SECONDS: float = 30 * 60
    """两次检查的间隔"""

    def __init__(self, ctx: OneDragonContext) -> None:
        self.ctx: OneDragonContext = ctx

        self._stop_event: threading.Event = threading.Event()
        self._loop_thread: threading.Thread | None = None
        self._last_notified_commit_id: str | None = None
        """已通知过的远程 commit 用于去重 同一个版本只提示一次"""

    def start_checking(self) -> None:
        """启动后台定时检查 幂等"""
        if self._loop_thread is not None and self._loop_thread.is_alive():
            return
        self._stop_event.clear()
        self._loop_thread = threading.Thread(
            target=self._check_loop, name='update_check_loop', daemon=True
        )
        self._loop_thread.start()

    def stop_checking(self) -> None:
        """停止后台定时检查"""
        self._stop_event.set()

    def _check_loop(self) -> None:
        """定时检查循环 单次失败不影响后续检查"""
        self._stop_event.wait(self.FIRST_CHECK_DELAY_SECONDS)
        while not self._stop_event.is_set():
            try:
                self.check_once()
            except Exception:
                log.error('后台检查代码更新失败', exc_info=True)
            self._stop_event.wait(self.CHECK_INTERVAL_SECONDS)

    def check_once(self) -> None:
        """立即检查一次 发现有新版本时打信号并推送通知 失败时静默不打扰"""
        git_service = self.ctx.git_service
        if not git_service.check_repo_exists():
            return  # 还没完成安装 没有仓库可查

        # is_current_branch_latest 内部会做一次 fetch 只下载对象 不改工作区
        latest, message = git_service.is_current_branch_latest()
        if latest:
            return

        remote_commit_id = git_service.get_remote_head_commit_id()
        if remote_commit_id is None:
            # fetch 失败时远程跟踪分支可能不存在 静默跳过 等下一次检查
            log.debug(f'后台检查代码更新失败: {message}')
            return

        if remote_commit_id == self._last_notified_commit_id:
            return  # 该版本已提示过

        compatible, reason = git_service.check_remote_manifest_compatible()
        if not compatible:
            # 运行环境不兼容时 启动器更新也会失败 不通知避免误导
            log.warning(f'远程新版本与当前运行环境不兼容 跳过更新通知: {reason}')
            self._last_notified_commit_id = remote_commit_id
            return

        self._last_notified_commit_id = remote_commit_id
        self.ctx.signal.code_update_available = True

        current_commit_id = git_service.get_head_commit_id(short=True) or '未知'
        if self.ctx.env_config.auto_update_code:
            action_tip = '下次启动时自动更新生效'
        else:
            action_tip = '请到 [设置-Git相关] 手动同步代码'
        self.ctx.push_service.push_async(
            title='发现新版本',
            content=f'代码有更新: {current_commit_id} → {remote_commit_id[:8]}，{action_tip}',
        )
        log.info(f'后台发现代码更新: {current_commit_id} -> {remote_commit_id[:8]}')

    def after_app_shutdown(self) -> None:
        """App关闭后进行的操作 停止检查线程"""
        self.stop_checking()
