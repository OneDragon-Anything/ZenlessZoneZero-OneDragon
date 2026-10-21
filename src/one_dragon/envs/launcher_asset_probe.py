import urllib.error
import urllib.request

from one_dragon.envs.env_config import EnvConfig


def probe_launcher_asset_urls(
    urls: dict[str, str],
    env_config: EnvConfig,
) -> dict[str, str]:
    """确认启动器附件是否存在，并返回可用下载地址。

    Args:
        urls: 下载源编号到附件地址的映射。
        env_config: 提供个人代理和 GitHub 代理配置。

    Returns:
        可以访问的下载源编号和原始附件地址。

    Raises:
        FileNotFoundError: 所有下载源都明确返回附件不存在。
        RuntimeError: 网络或服务端错误导致无法确认附件是否存在。
    """
    available: dict[str, str] = {}
    errors: list[str] = []
    not_found = 0
    proxy_url = env_config.personal_proxy if env_config.is_personal_proxy else None
    opener = (
        urllib.request.build_opener(
            urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url})
        )
        if proxy_url
        else None
    )

    for source_id, url in urls.items():
        probe_url = url
        if (
            source_id == 'github'
            and env_config.is_gh_proxy
            and env_config.gh_proxy_url
        ):
            probe_url = f'{env_config.gh_proxy_url.rstrip("/")}/{url}'
        found, missing, source_errors = _probe_url(probe_url, source_id, opener)
        if found:
            available[source_id] = url
            continue
        if missing and not source_errors:
            not_found += 1
        errors.extend(source_errors)

    if available:
        return available
    if not_found == len(urls):
        raise FileNotFoundError('所选版本没有集成启动器安装包，请选择其他版本')
    detail = '；'.join(errors) if errors else '无法确认附件是否存在'
    raise RuntimeError(f'检查启动器安装包失败：{detail}')


def _probe_url(
    url: str,
    source_id: str,
    opener: urllib.request.OpenerDirector | None,
) -> tuple[bool, bool, list[str]]:
    """依次用 HEAD 和 Range 请求探测一个地址。

    Returns:
        是否可访问、是否明确不存在、探测过程中的错误。
    """
    errors: list[str] = []
    found, missing, head_errors = _open_probe(
        urllib.request.Request(url, method='HEAD'),
        source_id,
        opener,
    )
    if found:
        return True, False, []
    errors.extend(head_errors)

    found, range_missing, range_errors = _open_probe(
        urllib.request.Request(url, headers={'Range': 'bytes=0-0'}),
        source_id,
        opener,
    )
    return found, missing or range_missing, errors + range_errors


def _open_probe(
    request: urllib.request.Request,
    source_id: str,
    opener: urllib.request.OpenerDirector | None,
) -> tuple[bool, bool, list[str]]:
    """打开一次探测请求，并区分可访问、不存在和其他错误。"""
    try:
        response_context = (
            opener.open(request, timeout=5)
            if opener is not None
            else urllib.request.urlopen(request, timeout=5)
        )
        with response_context as response:
            return 200 <= response.status < 400, False, []
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return False, True, []
        return False, False, [f'{source_id}: HTTP {error.code}']
    except Exception as error:
        return False, False, [f'{source_id}: {error}']
