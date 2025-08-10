# push-tmux

Pushbulletのメッセージを特定のtmuxセッションに送信するCLIツール

## 概要

push-tmuxは、Pushbulletで受信したメッセージを自動的にtmuxセッションに送信するツールです。ディレクトリごとに異なるデバイス名で動作させることで、プロジェクト別のメッセージ管理が可能です。

### 主な機能

- 📱 **デバイス別メッセージルーティング** - プロジェクトごとに異なるデバイスを使用
- 🔄 **自動再起動デーモンモード** - プロセス監視と異常終了時の自動復旧
- 🎯 **自動ルーティング** - デバイス名と同じtmuxセッションへ自動送信
- 📝 **詳細なログ機能** - デバッグとトラブルシューティング支援
- ⚙️ **柔軟な設定** - TOML形式での詳細設定
- 🚀 **モジュール化アーキテクチャ** - パッケージ構造による保守性向上
- 📦 **標準ライブラリ使用** - asyncpushbulletなど信頼性の高い外部ライブラリを活用

## 主な使用方法

### 1. クイックスタート

```bash
# 1. Python環境セットアップ
mise trust && mise install

# 2. デバイス登録（複数デバイスを登録可能）
push-tmux device register  # 現在のディレクトリ名でデバイス登録

# 3. tmuxセッション作成（登録したデバイス名と同じ名前で）
tmux new-session -s device-name -d  # 複数作成可能

# 4. リスナー開始（すべてのデバイスを自動処理）
push-tmux start  # 自動ルーティングモードがデフォルト
```

### 2. ディレクトリベースのワークフロー

特定のプロジェクトディレクトリ（例：`1on1-ver2`）で作業する場合の推奨フローです。

#### 1. プロジェクトディレクトリへ移動
```bash
cd ~/projects/webapp
```

#### 2. 環境変数でデバイス名を設定
```bash
# .envファイルに設定
echo "DEVICE_NAME=webapp" >> .env

# または環境変数として設定
export DEVICE_NAME=webapp
```

注: `DEVICE_NAME`が設定されていない場合、現在のディレクトリ名が自動的にデバイス名として使用されます。

#### 3. デバイスを登録
```bash
push-tmux device register
# => デバイス 'webapp' を登録しました。
```

#### 4. tmuxセッションを開始
```bash
# 新しいtmuxセッションを開始
tmux new-session -s webapp

# または既存のセッションにアタッチ
tmux attach -t webapp
```

#### 5. リスナーを開始
```bash
# デフォルト：自動ルーティングモード（すべてのデバイスのメッセージを処理）
push-tmux start
# => 自動ルーティングモードで起動します

# 特定デバイスのみ受信したい場合
push-tmux start --no-auto-route
# => デバイス 'webapp' (ID: xxx) として待ち受けます

# デーモンモードで実行（推奨、自動再起動機能付き）
push-tmux start --daemon
# => 自動ルーティングモードでデーモンとして実行されます
```

#### 6. メッセージを送信
別のデバイス（スマートフォンなど）から、Pushbulletで「webapp」デバイス宛にメッセージを送信すると、自動的に現在のtmuxセッションの最初のウィンドウ・最初のペインにメッセージが入力されます。

## 動作の仕組み

1. **デバイス識別**: 各ディレクトリで異なるデバイス名を使用することで、プロジェクト別のメッセージルーティングを実現
2. **メッセージフィルタリング**: デバイス固有のメッセージを処理し、適切にルーティング
3. **tmux統合**: 受信したメッセージは対応するtmuxセッションに自動送信

### セッション解決の優先順位

tmuxセッションは以下の順序で決定されます：

1. **`[device_mapping]`での明示的なマッピング**（最優先）
2. **デバイス名マッチング**（`use_device_name_as_session=true`の場合、デフォルト）
3. **`default_target_session`設定**（フォールバック）
4. **現在のtmuxセッション**（最終手段）

## 設定

### 環境変数（.envファイル）

```bash
# Pushbullet APIキー（必須）
PUSHBULLET_TOKEN=o.xxxxxxxxxxxxxxxxxxxxx

# デバイス名（省略時は現在のディレクトリ名）
DEVICE_NAME=my-project
```

### config.toml（オプション）

設定ファイルで詳細な動作をカスタマイズできます。`config-example.toml`を参考にしてください。

```toml
[tmux]
# target_session = "main"   # 省略時はデバイス名と同じセッション名
# target_window = "1"       # 省略時は最初のウィンドウ（デフォルト）
# target_pane = "0"         # 省略時は最初のペイン（デフォルト）

[device_mapping]
# デバイス名とtmuxターゲットのマッピング
# シンプルな指定（セッションのみ）
"project-a" = "dev-session"    # project-aデバイス → dev-sessionセッション

# 詳細な指定（セッション、ウィンドウ、ペイン）
[device_mapping."mobile-app"]
session = "frontend"    # セッション名（必須）
window = "2"           # ウィンドウインデックス（省略時は "first"）
pane = "0"            # ペインインデックス（省略時は "first"）

[daemon]
reload_interval = 1.0       # ファイル監視間隔（秒）
watch_files = ["config.toml", ".env"]  # 監視ファイル

[daemon.logging]
log_level = "INFO"          # ログレベル
log_file = ""              # ログファイルパス（空文字で標準出力）
```

## コマンド一覧

### デバイス管理
```bash
# デバイスを登録
push-tmux device register
push-tmux device register --name custom-device

# デバイス一覧を表示
push-tmux device list

# デバイスを削除（インタラクティブ選択）
push-tmux device delete

# 特定デバイスを削除
push-tmux device delete --name device-name
push-tmux device delete --id device-id

# 非アクティブデバイスも含めて削除
push-tmux device delete --include-inactive
```

### メッセージ受信
```bash
# デフォルト：自動ルーティングモード（すべてのデバイスを処理）
push-tmux start

# 現在のデバイスのみ受信
push-tmux start --no-auto-route

# 特定のデバイスとして受信待機
push-tmux start --device other-device

# 全デバイスからのメッセージを受信（ルーティングなし）
push-tmux start --all-devices

# デバッグモードで実行
push-tmux start --debug
```

### デーモンモード
```bash
# デフォルト：自動ルーティングモードでデーモン実行
push-tmux start --daemon

# 現在のデバイスのみでデーモン実行
push-tmux start --daemon --no-auto-route

# 全デバイスからのメッセージを受信
push-tmux start --daemon --all-devices

# カスタム監視間隔
push-tmux start --daemon --reload-interval 5.0

# 追加ファイル監視
push-tmux start --daemon --watch-files myconfig.ini --watch-files secrets.env

# デバッグモード
push-tmux start --daemon --debug
```

### テスト
```bash
# tmuxに直接メッセージを送信（テスト用）
push-tmux send "test message"
push-tmux send "test" --session mysession --window 0 --pane 1
```

## 実用例

### プロジェクトごとの使い分け

```bash
# プロジェクトA
cd ~/projects/project-a
echo "DEVICE_NAME=project-a" > .env
push-tmux device register
tmux new -s project-a
push-tmux start --daemon  # project-a宛のメッセージのみ受信（自動再起動付き）

# プロジェクトB（別ターミナル）
cd ~/projects/project-b
echo "DEVICE_NAME=project-b" > .env
push-tmux device register
tmux new -s project-b
push-tmux start --daemon  # project-b宛のメッセージのみ受信（自動再起動付き）
```

### デバイスマッピングの使用例

異なるデバイス名とtmuxセッション名を使いたい場合：

```toml
# config.toml
[device_mapping]
# シンプルな指定（セッションのみ）
"mobile-dev" = "frontend"      # mobile-devデバイス → frontendセッション

# 詳細な指定（特定のウィンドウ・ペインを指定）
[device_mapping."backend-api"]
session = "backend"
window = "1"        # 2番目のウィンドウ（インデックス1）
pane = "2"         # 3番目のペイン（インデックス2）

[device_mapping."db-admin"]
session = "database"
window = "first"    # 最初のウィンドウ（デフォルト）
pane = "first"     # 最初のペイン（デフォルト）
```

```bash
# frontendセッションで作業
tmux new -s frontend
cd ~/projects/mobile-app
export DEVICE_NAME=mobile-dev
push-tmux device register
push-tmux start  # mobile-dev宛のメッセージをfrontendセッションで受信

# backend-apiの場合、backendセッションのwindow 1, pane 2に送信される
cd ~/projects/api
export DEVICE_NAME=backend-api
push-tmux device register
push-tmux start  # メッセージが特定のウィンドウ・ペインに送信される
```

### 自動ルーティングモード

複数のプロジェクトを同時に扱う場合に便利です：

```bash
# すべてのデバイスのメッセージを受信し、
# デバイス名と同じtmuxセッションに自動送信
push-tmux start --daemon  # 自動ルーティングがデフォルト

# セッション準備
tmux new -s project-a -d
tmux new -s project-b -d
tmux new -s project-c -d

# 各デバイス宛のメッセージが対応するセッションに自動送信されます
```

### スクリプト化

```bash
#!/bin/bash
# start-project.sh

PROJECT_NAME=$(basename $(pwd))
export DEVICE_NAME=$PROJECT_NAME

# デバイス登録
push-tmux device register

# tmuxセッション開始
tmux new-session -d -s $PROJECT_NAME

# push-tmuxデーモンを開始（自動再起動付き）
tmux send-keys -t $PROJECT_NAME "push-tmux start --daemon" C-m

# セッションにアタッチ
tmux attach -t $PROJECT_NAME
```

### systemdサービスとして実行

本番環境での常時稼働に適しています：

```bash
# /etc/systemd/system/push-tmux.service
[Unit]
Description=Push-tmux daemon
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/project
Environment=PUSHBULLET_TOKEN=your-token
ExecStart=/path/to/venv/bin/push-tmux start --daemon --auto-route
Restart=always

[Install]
WantedBy=multi-user.target
```

## トラブルシューティング

### メッセージが受信されない場合

1. デバイスが正しく登録されているか確認
   ```bash
   push-tmux device list
   ```

2. 正しいデバイス宛にメッセージを送信しているか確認
   - 全デバイス宛のメッセージは無視されます
   - 特定のデバイスを選択して送信してください

3. APIキーが正しく設定されているか確認
   ```bash
   cat .env | grep PUSHBULLET_TOKEN
   ```

### tmuxにメッセージが送信されない場合

1. tmuxセッション内で実行しているか確認
   ```bash
   echo $TMUX  # 値があればtmux内
   ```

2. ターゲットセッション/ウィンドウ/ペインが存在するか確認
   ```bash
   tmux list-sessions
   tmux list-windows
   tmux list-panes
   ```

### デーモンが頻繁に再起動する場合

1. ログを確認
   ```bash
   # デバッグモードで実行
   push-tmux start --daemon --debug
   ```

2. 監視間隔を調整
   ```bash
   # 監視間隔を長くする
   push-tmux start --daemon --reload-interval 5.0
   ```

3. 監視ファイルを確認
   - ログファイルなど頻繁に変更されるファイルが監視対象になっていないか確認
   - `config.toml`の`ignore_patterns`で除外設定

## インストール

```bash
# リポジトリをクローン
git clone https://github.com/cuzic/push-tmux.git
cd push-tmux

# mise環境のセットアップ（Python 3.12と依存関係を自動インストール）
mise trust
mise install

# 開発用依存関係のインストール
uv pip install -e ".[test]"

# 通常のインストール
uv pip install -e .
```

## 必要要件

- Python 3.12以上（mise設定）
- tmux
- Pushbullet アカウントとAPIキー
- mise（Python環境管理）
- uv（高速パッケージマネージャー）

## セキュリティ

- `.env`ファイルは`.gitignore`に追加し、バージョン管理に含めないでください
- APIキーは環境変数で管理し、コード内にハードコードしないでください
- デバイス名にはプロジェクト名など推測しにくい名前を使用してください

## ドキュメント

- [DAEMON.md](DAEMON.md) - デーモンモードの詳細説明
- [config-example.toml](config-example.toml) - 設定ファイルのサンプル
- [CLAUDE.md](CLAUDE.md) - 開発者向けガイド

## 言語

- [English README](README.md)

## ライセンス

MIT