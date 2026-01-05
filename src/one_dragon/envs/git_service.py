import contextlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from packaging import version
from pygit2 import (
    Oid,
    Remote,
    Repository,
    Walker,
    discover_repository,
    init_repository,
    settings,
)
from pygit2.enums import CheckoutStrategy, ConfigLevel, ResetMode, SortMode

from one_dragon.envs.env_config import EnvConfig, RepositoryTypeEnum
from one_dragon.envs.project_config import ProjectConfig
from one_dragon.utils import os_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log


@dataclass
class GitLog:
    """Git 提交日志"""
    commit_id: str
    author: str
    commit_time: str
    commit_message: str


class GitService:

    def __init__(self, project_config: ProjectConfig, env_config: EnvConfig, repo_dir: str | None = None):
        self.project_config: ProjectConfig = project_config
        self.env_config: EnvConfig = env_config

        if repo_dir:
            if not Path(repo_dir).is_absolute():
                repo_dir = str(Path(os_utils.get_work_dir()) / repo_dir)
        else:
            repo_dir = os_utils.get_work_dir()
        self.repo_dir: str = repo_dir

        self._repo: Repository | None = None
        self._ensure_config_search_path()

    # ================== 私有辅助方法 ==================

    @staticmethod
    def _ensure_config_search_path() -> None:
        """
        通过设置配置搜索路径为空字符串，忽略用户的系统级和全局级 git 配置。
        这可以避免用户的全局配置（如 http.proxy、user.name、SSL 证书路径等）影响程序的 git 操作。
        同时忽略用户可能残留的无效 SSL 证书配置，让 libgit2 使用系统默认的证书验证机制，避免 SSL 证书问题。
        """
        settings.search_path[ConfigLevel.PROGRAMDATA] = ''  # 机器范围 (C:\ProgramData\Git\config)
        settings.search_path[ConfigLevel.SYSTEM] = ''       # 系统级 (如 C:\Program Files\Git\mingw64\etc\gitconfig)
        settings.search_path[ConfigLevel.GLOBAL] = ''       # 用户全局 (%USERPROFILE%\.gitconfig)
        settings.search_path[ConfigLevel.XDG] = ''          # XDG 配置 (%USERPROFILE%\.config\git\config)
        settings.owner_validation = False                   # 禁用仓库所有权验证

    def _open_repo(self, refresh: bool = False) -> Repository:
        """打开仓库（带缓存）"""
        if refresh:
            self._repo = None

        if self._repo is None:
            # 检查是否是有效的 git 仓库
            git_dir = discover_repository(self.repo_dir)
            if not git_dir:
                raise ValueError(f'目录 {self.repo_dir} 不是有效的 Git 仓库')
            self._repo = Repository(git_dir)

        return self._repo

    def _ensure_remote(self) -> Remote:
        """确保远程仓库配置正确

        Returns:
            Remote 对象
        """
        remote_url = self._get_git_repository()
        if not remote_url:
            raise ValueError('未能获取有效的远程仓库地址')

        repo = self._open_repo()
        remote_name = self.env_config.git_remote

        # 检查远程是否已存在
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

    def _get_git_repository(self) -> str:
        """获取仓库地址"""
        repo_type = self.env_config.repository_type

        if repo_type == RepositoryTypeEnum.GITHUB.value.value:
            repo = self.project_config.github_https_repository
            if self.env_config.is_gh_proxy:
                return f'{self.env_config.gh_proxy_url}/{repo}'
            return repo

        elif repo_type == RepositoryTypeEnum.GITEE.value.value:
            return self.project_config.gitee_https_repository

        return ''

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

    def _fetch_remote(self) -> bool:
        """获取远程代码

        根据本地是否存在有内容的同名分支来决定拉取深度：
        - 若本地不存在该分支或分支为空，则使用深度1（拉取最新1条）
        - 若本地已有该分支且有提交历史，则使用深度0（增量拉取）

        Returns:
            是否成功
        """
        log.info(gt('获取远程代码'))

        try:
            repo = self._open_repo()
            remote = self._ensure_remote()
            branch_name = self.env_config.git_branch
            refspecs = [f'+refs/heads/{branch_name}:refs/remotes/{remote.name}/{branch_name}']
            proxy = self._get_proxy_address()

            # 检查本地是否存在该分支且有提交历史
            depth = 1  # 默认深度为1
            local_ref = f'refs/heads/{branch_name}'
            if local_ref in repo.references:
                # 分支存在，检查是否有提交历史
                branch_target = repo.references[local_ref].target
                if branch_target is not None:
                    # 有提交历史，使用增量拉取
                    depth = 0

            try:
                remote.fetch(refspecs=refspecs, proxy=proxy, depth=depth)
            except KeyError as e:
                # 如果是因为找不到对象导致的错误，使用 depth=1 重试
                if 'object not found' in str(e) and depth == 0:
                    log.warning(f'增量拉取失败({e})，使用 depth=1 重试')
                    remote.fetch(refspecs=refspecs, proxy=proxy, depth=1)
                else:
                    raise

            log.info(gt('获取远程代码成功'))
            return True
        except Exception:
            log.error('获取远程代码失败', exc_info=True)
            return False

    def _reset_hard(self, target_id: str | Oid) -> bool:
        """硬重置仓库到指定提交
        会丢弃工作区和暂存区的所有修改

        Args:
            target_id: 目标提交ID，支持以下格式:
                - OID 对象: pygit2.Oid 实例
                - 提交哈希: 完整或短格式的 commit hash (如 'abc123' 或 'abc123def456...')
                - 引用名称: 分支名、标签名等 (如 'main', 'v1.0.0')
                - 相对引用: HEAD~1, HEAD^, origin/main 等

        Returns:
            是否成功
        """
        try:
            repo = self._open_repo()
            # 如果是字符串，需要先解析为OID对象
            if isinstance(target_id, str):
                obj = repo.revparse_single(target_id)
                target_oid = obj.id
            else:
                target_oid = target_id

            repo.reset(target_oid, ResetMode.HARD)
            return True
        except Exception:
            log.error(f'重置到提交 {target_id} 失败', exc_info=True)
            return False

    def _get_local_and_remote_oid(self) -> tuple[str | None, str | None, str]:
        """获取本地HEAD和远程分支的提交ID

        Returns:
            (本地提交ID, 远程提交ID, 错误消息) - 远程提交ID为None时表示失败
        """
        try:
            repo = self._open_repo()
            local_oid = repo.head.target
        except Exception:
            local_oid = None
            msg = gt('获取本地提交信息失败')
            log.error(msg, exc_info=True)
            return local_oid, None, msg

        # 检查远程分支是否存在
        remote_branch_name = f'{self.env_config.git_remote}/{self.env_config.git_branch}'
        remote_ref = f'refs/remotes/{remote_branch_name}'
        if remote_ref not in repo.references:
            msg = f'{gt("远程分支不存在")}: {remote_branch_name}'
            log.error(msg)
            return local_oid, None, msg

        try:
            remote_oid = repo.references[remote_ref].target
        except Exception:
            msg = gt('获取远程提交信息失败')
            log.error(msg, exc_info=True)
            return local_oid, None, msg

        return local_oid, remote_oid, ''

    def _validate_working_directory(self) -> tuple[bool, str]:
        """验证工作区状态

        Returns:
            (是否可以继续, 错误消息)
        """
        log.info(gt('检测当前代码是否有修改'))
        try:
            repo = self._open_repo()
            is_clean = len(repo.status()) == 0
        except Exception:
            log.error('检测当前代码是否有修改失败', exc_info=True)
            return False, gt('检测当前代码状态失败')

        if not is_clean and not self.env_config.force_update:
            return False, gt('当前代码有修改 请自行处理或开启强制更新')

        return True, ''

    def _get_commit_walker(self, sort_mode: SortMode = SortMode.TOPOLOGICAL) -> Walker | None:
        """获取commit遍历器

        Args:
            sort_mode: 排序模式

        Returns:
            commit遍历器，失败时返回None
        """
        try:
            repo = self._open_repo()
            head_target = repo.head.target
            return repo.walk(head_target, sort_mode)
        except Exception:
            log.error('获取commit遍历器失败', exc_info=True)
            return None

    def _checkout_branch(self) -> bool:
        """切换到指定分支

        Returns:
            是否成功
        """
        try:
            repo = self._open_repo()
        except Exception:
            log.error('打开本地仓库失败', exc_info=True)
            return False

        remote_name = self.env_config.git_remote
        branch_name = self.env_config.git_branch
        remote_branch_name = f'{remote_name}/{branch_name}'
        local_ref = f'refs/heads/{branch_name}'
        remote_ref = f'refs/remotes/{remote_branch_name}'

        # 确保本地分支存在
        if local_ref not in repo.references:
            # 尝试从远程分支创建
            if remote_ref in repo.references:
                try:
                    remote_commit = repo.get(repo.references[remote_ref].target)
                    repo.create_branch(branch_name, remote_commit)
                    log.debug(f'从远程分支创建本地分支: {branch_name}')
                except Exception:
                    log.error(f'创建本地分支 {branch_name} 失败', exc_info=True)
                    return False
            else:
                log.error(f'本地和远程都不存在分支 {branch_name}')
                return False

        # 切换到分支
        try:
            repo.checkout(local_ref, strategy=CheckoutStrategy.FORCE)
            repo.set_head(local_ref)
            log.info(f'成功切换到分支 {branch_name}')
            return True
        except Exception:
            log.error(f'切换到分支 {branch_name} 失败', exc_info=True)
            return False

    def _sync_with_remote(self, force: bool) -> tuple[bool, str]:
        """同步远程分支到本地

        Args:
            force: 是否强制更新（重置本地修改）

        Returns:
            (是否成功, 消息)
        """
        # 获取本地和远程的提交ID
        local_oid, remote_oid, msg = self._get_local_and_remote_oid()
        if remote_oid is None:
            return False, msg

        # HEAD 不存在，直接重置
        if local_oid is None:
            if force:
                if self._reset_hard(remote_oid):
                    msg = gt('更新本地代码成功')
                    log.debug(f'重置到远程提交成功: {str(remote_oid)[:7]}')
                    return True, msg

                msg = gt('重置到远程提交失败')
                log.error(f'{msg}: {str(remote_oid)[:7]}')
                return False, msg

            msg = gt('HEAD 不存在且未开启强制更新')
            log.error(msg)
            return False, msg

        # 如果相同则无需更新
        if local_oid == remote_oid:
            log.info(f'本地代码已是最新: {str(local_oid)[:7]}')
            return True, gt('本地代码已是最新')

        # 检查是否可以快进
        can_fast_forward = False
        with contextlib.suppress(Exception):
            repo = self._open_repo()
            can_fast_forward = repo.descendant_of(remote_oid, local_oid) and len(repo.status()) == 0

        # 快进更新
        if can_fast_forward:
            if self._reset_hard(remote_oid):
                msg = gt('更新本地代码成功')
                log.debug(f'快进更新成功: {str(local_oid)[:7]} -> {str(remote_oid)[:7]}')
                return True, msg

            msg = gt('快进更新失败')
            log.error(f'{msg}: {str(local_oid)[:7]} -> {str(remote_oid)[:7]}')
            return False, msg

        # 强制更新
        if force:
            if self._reset_hard(remote_oid):
                msg = gt('更新本地代码成功')
                log.debug(f'强制更新成功: {str(local_oid)[:7]} -> {str(remote_oid)[:7]}')
                return True, msg

            msg = gt('强制更新失败')
            log.error(f'{msg}: {str(local_oid)[:7]} -> {str(remote_oid)[:7]}')
            return False, msg

        # 需要手动处理
        msg = gt('本地代码有修改且无法快进更新，请手动处理后再更新')
        log.error(f'{msg}: {str(local_oid)[:7]} -> {str(remote_oid)[:7]}')
        return False, msg

    def _clone_repository(self, progress_callback: Callable[[float, str], None] | None = None) -> tuple[bool, str]:
        """
        初始化本地仓库并同步远程目标分支
        """
        # 初始化仓库
        if progress_callback:
            progress_callback(1/5, gt('初始化本地 Git 仓库'))

        try:
            init_repository(self.repo_dir)
        except Exception:
            msg = gt('初始化本地 Git 仓库失败')
            log.error(msg, exc_info=True)
            return False, msg

        # 获取远程代码
        if progress_callback:
            progress_callback(2/5, gt('获取远程代码'))

        if not self._fetch_remote():
            return False, gt('获取远程代码失败')

        # 切换到目标分支
        if progress_callback:
            progress_callback(3/5, gt('切换到目标分支'))

        if not self._checkout_branch():
            return False, gt('切换到目标分支失败')

        # 同步远程代码
        if progress_callback:
            progress_callback(4/5, gt('同步远程代码'))

        success, message = self._sync_with_remote(force=True)
        if not success:
            return False, message

        if progress_callback:
            progress_callback(5/5, gt('克隆仓库成功'))

        return True, gt('克隆仓库成功')

    def _fetch_and_checkout_latest_branch(self, progress_callback: Callable[[float, str], None] | None = None) -> tuple[bool, str]:
        """
        切换到最新的目标分支并更新代码
        """
        log.info(gt('核对当前仓库'))

        # 获取远程代码
        if progress_callback:
            progress_callback(1/5, gt('获取远程代码'))

        if not self._fetch_remote():
            return False, gt('获取远程代码失败')

        # 检查工作区状态
        if progress_callback:
            progress_callback(2/5, gt('检查工作区状态'))

        success, message = self._validate_working_directory()
        if not success:
            return False, message

        # 切换到目标分支
        if progress_callback:
            progress_callback(3/5, gt('切换到目标分支'))

        if not self._checkout_branch():
            return False, gt('切换到目标分支失败')

        # 同步远程分支
        if progress_callback:
            progress_callback(4/5, gt('同步远程分支'))

        success, message = self._sync_with_remote(self.env_config.force_update)
        if not success:
            return False, message

        if progress_callback:
            progress_callback(5/5, message)

        return True, message

    # ================== 公共 API ==================

    def check_repo_exists(self) -> bool:
        """
        检查本地仓库是否存在
        """
        return discover_repository(self.repo_dir) is not None

    def fetch_latest_code(self, progress_callback: Callable[[float, str], None] | None = None) -> tuple[bool, str]:
        """
        更新最新的代码：不存在 .git 则克隆，存在则拉取并更新分支
        """
        if not self.check_repo_exists():
            return self._clone_repository(progress_callback)
        else:
            return self._fetch_and_checkout_latest_branch(progress_callback)

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
            log.error('获取当前分支失败', exc_info=True)
            return None

    def is_current_branch_latest(self) -> tuple[bool, str]:
        """
        当前分支是否已经最新 与远程分支一致
        """
        log.info(gt('检测当前代码是否最新'))

        if not self._fetch_remote():
            return False, gt('获取远程代码失败')

        # 获取本地和远程的提交ID
        local_oid, remote_oid, msg = self._get_local_and_remote_oid()
        if local_oid is None or remote_oid is None:
            log.error(msg)
            return False, msg

        # 比较提交是否相同
        if local_oid == remote_oid:
            return True, ''

        return False, gt('与远程分支不一致')

    def fetch_total_commit(self) -> int:
        """
        获取commit的总数。获取失败时返回0
        """
        log.info(gt('获取commit总数'))
        walker = self._get_commit_walker()
        return sum(1 for _ in walker) if walker else 0

    def fetch_page_commit(self, page_num: int, page_size: int) -> list[GitLog]:
        """获取分页commit

        Args:
            page_num: 页码（从0开始）
            page_size: 每页数量

        Returns:
            GitLog列表
        """
        log.info(f"{gt('获取commit')} 第{page_num + 1}页")
        walker = self._get_commit_walker()
        if not walker:
            return []

        logs: list[GitLog] = []
        for idx, commit in enumerate(walker):
            if idx < page_num * page_size:
                continue
            if len(logs) >= page_size:
                break

            short_id = str(commit.id)[:7]
            author = commit.author.name if commit.author and commit.author.name else ''
            commit_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(commit.commit_time))
            message = commit.message.splitlines()[0] if commit.message else ''

            logs.append(GitLog(short_id, author, commit_time, message))

        return logs

    def update_remote(self) -> None:
        """
        更新remote
        """
        if not self.check_repo_exists():
            return

        try:
            self._ensure_remote()
        except Exception:
            log.error('更新远程仓库地址失败', exc_info=True)

    def reset_to_commit(self, commit_id: str) -> bool:
        """
        回滚到特定commit
        """
        return self._reset_hard(commit_id)

    def get_current_version(self) -> str | None:
        """
        获取当前代码版本
        """
        logs = self.fetch_page_commit(0, 1)
        return logs[0].commit_id if logs else None

    def get_latest_tag(self) -> tuple[str, str]:
        """获取最新tag，未找到时返回空字符串

        Returns:
            (最新稳定版, 最新测试版)
        """
        # 如果不存在本地仓库，返回空
        if not self.check_repo_exists():
            return '', ''

        try:
            remote = self._ensure_remote()
            heads = remote.list_heads(proxy=self._get_proxy_address())
        except Exception:
            log.error('获取最新标签失败', exc_info=True)
            return '', ''

        # 提取标签名称并解析为 Version 对象
        tags: dict[str, version.Version] = {}
        for h in heads:
            if h.name.startswith("refs/tags/"):
                tag = h.name[len("refs/tags/"):]
                # 验证是否为有效版本
                with contextlib.suppress(version.InvalidVersion):
                    parsed = version.parse(tag)
                    tags[tag] = parsed

        # 按 Version 对象排序
        versions = sorted(tags.items(), key=lambda x: x[1], reverse=True)

        # 找出最新的稳定版和测试版
        latest_stable = ''
        latest_beta = ''

        for tag, ver in versions:
            if ver.is_prerelease:
                if not latest_beta:
                    latest_beta = tag
            else:
                if not latest_stable:
                    latest_stable = tag
                    break

        return latest_stable, latest_beta


def __fetch_latest_code():
    project_config = ProjectConfig()
    env_config = EnvConfig()
    git_service = GitService(project_config, env_config)
    return git_service.fetch_latest_code(progress_callback=None)

if __name__ == '__main__':
    __fetch_latest_code()
