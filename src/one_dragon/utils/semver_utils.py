import re

SEMVER_RE = re.compile(
    r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z.-]+))?"     # 预发布
    r"(?:\+[0-9A-Za-z.-]+)?$"     # build 元数据（不参与比较）
)

def semver_key(tag: str):
    m = SEMVER_RE.match(tag)
    if not m:
        return (-1,)  # 非语义化版本：排最前或最末都行
    major, minor, patch, pre = m.groups()
    major, minor, patch = int(major), int(minor), int(patch)
    if pre is None:
        # 正式版权重大：1.2.3 > 1.2.3-rc.1
        pre_key = (1,)
    else:
        parts = pre.split(".")
        def part(p):
            return (0, int(p)) if p.isdigit() else (1, p)
        pre_key = (0, *map(part, parts))
    return (major, minor, patch, pre_key)

def sort_tags(tags: list[str], non_semver_last: bool = True, reverse: bool = False) -> list[str]:
    """
    将 tags 列表按语义化版本排序并返回新的列表。
    - 非语义化版本的 tag（semver_key 返回 (-1,)）默认排在末尾（non_semver_last=True）。
    - reverse=True 可反转最终顺序。
    """
    semver_bucket, non_semver_bucket = (0, 1) if non_semver_last else (1, 0)

    def sort_key(tag: str):
        version_key = semver_key(tag)
        bucket = non_semver_bucket if version_key[0] == -1 else semver_bucket
        # 先按是否为语义化版本进行分组，再按语义化版本键排序
        return bucket, version_key

    return sorted(tags, key=sort_key, reverse=reverse)
