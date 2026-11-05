#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname "$0")/../.." && pwd)"
BUILD_DIR="$PROJECT_DIR/.install/macos-vhid"
SOURCE_DIR="$BUILD_DIR/upstream"
CLIENT_SOURCE="$PROJECT_DIR/tools/macos/vhid_click_client.cpp"
CLIENT_BINARY="$BUILD_DIR/vhid-click-client"

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "虚拟 HID 点击客户端只能在 macOS 上构建。" >&2
    exit 1
fi

mkdir -p "$BUILD_DIR"

if [[ ! -d "$SOURCE_DIR/.git" ]]; then
    if [[ -e "$SOURCE_DIR" ]]; then
        echo "上游源码目录存在但不是 Git 仓库：$SOURCE_DIR" >&2
        exit 1
    fi
    git clone --depth 1 --branch v8.7.0 \
        https://github.com/pqrs-org/Karabiner-DriverKit-VirtualHIDDevice.git \
        "$SOURCE_DIR"
fi

UPSTREAM_TAG="$(git -C "$SOURCE_DIR" describe --tags --exact-match HEAD 2>/dev/null || true)"
if [[ "$UPSTREAM_TAG" != "v8.7.0" ]]; then
    echo "Karabiner 客户端源码版本不匹配：预期 v8.7.0，实际 ${UPSTREAM_TAG:-未知版本}" >&2
    exit 1
fi

if [[ -x "$CLIENT_BINARY" && "$CLIENT_BINARY" -nt "$CLIENT_SOURCE" ]]; then
    exit 0
fi

CLANGXX="$(xcrun --find clang++)"
MACOS_SDK="$(xcrun --show-sdk-path)"
"$CLANGXX" \
    -std=c++23 \
    -O2 \
    -Wall \
    -Wextra \
    -isysroot "$MACOS_SDK" \
    -I "$SOURCE_DIR/include" \
    -I "$SOURCE_DIR/vendor/vendor/include" \
    "$CLIENT_SOURCE" \
    -o "$CLIENT_BINARY" \
    -pthread

chmod 755 "$CLIENT_BINARY"
echo "已构建虚拟 HID 点击客户端：$CLIENT_BINARY"
