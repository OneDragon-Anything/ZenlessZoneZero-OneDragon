import contextlib
import sys
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import yaml
from packaging import version
from pygit2 import (
    Blob,
    Oid,
    Remote,
    RemoteCallbacks,
    Repository,
    Walker,
    discover_repository,
    init_repository,
    settings,
)
from pygit2.enums import CheckoutStrategy, ConfigLevel, ResetMode, SortMode

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.envs.env_config import EnvConfig
from one_dragon.envs.project_config import ProjectConfig
from one_dragon.envs.repo_config import RepoConfig, RepositoryItem
from one_dragon.utils import os_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log

REMOTE_FETCH_TIMEOUT = 30.0


@dataclass
class GitLog:
    """Git 提交日志"""
    commit_id: str
    author: str
    commit_time: str
    commit_message: str


class _FetchProgressRemoteCallbacks(RemoteCallbacks):
    """转发 Git 传输进度、服务端消息和引用更新信息。"""

    def __init__(
        self,
        progress_callback: Callable[[float, str], None] | None,
        timeout: float | None = REMOTE_FETCH_TIMEOUT,
    ) -> None:
        super().__init__()
        self._progress_callback: Callable[[float, str], None] | None = progress_callback
        self._timeout: float | None = timeout
        self._started_at: float = time.monotonic()
        self._progress: float = 0.0
        self._last_message: str | None = None
        self._last_sideband_message: str | None = None
        self._last_log_at: float | None = None

    def _check_timeout(self) -> None:
        if self._timeout is not None and time.monotonic() - self._started_at >= self._timeout:
            raise TimeoutError(f'Git 远程拉取超过 {self._timeout:g} 秒')

    def _emit(self, message: str, progress: float | None = None) -> None:
        if self._progress_callback is not None:
            self._progress_callback(self._progress if progress is None else progress, message)
        else:
            log.info(message)

    def transfer_progress(self, stats: object) -> None:
        self._check_timeout()
        total_objects = int(getattr(stats, 'total_objects', 0) or 0)
        received_objects = int(getattr(stats, 'received_objects', 0) or 0)
        received_bytes = int(getattr(stats, 'received_bytes', 0) or 0)

        fetch_message = gt('拉取对象')
        is_final = total_objects > 0 and received_objects >= total_objects
        if total_objects > 0:
            progress = min(max(received_objects / total_objects, 0.0), 1.0)
            message = f'{fetch_message} {received_objects}/{total_objects} ({round(progress * 100)}%)'
        else:
            progress = 0.0
            received_mb = received_bytes / 1024 / 1024
            message = f'{fetch_message} {received_mb:.2f} MB'

        self._progress = progress
        if message == self._last_message:
            return

        now = time.monotonic()
        if not is_final and self._last_log_at is not None and now - self._last_log_at < 0.2:
            return

        self._last_log_at = now
        self._last_message = message
        self._emit(message, progress)

    def sideband_progress(self, string: str) -> None:
        self._check_timeout()
        message = string.strip()
        if not message or message == self._last_sideband_message:
            return
        self._last_sideband_message = message
        self._emit(f'远程消息: {message}')

    def update_tips(self, refname: str, old: Oid, new: Oid) -> None:
        self._check_timeout()
        self._emit(f'更新引用: {refname}')


class GitService:

    def __init__(
        self,
        project_config: ProjectConfig,
        env_config: EnvConfig,
        repo_config: RepoConfig,
        repo_dir: str | None = None,
    ):
        self.project_config: ProjectConfig = project_config
        self.env_config: EnvConfig = env_config
        self.repo_config: RepoConfig = repo_config

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

    def _ensure_remote(self, remote_url: str | None = None) -> Remote:
        """确保指定远程仓库地址配置到当前本地 remote。"""
        if remote_url is None:
            remote_url = self._get_git_repository()
        if not remote_url:
            raise ValueError('未能获取有效的远程仓库地址')

        repo = self._open_repo()
        remote_name = self.env_config.git_remote

        if remote_name in repo.remotes.names():
            remote = repo.remotes[remote_name]
            if remote.url == remote_url:
                return remote

            log.info(f'更新远程仓库地址: {remote.url} -> {remote_url}')
            repo.remotes.set_url(remote_name, remote_url)
            return repo.remotes[remote_name]

        log.info(f'创建远程仓库: {remote_name} -> {remote_url}')
        repo.remotes.create(remote_name, remote_url)
        return repo.remotes[remote_name]

    def _get_repository_item(self, repository: RepositoryItem) -> ConfigItem:
        """获取代码源配置项。"""
        return repository.config_item

    def _find_repository(self, value: str) -> RepositoryItem | None:
        """按仓库 ID、显示标题或 URL 查找代码源。"""
        return self.repo_config.find_repository(value)

    def _get_repository_url(self, repository: RepositoryItem, use_gh_proxy: bool = True) -> str:
        """获取指定代码源的 HTTPS 地址。"""
        repository_url = repository.url
        if use_gh_proxy and repository.use_proxy and self.env_config.is_gh_proxy:
            return f'{self.env_config.gh_proxy_url.rstrip("/")}/{repository_url}'
        return repository_url

    def _get_repository_candidates(self) -> list[tuple[RepositoryItem, str]]:
        """按用户首选和 YAML 声明顺序生成代码源候选列表。"""
        preferred_repository = self._find_repository(self.env_config.repository_url)
        candidates: list[tuple[RepositoryItem, str]] = []
        for repository in [preferred_repository, *self.repo_config.repositories]:
            if repository is None or any(candidate[0] is repository for candidate in candidates):
                continue
            repository_url = self._get_repository_url(repository)
            if repository_url:
                candidates.append((repository, repository_url))
        return candidates

    def _get_git_repository(self) -> str:
        """获取首选代码源地址。"""
        preferred_repository = self._find_repository(self.env_config.repository_url)
        if preferred_repository is None:
            preferred_repository = self.repo_config.primary_repository
        return self._get_repository_url(preferred_repository)

    def _restore_origin(self) -> bool:
        """将当前本地 remote 恢复为项目主仓库 HTTPS 地址。"""
        primary_url = self._get_repository_url(self.repo_config.primary_repository, use_gh_proxy=False)
        if not primary_url:
            return False
        try:
            self._ensure_remote(primary_url)
            return True
        except Exception:
            log.error('恢复主仓库远程地址失败', exc_info=True)
            return False

    @contextlib.contextmanager
    def _temporary_fetch_timeout(self) -> Iterator[None]:
        """临时设置 pygit2 的连接和网络读写超时，并恢复原值。"""
        timeout_ms = int(REMOTE_FETCH_TIMEOUT * 1000)
        setting_names = ('server_connect_timeout', 'server_timeout')
        original_values: dict[str, int] = {}
        try:
            for setting_name in setting_names:
                if hasattr(settings, setting_name):
                    original_values[setting_name] = int(getattr(settings, setting_name))
                    setattr(settings, setting_name, timeout_ms)
            yield
        finally:
            for setting_name, original_value in original_values.items():
                setattr(settings, setting_name, original_value)

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

    def _create_fetch_callbacks(
        self,
        progress_callback: Callable[[float, str], None] | None,
        stage_start: float,
        stage_end: float,
    ) -> RemoteCallbacks:
        """创建远程拉取回调。"""
        def stage_progress_callback(progress: float, message: str) -> None:
            mapped_progress = stage_start + (stage_end - stage_start) * progress
            if progress_callback is not None:
                progress_callback(mapped_progress, message)

        return _FetchProgressRemoteCallbacks(stage_progress_callback, REMOTE_FETCH_TIMEOUT)

    def _fetch_remote_once(
        self,
        remote_url: str,
        progress_callback: Callable[[float, str], None] | None,
        stage_start: float,
        stage_end: float,
    ) -> None:
        """从单个代码源拉取远程代码。"""
        repo = self._open_repo()
        remote = self._ensure_remote(remote_url)
        branch_name = self.env_config.git_branch
        refspecs = [f'+refs/heads/{branch_name}:refs/remotes/{remote.name}/{branch_name}']
        proxy = self._get_proxy_address()
        callbacks = self._create_fetch_callbacks(progress_callback, stage_start, stage_end)

        depth = 1
        local_ref = f'refs/heads/{branch_name}'
        if local_ref in repo.references and repo.references[local_ref].target is not None:
            depth = 0

        try:
            with self._temporary_fetch_timeout():
                remote.fetch(refspecs=refspecs, proxy=proxy, depth=depth, callbacks=callbacks)
        except KeyError as e:
            if 'object not found' in str(e) and depth == 0:
                log.warning(f'增量拉取失败({e})，使用 depth=1 重试')
                with self._temporary_fetch_timeout():
                    remote.fetch(refspecs=refspecs, proxy=proxy, depth=1, callbacks=callbacks)
            else:
                raise

    def _fetch_remote(
        self,
        progress_callback: Callable[[float, str], None] | None = None,
        stage_start: float = 0.0,
        stage_end: float = 1.0,
    ) -> bool:
        """按候选代码源顺序拉取远程代码，失败后自动回退。"""
        log.info(gt('拉取远程代码...'))
        success = False
        used_repository: RepositoryItem | None = None

        try:
            for repository, repository_url in self._get_repository_candidates():
                repository_name = self._get_repository_item(repository).ui_text
                log.info(f'尝试代码源: {repository_name}')
                if progress_callback is not None:
                    progress_callback(stage_start, f'尝试代码源: {repository_name}')
                try:
                    self._fetch_remote_once(repository_url, progress_callback, stage_start, stage_end)
                    success = True
                    used_repository = repository
                    break
                except Exception:
                    log.warning(f'代码源 {repository_name} 拉取失败，尝试下一个代码源', exc_info=True)
        finally:
            restored = self._restore_origin()

        if not restored:
            log.error('拉取结束后无法恢复主仓库远程地址')
            return False
        if not success:
            log.error('所有代码源均拉取失败')
            return False

        used_repository_name = self._get_repository_item(used_repository).ui_text if used_repository else ''
        log.info(f'远程代码拉取成功，实际代码源: {used_repository_name}')
        if progress_callback is not None:
            progress_callback(stage_end, gt('拉取远程代码成功'))
        return True

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

    def _get_file_at_commit(self, commit_oid: Oid, file_path: str) -> bytes | None:
        """获取指定 commit 中某文件的内容

        Args:
            commit_oid: 提交 OID
            file_path: 相对于仓库根目录的文件路径（如 'deploy/module_manifest.py'）

        Returns:
            文件内容的字节，文件不存在时返回 None
        """
        try:
            repo = self._open_repo()
            obj = repo.revparse_single(f'{commit_oid}:{file_path}')
            if isinstance(obj, Blob):
                return obj.data
            return None
        except (KeyError, ValueError):
            return None

    # ================== 模块清单检查 ==================

    def _check_manifest_compatible(self, target_oid: Oid) -> tuple[bool, str]:
        """检查模块清单是否与当前运行环境兼容

        本地清单从 .runtime/module_manifest.py 读取（打包时写入），
        远程清单路径从目标 commit 的 project.yml 的 manifest_path 字段获取。
        仅在 frozen 环境（PyInstaller 打包后）下执行检查。

        Args:
            target_oid: 目标提交 OID

        Returns:
            (是否兼容, 提示消息)
        """
        if not getattr(sys, 'frozen', False):
            return True, ''

        # 读取本地 manifest（打包进 .runtime/ 的文件）
        runtime_dir = Path(getattr(sys, '_MEIPASS', ''))
        local_manifest_path = runtime_dir / 'module_manifest.py'
        if not local_manifest_path.is_file():
            return True, ''

        try:
            local_manifest = local_manifest_path.read_bytes()
        except Exception:
            log.warning('读取本地模块清单失败，跳过检查', exc_info=True)
            return True, ''

        # 从目标 commit 的 project.yml 获取清单路径
        manifest_git_path = self._get_manifest_path_from_commit(target_oid)
        if not manifest_git_path:
            return True, ''

        # 读取目标 commit 中的 manifest
        remote_manifest = self._get_file_at_commit(target_oid, manifest_git_path)
        if remote_manifest is None:
            return True, ''

        if local_manifest == remote_manifest:
            return True, ''

        # 兼容旧打包产物的 CRLF；先走 raw bytes 快路径，仅不一致时再归一化。
        if b'\r' in local_manifest or b'\r' in remote_manifest:
            normalized_local_manifest = local_manifest.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
            normalized_remote_manifest = remote_manifest.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
            if normalized_local_manifest == normalized_remote_manifest:
                return True, ''

        msg = gt('目标版本的运行环境与当前不兼容')
        log.warning(f'模块清单已变更，阻止代码更新。目标: {str(target_oid)[:7]}')
        return False, msg

    def _get_manifest_path_from_commit(self, commit_oid: Oid) -> str | None:
        """从指定 commit 的 project.yml 中读取 manifest_path

        Args:
            commit_oid: 目标提交 OID

        Returns:
            清单文件的仓库路径，读取失败时返回 None
        """
        raw = self._get_file_at_commit(commit_oid, 'config/project.yml')
        if raw is None:
            return None
        try:
            data = yaml.safe_load(raw)
            path = data.get('manifest_path') if isinstance(data, dict) else None
            return path if isinstance(path, str) and path else None
        except Exception:
            return None

    def _check_remote_manifest_compatible(self) -> tuple[bool, str]:
        """检查远程分支的模块清单是否与当前运行环境兼容

        封装远程 OID 解析 + 清单比对，异常时跳过检查。

        Returns:
            (是否兼容, 提示消息)
        """
        remote_ref = f'refs/remotes/{self.env_config.git_remote}/{self.env_config.git_branch}'
        try:
            repo = self._open_repo()
            if remote_ref not in repo.references:
                return True, ''
            remote_oid = repo.references[remote_ref].target
            return self._check_manifest_compatible(remote_oid)
        except Exception:
            log.warning('检查模块清单时出错，跳过检查', exc_info=True)
            return True, ''

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
        """同步本地代码到远程分支状态

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

        # 拉取远程代码
        if progress_callback:
            progress_callback(2/5, gt('拉取远程代码'))

        if not self._fetch_remote(progress_callback, 2 / 5, 3 / 5):
            return False, gt('拉取远程代码失败')

        # 切换到目标分支
        if progress_callback:
            progress_callback(3/5, gt('切换到目标分支'))

        if not self._checkout_branch():
            return False, gt('切换到目标分支失败')

        # 同步本地代码
        if progress_callback:
            progress_callback(4/5, gt('同步本地代码'))

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

        # 拉取远程代码
        if progress_callback:
            progress_callback(1/6, gt('拉取远程代码'))

        if not self._fetch_remote(progress_callback, 1 / 6, 2 / 6):
            return False, gt('拉取远程代码失败')

        # 检查模块清单兼容性（仅 frozen 环境）
        if progress_callback:
            progress_callback(2/6, gt('检查运行环境兼容性'))

        compatible, msg = self._check_remote_manifest_compatible()
        if not compatible:
            return False, msg

        # 检查工作区状态
        if progress_callback:
            progress_callback(3/6, gt('检查工作区状态'))

        success, message = self._validate_working_directory()
        if not success:
            return False, message

        # 切换到目标分支
        if progress_callback:
            progress_callback(4/6, gt('切换到目标分支'))

        if not self._checkout_branch():
            return False, gt('切换到目标分支失败')

        # 同步本地代码
        if progress_callback:
            progress_callback(5/6, gt('同步本地代码'))

        success, message = self._sync_with_remote(self.env_config.force_update)
        if not success:
            return False, message

        if progress_callback:
            progress_callback(6/6, message)

        return True, message

    # ================== 公共 API ==================

    def check_repo_exists(self) -> bool:
        """
        检查本地仓库是否存在
        """
        return discover_repository(self.repo_dir) is not None

    def fetch_latest_code(
        self,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> tuple[bool, str]:
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

    def get_head_commit_id(self, short: bool = False) -> str | None:
        """获取当前 HEAD 的 commit hash"""
        try:
            repo = self._open_repo()
            oid = str(repo.head.target)
            return oid[:8] if short else oid
        except Exception:
            return None

    def is_current_branch_latest(self) -> tuple[bool, str]:
        """
        当前分支是否已经最新 与远程分支一致
        """
        log.info(gt('检测当前代码是否最新'))

        if not self._fetch_remote():
            return False, gt('拉取远程代码失败')

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

    def reset_to_commit(self, commit_id: str) -> tuple[bool, str]:
        """
        回滚到特定commit，会先检查模块清单兼容性

        Returns:
            (是否成功, 提示消息)
        """
        try:
            repo = self._open_repo()
            obj = repo.revparse_single(commit_id)
            target_oid = obj.id
        except Exception:
            log.error(f'解析提交ID失败: {commit_id}', exc_info=True)
            return False, gt('解析提交ID失败')

        compatible, msg = self._check_manifest_compatible(target_oid)
        if not compatible:
            return False, msg

        if self._reset_hard(target_oid):
            return True, ''
        return False, gt('回滚失败')

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

        heads = None
        try:
            for repository, repository_url in self._get_repository_candidates():
                repository_name = self._get_repository_item(repository).ui_text
                try:
                    remote = self._ensure_remote(repository_url)
                    callbacks = self._create_fetch_callbacks(None, 0.0, 1.0)
                    with self._temporary_fetch_timeout():
                        heads = remote.list_heads(callbacks=callbacks, proxy=self._get_proxy_address())
                    log.info(f'标签查询使用代码源: {repository_name}')
                    break
                except Exception:
                    log.warning(f'代码源 {repository_name} 获取标签失败，尝试下一个代码源', exc_info=True)
        finally:
            restored = self._restore_origin()

        if heads is None or not restored:
            log.error('获取最新标签失败')
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
