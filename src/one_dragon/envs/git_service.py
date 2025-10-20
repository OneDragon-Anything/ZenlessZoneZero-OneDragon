import contextlib
import os
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass

import pygit2

from one_dragon.envs.env_config import EnvConfig, GitMethodEnum, RepositoryTypeEnum
from one_dragon.envs.project_config import ProjectConfig
from one_dragon.utils import os_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon.utils.semver_utils import sort_tags

DOT_GIT_DIR_PATH = os.path.join(os_utils.get_work_dir(), '.git')


class GitLog:
    """Git 提交日志"""

    def __init__(self, commit_id: str, author: str, commit_time: str, commit_message: str):
        self.commit_id: str = commit_id
        self.author: str = author
        self.commit_time: str = commit_time
        self.commit_message: str = commit_message


@dataclass
class GitOperationResult:
    """Git 操作结果"""
    success: bool
    code: str
    message: str
    detail: str | None = None

    def to_tuple(self) -> tuple[bool, str]:
        return self.success, self.message


class GitService:
    """Git 服务，提供仓库管理和代码同步功能"""

    def __init__(self, project_config: ProjectConfig, env_config: EnvConfig):
        self.project_config: ProjectConfig = project_config
        self.env_config: EnvConfig = env_config
        self.is_proxy_set: bool = False

        self._repo: pygit2.Repository | None = None
        self._ensure_config_search_path()

    # ================== 私有辅助方法 ==================

    @staticmethod
    def _ensure_config_search_path() -> None:
        """禁用系统/用户级 git config，仅使用仓库级配置"""
        settings = getattr(pygit2, 'settings', None)
        if settings is None:
            log.warning('pygit2.settings 不可用，无法覆盖 git config 搜索路径')
            return

        levels = [
            getattr(pygit2, 'GIT_CONFIG_LEVEL_SYSTEM', None),
            getattr(pygit2, 'GIT_CONFIG_LEVEL_GLOBAL', None),
            getattr(pygit2, 'GIT_CONFIG_LEVEL_XDG', None),
        ]

        for level in levels:
            if level is not None:
                with contextlib.suppress(Exception):
                    settings.set_search_path(level, '')

        log.info('已禁用系统/用户级 git config 搜索路径，仅保留仓库级配置')

    def _open_repo(self, refresh: bool = False) -> pygit2.Repository:
        """打开仓库（带缓存）"""
        if refresh:
            self._repo = None

        if self._repo is None:
            self._repo = pygit2.Repository(os_utils.get_work_dir())

        return self._repo

    def _invalidate_repo_cache(self) -> None:
        """清空仓库缓存"""
        self._repo = None
        self.is_proxy_set = False

    def _ensure_remote(self, repo: pygit2.Repository | None = None, remote_url: str | None = None) -> pygit2.Remote | None:
        """确保远程仓库配置正确

        Args:
            repo: 仓库对象，如果为None则自动获取最新的仓库对象
            remote_url: 远程仓库URL，如果为None则使用默认配置

        Returns:
            Remote对象，失败时返回None
        """
        remote_url = remote_url or self.get_git_repository()
        if not remote_url:
            log.error('未能获取有效的远程仓库地址')
            return None

        remote_name = 'origin'

        try:
            # 如果没有传入repo，则获取最新的仓库对象（避免使用过期缓存）
            if repo is None:
                repo = self._open_repo()

            # 检查远程是否已存在（使用最新的repo对象）
            if remote_name in repo.remotes.names():
                remote = repo.remotes[remote_name]

                # URL相同，直接返回
                if remote.url == remote_url:
                    return remote

                # URL不同，需要更新
                log.info(f'更新远程仓库地址: {remote.url} -> {remote_url}')
                repo.remotes.set_url(remote_name, remote_url)
                return repo.remotes[remote_name]

            # 远程不存在，创建新的
            log.info(f'创建远程仓库: {remote_name} -> {remote_url}')
            repo.remotes.create(remote_name, remote_url)
            return repo.remotes[remote_name]

        except Exception as exc:
            log.error(f'配置远程仓库失败: {exc}', exc_info=True)
            return None

    def _get_proxy_address(self) -> str | None:
        """获取代理地址"""
        if not self.env_config.is_personal_proxy:
            return None

        proxy = self.env_config.personal_proxy.strip()
        if not proxy:
            return None

        if proxy.startswith(('http://', 'https://', 'socks5://')):
            return proxy

        return f'http://{proxy}'

    def _apply_proxy(self, repo: pygit2.Repository) -> None:
        """应用代理配置到仓库"""
        proxy = self._get_proxy_address()

        try:
            cfg = repo.config
            if proxy is None:
                # 清除代理
                for key in ('http.proxy', 'https.proxy'):
                    with contextlib.suppress(KeyError, pygit2.GitError):
                        del cfg[key]
            else:
                # 设置代理
                cfg['http.proxy'] = proxy
                cfg['https.proxy'] = proxy
        except Exception as exc:
            log.warning(f'设置代理失败: {exc}')

    @contextlib.contextmanager
    def _with_proxy(self, repo: pygit2.Repository | None = None):
        """在代理环境中执行操作"""
        if repo is None:
            with contextlib.suppress(Exception):
                repo = self._open_repo()

        if repo is not None:
            self._apply_proxy(repo)

        yield repo

    def _fetch_remote(self, repo: pygit2.Repository | None = None,
                      remote: pygit2.Remote | None = None) -> GitOperationResult:
        """获取远程代码

        Args:
            repo: 仓库对象，如果为None则自动打开
            remote: 远程对象
        """
        log.info(gt('获取远程代码'))

        try:
            repo = repo or self._open_repo()
        except Exception as exc:
            log.error(f'打开仓库失败: {exc}', exc_info=True)
            return GitOperationResult(False, 'OPEN_REPO_FAILED', gt('获取远程代码失败'),
                                      detail=str(exc))

        if remote is None:
            return GitOperationResult(False, 'REMOTE_NOT_CONFIGURED', gt('获取远程代码失败'),
                                      detail='remote origin missing')

        try:
            with self._with_proxy(repo):
                remote.fetch()
            log.info(gt('获取远程代码成功'))
            return GitOperationResult(True, 'FETCH_SUCCESS', gt('获取远程代码成功'))
        except Exception as exc:
            log.error(f'获取远程代码失败: {exc}', exc_info=True)
            return GitOperationResult(False, 'FETCH_ERROR', gt('获取远程代码失败'),
                                      detail=str(exc))

    def _get_branch_commit(self, repo: pygit2.Repository, branch: str,
                           allow_local: bool = False) -> pygit2.Commit | None:
        """获取分支的提交对象"""
        # 优先使用远程分支
        remote_ref = f'refs/remotes/origin/{branch}'
        try:
            if remote_ref in repo.references:
                return repo.get(repo.references[remote_ref].target)
        except Exception as exc:
            log.error(f'读取远程分支 {remote_ref} 失败: {exc}')

        # 回退到本地 HEAD
        if allow_local:
            try:
                return repo.head.peel()
            except Exception as exc:
                log.error(f'获取本地 HEAD 失败: {exc}')

        return None

    def _checkout_branch(self, repo: pygit2.Repository, branch: str,
                         allow_local: bool = False) -> tuple[bool, pygit2.Oid | None]:
        """切换到指定分支"""
        commit = self._get_branch_commit(repo, branch, allow_local)
        if commit is None:
            return False, None

        local_ref = f'refs/heads/{branch}'
        try:
            # 更新或创建本地分支
            if local_ref in repo.references:
                repo.references[local_ref].set_target(commit.id)
            else:
                repo.create_branch(branch, commit)

            # 切换分支
            repo.checkout(local_ref, strategy=pygit2.GIT_CHECKOUT_FORCE)
            repo.set_head(local_ref)

            return True, commit.id

        except Exception as exc:
            log.error(f'切换分支失败: {exc}', exc_info=True)
            return False, None

    def _sync_with_remote(self, repo: pygit2.Repository, branch: str,
                          force: bool) -> GitOperationResult:
        """同步本地分支到远程"""
        remote_ref = f'refs/remotes/origin/{branch}'

        try:
            # 检查远程分支是否存在
            if remote_ref not in repo.references:
                return GitOperationResult(True, 'REMOTE_BRANCH_MISSING', '',
                                          detail=f'missing {remote_ref}')

            remote_oid = repo.references[remote_ref].target

            # 获取本地 HEAD
            try:
                local_oid = repo.head.target
            except Exception:
                local_oid = None

            # HEAD 不存在，直接重置
            if local_oid is None:
                if force:
                    repo.reset(remote_oid, pygit2.GIT_RESET_HARD)
                    return GitOperationResult(True, 'RESET_HEAD', gt('更新本地代码成功'),
                                              detail=f'reset to {remote_oid}')
                return GitOperationResult(False, 'HEAD_MISSING', gt('更新本地代码失败'),
                                          detail='HEAD missing')

            # 检查是否可以快进
            can_fast_forward = False
            with contextlib.suppress(Exception):
                can_fast_forward = repo.descendant_of(remote_oid, local_oid)

            # 快进更新
            if can_fast_forward:
                repo.reset(remote_oid, pygit2.GIT_RESET_HARD)
                return GitOperationResult(True, 'FAST_FORWARD', gt('更新本地代码成功'),
                                          detail=f'{local_oid} -> {remote_oid}')

            # 强制更新
            if force:
                repo.reset(remote_oid, pygit2.GIT_RESET_HARD)
                return GitOperationResult(True, 'FORCED_RESET', gt('更新本地代码成功'),
                                          detail=f'{local_oid} -> {remote_oid}')

            # 需要手动处理
            return GitOperationResult(False, 'NEED_MANUAL_REBASE', gt('更新本地代码失败'),
                                      detail=f'local {local_oid} ahead of {remote_oid}')

        except Exception as exc:
            log.error(f'同步分支失败: {exc}', exc_info=True)
            return GitOperationResult(False, 'SYNC_ERROR', gt('更新本地代码失败'),
                                      detail=str(exc))

    # ================== 公共 API ==================

    def fetch_latest_code(self, progress_callback: Callable[[float, str], None] | None = None) -> tuple[bool, str]:
        """
        更新最新的代码：不存在 .git 则克隆，存在则拉取并更新分支
        """
        log.info(f".git {gt('目录')} {DOT_GIT_DIR_PATH}")
        self.set_safe_dir()

        if not os.path.exists(DOT_GIT_DIR_PATH):
            return self.clone_repository(progress_callback)
        else:
            return self.checkout_latest_project_branch(progress_callback)

    def clone_repository(self, progress_callback: Callable[[float, str], None] | None = None) -> tuple[bool, str]:
        """
        初始化本地仓库并同步远程目标分支
        """
        work_dir = os_utils.get_work_dir()
        repo_url = self.get_git_repository(for_clone=True)

        if not repo_url:
            log.error('缺少有效的远程仓库地址')
            return False, gt('克隆仓库失败')

        # 初始化仓库
        if progress_callback:
            progress_callback(-1, gt('初始化本地 Git 仓库'))
        log.info(gt('初始化本地 Git 仓库'))

        try:
            pygit2.init_repository(work_dir, False)
            self._invalidate_repo_cache()
            repo = self._open_repo(refresh=True)
        except Exception as exc:
            log.error(f'初始化仓库失败: {exc}', exc_info=True)
            return False, gt('克隆仓库失败')

        # 配置远程
        remote = self._ensure_remote(repo, repo_url)
        if remote is None:
            return False, gt('克隆仓库失败')

        # 获取远程代码
        fetch_result = self._fetch_remote(repo, remote)
        if not fetch_result.success:
            return fetch_result.to_tuple()

        if progress_callback:
            progress_callback(0.6, fetch_result.message or gt('获取远程代码成功'))

        # 切换分支
        target_branch = self.env_config.git_branch
        success, target_oid = self._checkout_branch(repo, target_branch, allow_local=False)
        if not success:
            return False, gt('克隆仓库失败')

        # 重置到目标提交
        if target_oid:
            repo.reset(target_oid, pygit2.GIT_RESET_HARD)

        if progress_callback:
            progress_callback(1.0, gt('克隆仓库成功'))

        return True, gt('克隆仓库成功')

    def checkout_latest_project_branch(self, progress_callback: Callable[[float, str], None] | None = None) -> tuple[bool, str]:
        """
        切换到最新的目标分支并更新代码
        """
        log.info(gt('核对当前仓库'))

        # 打开仓库
        try:
            repo = self._open_repo()
        except Exception as exc:
            log.error(f'打开仓库失败: {exc}', exc_info=True)
            return False, gt('打开仓库失败')

        # 更新远程配置
        remote = self._ensure_remote(repo, self.get_git_repository())
        if remote is None:
            return False, gt('更新远程仓库地址失败')

        # 获取远程代码
        fetch_result = self._fetch_remote(repo, remote)
        if not fetch_result.success:
            return fetch_result.to_tuple()

        if progress_callback:
            progress_callback(0.2, fetch_result.message)

        # 检查工作区状态
        is_clean = self.is_current_branch_clean()
        if not is_clean:
            if self.env_config.force_update:
                # 强制重置
                commit = self._get_branch_commit(repo, self.env_config.git_branch, allow_local=False)
                if commit is None:
                    return False, gt('强制更新失败')
                try:
                    repo.reset(commit.id, pygit2.GIT_RESET_HARD)
                except Exception as exc:
                    log.error(f'强制更新失败: {exc}', exc_info=True)
                    return False, gt('强制更新失败')
            else:
                return False, gt('未开启强制更新 当前代码有修改 请自行处理后再更新')

        if progress_callback:
            progress_callback(0.4, gt('当前代码无修改'))

        # 获取当前分支
        current_branch = self.get_current_branch()
        if current_branch is None:
            return False, gt('获取当前分支失败')

        if progress_callback:
            progress_callback(0.6, gt('获取当前分支成功'))

        # 切换到目标分支
        target = self.env_config.git_branch
        success, _ = self._checkout_branch(repo, target, allow_local=True)
        if not success:
            return False, gt('切换到目标分支失败')

        if progress_callback:
            progress_callback(0.8, gt('切换到目标分支成功'))

        # 同步远程分支
        sync_result = self._sync_with_remote(repo, target, self.env_config.force_update)
        if not sync_result.success:
            log.error(f'{sync_result.message} [{sync_result.code}] {sync_result.detail or ""}')
            return sync_result.to_tuple()

        if progress_callback:
            progress_callback(1.0, sync_result.message or gt('更新本地代码成功'))

        if sync_result.detail:
            log.info(f'分支同步详情: {sync_result.detail}')

        return sync_result.to_tuple()

    def get_current_branch(self) -> str | None:
        """
        获取当前分支名称
        """
        log.info(gt('检测当前代码分支'))
        try:
            repo = self._open_repo()
            head = repo.head
            return head.shorthand if head else None
        except Exception:
            return None

    def is_current_branch_clean(self) -> bool | None:
        """
        当前分支是否没有任何修改内容
        """
        log.info(gt('检测当前代码是否有修改'))
        try:
            repo = self._open_repo()
            return len(repo.status()) == 0
        except Exception:
            return None

    def is_current_branch_latest(self) -> tuple[bool, str]:
        """
        当前分支是否已经最新 与远程分支一致
        """
        log.info(gt('检测当前代码是否最新'))
        try:
            repo = self._open_repo()
            remote = self._ensure_remote(repo, self.get_git_repository())
            if remote is None:
                return False, gt('更新远程仓库地址失败')

            fetch_result = self._fetch_remote(repo, remote)
            if not fetch_result.success:
                return fetch_result.to_tuple()

            remote_ref = f'refs/remotes/origin/{self.env_config.git_branch}'
            if remote_ref not in repo.references:
                return False, gt('与远程分支不一致')

            remote_oid = repo.references[remote_ref].target
            local_oid = repo.head.target

            # 比较提交是否相同；否则比较树差异
            if local_oid == remote_oid:
                return True, ''

            diff = repo.diff(local_oid, remote_oid)
            is_same = diff.patch is None or len(diff) == 0
            return (is_same, '' if is_same else gt('与远程分支不一致'))

        except Exception as exc:
            log.error(f'检测代码是否最新失败: {exc}', exc_info=True)
            return False, gt('与远程分支不一致')

    def fetch_total_commit(self) -> int:
        """
        获取commit的总数。获取失败时返回0
        """
        log.info(gt('获取commit总数'))
        try:
            repo = self._open_repo()

            # 检查HEAD是否有效
            try:
                head_target = repo.head.target
            except Exception as exc:
                log.error(f'获取HEAD失败: {exc}，可能仓库为空或HEAD不存在')
                return 0

            walker = repo.walk(head_target, pygit2.GIT_SORT_TOPOLOGICAL)
            return sum(1 for _ in walker)
        except Exception as exc:
            log.error(f'获取commit总数失败: {exc}', exc_info=True)
            return 0

    def fetch_page_commit(self, page_num: int, page_size: int) -> list[GitLog]:
        """
        获取分页的commit
        :param page_num: 页码 从0开始
        :param page_size: 每页数量
        :return:
        """
        log.info(f"{gt('获取commit')} 第{page_num + 1}页")
        try:
            repo = self._open_repo()

            # 检查HEAD是否有效
            try:
                head_target = repo.head.target
            except Exception as exc:
                log.error(f'获取HEAD失败: {exc}，可能仓库为空或HEAD不存在')
                return []

            walker = repo.walk(head_target, pygit2.GIT_SORT_TIME)

            logs: list[GitLog] = []
            for idx, commit in enumerate(walker):
                if idx < page_num * page_size:
                    continue
                if len(logs) >= page_size:
                    break

                short_id = str(commit.id)[:7]
                author = commit.author.name if commit.author and commit.author.name else ''
                commit_time = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(commit.commit_time))
                message = commit.message.splitlines()[0] if commit.message else ''

                logs.append(GitLog(short_id, author, commit_time, message))

            return logs
        except Exception as exc:
            log.error(f'获取commit失败: {exc}', exc_info=True)
            return []

    def get_git_repository(self, for_clone: bool = False) -> str:
        """
        获取使用的仓库地址
        """
        repo_type = self.env_config.repository_type
        git_method = self.env_config.git_method

        if repo_type == RepositoryTypeEnum.GITHUB.value.value:
            if git_method == GitMethodEnum.HTTPS.value.value:
                repo = self.project_config.github_https_repository
                if self.env_config.is_gh_proxy and for_clone:
                    return f'{self.env_config.gh_proxy_url}/{repo}'
                return repo
            else:
                return self.project_config.github_ssh_repository

        elif repo_type == RepositoryTypeEnum.GITEE.value.value:
            if git_method == GitMethodEnum.HTTPS.value.value:
                return self.project_config.gitee_https_repository
            else:
                return self.project_config.gitee_ssh_repository

        return ''

    def init_git_proxy(self) -> None:
        """
        初始化 git 使用的代理：通过仓库级配置设置代理，避免污染进程环境
        """
        if self.is_proxy_set or not os.path.exists(DOT_GIT_DIR_PATH):
            return

        try:
            repo = self._open_repo()
            with self._with_proxy(repo):
                pass
            self.is_proxy_set = True
        except Exception as exc:
            log.warning(f'初始化代理失败: {exc}', exc_info=True)

    def update_git_remote(self) -> None:
        """
        更新remote
        """
        if not os.path.exists(DOT_GIT_DIR_PATH):
            return

        try:
            # 不传入repo参数，让_ensure_remote自动获取最新的仓库对象
            self._ensure_remote()
        except Exception as exc:
            log.warning(f'更新远程仓库失败: {exc}')

    def set_safe_dir(self) -> None:
        """
        libgit2 不需要 safe.directory，保留为 no-op
        """
        pass

    def reset_to_commit(self, commit_id: str) -> bool:
        """
        回滚到特定commit
        """
        try:
            repo = self._open_repo()
            obj = repo.revparse_single(commit_id)
            repo.reset(obj.id, pygit2.GIT_RESET_HARD)
            return True
        except Exception as exc:
            log.error(f'回滚到提交失败: {exc}', exc_info=True)
            return False

    def get_current_version(self) -> str | None:
        """
        获取当前代码版本
        """
        logs = self.fetch_page_commit(0, 1)
        return logs[0].commit_id if logs else None

    def get_latest_tag(self) -> tuple[str | None, str | None]:
        """
        获取最新的稳定版与测试版 tag
        """
        try:
            with tempfile.TemporaryDirectory() as td:
                repo = pygit2.init_repository(td, bare=True)
                remote = repo.remotes.create_anonymous(self.get_git_repository())
                heads = remote.list_heads(callbacks=pygit2.RemoteCallbacks(), connect=True)

                # 提取标签名称
                tags = []
                for h in heads:
                    name = getattr(h, "name", None)
                    if name and name.startswith("refs/tags/"):
                        tags.append(name[len("refs/tags/"):])

                # 去重并排序
                versions = sort_tags(list(dict.fromkeys(tags)))

            # 找出最新的稳定版和测试版
            latest_stable: str | None = None
            latest_beta: str | None = None

            for version in versions:
                if '-beta' in version:
                    if latest_beta is None:
                        latest_beta = version
                else:
                    if latest_stable is None:
                        latest_stable = version
                        break

            return latest_stable, latest_beta

        except Exception as exc:
            log.error(f'获取最新标签失败: {exc}', exc_info=True)
            return None, None


def __fetch_latest_code():
    project_config = ProjectConfig()
    env_config = EnvConfig()
    git_service = GitService(project_config, env_config)
    return git_service.fetch_latest_code(progress_callback=None)

def __debug_set_safe_dir():
    project_config = ProjectConfig()
    env_config = EnvConfig()
    git_service = GitService(project_config, env_config)
    return git_service.set_safe_dir()

if __name__ == '__main__':
    __fetch_latest_code()
