import os
import re
import subprocess
from datetime import UTC, datetime, timedelta


def main():
    github_ref = os.environ.get('GITHUB_REF', '')
    create_release = os.environ.get('CREATE_RELEASE', 'false').lower() == 'true'
    github_output = os.environ.get('GITHUB_OUTPUT')

    version = ""
    tag = ""
    should_push_tag = False

    if github_ref.startswith('refs/tags/'):
        # 已由 tag 推送触发，直接使用该 tag 作为版本
        version = github_ref[10:]
        tag = version
    elif not create_release:
        # 非 release 构建，使用日期作为版本号 (UTC+8)
        now_plus_8 = datetime.now(UTC) + timedelta(hours=8)
        version = now_plus_8.strftime('v%Y.%m%d.%H%M')
        tag = version
    else:
        # 手动触发且要求创建 release：生成新的 beta 版本
        # 获取远程 tag 列表并按版本排序
        cmd = ['git', 'ls-remote', '--refs', '--tags', '--sort=-version:refname', 'origin', 'v*']
        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stdout.strip() if result.returncode == 0 else None

        latest_tag = None
        if output:
            for line in output.splitlines():
                # 行格式: <hash>\trefs/tags/<tagname>
                match = re.search(r'refs/tags/(v\d+\.\d+\.\d+(?:-beta\.\d+)?)$', line)
                if match:
                    latest_tag = match.group(1)
                    break

        if not latest_tag:
            # 仓库还没有任何符合语义版本的 tag，初始化
            tag = "v0.1.0-beta.1"
        else:
            # 根据最新 tag 递增
            beta_match = re.match(r'^(v\d+\.\d+\.\d+)-beta\.(\d+)$', latest_tag)
            if beta_match:
                # 最新即为 beta，在编号上 +1
                base = beta_match.group(1)
                num = int(beta_match.group(2)) + 1
                tag = f"{base}-beta.{num}"
            else:
                # 最新为稳定版本，从该稳定版本的下一位开始新的 beta 序列
                stable_match = re.match(r'^(v\d+\.\d+\.)(\d+)$', latest_tag)
                if stable_match:
                    prefix = stable_match.group(1)
                    patch = int(stable_match.group(2)) + 1
                    tag = f"{prefix}{patch}-beta.1"
                else:
                    tag = "v0.1.0-beta.1"

        version = tag
        should_push_tag = True

    print(f"Version: {version}")
    print(f"Tag: {tag}")

    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"version={version}\n")
            f.write(f"tag={tag}\n")

    if should_push_tag:
        print(f"Creating and pushing new tag: {tag}")
        subprocess.run(['git', '-c', 'user.name=GitHub Actions', '-c', 'user.email=actions@github.com', 'tag', tag])
        subprocess.run(['git', 'push', 'origin', tag])

if __name__ == "__main__":
    main()
