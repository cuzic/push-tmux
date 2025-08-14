#!/bin/bash
# push-tmux wrapper script
# Allows running push-tmux from any directory

# push-tmuxプロジェクトのパスを設定
# 環境変数 PUSH_TMUX_DIR で上書き可能
PUSH_TMUX_DIR="${PUSH_TMUX_DIR:-$(cd "$(dirname "$0")" && pwd)}"

# プロジェクトディレクトリが存在するかチェック
if [ ! -d "$PUSH_TMUX_DIR" ]; then
    echo "Error: push-tmux directory not found at $PUSH_TMUX_DIR" >&2
    echo "Set PUSH_TMUX_DIR environment variable to the correct path" >&2
    exit 1
fi

# pyproject.tomlが存在するかチェック（プロジェクトの妥当性確認）
if [ ! -f "$PUSH_TMUX_DIR/pyproject.toml" ]; then
    echo "Error: $PUSH_TMUX_DIR doesn't appear to be a push-tmux project" >&2
    echo "pyproject.toml not found" >&2
    exit 1
fi

# uvが利用可能かチェック
if ! command -v uv >/dev/null 2>&1; then
    echo "Error: uv is not installed" >&2
    echo "Please install uv: https://github.com/astral-sh/uv" >&2
    exit 1
fi

# プロジェクトディレクトリに移動して実行
cd "$PUSH_TMUX_DIR" && exec uv run python -m push_tmux "$@"