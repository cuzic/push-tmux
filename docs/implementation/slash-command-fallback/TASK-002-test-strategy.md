# TASK-002: テスト戦略の策定

## 既存テストへの影響評価

### 影響を受けるテストファイル:

1. **test_slash_commands.py**
   - `test_expand_slash_command_*` 関数群
   - 戻り値の変更に対応が必要

2. **test_device_targeting.py**
   - メッセージ処理ロジックのテスト
   - フォールバック動作の追加テストが必要

3. **test_push_tmux_commands.py**
   - listen コマンドのテスト
   - 新しい動作パスのカバレッジが必要

## 新規テストケースの設計

### 1. 設定読み込みテスト

```python
def test_fallback_undefined_default_value():
    """デフォルト値が true であることを確認"""
    
def test_fallback_undefined_from_config():
    """設定ファイルから値を読み込めることを確認"""
    
def test_fallback_undefined_false_behavior():
    """false に設定した場合の従来動作を確認"""
```

### 2. スラッシュコマンド処理テスト

```python
def test_undefined_command_with_fallback_enabled():
    """fallback有効時: /login が通常メッセージとして処理される"""
    
def test_undefined_command_with_fallback_disabled():
    """fallback無効時: /login が無視される（従来動作）"""
    
def test_defined_command_always_works():
    """定義済みコマンドは設定に関わらず動作する"""
```

### 3. メッセージ送信テスト

```python
def test_fallback_message_sent_to_tmux():
    """フォールバックされたメッセージがtmuxに送信される"""
    
def test_fallback_preserves_original_message():
    """メッセージが変更されずにそのまま送信される"""
```

## エッジケースの洗い出し

### 1. 境界条件

- **空のスラッシュ**: `/` のみのメッセージ
- **スペース付き**: `/ login` （スラッシュの後にスペース）
- **特殊文字**: `/日本語コマンド`、`/@mention`、`/#hashtag`

### 2. 設定の競合

- **設定ファイルの破損**: 不正な値（文字列 "yes" など）
- **セクション欠落**: `[slash_commands_settings]` がない場合
- **キー欠落**: `fallback_undefined` キーがない場合

### 3. 並行性

- **複数メッセージ**: 同時に複数の未定義コマンドを受信
- **設定変更中**: 実行中に設定が変更された場合

## テストマトリクス

| テストケース | fallback_undefined | コマンド定義 | 期待される動作 |
|------------|-------------------|------------|--------------|
| `/deploy` | true | あり | カスタムコマンド実行 |
| `/deploy` | false | あり | カスタムコマンド実行 |
| `/login` | true | なし | 通常メッセージとして送信 |
| `/login` | false | なし | 無視（エラーメッセージ） |
| `hello` | true/false | - | 通常メッセージとして送信 |

## モックとスタブの戦略

### 必要なモック:

1. **AsyncPushbullet**: API呼び出しのモック
2. **subprocess**: tmux コマンド実行のモック
3. **config loader**: 設定ファイル読み込みのモック

### テストフィクスチャ:

```python
@pytest.fixture
def config_with_fallback_enabled():
    return {
        'slash_commands_settings': {
            'fallback_undefined': True
        },
        'slash_commands': {
            'deploy': {...}
        }
    }

@pytest.fixture
def config_with_fallback_disabled():
    return {
        'slash_commands_settings': {
            'fallback_undefined': False
        },
        'slash_commands': {
            'deploy': {...}
        }
    }
```

## 完了条件

- [x] 既存テストへの影響を評価
- [x] 新規テストケースを設計
- [x] エッジケースを洗い出し
- [x] テストマトリクスを作成
- [x] モック戦略を決定