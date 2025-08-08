# push-tmux

Pushbulletのメッセージを特定のtmuxセッションに送信するCLIツール

## 概要

push-tmuxは、Pushbulletで受信したメッセージを自動的にtmuxセッションに送信するツールです。ディレクトリごとに異なるデバイス名で動作させることで、プロジェクト別のメッセージ管理が可能です。

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
# tmuxセッション内で実行
push-tmux listen
# => デバイス '1on1-ver2' (ID: xxx) として待ち受けます。
```

#### 6. メッセージを送信
別のデバイス（スマートフォンなど）から、Pushbulletで「1on1-ver2」デバイス宛にメッセージを送信すると、自動的に現在のtmuxセッションの最初のウィンドウ・最初のペインにメッセージが入力されます。

## 動作の仕組み

1. **デバイス識別**: 各ディレクトリで異なるデバイス名を使用することで、プロジェクト別のメッセージルーティングを実現
2. **メッセージフィルタリング**: 全デバイス宛のメッセージは無視し、特定デバイス宛のメッセージのみを処理
3. **tmux統合**: 受信したメッセージは自動的に現在のtmuxセッションに送信される

### デフォルト動作

- **ターゲットセッション**: tmux内で実行時は現在のセッション、それ以外は`config.toml`で指定
- **ターゲットウィンドウ**: セッションの最初のウィンドウ（インデックス順）
- **ターゲットペイン**: ウィンドウの最初のペイン（インデックス順）

## 設定

### 環境変数（.envファイル）

```bash
# Pushbullet APIキー（必須）
PUSHBULLET_TOKEN=o.xxxxxxxxxxxxxxxxxxxxx

# デバイス名（省略時は現在のディレクトリ名）
DEVICE_NAME=my-project
```

### config.toml（オプション）

tmuxのターゲットを固定したい場合に使用：

```toml
[tmux]
target_session = "main"     # 固定のセッション名
target_window = "1"         # 固定のウィンドウインデックス
target_pane = "0"          # 固定のペインインデックス
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
# 現在のデバイス名で受信待機
push-tmux listen

# 特定のデバイスとして受信待機
push-tmux listen --device other-device
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
push-tmux listen  # project-a宛のメッセージのみ受信

# プロジェクトB（別ターミナル）
cd ~/projects/project-b
echo "DEVICE_NAME=project-b" > .env
push-tmux register
tmux new -s project-b
push-tmux listen  # project-b宛のメッセージのみ受信
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

# push-tmuxリスナーを開始
tmux send-keys -t $PROJECT_NAME "push-tmux listen" C-m

# セッションにアタッチ
tmux attach -t $PROJECT_NAME
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

## セキュリティ

- `.env`ファイルは`.gitignore`に追加し、バージョン管理に含めないでください
- APIキーは環境変数で管理し、コード内にハードコードしないでください
- デバイス名にはプロジェクト名など推測しにくい名前を使用してください

## ライセンス

MIT