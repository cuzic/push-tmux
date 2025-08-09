# push-tmux Daemon 機能

hupper ライブラリを使った自動再起動機能付きのデーモンモードを追加しました。

## 機能概要

- **自動再起動**: プロセス異常終了時の自動復旧
- **ファイル監視**: 設定ファイルやコード変更時の自動再起動
- **ログ機能**: 詳細なログ出力と設定可能なログレベル
- **設定管理**: TOML形式での柔軟な設定

## 基本的な使用方法

### 1. シンプルな起動
```bash
# デフォルト設定でdaemonモード開始
push-tmux daemon

# 自動ルーティングモードでdaemon開始
push-tmux daemon --auto-route

# デバッグモード付きでdaemon開始  
push-tmux daemon --auto-route --debug
```

### 2. カスタム設定での起動
```bash
# 監視間隔を5秒に設定
push-tmux daemon --reload-interval 5.0

# 追加のファイルを監視
push-tmux daemon --watch-files myconfig.ini --watch-files secrets.env

# 特定のデバイスを指定
push-tmux daemon --device my-device --debug
```

## 設定ファイル (config.toml)

```toml
[daemon]
# ファイル監視間隔（秒）
reload_interval = 1.0

# 監視するファイルのリスト
watch_files = ["config.toml", ".env", "secrets.conf"]

# 無視するファイルパターン
ignore_patterns = [
    "*.pyc",
    "__pycache__/*", 
    ".git/*",
    "*.log",
    "*.tmp"
]

[daemon.logging]
# リロードログの有効化
enable_reload_logs = true

# ログファイルのパス（空文字で標準出力のみ）
log_file = "/var/log/push-tmux-daemon.log"

# ログレベル（DEBUG, INFO, WARNING, ERROR）
log_level = "INFO"

[daemon.monitoring]
# CPU使用率の閾値（%）
cpu_threshold = 80.0

# メモリ使用量の閾値（MB）
memory_threshold = 500

# WebSocket接続確認
websocket_check = true

# ハートビート間隔（秒）
heartbeat_interval = 30
```

## コマンドライン オプション

| オプション | 説明 |
|------------|------|
| `--device TEXT` | メッセージを受信するデバイス名またはID |
| `--all-devices` | 全デバイス宛のメッセージを受信 |
| `--auto-route` | デバイス名と同じtmuxセッションに自動ルーティング |
| `--debug` | デバッグモードで実行（詳細ログを表示） |
| `--reload-interval FLOAT` | ファイル監視間隔（秒、デフォルト: 1.0） |
| `--watch-files TEXT` | 追加で監視するファイル（複数指定可能） |

## ログ出力例

```
[09:30:15] [START] プロセス監視を開始
[09:30:15] [INFO] 監視間隔: 1.0秒
[09:30:15] [INFO] 監視ファイル: config.toml, .env
[09:30:15] [INFO] オプション: device=None, auto_route=True, debug=False
[09:30:16] [START] ワーカープロセスを開始
[09:30:16] [INFO] ワーカー開始 - device=None, auto_route=True, debug=False
自動ルーティングモード: 全デバイスのメッセージを受信し、対応するtmuxセッションに送信します。
[09:30:17] [FILE] ファイル変更を検知、プロセスを再起動
[09:30:17] [RESTART] ワーカープロセスでエラー: KeyboardInterrupt
```

## 実運用での使用

### systemd サービスとしての利用

`/etc/systemd/system/push-tmux.service` を作成：

```ini
[Unit]
Description=Push-tmux daemon
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/push-tmux
Environment=PUSHBULLET_TOKEN=your-token
ExecStart=/path/to/venv/bin/push-tmux daemon --auto-route
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

サービスの有効化と起動：
```bash
sudo systemctl enable push-tmux.service
sudo systemctl start push-tmux.service
sudo systemctl status push-tmux.service
```

### Docker での利用

Dockerfile 例：
```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install -e .

CMD ["push-tmux", "daemon", "--auto-route"]
```

## トラブルシューティング

### 1. プロセスが頻繁に再起動される場合
- `reload_interval` を大きくする（例: 5.0秒）
- `ignore_patterns` でログファイルや一時ファイルを除外

### 2. ログファイルが作成されない場合
- ディレクトリの書き込み権限を確認
- `log_file` のパスが正しいかチェック

### 3. メモリ使用量が多い場合
- `debug` モードを無効にする
- 不要な `watch_files` を削除

## 従来の listen コマンドとの比較

| 機能 | listen コマンド | daemon コマンド |
|------|----------------|-----------------|
| 基本機能 | ✅ | ✅ |
| 自動再起動 | ❌ | ✅ |
| ファイル監視 | ❌ | ✅ |
| ログ機能 | 基本的 | 高機能 |
| 設定管理 | 基本的 | 高機能 |
| 運用監視 | ❌ | ✅ |

## 注意事項

1. **hupper 依存**: daemon機能は `hupper` パッケージに依存します
2. **ファイル監視**: 大量のファイル変更がある環境では CPU使用量が増加する可能性があります
3. **ログサイズ**: ログファイルのローテーションは別途設定が必要です
4. **権限**: ログファイル作成には適切な書き込み権限が必要です

## 今後の拡張予定

- [ ] ヘルスチェック機能
- [ ] メトリクス監視
- [ ] Web UI でのステータス確認
- [ ] 複数インスタンス管理