import os
import re
import subprocess

TAG_PATTERN = re.compile(r'^v\d+\.\d+\.\d+(?:-beta\.\d+)?$')

# vX.Y.Z-beta.N；稳定版同一 base 下排在 beta 之后
_VERSION_PATTERN = re.compile(r'^v(\d+)\.(\d+)\.(\d+)(?:-beta\.(\d+))?$')


def _version_sort_key(tag: str) -> tuple[int, int, int, int, int]:
    """把 tag 换成可排序的元组，稳定版排在同一个 base 的 beta 之后。"""
    match = _VERSION_PATTERN.match(tag)
    if match is None:
        return (0, 0, 0, 0, 0)
    major, minor, patch, beta = match.groups()
    return (int(major), int(minor), int(patch), 1 if beta is None else 0, int(beta or 0))


def _remote_tags_by_version_desc() -> list[str]:
    """读取远端 tag，按版本号从高到低返回。

    git 自带的 `--sort=-version:refname` 会把 `v2.6.0-beta.2` 排在 `v2.6.0` 后面，
    递增 beta 号时就会算错，所以这里自己按语义排序。

    Returns:
        形如 `['v2.6.0', 'v2.5.2-beta.3']` 的 tag 列表；读取失败时返回空列表。
    """
    result = subprocess.run(
        ['git', 'ls-remote', '--refs', '--tags', 'origin', 'v*'],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    tags: list[str] = []
    for line in result.stdout.strip().splitlines():
        match = re.search(r'refs/tags/(v\d+\.\d+\.\d+(?:-beta\.\d+)?)$', line)
        if match:
            tags.append(match.group(1))
    return sorted(tags, key=_version_sort_key, reverse=True)


def next_version(latest_tag: str | None) -> str:
    """在最新 tag 上递增出一个 beta 版本号。

    Args:
        latest_tag: 当前最新的版本 tag，没有则为 None。

    Returns:
        下一个 beta 版本号。
    """
    if not latest_tag:
        return 'v0.1.0-beta.1'

    beta_match = re.match(r'^(v\d+\.\d+\.\d+)-beta\.(\d+)$', latest_tag)
    if beta_match:
        return f'{beta_match.group(1)}-beta.{int(beta_match.group(2)) + 1}'

    stable_match = re.match(r'^(v\d+\.\d+\.)(\d+)$', latest_tag)
    if stable_match:
        return f'{stable_match.group(1)}{int(stable_match.group(2)) + 1}-beta.1'

    return 'v0.1.0-beta.1'


def resolve_version(
        github_ref: str,
        create_release: bool,
        version_input: str,
        remote_tags: list[str],
        short_hash: str,
        pr_number: str | None,
) -> str:
    """计算本次构建的版本号。

    tag 触发的补发直接用该 tag，忽略手填版本号；分支手动发版才使用手填版本号，
    没传就在最新 tag 上递增一个 beta。这里不推 tag：tag 留到 release 步骤和产物
    一起创建，避免 tag 先出现、产物还没上传的空窗期。

    Args:
        github_ref: GitHub 的 ref，例如 `refs/heads/main`。
        create_release: 本次是否要创建 Release。
        version_input: 手动触发时填写的版本号，可为空。
        remote_tags: 远端 tag 列表，按版本从高到低排序。
        short_hash: 当前 commit 的短 hash，用于 PR / 开发版本。
        pr_number: PR 编号，非 PR 构建为 None。

    Returns:
        版本号字符串。

    Raises:
        ValueError: 手填的版本号格式不合法。
    """
    if github_ref.startswith('refs/tags/'):
        return github_ref[10:]

    if create_release and version_input:
        if not TAG_PATTERN.match(version_input):
            raise ValueError(f'版本号格式不对: {version_input}，应为 vX.Y.Z 或 vX.Y.Z-beta.N')
        return version_input

    if create_release:
        return next_version(remote_tags[0] if remote_tags else None)

    if pr_number:
        return f'pr{pr_number}+{short_hash}'
    return f'dev+{short_hash}'


def tag_exists_on_remote(version: str) -> bool:
    """检查远端是否已经有这个 tag。

    按完整 ref 匹配：`git ls-remote --tags origin v2.6.0` 是尾部匹配，会命中
    `refs/tags/archive/v2.6.0`，让发版误判成 tag 已存在。

    Args:
        version: 版本号，也就是 tag 名。

    Returns:
        已存在返回 True。

    Raises:
        RuntimeError: 读取远端 tag 失败，无法确认是否重复
    """
    result = subprocess.run(
        ['git', 'ls-remote', '--refs', '--tags', 'origin', f'refs/tags/{version}'],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f'读取远端 tag 失败，无法确认 {version} 是否已存在')
    return bool(result.stdout.strip())


def main() -> int:
    github_ref = os.environ.get('GITHUB_REF', '')
    github_output = os.environ.get('GITHUB_OUTPUT')
    create_release = os.environ.get('CREATE_RELEASE', 'false').lower() == 'true'
    version_input = os.environ.get('VERSION_INPUT', '').strip()

    short_hash = subprocess.run(
        ['git', 'rev-parse', '--short', 'HEAD'],
        capture_output=True,
        text=True,
    ).stdout.strip() or 'unknown'
    pr_match = re.match(r'^refs/pull/(\d+)/', github_ref)

    try:
        version = resolve_version(
            github_ref=github_ref,
            create_release=create_release,
            version_input=version_input,
            remote_tags=_remote_tags_by_version_desc(),
            short_hash=short_hash,
            pr_number=pr_match.group(1) if pr_match else None,
        )
    except ValueError as error:
        print(f'::error::{error}')
        return 1

    # 从 tag 触发的补发版允许复用已有 tag；分支上的手动发版不允许同名 tag
    if create_release and not github_ref.startswith('refs/tags/'):
        try:
            existed = tag_exists_on_remote(version)
        except RuntimeError as error:
            print(f'::error::{error}')
            return 1
        if existed:
            print(f'::error::tag {version} 已经存在。发版时 tag 会和产物一起创建，'
                  f'不要再手动推同名 tag；要重发请换一个版本号。')
            return 1

    print(f'Version: {version}')

    if github_output:
        with open(github_output, 'a') as f:
            f.write(f'version={version}\n')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
