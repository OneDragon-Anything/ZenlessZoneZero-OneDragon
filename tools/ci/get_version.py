import os
import re
import subprocess


def main() -> int:
    github_ref = os.environ.get('GITHUB_REF', '')
    github_output = os.environ.get('GITHUB_OUTPUT')
    create_release = os.environ.get('CREATE_RELEASE', 'false').lower() == 'true'

    version = ""
    should_push_tag = False

    if github_ref.startswith('refs/tags/'):
        # 已由 tag 推送触发，直接使用该 tag 作为版本
        version = github_ref[10:]
    elif create_release:
        # 手动触发且要求创建 release：生成新的 beta 版本
        # 获取远程 tag 列表并按版本排序
        cmd = ['git', 'ls-remote', '--refs', '--tags', '--sort=-version:refname', 'origin', 'v*']
        result = subprocess.run(cmd, capture_output=True, text=True)

        latest_tag = None
        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.strip().splitlines():
                match = re.search(r'refs/tags/(v\d+\.\d+\.\d+(?:-beta\.\d+)?)$', line)
                if match:
                    latest_tag = match.group(1)
                    break

        if not latest_tag:
            # 仓库还没有任何符合语义版本的 tag，初始化
            version = "v0.1.0-beta.1"
        else:
            # 根据最新 tag 递增
            beta_match = re.match(r'^(v\d+\.\d+\.\d+)-beta\.(\d+)$', latest_tag)
            if beta_match:
                # 最新即为 beta，在编号上 +1
                version = f"{beta_match.group(1)}-beta.{int(beta_match.group(2)) + 1}"
            else:
                # 最新为稳定版本，从该稳定版本的下一位开始新的 beta 序列
                stable_match = re.match(r'^(v\d+\.\d+\.)(\d+)$', latest_tag)
                if stable_match:
                    version = f"{stable_match.group(1)}{int(stable_match.group(2)) + 1}-beta.1"
                else:
                    version = "v0.1.0-beta.1"

        should_push_tag = True
    else:
        # PR 或非发布构建
        short_hash = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True, text=True,
        ).stdout.strip() or 'unknown'

        pr_match = re.match(r'^refs/pull/(\d+)/', github_ref)
        if pr_match:
            version = f"pr{pr_match.group(1)}+{short_hash}"
        else:
            version = f"dev+{short_hash}"

    print(f"Version: {version}")

    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"version={version}\n")

    if should_push_tag:
        print(f"Creating and pushing new tag: {version}")
        subprocess.run(['git', '-c', 'user.name=GitHub Actions', '-c', 'user.email=actions@github.com', 'tag', version], check=True)
        subprocess.run(['git', 'push', 'origin', version], check=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
