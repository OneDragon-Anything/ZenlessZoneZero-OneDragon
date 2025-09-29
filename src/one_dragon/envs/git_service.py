import contextlib
import os
import time
import tempfile
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
PROXY_ENV_KEYS: tuple[str, ...] = (
    'HTTP_PROXY',
    'HTTPS_PROXY',
    'http_proxy',
    'https_proxy',
    'NO_PROXY',
    'no_proxy',
)


class GitLog:

    def __init__(self, commit_id: str, author: str, commit_time: str, commit_message: str):
        self.commit_id: str = commit_id
        self.author: str = author
        self.commit_time: str = commit_time
        self.commit_message: str = commit_message


@dataclass
class GitOperationResult:
    success: bool
    code: str
    message: str
    detail: str | None = None

    def to_tuple(self) -> tuple[bool, str]:
        return self.success, self.message


class RepoStateManager:
    """集中封装仓库实例缓存、远程配置与分支同步逻辑"""

    def __init__(self, service: 'GitService'):
        self._service = service
        self._repo: pygit2.Repository | None = None

    def invalidate(self) -> None:
        self._repo = None

    def open_repo(self, refresh: bool = False) -> pygit2.Repository:
        if refresh:
            self._repo = None

        if self._repo is not None:
            return self._repo

        work_dir = os_utils.get_work_dir()
        try:
            self._repo = pygit2.Repository(work_dir)
            return self._repo
        except Exception:
            self._repo = None
            raise

    def ensure_remote(self, repo: pygit2.Repository, remote_name: str = 'origin',
                      remote_url: str | None = None) -> pygit2.Remote | None:
        remote_url = remote_url or self._service.get_git_repository()
        if not remote_url:
            log.error('未能获取有效的远程仓库地址')
            return None

        try:
            remote = repo.remotes[remote_name]
            if remote.url != remote_url:
                cfg = repo.config
                cfg[f'remote.{remote_name}.url'] = remote_url
                remote = repo.remotes[remote_name]
            return remote
        except KeyError:
            try:
                repo.remotes.create(remote_name, remote_url)
                return repo.remotes[remote_name]
            except (KeyError, AttributeError, pygit2.GitError) as exc:
                log.error(f'配置远程 {remote_name} 失败: {exc}')
                return None
        except (AttributeError, pygit2.GitError) as exc:
            log.error(f'读取远程 {remote_name} 失败: {exc}')
            return None
        except Exception as exc:  # pylint: disable=broad-except
            log.error(f'配置远程 {remote_name} 时出现异常: {exc}')
            return None

    def sync_with_remote(self, repo: pygit2.Repository, target_branch: str,
                         force_update: bool) -> GitOperationResult:
        origin_ref_name = f'refs/remotes/origin/{target_branch}'
        try:
            if origin_ref_name not in repo.references:
                return GitOperationResult(
                    True,
                    'REMOTE_BRANCH_MISSING',
                    '',
                    detail=f'missing reference {origin_ref_name}',
                )

            origin_ref = repo.references.get(origin_ref_name)
            origin_oid = origin_ref.target

            try:
                local_oid = repo.head.target
            except (KeyError, pygit2.GitError, ValueError):
                local_oid = None

            if local_oid is None:
                if force_update:
                    repo.reset(origin_oid, pygit2.GIT_RESET_HARD)
                    return GitOperationResult(
                        True,
                        'RESET_HEAD_TO_REMOTE',
                        gt('更新本地代码成功'),
                        detail=f'head missing reset to {origin_oid}',
                    )
                return GitOperationResult(
                    False,
                    'LOCAL_HEAD_MISSING',
                    gt('更新本地代码失败'),
                    detail='HEAD reference is missing',
                )

            try:
                remote_ahead = repo.descendant_of(origin_oid, local_oid)
            except Exception as exc:
                detail = f'{type(exc).__name__}: {exc}'
                log.debug(f'判断分支祖先关系失败: {detail}')
                remote_ahead = False

            if remote_ahead:
                repo.reset(origin_oid, pygit2.GIT_RESET_HARD)
                return GitOperationResult(
                    True,
                    'FAST_FORWARD',
                    gt('更新本地代码成功'),
                    detail=f'{local_oid} -> {origin_oid}',
                )

            if force_update:
                repo.reset(origin_oid, pygit2.GIT_RESET_HARD)
                return GitOperationResult(
                    True,
                    'FORCED_RESET',
                    gt('更新本地代码成功'),
                    detail=f'{local_oid} -> {origin_oid}',
                )

            detail = f'local {local_oid} is ahead of origin {origin_oid}'
            return GitOperationResult(
                False,
                'NEED_MANUAL_REBASE',
                gt('更新本地代码失败'),
                detail=detail,
            )
        except Exception as exc:
            detail = f'{type(exc).__name__}: {exc}'
            log.error(f'同步分支到远程失败: {detail}', exc_info=True)
            return GitOperationResult(
                False,
                'SYNC_EXCEPTION',
                gt('更新本地代码失败'),
                detail=detail,
            )


class GitService:

    def __init__(self, project_config: ProjectConfig, env_config: EnvConfig):
        self.project_config: ProjectConfig = project_config
        self.env_config: EnvConfig = env_config

        self._ensure_config_search_path()
        self.is_proxy_set: bool = False  # 是否已经设置代理了
        self._repo_manager = RepoStateManager(self)

    # ---- helpers ----
    @staticmethod
    def _ensure_config_search_path() -> None:
        """覆盖 libgit2 的配置搜索路径，避免读取系统/用户级 gitconfig"""
        settings = getattr(pygit2, 'settings', None)
        if settings is None:
            log.warning('pygit2.settings 不可用，无法覆盖 git config 搜索路径')
            return

        levels = [
            getattr(pygit2, 'GIT_CONFIG_LEVEL_SYSTEM', None),
            getattr(pygit2, 'GIT_CONFIG_LEVEL_GLOBAL', None),
            getattr(pygit2, 'GIT_CONFIG_LEVEL_XDG', None),
        ]
        errors = []
        for level in levels:
            if level is None:
                continue
            try:
                settings.set_search_path(level, '')
            except Exception as exc:  # pylint: disable=broad-except
                errors.append((level, exc))

        if errors:
            for level, exc in errors:
                log.warning(f'禁用 git config 等级 {level} 失败: {exc}')
        else:
            log.info('已禁用系统/用户级 git config 搜索路径，仅保留仓库级配置')

    def _open_repo(self, refresh: bool = False) -> pygit2.Repository:
        """打开当前工作目录的仓库（带缓存，可按需刷新）"""
        return self._repo_manager.open_repo(refresh=refresh)

    def _ensure_remote(self, repo: pygit2.Repository, remote_name: str = 'origin',
                       remote_url: str | None = None) -> pygit2.Remote | None:
        """确保仓库存在指定远程且指向期望 URL，返回远程对象"""
        return self._repo_manager.ensure_remote(repo, remote_name=remote_name, remote_url=remote_url)

    def _invalidate_repo_cache(self) -> None:
        """当 .git 目录被重建等场景时，清空仓库缓存"""
        self._repo_manager.invalidate()
        self.is_proxy_set = False

    @staticmethod
    def _remote_branch_ref(branch: str) -> str:
        return f'refs/remotes/origin/{branch}'

    @staticmethod
    def _local_branch_ref(branch: str) -> str:
        return f'refs/heads/{branch}'

    def _resolve_branch_commit(
        self,
        repo: pygit2.Repository,
        branch: str,
        *,
        allow_local_fallback: bool,
    ) -> pygit2.Commit | None:
        remote_ref_name = self._remote_branch_ref(branch)
        try:
            remote_ref = repo.references.get(remote_ref_name)
        except (KeyError, pygit2.GitError):
            remote_ref = None

        if remote_ref is not None:
            try:
                return repo.get(remote_ref.target)
            except (KeyError, pygit2.GitError) as exc:
                log.error(f'读取远程分支 {remote_ref_name} 失败: {exc}', exc_info=True)
                return None

        if not allow_local_fallback:
            log.error(f'远程分支不存在: {remote_ref_name}')
            return None

        try:
            head = repo.head
            if head is None:
                log.error('当前仓库缺少 HEAD，无法切换到目标分支')
                return None
            peeled = head.peel()
            if hasattr(peeled, 'oid'):
                return peeled
            return repo.get(head.target)
        except (KeyError, ValueError, pygit2.GitError) as exc:
            log.error(f'获取本地 HEAD 失败: {exc}', exc_info=True)
            return None

    def _checkout_branch(
        self,
        repo: pygit2.Repository,
        branch: str,
        *,
        allow_local_fallback: bool = False,
    ) -> tuple[bool, pygit2.Oid | None]:
        target_commit = self._resolve_branch_commit(
            repo,
            branch,
            allow_local_fallback=allow_local_fallback,
        )
        if target_commit is None:
            return False, None

        local_ref_name = self._local_branch_ref(branch)
        try:
            if local_ref_name in repo.references:
                repo.lookup_reference(local_ref_name).set_target(target_commit.id)
            else:
                repo.create_branch(branch, target_commit)
            repo.checkout(local_ref_name, strategy=pygit2.GIT_CHECKOUT_FORCE)
            repo.set_head(local_ref_name)
            return True, target_commit.id
        except Exception as exc:  # pylint: disable=broad-except
            log.error(f'切换到目标分支失败: {exc}', exc_info=True)
            return False, None

    def _resolve_proxy_address(self) -> str | None:
        if not self.env_config.is_personal_proxy:
            return None
        proxy_address = self.env_config.personal_proxy.strip()
        if not proxy_address:
            return None
        if proxy_address.startswith(('http://', 'https://', 'socks5://')):
            return proxy_address
        return f'http://{proxy_address}'

    def _apply_repo_proxy(self, repo: pygit2.Repository) -> None:
        proxy_address = self._resolve_proxy_address()
        try:
            cfg = repo.config
        except Exception as exc:  # pylint: disable=broad-except
            log.warning(f'读取仓库配置失败，无法设置代理: {exc}')
            return

        try:
            if proxy_address is None:
                for key in ('http.proxy', 'https.proxy'):
                    try:
                        cfg.delete_multivar(key, '.*')
                    except (KeyError, pygit2.GitError):
                        try:
                            del cfg[key]
                        except KeyError:
                            pass
            else:
                cfg['http.proxy'] = proxy_address
                cfg['https.proxy'] = proxy_address
        except pygit2.GitError as exc:
            log.warning(f'设置仓库级代理失败: {exc}')

    def _set_proxy_env(self, proxy_address: str | None) -> None:
        if proxy_address:
            for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy'):
                os.environ[key] = proxy_address
            for key in ('NO_PROXY', 'no_proxy'):
                os.environ.pop(key, None)
        else:
            for key in PROXY_ENV_KEYS:
                os.environ.pop(key, None)

    @staticmethod
    def _restore_proxy_env(snapshot: dict[str, str | None]) -> None:
        for key, value in snapshot.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    @contextlib.contextmanager
    def _with_proxy(self, repo: pygit2.Repository | None = None):
        repo_to_use = repo
        if repo_to_use is None:
            try:
                repo_to_use = self._open_repo()
            except Exception:
                repo_to_use = None

        if repo_to_use is not None:
            self._apply_repo_proxy(repo_to_use)

        env_backup = {key: os.environ.get(key) for key in PROXY_ENV_KEYS}
        proxy_address = self._resolve_proxy_address()

        try:
            self._set_proxy_env(proxy_address)
        except Exception:
            self._restore_proxy_env(env_backup)
            raise

        try:
            yield repo_to_use
        finally:
            self._restore_proxy_env(env_backup)

    def _fetch_remote_code_result(self, repo: pygit2.Repository | None = None) -> GitOperationResult:
        log.info(gt('获取远程代码'))
        try:
            repository = repo or self._open_repo()
        except Exception as exc:
            detail = f'{type(exc).__name__}: {exc}'
            log.error(f'打开仓库失败: {detail}', exc_info=True)
            return GitOperationResult(False, 'OPEN_REPO_FAILED', gt('获取远程代码失败'), detail=detail)

        remote = self._ensure_remote(repository)
        if remote is None:
            return GitOperationResult(False, 'REMOTE_NOT_CONFIGURED', gt('获取远程代码失败'),
                                      detail='remote origin missing')

        try:
            with self._with_proxy(repository):
                remote.fetch()
            log.info(gt('获取远程代码成功'))
            return GitOperationResult(True, 'FETCH_SUCCESS', gt('获取远程代码成功'))
        except pygit2.GitError as exc:
            detail = f'{type(exc).__name__}: {exc}'
            log.error(f'获取远程代码失败: {detail}', exc_info=True)
            return GitOperationResult(False, 'FETCH_GIT_ERROR', gt('获取远程代码失败'), detail=detail)
        except Exception as exc:
            detail = f'{type(exc).__name__}: {exc}'
            log.error(f'获取远程代码失败: {detail}', exc_info=True)
            return GitOperationResult(False, 'FETCH_ERROR', gt('获取远程代码失败'), detail=detail)

    # ---- public methods ----

    def fetch_latest_code(self, progress_callback: Callable[[float, str], None] | None = None) -> tuple[bool, str]:
        """
        更新最新的代码：不存在 .git 则克隆，存在则拉取并更新分支
        """
        log.info(f".git {gt('目录')} {DOT_GIT_DIR_PATH}")
        self.set_safe_dir()
        if not os.path.exists(DOT_GIT_DIR_PATH):  # 第一次直接克隆
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

        if progress_callback is not None:
            progress_callback(-1, gt('初始化本地 Git 仓库'))
        log.info(gt('初始化本地 Git 仓库'))

        try:
            pygit2.init_repository(work_dir, False)
        except pygit2.GitError as exc:
            log.error(f'初始化本地仓库失败: {exc}', exc_info=True)
            return False, gt('克隆仓库失败')
        except Exception as exc:  # pylint: disable=broad-except
            log.error(f'初始化本地仓库失败: {exc}', exc_info=True)
            return False, gt('克隆仓库失败')

        self._invalidate_repo_cache()

        try:
            repo = self._open_repo(refresh=True)
        except Exception as exc:
            log.error(f'打开仓库失败: {exc}', exc_info=True)
            return False, gt('克隆仓库失败')

        remote = self._ensure_remote(repo, remote_url=repo_url)
        if remote is None:
            return False, gt('克隆仓库失败')

        fetch_result = self._fetch_remote_code_result(repo=repo)
        if not fetch_result.success:
            return fetch_result.to_tuple()

        if progress_callback is not None:
            progress_callback(0.6, fetch_result.message or gt('获取远程代码成功'))

        target_branch = self.env_config.git_branch
        branch_ready, target_oid = self._checkout_branch(
            repo,
            target_branch,
            allow_local_fallback=False,
        )
        if not branch_ready:
            return False, gt('克隆仓库失败')

        if target_oid is not None:
            repo.reset(target_oid, pygit2.GIT_RESET_HARD)

        if progress_callback is not None:
            progress_callback(1.0, gt('克隆仓库成功'))
        return True, gt('克隆仓库成功')

    def checkout_latest_project_branch(self, progress_callback: Callable[[float, str], None] | None = None) -> tuple[bool, str]:
        """
        切换到最新的目标分支并更新代码
        """
        log.info(gt('核对当前仓库'))
        try:
            repo = self._open_repo()
        except Exception:
            log.info(gt('未找到远程仓库'))
            self.update_git_remote()
            log.info(gt('添加远程仓库地址'))
            try:
                repo = self._open_repo(refresh=True)
            except Exception as exc:
                log.error(f'打开仓库失败: {exc}', exc_info=True)
                return False, gt('打开仓库失败')

        desired_repo = self.get_git_repository()
        if self._ensure_remote(repo, remote_url=desired_repo) is None:
            msg = gt('更新远程仓库地址失败')
            log.error(msg)
            return False, msg

        fetch_result = self._fetch_remote_code_result(repo=repo)
        if not fetch_result.success:
            return fetch_result.to_tuple()
        if progress_callback is not None:
            progress_callback(1 / 5, fetch_result.message)

        clean_result = self.is_current_branch_clean()
        if clean_result is None or not clean_result:
            if self.env_config.force_update:
                target_commit = self._resolve_branch_commit(
                    repo,
                    self.env_config.git_branch,
                    allow_local_fallback=False,
                )
                if target_commit is None:
                    return False, gt('强制更新失败')
                try:
                    repo.reset(target_commit.id, pygit2.GIT_RESET_HARD)
                except Exception as exc:
                    log.error(f'强制更新失败: {exc}', exc_info=True)
                    return False, gt('强制更新失败')
            else:
                msg = gt('未开启强制更新 当前代码有修改 请自行处理后再更新')
                log.error(msg)
                return False, msg
        else:
            if progress_callback is not None:
                progress_callback(2 / 5, gt('当前代码无修改'))

        current_branch = self.get_current_branch()
        if current_branch is None:
            msg = gt('获取当前分支失败')
            log.error(msg)
            return False, msg
        if progress_callback is not None:
            progress_callback(3 / 5, gt('获取当前分支成功'))

        target = self.env_config.git_branch
        branch_ready, _ = self._checkout_branch(
            repo,
            target,
            allow_local_fallback=True,
        )
        if not branch_ready:
            return False, gt('切换到目标分支失败')

        if progress_callback is not None:
            progress_callback(4 / 5, gt('切换到目标分支成功'))

        sync_result = self._repo_manager.sync_with_remote(
            repo,
            target_branch=target,
            force_update=self.env_config.force_update
        )
        if not sync_result.success:
            detail_log = f'[{sync_result.code}] {sync_result.detail}' if sync_result.detail else sync_result.code
            log.error(f'{sync_result.message} {detail_log}')
            return sync_result.to_tuple()

        if progress_callback is not None:
            progress_callback(5 / 5, sync_result.message or gt('更新本地代码成功'))

        if sync_result.detail:
            log.info(f'分支同步详情: {sync_result.detail}')

        return sync_result.to_tuple()

    def get_current_branch(self) -> str | None:
        """
        获取当前分支名称
        :return:
        """
        log.info(gt('检测当前代码分支'))
        try:
            repo = self._open_repo()
            head = repo.head
            return None if head is None else head.shorthand
        except Exception:
            return None

    def is_current_branch_clean(self) -> bool | None:
        """
        当前分支是否没有任何修改内容
        :return:
        """
        log.info(gt('检测当前代码是否有修改'))
        try:
            repo = self._open_repo()
            status = repo.status()
            return len(status) == 0
        except Exception:
            return None

    def is_current_branch_latest(self) -> tuple[bool, str]:
        """
        当前分支是否已经最新 与远程分支一致
        """
        fetch_result = self._fetch_remote_code_result()
        if not fetch_result.success:
            return fetch_result.to_tuple()
        log.info(gt('检测当前代码是否最新'))
        try:
            repo = self._open_repo()
            origin_ref_name = f'refs/remotes/origin/{self.env_config.git_branch}'
            if origin_ref_name in repo.references:
                origin_oid = repo.references.get(origin_ref_name).target
                local_oid = repo.head.target
                if local_oid == origin_oid:
                    return True, ''
                local_tree = repo.get(local_oid).tree
                origin_tree = repo.get(origin_oid).tree
                diff = local_tree.diff(origin_tree)
                if len(diff) == 0:
                    return True, ''
                return False, gt('与远程分支不一致')
            else:
                return False, gt('与远程分支不一致')
        except Exception as exc:
            log.error(f'is_current_branch_latest error: {exc}', exc_info=True)
            return False, gt('与远程分支不一致')

    def fetch_total_commit(self) -> int:
        """
        获取commit的总数。获取失败时返回0
        :return:
        """
        log.info(gt('获取commit总数'))
        try:
            repo = self._open_repo()
            walker = repo.walk(repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL)
            count = 0
            for _ in walker:
                count += 1
            return count
        except Exception:
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
            walker = repo.walk(repo.head.target, pygit2.GIT_SORT_TIME)
            start = page_num * page_size
            idx = 0
            logs: list[GitLog] = []
            for commit in walker:
                if idx < start:
                    idx += 1
                    continue
                if len(logs) >= page_size:
                    break
                short_id = commit.hex[:7]
                author = commit.author.name if commit.author and commit.author.name else ''
                commit_time = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(commit.commit_time))
                message = commit.message.splitlines()[0] if commit.message else ''
                logs.append(GitLog(short_id, author, commit_time, message))
                idx += 1
            return logs
        except Exception:
            return []

    def get_git_repository(self, for_clone: bool = False) -> str:
        """
        获取使用的仓库地址
        :return:
        """
        if self.env_config.repository_type == RepositoryTypeEnum.GITHUB.value.value:
            if self.env_config.git_method == GitMethodEnum.HTTPS.value.value:
                if self.env_config.is_gh_proxy and for_clone:
                    return f'{self.env_config.gh_proxy_url}/{self.project_config.github_https_repository}'
                else:
                    return self.project_config.github_https_repository
            else:
                return self.project_config.github_ssh_repository
        elif self.env_config.repository_type == RepositoryTypeEnum.GITEE.value.value:
            if self.env_config.git_method == GitMethodEnum.HTTPS.value.value:
                return self.project_config.gitee_https_repository
            else:
                return self.project_config.gitee_ssh_repository
        else:
            return ''

    def init_git_proxy(self) -> None:
        """
        初始化 git 使用的代理：通过仓库级配置设置代理，避免污染进程环境
        """
        if self.is_proxy_set:
            return
        if not os.path.exists(DOT_GIT_DIR_PATH):  # 未有.git文件夹
            return

        try:
            repo = self._open_repo()
        except Exception as exc:  # pylint: disable=broad-except
            log.warning(f'init_git_proxy 打开仓库失败: {exc}', exc_info=True)
            return

        try:
            with self._with_proxy(repo):
                pass
        except Exception as exc:  # pylint: disable=broad-except
            log.warning(f'init_git_proxy 设置代理失败: {exc}', exc_info=True)
            return

        self.is_proxy_set = True

    def update_git_remote(self) -> None:
        """
        更新remote（通过 repo.config 修改 remote.origin.url）
        """
        if not os.path.exists(DOT_GIT_DIR_PATH):  # 未有.git文件夹
            return
        try:
            repo = self._open_repo()
        except Exception as exc:  # pylint: disable=broad-except
            log.warning(f'update_git_remote 打开仓库失败: {exc}')
            return

        if self._ensure_remote(repo) is None:
            log.warning('update_git_remote 无法配置远程 origin')

    def set_safe_dir(self) -> None:
        """
        libgit2 不需要 safe.directory，保留为 no-op
        """
        return

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
            log.error(f'reset_to_commit failed: {exc}', exc_info=True)
            return False

    def get_current_version(self) -> str | None:
        """
        获取当前代码版本
        @return:
        """
        log_list = self.fetch_page_commit(0, 1)
        return None if len(log_list) == 0 else log_list[0].commit_id

    def get_latest_tag(self) -> tuple[str | None, str | None]:
        """
        获取最新的稳定版与测试版 tag
        """
        with tempfile.TemporaryDirectory() as td:
            repo = pygit2.init_repository(td, bare=True)
            url = self.get_git_repository()
            remote = repo.remotes.create_anonymous(url)
            callbacks = pygit2.RemoteCallbacks()
            heads = remote.list_heads(callbacks=callbacks, connect=True)

            tags = []
            for h in heads:
                name = getattr(h, "name", None)
                if name and name.startswith("refs/tags/"):
                    tags.append(name[len("refs/tags/"):])

            uniq = list(dict.fromkeys(tags))
            versions = sort_tags(uniq)

        latest_stable: str | None = None
        latest_beta: str | None = None
        first_seen_type: str | None = None

        for version in versions:
            is_beta = '-beta' in version
            if first_seen_type is None:
                if is_beta:
                    first_seen_type = 'beta'
                    latest_beta = version
                    continue
                else:
                    first_seen_type = 'stable'
                    latest_stable = version
                    break
            if first_seen_type == 'beta' and not is_beta and latest_stable is None:
                latest_stable = version
                break

        return latest_stable, latest_beta


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
    __debug_set_safe_dir()
