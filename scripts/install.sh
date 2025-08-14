#!/bin/bash

# install.sh - push-tmuxのインストールスクリプト

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# インストール先
INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/bin}"

echo -e "${GREEN}push-tmux インストールスクリプト${NC}"
echo ""

# インストールディレクトリの作成
if [ ! -d "$INSTALL_DIR" ]; then
    echo "インストールディレクトリを作成: $INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
fi

# PATHチェック
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo -e "${YELLOW}警告: $INSTALL_DIR がPATHに含まれていません${NC}"
    echo "以下を ~/.bashrc または ~/.zshrc に追加してください:"
    echo "  export PATH=\"\$PATH:$INSTALL_DIR\""
    echo ""
fi

# Pythonパッケージのインストール
if command -v uv &> /dev/null; then
    echo "uvを使用してパッケージをインストール..."
    uv pip install -e .
elif command -v pip &> /dev/null; then
    echo "pipを使用してパッケージをインストール..."
    pip install -e .
else
    echo -e "${RED}エラー: pipまたはuvが見つかりません${NC}"
    exit 1
fi

# スクリプトのインストール
echo ""
echo "スクリプトをインストール..."

# push-tmux-sessionスクリプト
if [ -f "push-tmux-session" ]; then
    cp push-tmux-session "$INSTALL_DIR/"
    chmod +x "$INSTALL_DIR/push-tmux-session"
    echo "  ✓ push-tmux-session"
fi

# ptmuxスクリプト
if [ -f "ptmux" ]; then
    cp ptmux "$INSTALL_DIR/"
    chmod +x "$INSTALL_DIR/ptmux"
    echo "  ✓ ptmux"
fi

# 設定ファイルのサンプル作成
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/push-tmux"
if [ ! -d "$CONFIG_DIR" ]; then
    mkdir -p "$CONFIG_DIR"
    echo "設定ディレクトリを作成: $CONFIG_DIR"
fi

# サンプル.envファイル
if [ ! -f "$CONFIG_DIR/.env.sample" ]; then
    cat > "$CONFIG_DIR/.env.sample" << 'EOF'
# Pushbullet APIトークン（必須）
# https://www.pushbullet.com/#settings/account から取得
PUSHBULLET_TOKEN=o.xxxxxxxxxxxxxxxxxxxxx

# デバイス名（省略時はディレクトリ名を使用）
# DEVICE_NAME=my-device

# tmux設定（オプション）
# TMUX_WINDOW_MAIN=1      # メインウィンドウ番号
# TMUX_WINDOW_LISTEN=0    # リスナーウィンドウ番号
# TMUX_CREATE_LOGS_WINDOW=1  # logsウィンドウを作成
# TMUX_CREATE_TEST_WINDOW=1  # testウィンドウを作成
EOF
    echo "  ✓ サンプル設定ファイル: $CONFIG_DIR/.env.sample"
fi

# グローバル設定スクリプト
cat > "$INSTALL_DIR/push-tmux-init" << 'EOF'
#!/bin/bash
# push-tmux-init - グローバル設定の初期化

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/push-tmux"

# グローバル設定が存在すれば読み込む
if [ -f "$CONFIG_DIR/.env" ]; then
    export $(grep -v '^#' "$CONFIG_DIR/.env" | xargs)
fi

# ローカル設定が存在すれば上書き
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi
EOF
chmod +x "$INSTALL_DIR/push-tmux-init"
echo "  ✓ push-tmux-init"

# bashコンプリーション
COMPLETION_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/bash-completion/completions"
if [ -d "$COMPLETION_DIR" ] || mkdir -p "$COMPLETION_DIR" 2>/dev/null; then
    cat > "$COMPLETION_DIR/push-tmux-session" << 'EOF'
# bash completion for push-tmux-session

_push_tmux_session() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    opts="-h --help -d --detach -k --kill -r --resume -n --name -w --window -p --pane --no-register"

    case "${prev}" in
        -n|--name)
            # デバイス名の補完（push-tmux list-devicesから取得）
            if command -v push-tmux &>/dev/null; then
                local devices=$(push-tmux list-devices 2>/dev/null | grep "名前:" | sed 's/名前: //')
                COMPREPLY=( $(compgen -W "${devices}" -- ${cur}) )
            fi
            return 0
            ;;
        -w|--window|-p|--pane)
            # 数字の補完
            COMPREPLY=( $(compgen -W "0 1 2 3 4 5 6 7 8 9" -- ${cur}) )
            return 0
            ;;
        *)
            if [[ ${cur} == -* ]] ; then
                COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
                return 0
            else
                # tmuxセッション名の補完
                if command -v tmux &>/dev/null; then
                    local sessions=$(tmux list-sessions -F "#{session_name}" 2>/dev/null)
                    COMPREPLY=( $(compgen -W "${sessions}" -- ${cur}) )
                fi
            fi
            ;;
    esac
}

complete -F _push_tmux_session push-tmux-session
EOF
    echo "  ✓ bash補完: $COMPLETION_DIR/push-tmux-session"
fi

# エイリアスの提案
echo ""
echo -e "${GREEN}インストール完了！${NC}"
echo ""
echo "使い方:"
echo "  1. APIトークンを設定:"
echo "     echo 'PUSHBULLET_TOKEN=your-token' > ~/.config/push-tmux/.env"
echo ""
echo "  2. プロジェクトディレクトリで実行:"
echo "     ptmux                    # 簡易起動（ディレクトリ名を使用）"
echo "     push-tmux-session        # 詳細オプション付き起動"
echo ""
echo "  3. 便利なエイリアス（~/.bashrcに追加）:"
echo "     alias pts='push-tmux-session'"
echo "     alias ptr='push-tmux-session -r'  # 再開"
echo "     alias ptk='push-tmux-session -k'  # 再起動"
echo ""

# パスの再読み込み提案
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo -e "${YELLOW}注意: パスを更新するには、シェルを再起動するか以下を実行してください:${NC}"
    echo "  source ~/.bashrc  # bashの場合"
    echo "  source ~/.zshrc   # zshの場合"
fi