# push-tmux 使用ガイド

## クイックスタート

### 最小構成での使い方

1. **初期設定**
   ```bash
   # APIキーを環境変数に設定
   echo "PUSHBULLET_TOKEN=your-api-key-here" > .env
   ```

2. **ディレクトリごとの使用**
   ```bash
   # プロジェクトディレクトリに移動
   cd ~/projects/1on1-ver2
   
   # デバイスを登録（ディレクトリ名が自動的にデバイス名になる）
   push-tmux register
   
   # tmuxセッションを開始
   tmux new -s 1on1-ver2
   
   # tmux内でリスナーを起動
   push-tmux listen
   ```

3. **メッセージ送信**
   - Pushbulletアプリから「1on1-ver2」デバイス宛にメッセージを送信
   - メッセージは自動的にtmuxの現在のセッションに入力される

## 典型的な使用パターン

### パターン1: プロジェクトごとの独立した環境

各プロジェクトで独立したPushbulletデバイスとtmuxセッションを使用する方法です。

```bash
# プロジェクトA用の設定
cd ~/work/project-a
cat > .env << EOF
PUSHBULLET_TOKEN=o.xxxxxxxxxxxxx
DEVICE_NAME=project-a
EOF

push-tmux register
tmux new -s project-a -d
tmux send -t project-a "push-tmux listen" Enter
tmux attach -t project-a
```

### パターン2: 自動起動スクリプト

プロジェクト開始時に自動的に環境を構築するスクリプト：

```bash
#!/bin/bash
# ~/bin/start-push-tmux.sh

# ディレクトリ名をプロジェクト名として使用
PROJECT=$(basename $(pwd))

# 環境変数設定
export DEVICE_NAME=$PROJECT

# デバイスが未登録なら登録
if ! push-tmux list-devices | grep -q $PROJECT; then
    push-tmux register
fi

# tmuxセッションを作成または再利用
if ! tmux has-session -t $PROJECT 2>/dev/null; then
    # 新規セッション作成
    tmux new-session -d -s $PROJECT
    
    # 最初のウィンドウでlistenを開始
    tmux send-keys -t $PROJECT:0 "push-tmux listen" C-m
    
    # 作業用の新しいウィンドウを作成
    tmux new-window -t $PROJECT:1 -n "work"
fi

# セッションにアタッチ
tmux attach-session -t $PROJECT
```

### パターン3: systemdサービスとして実行

バックグラウンドで常時実行する場合：

```ini
# ~/.config/systemd/user/push-tmux@.service
[Unit]
Description=Push-tmux listener for %i
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/user/projects/%i
Environment="DEVICE_NAME=%i"
ExecStart=/usr/local/bin/push-tmux listen
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
```

使用方法：
```bash
# サービスを有効化
systemctl --user enable push-tmux@1on1-ver2.service
systemctl --user start push-tmux@1on1-ver2.service

# ログ確認
journalctl --user -u push-tmux@1on1-ver2.service -f
```

## メッセージの送信方法

### Pushbulletアプリから

1. Pushbulletアプリを開く
2. 「New Push」または「+」ボタンをタップ
3. 「Note」を選択
4. デバイスリストから対象デバイス（例：「1on1-ver2」）を選択
5. タイトルと本文を入力して送信

### コマンドラインから（テスト用）

```python
#!/usr/bin/env python3
# send-to-device.py
import asyncio
import sys
from async_pushbullet import AsyncPushbullet
import os
from dotenv import load_dotenv

load_dotenv()

async def send_message(device_name, message):
    api_key = os.getenv('PUSHBULLET_TOKEN')
    async with AsyncPushbullet(api_key) as pb:
        devices = await pb.get_devices()
        for device in devices:
            if device.get('nickname') == device_name:
                await pb.push_note('Command', message, device['iden'])
                print(f"Sent to {device_name}")
                return
        print(f"Device {device_name} not found")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: send-to-device.py <device-name> <message>")
        sys.exit(1)
    
    asyncio.run(send_message(sys.argv[1], sys.argv[2]))
```

使用例：
```bash
python send-to-device.py 1on1-ver2 "echo 'Hello from Pushbullet'"
```

## tmuxとの連携

### tmuxセッションの構成

推奨されるtmuxセッション構成：

```
Session: project-name
├── Window 0: listener (push-tmux listen実行用)
├── Window 1: main (メイン作業用)
├── Window 2: logs (ログ監視用)
└── Window 3: test (テスト実行用)
```

セットアップスクリプト：
```bash
#!/bin/bash
PROJECT=$(basename $(pwd))

tmux new-session -d -s $PROJECT -n listener
tmux send-keys -t $PROJECT:listener "push-tmux listen" C-m

tmux new-window -t $PROJECT -n main
tmux new-window -t $PROJECT -n logs
tmux new-window -t $PROJECT -n test

tmux select-window -t $PROJECT:main
tmux attach-session -t $PROJECT
```

### カスタムターゲット設定

特定のウィンドウ/ペインに送信したい場合：

```toml
# config.toml
[tmux]
target_session = "current"  # または固定のセッション名
target_window = "1"          # mainウィンドウ
target_pane = "0"            # 最初のペイン
```

または一時的に変更：
```bash
push-tmux send-key "test" --session project --window 2 --pane 1
```

## トラブルシューティング

### よくある問題と解決方法

**Q: メッセージが受信されない**
```bash
# デバッグモードで実行
DEBUG_PUSHBULLET=1 push-tmux listen

# WebSocket接続を確認
curl -H "Access-Token: $PUSHBULLET_TOKEN" \
     https://api.pushbullet.com/v2/users/me
```

**Q: 間違ったtmuxセッションに送信される**
```bash
# 現在のtmux情報を確認
tmux display-message -p "Session: #{session_name}"
tmux display-message -p "Window: #{window_index}"
tmux display-message -p "Pane: #{pane_index}"

# config.tomlをリセット
rm config.toml
```

**Q: デバイス名が重複している**
```bash
# 既存デバイスを確認
push-tmux list-devices

# 重複デバイスを削除
push-tmux delete-device --name duplicate-name
```

## ベストプラクティス

1. **プロジェクトごとに.envファイルを作成**
   - 各プロジェクトで独立した設定を維持
   - .gitignoreに.envを追加

2. **デバイス名の命名規則**
   - プロジェクト名と同じにする
   - 環境を含める（例：`project-dev`, `project-prod`）
   - 日付を含める（例：`project-20240108`）

3. **tmuxセッション管理**
   - tmuxinatorやtmux-resurrectと併用
   - セッション名とデバイス名を統一

4. **セキュリティ**
   - APIキーは絶対にコミットしない
   - デバイス名に個人情報を含めない
   - 定期的に未使用デバイスを削除

## 応用例

### CI/CDパイプラインへの組み込み

```yaml
# .github/workflows/notify.yml
name: Notify via Pushbullet
on:
  push:
    branches: [main]
jobs:
  notify:
    runs-on: ubuntu-latest
    steps:
      - name: Send notification
        run: |
          curl -X POST https://api.pushbullet.com/v2/pushes \
            -H "Access-Token: ${{ secrets.PUSHBULLET_TOKEN }}" \
            -H "Content-Type: application/json" \
            -d '{
              "type": "note",
              "title": "Build Complete",
              "body": "git pull && make test",
              "device_iden": "${{ secrets.DEVICE_IDEN }}"
            }'
```

### リモートコマンド実行

```bash
# remote-exec.sh
#!/bin/bash
# 別マシンからコマンドを実行

DEVICE="remote-server"
COMMAND="$*"

python send-to-device.py $DEVICE "$COMMAND"
echo "Command sent to $DEVICE: $COMMAND"
```

使用例：
```bash
./remote-exec.sh "cd /var/log && tail -f syslog"
./remote-exec.sh "docker-compose restart"
./remote-exec.sh "git pull && npm test"
```