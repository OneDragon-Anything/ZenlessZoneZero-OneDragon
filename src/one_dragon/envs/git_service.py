import contextlib
import os
import time
from collections.abc import Callable
from dataclasses import dataclass

import pygit2
from packaging import version

from one_dragon.envs.env_config import EnvConfig, GitMethodEnum, RepositoryTypeEnum
from one_dragon.envs.project_config import ProjectConfig
from one_dragon.utils import os_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log

DOT_GIT_DIR_PATH = os.path.join(os_utils.get_work_dir(), '.git')


@dataclass
class GitLog:
    """Git 提交日志"""
    commit_id: str
    author: str
    commit_time: str
    commit_message: str


class GitService:

    def __init__(self, project_config: ProjectConfig, env_config: EnvConfig):
        self.project_config: ProjectConfig = project_config
        self.env_config: EnvConfig = env_config

        self._repo: pygit2.Repository | None = None
        self._ensure_config_search_path()

    # ================== 私有辅助方法 ==================

    @staticmethod
    def _ensure_config_search_path() -> None:
        """
        通过设置配置搜索路径为空字符串，忽略用户的系统级和全局级 git 配置。
        这可以避免用户的全局配置（如 http.proxy、user.name、SSL 证书路径等）影响程序的 git 操作。
        同时忽略用户可能残留的无效 SSL 证书配置，让 libgit2 使用系统默认的证书验证机制，避免 SSL 证书问题。
        """
        pygit2.settings.search_path[pygit2.enums.ConfigLevel.SYSTEM] = ''  # 系统级配置 (如 /etc/gitconfig)
        pygit2.settings.search_path[pygit2.enums.ConfigLevel.GLOBAL] = ''  # 全局用户配置 (~/.gitconfig)
        pygit2.settings.search_path[pygit2.enums.ConfigLevel.XDG] = ''     # XDG 配置 (~/.config/git/config)
        pygit2.settings.owner_validation = False  # 禁用仓库所有权验证

    def _open_repo(self, refresh: bool = False) -> pygit2.Repository:
        """打开仓库（带缓存）"""
        if refresh:
            self._repo = None

        if self._repo is None:
            work_dir = os_utils.get_work_dir()
            # 检查是否是有效的 git 仓库
            if not pygit2.discover_repository(work_dir):
                raise pygit2.GitError(f'目录 {work_dir} 不是有效的 Git 仓库')
            self._repo = pygit2.Repository(work_dir)

        return self._repo

    def _ensure_remote(self, for_clone: bool = False) -> pygit2.Remote | None:
        """确保远程仓库配置正确

        Args:
            for_clone: 是否用于克隆（会影响代理地址的选择）

        Returns:
            Remote对象，失败时返回None
        """
        remote_url = self._get_git_repository(for_clone)
        if not remote_url:
            raise pygit2.GitError('未能获取有效的远程仓库地址')

        remote_name = 'origin'

        # 获取最新的仓库对象
        repo = self._open_repo()

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

    def _get_git_repository(self, for_clone: bool = False) -> str:
        """获取仓库地址

        Args:
            for_clone: 是否用于克隆
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

        Returns:
            是否成功
        """
        log.info(gt('获取远程代码'))

        try:
            remote = self._ensure_remote()
            branch = self.env_config.git_branch
            refspec = f'+refs/heads/{branch}:refs/remotes/{remote.name}/{branch}'

            repo = self._open_repo()
            with contextlib.suppress(Exception):
                repo.config.set_multivar(f'remote.{remote.name}.fetch', '.*', refspec)

            remote.fetch(
                refspecs=[refspec],
                proxy=self._get_proxy_address(),
                depth=1
            )
            log.info(gt('获取远程代码成功'))
            return True
        except Exception:
            log.error('获取远程代码失败', exc_info=True)
            return False

    def _reset_to_oid(self, target_oid: pygit2.Oid) -> bool:
        """重置仓库到指定提交

        Args:
            target_oid: 目标提交ID

        Returns:
            是否成功
        """
        try:
            repo = self._open_repo()
            repo.reset(target_oid, pygit2.GIT_RESET_HARD)
            return True
        except Exception:
            log.error(f'重置到提交 {target_oid} 失败', exc_info=True)
            return False

    def _is_current_branch_clean(self) -> bool | None:
        """
        当前分支是否没有任何修改内容
        """
        log.info(gt('检测当前代码是否有修改'))
        try:
            repo = self._open_repo()
            return len(repo.status()) == 0
        except Exception:
            log.error('检测当前代码是否有修改失败', exc_info=True)
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

        branch = self.env_config.git_branch
        local_ref = f'refs/heads/{branch}'
        remote_ref = f'refs/remotes/origin/{branch}'

        # 确保本地分支存在
        if local_ref not in repo.references:
            # 尝试从远程分支创建
            if remote_ref in repo.references:
                try:
                    remote_commit = repo.get(repo.references[remote_ref].target)
                    repo.create_branch(branch, remote_commit)
                    log.debug(f'从远程分支创建本地分支: {branch}')
                except Exception:
                    log.error(f'创建本地分支 {branch} 失败', exc_info=True)
                    return False
            else:
                log.error(f'本地和远程都不存在分支 {branch}')
                return False

        # 配置远程追踪
        try:
            remote = self._ensure_remote()
            local_branch = repo.branches.get(branch)
            remote_branch = repo.lookup_branch(f'{remote.name}/{branch}', pygit2.GIT_BRANCH_REMOTE)
            if local_branch and remote_branch:
                local_branch.upstream = remote_branch
                log.debug(f'配置分支追踪: {branch} -> {remote.name}/{branch}')
        except Exception:
            log.error('配置远程追踪失败', exc_info=True)

        # 切换到分支
        try:
            repo.checkout(local_ref, strategy=pygit2.GIT_CHECKOUT_FORCE)
            repo.set_head(local_ref)
            log.info(f'成功切换到分支 {branch}')
            return True
        except Exception:
            log.error(f'切换到分支 {branch} 失败', exc_info=True)
            return False

    def _sync_with_remote(self, force: bool) -> tuple[bool, str]:
        """同步远程分支到本地

        Args:
            force: 是否强制更新（重置本地修改）

        Returns:
            是否成功, 消息
        """
        try:
            repo = self._open_repo()
        except Exception:
            msg = gt('打开本地仓库失败')
            log.error(msg, exc_info=True)
            return False, msg

        # 检查远程分支是否存在
        remote_ref = f'refs/remotes/origin/{self.env_config.git_branch}'
        if remote_ref not in repo.references:
            msg = f'{gt("远程分支不存在")}: {remote_ref}'
            log.error(msg)
            return False, msg

        try:
            remote_oid = repo.references[remote_ref].target
        except Exception:
            msg = gt('获取远程分支提交失败')
            log.error(msg, exc_info=True)
            return False, msg

        # 获取本地 HEAD
        local_oid = getattr(repo.head, 'target', None) if hasattr(repo, 'head') else None

        # HEAD 不存在，直接重置
        if local_oid is None:
            if force:
                if self._reset_to_oid(remote_oid):
                    msg = gt('更新本地代码成功')
                    log.debug(f'重置到远程提交成功: {remote_oid}')
                    return True, msg

                msg = f'{gt("重置到远程提交失败")}: {remote_oid}'
                log.error(msg)
                return False, msg

            msg = gt('HEAD 不存在且未开启强制更新')
            log.error(msg)
            return False, msg

        # 如果相同则无需更新
        if local_oid == remote_oid:
            log.info(f'本地代码已是最新: {local_oid}')
            return True, gt('本地代码已是最新')

        # 检查是否可以快进
        can_fast_forward = False
        with contextlib.suppress(Exception):
            can_fast_forward = repo.descendant_of(remote_oid, local_oid)

        # 快进更新
        if can_fast_forward:
            if self._reset_to_oid(remote_oid):
                msg = gt('更新本地代码成功')
                log.debug(f'快进更新成功: {local_oid} -> {remote_oid}')
                return True, msg

            msg = f'{gt("快进更新失败")}: {local_oid} -> {remote_oid}'
            log.error(msg)
            return False, msg

        # 强制更新
        if force:
            if self._reset_to_oid(remote_oid):
                msg = gt('更新本地代码成功')
                log.debug(f'强制更新成功: {local_oid} -> {remote_oid}')
                return True, msg

            msg = f'{gt("强制更新失败")}: {local_oid} -> {remote_oid}'
            log.error(msg)
            return False, msg

        # 需要手动处理
        msg = f'{gt("本地代码有修改且无法快进更新，请手动处理后再更新")}: {local_oid} -> {remote_oid}'
        log.error(msg)
        return False, msg

    def _clone_repository(self, progress_callback: Callable[[float, str], None] | None = None) -> tuple[bool, str]:
        """
        初始化本地仓库并同步远程目标分支
        """
        work_dir = os_utils.get_work_dir()

        # 初始化仓库
        if progress_callback:
            progress_callback(1/5, gt('初始化本地 Git 仓库'))

        try:
            pygit2.init_repository(work_dir, False)
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

        is_clean = self._is_current_branch_clean()
        if is_clean is None:
            return False, gt('检测当前代码状态失败')

        # 工作区不干净且未开启强制更新时，拒绝操作
        if not is_clean and not self.env_config.force_update:
            return False, gt('当前代码有修改 请自行处理或开启强制更新')

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

    def fetch_latest_code(self, progress_callback: Callable[[float, str], None] | None = None) -> tuple[bool, str]:
        """
        更新最新的代码：不存在 .git 则克隆，存在则拉取并更新分支
        """
        if not os.path.exists(DOT_GIT_DIR_PATH):
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
        try:
            if not self._fetch_remote():
                return False, gt('获取远程代码失败')

            repo = self._open_repo()
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

        except Exception:
            log.error('检测代码是否最新失败', exc_info=True)
            return False, gt('与远程分支不一致')

    def fetch_total_commit(self) -> int:
        """
        获取commit的总数。获取失败时返回0
        """
        log.info(gt('获取commit总数'))
        try:
            repo = self._open_repo()
            head_target = repo.head.target
            walker = repo.walk(head_target, pygit2.GIT_SORT_TOPOLOGICAL)
            return sum(1 for _ in walker)
        except Exception:
            log.error('获取commit总数失败，可能仓库为空或HEAD不存在', exc_info=True)
            return 0

    def fetch_page_commit(self, page_num: int, page_size: int) -> list[GitLog]:
        """获取分页commit

        Args:
            page_num: 页码（从0开始）
            page_size: 每页数量

        Returns:
            GitLog列表
        """
        log.info(f"{gt('获取commit')} 第{page_num + 1}页")
        try:
            repo = self._open_repo()
            head_target = repo.head.target
            walker = repo.walk(head_target, pygit2.GIT_SORT_TIME)

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
        except Exception:
            log.error('获取commit失败，可能仓库为空或HEAD不存在', exc_info=True)
            return []

    def update_remote(self) -> None:
        """
        更新remote
        """
        if not os.path.exists(DOT_GIT_DIR_PATH):
            return

        try:
            self._ensure_remote()
        except Exception:
            log.error('更新远程仓库地址失败', exc_info=True)

    def reset_to_commit(self, commit_id: str) -> bool:
        """
        回滚到特定commit
        """
        try:
            repo = self._open_repo()
            obj = repo.revparse_single(commit_id)
            return self._reset_to_oid(obj.id)
        except Exception:
            log.error(f'回滚到提交 {commit_id} 失败', exc_info=True)
            return False

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
        if not os.path.exists(DOT_GIT_DIR_PATH):
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
