#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新贡献者信息脚本
从各个来源抓取贡献者信息，并更新contributors.yaml文件
"""

import urllib.request
import urllib.error
import re
import yaml
import os
import time
import json
from datetime import datetime
from typing import List, Dict, Any, Optional


def http_get(url: str, headers: Optional[dict] = None, retries: int = 5, backoff: float = 1.0) -> str:
    """
    执行带重试和请求头的HTTP GET请求，返回文本内容
    """
    if headers is None:
        headers = {}

    req = urllib.request.Request(url, headers=headers)

    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                # 检查响应头中的速率限制信息
                if 'X-RateLimit-Remaining' in resp.headers:
                    remaining = int(resp.headers.get('X-RateLimit-Remaining', 0))
                    reset_time = resp.headers.get('X-RateLimit-Reset', 0)

                    if remaining < 2:  # 如果剩余请求数很少，则等待
                        import datetime
                        reset_timestamp = int(reset_time)
                        current_time = int(time.time())
                        wait_time = max(0, reset_timestamp - current_time)

                        if wait_time > 0:
                            print(f"检测到接近速率限制，等待 {wait_time} 秒...")
                            time.sleep(wait_time)

                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            print(f"HTTP错误 (尝试 {attempt}/{retries}): {e.code} {e.reason}")

            # 检查是否是速率限制错误
            if e.code == 403:
                print("警告: 可能遇到GitHub API速率限制")
                try:
                    error_content = e.read().decode()
                    if 'rate limit' in error_content.lower():
                        print("提示: 设置 GITHUB_TOKEN 环境变量可以提高速率限制")
                except:
                    pass  # 忽略读取错误内容的异常

            # 对于5xx错误和403错误进行重试（403可能是速率限制）
            if (500 <= e.code < 600 or e.code == 403) and attempt < retries:
                sleep_time = backoff * (2 ** (attempt - 1))
                print(f"等待 {sleep_time} 秒后重试...")
                time.sleep(sleep_time)
                continue
            raise
        except urllib.error.URLError as e:
            print(f"URL错误 (尝试 {attempt}/{retries}): {e.reason}")
            if attempt < retries:
                sleep_time = backoff * (2 ** (attempt - 1))
                print(f"等待 {sleep_time} 秒后重试...")
                time.sleep(sleep_time)
                continue
            raise
        except Exception as e:
            print(f"未知错误 (尝试 {attempt}/{retries}): {str(e)}")
            if attempt < retries:
                sleep_time = backoff * (2 ** (attempt - 1))
                print(f"等待 {sleep_time} 秒后重试...")
                time.sleep(sleep_time)
                continue
            raise
    
    # 如果所有重试都失败，抛出异常而不是返回None
    raise Exception(f"在进行了 {retries} 次重试后仍然无法获取URL: {url}")


def fetch_github_contributors(url: str) -> List[Dict[str, Any]]:
    """
    从GitHub贡献者页面抓取贡献者信息

    Args:
        url: GitHub贡献者页面URL

    Returns:
        贡献者列表，每个元素是包含name和contributions的字典
    """
    print(f"正在从 {url} 抓取贡献者信息...")
    contributors: List[Dict[str, Any]] = []

    # 支持从环境变量读取 GitHub token 以提高成功率
    token = os.environ.get("GITHUB_TOKEN")
    # 使用更标准的用户代理字符串
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) OneDragon-Contrib-Script/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"  # 使用Bearer token格式
        headers["Accept"] = "application/vnd.github.v3+json"

    try:
        # 如果调用的是 graphs/contributors 页面，尽量使用 API 替代
        if "github.com" in url:
            # 解析 owner/repo
            m = re.search(r"github\.com/([^/]+/[^/]+)", url)
            if m:
                owner_repo = m.group(1).rstrip("/")
                api_url = f"https://api.github.com/repos/{owner_repo}/contributors?per_page=100&page=1"

                try:
                    text = http_get(api_url, headers=headers)
                    data = json.loads(text)

                    # 检查是否是错误响应
                    if isinstance(data, dict) and 'message' in data:
                        print(f"GitHub API 错误: {data.get('message', 'Unknown error')}")
                        if 'API rate limit exceeded' in data.get('message', ''):
                            print("提示: GitHub API 速率限制已达到，请稍后再试或设置 GITHUB_TOKEN 环境变量")
                        return []

                    for item in data:
                        name = item.get("login") or item.get("name") or ""
                        contributions_count = item.get("contributions")
                        contrib_str = f"{contributions_count} contributions" if contributions_count is not None else ""
                        if name:
                            contributors.append({"name": name, "contributions": contrib_str})
                    print(f"成功抓取 {len(contributors)} 个贡献者信息 (via API)")
                    return contributors
                except Exception as api_error:
                    print(f"API 请求失败: {api_error}")
                    # 如果API失败，回退到HTML解析
                    pass

        # 回退：直接抓取页面并解析HTML（保持原有解析逻辑）
        html_content = http_get(url, headers=headers)
        pattern = r'<a class="Link--secondary".*?>(.*?)</a>.*?<span class="text-muted text-small">([0-9,]+) contributions</span>'
        matches = re.finditer(pattern, html_content, re.DOTALL)
        for match in matches:
            name = match.group(1).strip()
            contributions = match.group(2).strip().replace(",", "")
            if name and contributions:
                contributors.append({"name": name, "contributions": f"{contributions} contributions"})

        print(f"成功抓取 {len(contributors)} 个贡献者信息 (via HTML)")
        return contributors
    except Exception as e:
        print(f"从GitHub抓取贡献者信息失败: {e}")
        return []


def fetch_qq_channel_authors(url: str) -> List[Dict[str, Any]]:
    """
    从QQ频道抓取作者信息

    Args:
        url: QQ频道URL

    Returns:
        作者列表，每个元素是包含name的字典
    """
    print(f"正在从 {url} 抓取作者信息...")
    # 使用更标准的用户代理字符串
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 OneDragon-Contrib-Script/1.0"}
    try:
        html_content = http_get(url, headers=headers)
        authors: List[Dict[str, Any]] = []
        seen_names = set()  # 用于去重
        
        # 尝试多种可能的模式来匹配作者
        patterns = [
            r'<h3 class="nick hover-underline".*?>(.*?)</h3>',
            r'<div class="nick".*?>(.*?)</div>',
            r'class="nickname".*?>(.*?)</a>',
            r'<p[^>]*class="[^"]*nick[^"]*"[^>]*>(.*?)</p>',
            r'<span[^>]*class="[^"]*nick[^"]*"[^>]*>(.*?)</span>',
            r'nickname["\']?\s*[:=]\s*["\']([^"\'>]+)["\']?',  # JSON-like数据
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, html_content, re.DOTALL | re.IGNORECASE)
            for match in matches:
                name = match.group(1).strip()
                # 清理HTML实体和多余的空白
                name = re.sub(r'<[^>]+>', '', name)  # 移除任何剩余的HTML标签
                name = re.sub(r'&nbsp;|&#160;', ' ', name)  # 替换非断空格
                name = re.sub(r'&[a-z]+;?', '', name)  # 移除其他HTML实体
                name = name.strip()
                
                if name and name not in seen_names and len(name) > 0 and len(name) < 50:  # 过滤掉太长或太短的名字
                    seen_names.add(name)
                    authors.append({"name": name, "role": "社区作者", "contributions": "社区文章贡献"})
        
        print(f"成功抓取 {len(authors)} 个作者信息")
        return authors
    except Exception as e:
        print(f"从QQ频道抓取作者信息失败: {e}")
        return []


def fetch_recent_commits(url: str) -> List[Dict[str, Any]]:
    """
    从GitHub获取最近的commit信息

    Args:
        url: GitHub仓库URL

    Returns:
        最近10个commiter列表
    """
    print(f"正在从 {url} 抓取最近commit信息...")
    token = os.environ.get("GITHUB_TOKEN")
    # 使用更标准的用户代理字符串
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) OneDragon-Contrib-Script/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"  # 使用Bearer token格式
        headers["Accept"] = "application/vnd.github.v3+json"

    try:
        if "github.com" in url:
            m = re.search(r"github\.com/([^/]+/[^/]+)", url)
            if m:
                owner_repo = m.group(1).rstrip("/")
                api_url = f"https://api.github.com/repos/{owner_repo}/commits?per_page=10"

                try:
                    text = http_get(api_url, headers=headers)
                    commits = json.loads(text)

                    # 检查是否是错误响应
                    if isinstance(commits, dict) and 'message' in commits:
                        print(f"GitHub API 错误: {commits.get('message', 'Unknown error')}")
                        if 'API rate limit exceeded' in commits.get('message', ''):
                            print("提示: GitHub API 速率限制已达到，请稍后再试或设置 GITHUB_TOKEN 环境变量")
                        return []

                    recent_contributors: List[Dict[str, Any]] = []
                    seen_authors = set()
                    for commit in commits:
                        # 有时 author 信息在不同位置
                        name = None
                        if isinstance(commit, dict):
                            if commit.get("author") and isinstance(commit.get("author"), dict):
                                name = commit["author"].get("login")
                            elif not name and commit.get("commit") and commit["commit"].get("author"):
                                name = commit["commit"]["author"].get("name")
                        if name and name not in seen_authors:
                            seen_authors.add(name)
                            recent_contributors.append({"name": name, "role": "开发者", "contributions": "近期提交"})

                    print(f"成功抓取 {len(recent_contributors)} 个近期贡献者")
                    return recent_contributors
                except Exception as api_error:
                    print(f"Commit API 请求失败: {api_error}")
                    return []

        # 回退：如果API不可用则返回空列表
        print("抓取最近commit信息失败: 无法通过API获得数据")
        return []
    except Exception as e:
        print(f"抓取最近commit信息失败: {e}")
        return []


def update_contributors_file():
    """
    更新contributors.yaml文件
    """
    # 定义各个来源的URL
    github_repo_url = "https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon"
    github_docs_url = (
        "https://github.com/OneDragon-Anything/onedragon-anything.github.io"
    )
    qq_channel_url = "https://pd.qq.com/g/onedrag00n?subc=714508468"

    # 抓取各个来源的贡献者信息
    core_contributors = fetch_github_contributors(
        f"{github_repo_url}/graphs/contributors"
    )
    recent_contributors = fetch_recent_commits(github_repo_url)
    docs_contributors = fetch_github_contributors(
        f"{github_docs_url}/graphs/contributors"
    )
    community_maintainers = fetch_qq_channel_authors(qq_channel_url)

    # 读取现有文件内容
    contributors_file = "contributors.yaml"
    existing_data = {}

    if os.path.exists(contributors_file):
        with open(contributors_file, "r", encoding="utf-8") as f:
            existing_data = yaml.safe_load(f)

    # 更新贡献者信息
    contributors_data = {
        "# 项目贡献者信息": "",
        "# 此文件包含项目的所有贡献者信息，用于滚动字幕显示": "",
        "# 更新时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "# 项目核心贡献者（来自GitHub）": "",
        "core_contributors": core_contributors[:10],  # 只保留前10个核心贡献者
        "# 近期贡献者（最后10个commiter，合并显示）": "",
        "recent_contributors": [{"name": "近期贡献者", "members": [c["name"] for c in recent_contributors[:10]], "contributions": f"最近{len(recent_contributors[:10])}次提交"}] if len(recent_contributors) >= 1 else [],  # 将近期贡献者合并为一个条目，如果没有则为空
        "# 文档组贡献者（来自官网/官方文档）": "",
        "documentation_contributors": docs_contributors[:10],  # 只保留前10个文档贡献者
        "# 社区维护者（来自QQ频道，合并显示）": "",
        "community_maintainers": [{"name": "社区维护者", "members": [c["name"] for c in community_maintainers[:50]], "contributions": f"QQ频道{len(community_maintainers[:50])}名作者"}] if len(community_maintainers) >= 1 else [],  # 将社区维护者合并为一个条目，如果没有则为空，最多显示20个
        "# 其他贡献者（手动添加）": "",
        "other_contributors": existing_data.get(
            "other_contributors", [
                {"name": "模范好市民🏅", "members": ["(#_#)", "Theresa Apocalypse", "YU4106", "顾北然"]},
                {"name": "测试先锋队🚀", "members": ["自然"]},
                {"name": "空洞观察员📚", "members": ["乌萨奇", "自然", "红豆泥", "茶峒"]}
            ]
        ),  # 保留手动添加的贡献者，提供默认模板，基于现有格式
    }

    # 写入更新后的文件
    with open(contributors_file, "w", encoding="utf-8") as f:
        yaml.dump(
            contributors_data,
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    print(f"成功更新 {contributors_file} 文件")
    print(f"核心贡献者: {len(contributors_data['core_contributors'])}")
    print(f"近期贡献者: {len(contributors_data['recent_contributors'])}")
    print(f"文档贡献者: {len(contributors_data['documentation_contributors'])}")
    print(f"社区维护者: {len(contributors_data['community_maintainers'])}")
    print(f"其他贡献者: {len(contributors_data['other_contributors'])}")


if __name__ == "__main__":
    print("开始更新贡献者信息...")
    update_contributors_file()
    print("贡献者信息更新完成！")
