# push-tmux

Pushbulletのメッセージを特定のtmuxセッションに送信するCLIツール

## 概要

push-tmuxは、Pushbulletで受信したメッセージを自動的にtmuxセッションに送信するツールです。ディレクトリごとに異なるデバイス名で動作させることで、プロジェクト別のメッセージ管理が可能です。

### 主な機能

- 📱 **デバイス別メッセージルーティング** - プロジェクトごとに異なるデバイスを使用
- 🔄 **自動再起動デーモンモード** - プロセス監視と異常終了時の自動復旧（NEW!）
- 🎯 **自動ルーティング** - デバイス名と同じtmuxセッションへ自動送信
- 📝 **詳細なログ機能** - デバッグとトラブルシューティング支援
- ⚙️ **柔軟な設定** - TOML形式での詳細設定

## 主な使用方法

### ディレクトリベースのワークフロー

特定のプロジェクトディレクトリ（例：`1on1-ver2`）で作業する場合の推奨フローです。

#### 1. プロジェクトディレクトリへ移動
```bash
cd ~/projects/1on1-ver2
```

#### 2. 環境変数でデバイス名を設定
```bash
# .envファイルに設定
echo "DEVICE_NAME=1on1-ver2" >> .env

# または環境変数として設定
export DEVICE_NAME=1on1-ver2
```

注: `DEVICE_NAME`が設定されていない場合、現在のディレクトリ名が自動的にデバイス名として使用されます。

#### 3. デバイスを登録
```bash
push-tmux register
# => デバイス '1on1-ver2' を登録しました。
```

#### 4. tmuxセッションを開始
```bash
# 新しいtmuxセッションを開始
tmux new-session -s 1on1-ver2

# または既存のセッションにアタッチ
tmux attach -t 1on1-ver2
```

#### 5. tmux内でlistenを開始
```bash
# tmuxセッション内で実行（従来の方法）
push-tmux listen
# => デバイス '1on1-ver2' (ID: xxx) として待ち受けます。

# または、デーモンモードで実行（推奨）
push-tmux daemon
# => 自動再起動機能付きで実行されます
```

#### 6. メッセージを送信
別のデバイス（スマートフォンなど）から、Pushbulletで「1on1-ver2」デバイス宛にメッセージを送信すると、自動的に現在のtmuxセッションの最初のウィンドウ・最初のペインにメッセージが入力されます。

## 動作の仕組み

1. **デバイス識別**: 各ディレクトリで異なるデバイス名を使用することで、プロジェクト別のメッセージルーティングを実現
2. **メッセージフィルタリング**: 全デバイス宛のメッセージは無視し、特定デバイス宛のメッセージのみを処理
3. **tmux統合**: 受信したメッセージは自動的に現在のtmuxセッションに送信される

### デフォルト動作

- **ターゲットセッション**: 
  1. `config.toml`の`[tmux].target_session`設定（最優先）
  2. `[device_mapping]`セクションのマッピング設定
  3. デバイス名と同じtmuxセッション名（デフォルト）
  4. 現在のtmuxセッション（tmux内で実行時）
- **ターゲットウィンドウ**: セッションの最初のウィンドウ（インデックス順、デフォルト）
- **ターゲットペイン**: ウィンドウの最初のペイン（インデックス順、デフォルト）

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
# デバイス名とtmuxセッションのマッピング
"project-a" = "dev-session"    # project-aデバイス → dev-sessionセッション
"1on1-ver2" = "work"          # 1on1-ver2デバイス → workセッション

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
push-tmux register
push-tmux register --name custom-device

# デバイス一覧を表示
push-tmux list-devices

# デバイスを削除
push-tmux delete-device --name device-name
push-tmux delete-device --id device-id
```

### メッセージ受信
```bash
# 現在のデバイス名で受信待機（従来の方法）
push-tmux listen

# 特定のデバイスとして受信待機
push-tmux listen --device other-device

# デバッグモードで実行
push-tmux listen --debug

# 自動ルーティングモード（NEW!）
push-tmux listen --auto-route
```

### デーモンモード（NEW!）
```bash
# デーモンモードで実行（自動再起動機能付き）
push-tmux daemon

# 自動ルーティング付きデーモン
push-tmux daemon --auto-route

# カスタム監視間隔
push-tmux daemon --reload-interval 5.0

# 追加ファイル監視
push-tmux daemon --watch-files myconfig.ini --watch-files secrets.env

# デバッグモード
push-tmux daemon --debug
```

### テスト
```bash
# tmuxに直接メッセージを送信（テスト用）
push-tmux send-key "test message"
push-tmux send-key "test" --session mysession --window 0 --pane 1
```

## 実用例

### プロジェクトごとの使い分け

```bash
# プロジェクトA
cd ~/projects/project-a
echo "DEVICE_NAME=project-a" > .env
push-tmux register
tmux new -s project-a
push-tmux daemon  # project-a宛のメッセージのみ受信（自動再起動付き）

# プロジェクトB（別ターミナル）
cd ~/projects/project-b
echo "DEVICE_NAME=project-b" > .env
push-tmux register
tmux new -s project-b
push-tmux daemon  # project-b宛のメッセージのみ受信（自動再起動付き）
```

### デバイスマッピングの使用例

異なるデバイス名とtmuxセッション名を使いたい場合：

```toml
# config.toml
[device_mapping]
"mobile-dev" = "frontend"      # mobile-devデバイス → frontendセッション
"backend-api" = "backend"       # backend-apiデバイス → backendセッション
"db-admin" = "database"         # db-adminデバイス → databaseセッション
```

```bash
# frontendセッションで作業
tmux new -s frontend
cd ~/projects/mobile-app
export DEVICE_NAME=mobile-dev
push-tmux register
push-tmux listen  # mobile-dev宛のメッセージをfrontendセッションで受信
```

### 自動ルーティングモード（NEW!）

複数のプロジェクトを同時に扱う場合に便利です：

```bash
# すべてのデバイスのメッセージを受信し、
# デバイス名と同じtmuxセッションに自動送信
push-tmux daemon --auto-route

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
push-tmux register

# tmuxセッション開始
tmux new-session -d -s $PROJECT_NAME

# push-tmuxデーモンを開始（自動再起動付き）
tmux send-keys -t $PROJECT_NAME "push-tmux daemon" C-m

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
ExecStart=/path/to/venv/bin/push-tmux daemon --auto-route
Restart=always

[Install]
WantedBy=multi-user.target
```

## トラブルシューティング

### メッセージが受信されない場合

1. デバイスが正しく登録されているか確認
   ```bash
   push-tmux list-devices
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
   push-tmux daemon --debug
   ```

2. 監視間隔を調整
   ```bash
   # 監視間隔を長くする
   push-tmux daemon --reload-interval 5.0
   ```

3. 監視ファイルを確認
   - ログファイルなど頻繁に変更されるファイルが監視対象になっていないか確認
   - `config.toml`の`ignore_patterns`で除外設定

## インストール

```bash
# リポジトリをクローン
git clone https://github.com/cuzic/push-tmux.git
cd push-tmux

# 依存関係をインストール（uv推奨）
uv pip install -e .

# または pip
pip install -e .
```

## 必要要件

- Python 3.10以上
- tmux
- Pushbullet アカウントとAPIキー

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