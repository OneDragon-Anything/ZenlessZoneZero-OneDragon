from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SQUASH_SOURCE_PATTERN = re.compile(
    r"^Squashed from PR: https://github\.com/[^/]+/[^/]+/pull/([0-9]+) .*",
    re.MULTILINE,
)


@dataclass(frozen=True)
class PrInfo:
    number: str
    state: str
    title: str
    labels: set[str]
    author_login: str


@dataclass(frozen=True)
class AppliedPr:
    number: str
    title: str
    author: str


@dataclass(frozen=True)
class ConflictPr:
    number: str
    title: str


@dataclass(frozen=True)
class SkippedPr:
    number: str
    reason: str


def run_command(
    args: list[str],
    *,
    check: bool = True,
    capture_output: bool = False,
    input_text: str | None = None,
    quiet: bool = False,
) -> subprocess.CompletedProcess[str]:
    """运行外部命令，并统一使用 UTF-8 处理文本。"""
    stdout: int | None = None
    stderr: int | None = None
    if capture_output:
        stdout = subprocess.PIPE
        stderr = subprocess.PIPE
    elif quiet:
        stdout = subprocess.DEVNULL
        stderr = subprocess.DEVNULL

    result = subprocess.run(
        args,
        cwd=REPO_ROOT,
        input=input_text,
        stdout=stdout,
        stderr=stderr,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            args,
            output=result.stdout,
            stderr=result.stderr,
        )
    return result


def normalize_line(value: str) -> str:
    """把标题或署名中的换行替换为空格。"""
    return value.replace("\r", " ").replace("\n", " ")


def parse_manual_prs(value: str) -> list[str]:
    """按出现顺序提取并去重手动输入中的 PR 编号。"""
    result: list[str] = []
    seen: set[str] = set()
    for number in re.findall(r"[0-9]+", value):
        if number in seen:
            continue
        seen.add(number)
        result.append(number)
    return result


def load_json(result: subprocess.CompletedProcess[str]) -> Any:
    """解析命令标准输出中的 JSON。"""
    return json.loads(result.stdout or "")


def configure_git() -> None:
    """配置 CI 创建提交时使用的 committer。"""
    run_command(["git", "config", "--global", "user.name", "github-actions[bot]"])
    run_command(
        [
            "git",
            "config",
            "--global",
            "user.email",
            "github-actions[bot]@users.noreply.github.com",
        ]
    )


def ensure_labels(include_label: str, conflict_label: str) -> None:
    """创建或更新 test 分支使用的标签。"""
    run_command(
        [
            "gh",
            "label",
            "create",
            include_label,
            "--color",
            "0E8A16",
            "--description",
            "合入 test 分支",
            "--force",
        ]
    )
    run_command(
        [
            "gh",
            "label",
            "create",
            conflict_label,
            "--color",
            "D93F0B",
            "--description",
            "合入 test 分支时冲突,需 rebase",
            "--force",
        ]
    )


def resolve_prs(input_prs: str, include_label: str) -> tuple[list[str], str, bool]:
    """根据手动输入或标签得到本次要处理的 PR。"""
    if re.sub(r"\s", "", input_prs):
        prs = parse_manual_prs(input_prs)
        source = "手动输入(按填写顺序)"
        require_label = False
    else:
        result = run_command(
            [
                "gh",
                "pr",
                "list",
                "--state",
                "open",
                "--label",
                include_label,
                "--limit",
                "100",
                "--json",
                "number",
            ],
            capture_output=True,
        )
        data = load_json(result)
        prs = sorted(
            (str(item["number"]) for item in data),
            key=int,
        )
        source = f"标签 `{include_label}`(按 PR 号升序)"
        require_label = True

    print(f"PR 来源: {source}")
    print(f"PR 列表: {' '.join(str(pr) for pr in prs) or '(空)'}")
    return prs, source, require_label


def get_pr_info(pr: str) -> PrInfo | None:
    """一次读取 PR 状态、标题、标签和发起人。"""
    result = run_command(
        ["gh", "pr", "view", str(pr), "--json", "state,title,labels,author"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        return None

    try:
        data = load_json(result)
    except json.JSONDecodeError:
        return None

    author = data.get("author") or {}
    return PrInfo(
        number=pr,
        state=str(data.get("state", "")),
        title=normalize_line(str(data.get("title", ""))),
        labels={str(label["name"]) for label in data.get("labels", [])},
        author_login=normalize_line(str(author.get("login", ""))),
    )


def get_short_sha(ref: str) -> str:
    """读取 Git ref 的短 SHA。"""
    result = run_command(
        ["git", "rev-parse", "--short", ref],
        capture_output=True,
    )
    return (result.stdout or "").strip()


def get_conflict_files() -> list[str]:
    """读取当前 index 中所有未合并文件。"""
    result = run_command(
        ["git", "diff", "--name-only", "--diff-filter=U"],
        check=False,
        capture_output=True,
    )
    return [line for line in (result.stdout or "").splitlines() if line]


def get_conflict_ranges(path: str) -> str:
    """读取工作区文件中的冲突标记行范围。"""
    file_path = REPO_ROOT / path
    if not file_path.is_file():
        return "文件级冲突（无行号）"

    lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    ranges: list[str] = []
    start: int | None = None
    for line_number, line in enumerate(lines, start=1):
        if line.startswith("<<<<<<< "):
            start = line_number
        elif line.startswith(">>>>>>> ") and start is not None:
            ranges.append(f"{start}-{line_number}")
            start = None
    if start is not None:
        ranges.append(f"{start}-{len(lines)}")
    return ", ".join(ranges) or "文件级冲突（无行号）"


def get_related_prs(path: str) -> str:
    """从此前 squash 提交中找出修改过冲突文件的 PR。"""
    result = run_command(
        ["git", "log", "--format=%B", "origin/main..HEAD", "--", path],
        check=False,
        capture_output=True,
    )
    numbers = sorted(
        {int(match.group(1)) for match in SQUASH_SOURCE_PATTERN.finditer(result.stdout or "")}
    )
    return ", ".join(f"#{number}" for number in numbers) or "无"


def build_conflict_report(pr: str, conflict_files: list[str], main_conflict: bool) -> str:
    """生成单个 PR 的冲突 Markdown 报告。"""
    lines: list[str] = []
    if main_conflict:
        lines.extend(
            [
                f"### PR #{pr} 与 main 冲突",
                "",
                "当前 PR 单独合入 `main` 已有冲突；若冲突文件也被此前 PR 修改，下表会列出相关 PR。",
            ]
        )
    else:
        lines.extend(
            [
                f"### PR #{pr} 与此前已合入 PR 冲突",
                "",
                "当前 PR 单独合入 `main` 无冲突，因此冲突来自当前 `test` 基线中此前已合入的 PR。",
            ]
        )

    lines.extend(
        [
            "",
            "| 文件 | 冲突行号 | 相关已合入 PR |",
            "| --- | --- | --- |",
        ]
    )
    if not conflict_files:
        lines.append("| 未能从 Git index 读取冲突文件 | 行号不可用 | 未定位 |")
    else:
        for path in conflict_files:
            lines.append(
                f"| `{path}` | {get_conflict_ranges(path)} | {get_related_prs(path)} |"
            )
    lines.append("")
    return "\n".join(lines)


def get_commit_authors(pr_ref: str) -> list[str]:
    """按提交顺序读取并去重 PR 中的作者。"""
    result = run_command(
        [
            "git",
            "log",
            "--reverse",
            "--format=%aN <%aE>",
            f"origin/main..{pr_ref}",
        ],
        check=False,
        capture_output=True,
    )
    authors: list[str] = []
    seen: set[str] = set()
    for line in (result.stdout or "").splitlines():
        author = normalize_line(line)
        if not author or author in seen:
            continue
        seen.add(author)
        authors.append(author)
    return authors


def get_github_author(login: str, authors: list[str]) -> str:
    """多作者 PR 使用发起人的 GitHub noreply 身份。"""
    if login:
        result = run_command(
            ["gh", "api", f"users/{login}"],
            check=False,
            capture_output=True,
        )
        if result.returncode == 0:
            try:
                data = load_json(result)
            except json.JSONDecodeError:
                data = {}
            user_id = normalize_line(str(data.get("id", "")))
            user_name = normalize_line(str(data.get("name") or data.get("login") or ""))
            if user_id:
                return f"{user_name} <{user_id}+{login}@users.noreply.github.com>"
    if authors:
        return authors[0]
    return "github-actions[bot] <github-actions[bot]@users.noreply.github.com>"


def commit_pr(
    pr: str,
    title: str,
    head_sha: str,
    repository: str,
    author: str,
    authors: list[str],
) -> None:
    """提交单个 PR 的 squash 结果。"""
    message = (
        f"[测试] {title}\n\n"
        f"Squashed from PR: https://github.com/{repository}/pull/{pr} ({head_sha}) "
        "by update-test-branch workflow.\n"
    )
    if len(authors) > 1:
        message += "\n" + "".join(f"Co-authored-by: {item}\n" for item in authors)
    run_command(
        ["git", "commit", "-q", "-F", "-", f"--author={author}"],
        input_text=message,
    )


def commit_summary(applied: list[AppliedPr]) -> None:
    """在所有测试提交之后追加面向用户的测试内容汇总。"""
    if not applied:
        return
    message = "[测试] 当前测试内容\n\n" + "".join(
        f"- {item.title}\n" for item in applied
    )
    run_command(
        ["git", "commit", "--allow-empty", "-q", "-F", "-"],
        input_text=message,
    )


def append_summary(path: Path, content: str) -> None:
    """追加 GitHub Actions Step Summary。"""
    with path.open("a", encoding="utf-8", newline="\n") as file:
        file.write(content)
        if not content.endswith("\n"):
            file.write("\n")


def build_failure_summary(conflict_report: str) -> str:
    """生成 test 分支 push 失败时的摘要。"""
    lines = [
        "## test 分支重建失败",
        "",
        "PR 已按顺序处理完,但 `git push --force origin test` 被拒绝,`test` 分支**未更新**。",
        "请检查 `test` 分支的保护规则是否禁止强制推送。",
    ]
    if conflict_report:
        lines.extend(["", conflict_report])
    return "\n".join(lines) + "\n"


def display_author_name(author: str) -> str:
    """从 Git 署名中提取公开摘要使用的作者名。"""
    return author.split(" <", maxsplit=1)[0]


def build_success_summary(
    base_sha: str,
    test_sha: str,
    source: str,
    applied: list[AppliedPr],
    conflicted: list[ConflictPr],
    skipped: list[SkippedPr],
    conflict_label: str,
    conflict_report: str,
) -> str:
    """生成 test 分支重建成功后的摘要。"""
    lines = [
        "## test 分支重建结果",
        "",
        f"- 基线:`main` @ `{base_sha}` → `test` @ `{test_sha}`",
        f"- PR 来源:{source}",
        "",
        f"### 已合入({len(applied)})",
        "",
    ]
    if not applied:
        lines.append("无,`test` 与 `main` 一致。")
    else:
        lines.extend(
            f"- #{item.number} {item.title} — {display_author_name(item.author)}"
            for item in applied
        )

    if conflicted:
        lines.extend(
            [
                "",
                f"### 冲突跳过({len(conflicted)})",
                "",
                f"> 已打上 `{conflict_label}` 标签，请根据下方冲突关系处理后重跑。",
                "",
            ]
        )
        lines.extend(f"- #{item.number} {item.title}" for item in conflicted)
        lines.extend(["", conflict_report])

    if skipped:
        lines.extend(["", f"### 其他跳过({len(skipped)})", ""])
        lines.extend(f"- #{item.number}:{item.reason}" for item in skipped)
    return "\n".join(lines) + "\n"


def maintain_conflict_labels(
    conflicted: list[ConflictPr],
    applied: list[AppliedPr],
    conflict_label: str,
) -> None:
    """push 成功后更新 PR 的冲突标签。"""
    for item in conflicted:
        run_command(
            ["gh", "pr", "edit", str(item.number), "--add-label", conflict_label],
            check=False,
        )
    for item in applied:
        run_command(
            ["gh", "pr", "edit", str(item.number), "--remove-label", conflict_label],
            check=False,
            quiet=True,
        )


def rebuild_test_branch(
    prs: list[str],
    source: str,
    require_label: bool,
    include_label: str,
    conflict_label: str,
    repository: str,
    summary_path: Path,
) -> int:
    """从 main 重建 test 分支，并逐个 squash 指定 PR。"""
    run_command(["git", "fetch", "origin", "main"])
    run_command(["git", "checkout", "-B", "test", "origin/main"])
    base_sha = get_short_sha("HEAD")

    applied: list[AppliedPr] = []
    conflicted: list[ConflictPr] = []
    skipped: list[SkippedPr] = []
    conflict_reports: list[str] = []

    for pr in prs:
        info = get_pr_info(pr)
        if info is None:
            skipped.append(SkippedPr(pr, "查不到该 PR"))
            continue
        if info.state != "OPEN":
            skipped.append(SkippedPr(pr, info.state or "查不到该 PR"))
            continue
        if require_label and include_label not in info.labels:
            skipped.append(SkippedPr(pr, f"已移除 {include_label} 标签"))
            continue

        pr_ref = f"refs/remotes/pr/{pr}"
        fetch_result = run_command(
            [
                "git",
                "fetch",
                "origin",
                f"refs/pull/{pr}/head:{pr_ref}",
                "--force",
            ],
            check=False,
        )
        if fetch_result.returncode != 0:
            skipped.append(SkippedPr(pr, "拉取 PR 分支失败"))
            continue
        head_sha = get_short_sha(pr_ref)

        merge_result = run_command(
            ["git", "merge", "--squash", pr_ref],
            check=False,
        )
        if merge_result.returncode != 0:
            conflict_files = get_conflict_files()
            main_conflict = (
                run_command(
                    ["git", "merge-tree", "--write-tree", "origin/main", pr_ref],
                    check=False,
                    quiet=True,
                ).returncode
                != 0
            )
            conflict_reports.append(
                build_conflict_report(pr, conflict_files, main_conflict)
            )
            run_command(["git", "reset", "--hard", "HEAD"])
            run_command(["git", "clean", "-fd"])
            conflicted.append(ConflictPr(pr, info.title))
            continue

        if run_command(["git", "diff", "--cached", "--quiet"], check=False).returncode == 0:
            skipped.append(SkippedPr(pr, "无变更(已在 main 中)"))
            continue

        authors = get_commit_authors(pr_ref)
        author = (
            authors[0]
            if len(authors) == 1
            else get_github_author(info.author_login, authors)
        )
        commit_pr(pr, info.title, head_sha, repository, author, authors)
        applied.append(AppliedPr(pr, info.title, author))

    commit_summary(applied)
    conflict_report = "\n".join(conflict_reports)

    push_result = run_command(
        ["git", "push", "--force", "origin", "test"],
        check=False,
    )
    if push_result.returncode != 0:
        append_summary(summary_path, build_failure_summary(conflict_report))
        return 1

    test_sha = get_short_sha("HEAD")
    maintain_conflict_labels(conflicted, applied, conflict_label)
    append_summary(
        summary_path,
        build_success_summary(
            base_sha,
            test_sha,
            source,
            applied,
            conflicted,
            skipped,
            conflict_label,
            conflict_report,
        ),
    )
    return 0


def main() -> int:
    """执行 Build Test Branch workflow 的全部逻辑。"""
    include_label = os.environ.get("INCLUDE_LABEL", "test-branch")
    conflict_label = os.environ.get("CONFLICT_LABEL", "test-conflict")
    input_prs = os.environ.get("INPUT_PRS", "")
    repository = os.environ["GITHUB_REPOSITORY"]
    summary_path = Path(os.environ["GITHUB_STEP_SUMMARY"])

    configure_git()
    ensure_labels(include_label, conflict_label)
    prs, source, require_label = resolve_prs(input_prs, include_label)
    return rebuild_test_branch(
        prs,
        source,
        require_label,
        include_label,
        conflict_label,
        repository,
        summary_path,
    )


if __name__ == "__main__":
    sys.exit(main())
