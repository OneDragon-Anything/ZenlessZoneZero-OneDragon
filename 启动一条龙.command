#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname "$0")" && pwd)"
USER_HOME="${HOME:?无法确定当前用户的 HOME}"

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "此启动脚本仅支持 macOS。"
    read -r -p "按 Enter 键关闭此窗口..."
    exit 1
fi

if [[ "$(id -u)" -eq 0 ]]; then
    echo "请以当前 macOS 登录用户启动一条龙，不要使用 sudo。"
    read -r -p "按 Enter 键关闭此窗口..."
    exit 1
fi

UV_BIN="$(command -v uv 2>/dev/null || true)"
if [[ -z "$UV_BIN" ]]; then
    for candidate in "$USER_HOME/.local/bin/uv" /opt/homebrew/bin/uv /usr/local/bin/uv; do
        if [[ -x "$candidate" ]]; then
            UV_BIN="$candidate"
            break
        fi
    done
fi

if [[ -z "$UV_BIN" ]]; then
    echo "找不到 uv，请先安装 uv。"
    read -r -p "按 Enter 键关闭此窗口..."
    exit 1
fi

if [[ ! -x "$PROJECT_DIR/.venv/bin/python" ]]; then
    echo "找不到项目虚拟环境：$PROJECT_DIR/.venv"
    echo "请先在项目目录运行：uv sync"
    read -r -p "按 Enter 键关闭此窗口..."
    exit 1
fi

if ! "$PROJECT_DIR/tools/macos/build_vhid_click_client.sh"; then
    echo "虚拟 HID 点击客户端构建失败。"
    read -r -p "按 Enter 键关闭此窗口..." || true
    exit 1
fi

echo "需要管理员授权启动 Karabiner 虚拟 HID 客户端；一条龙图形界面仍以当前用户运行。"
if ! sudo -v; then
    echo "未获得虚拟 HID 客户端所需的管理员授权，已取消启动。"
    read -r -p "按 Enter 键关闭此窗口..." || true
    exit 1
fi

UV_ARGS=(run --project "$PROJECT_DIR" --no-sync)
if [[ -f "$PROJECT_DIR/.env" ]]; then
    UV_ARGS+=(--env-file "$PROJECT_DIR/.env")
fi
UV_ARGS+=("$PROJECT_DIR/src/zzz_od/gui/app.py")

USER_PATH="$USER_HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$(dirname "$UV_BIN")"

cd "$PROJECT_DIR"
echo "以当前登录用户启动一条龙。首次使用时，请按 macOS 提示为实际运行程序授予屏幕录制和辅助功能权限。"
if /usr/bin/env \
    "HOME=$USER_HOME" \
    "PATH=$USER_PATH" \
    "PYTHONPATH=$PROJECT_DIR/src" \
    "$UV_BIN" "${UV_ARGS[@]}"; then
    EXIT_CODE=0
else
    EXIT_CODE=$?
fi

if [[ "$EXIT_CODE" -eq 0 ]]; then
    echo "一条龙已退出。"
else
    echo "一条龙退出时发生错误，退出码：$EXIT_CODE"
fi
read -r -p "按 Enter 键关闭此窗口..." || true
exit "$EXIT_CODE"
