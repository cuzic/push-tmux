"""
pytest設定ファイル
環境変数のモックとタイムアウト設定
"""
import os
import sys
import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from click.testing import CliRunner

# プロジェクトのルートディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

# テスト用のPushbullet APIトークンを設定
@pytest.fixture(autouse=True)
def mock_env_vars():
    """環境変数をモック"""
    with patch.dict(os.environ, {
        'PUSHBULLET_TOKEN': 'test_token_12345',
        'DEVICE_NAME': 'test_device'
    }):
        yield

# Click CLIテスト用のrunnerフィクスチャ
@pytest.fixture
def runner():
    """Click CLI用のテストランナー"""
    return CliRunner()

# モックされたAsyncioサブプロセス
@pytest.fixture
def mock_subprocess():
    """asyncio.create_subprocess_execのモック"""
    with patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock:
        yield mock

# 環境変数モック用フィクスチャ
@pytest.fixture
def mock_env():
    """環境変数を設定するフィクスチャ"""
    def _mock_env(**kwargs):
        with patch.dict(os.environ, kwargs, clear=False):
            return
    return _mock_env

# tmux環境変数のモック
@pytest.fixture
def mock_tmux_env():
    """TMUX環境変数を設定するフィクスチャ"""
    with patch.dict(os.environ, {
        'TMUX': '/tmp/tmux-1000/default,12345,0'
    }):
        yield

# サンプル設定フィクスチャ
@pytest.fixture
def sample_config():
    """テスト用のサンプル設定"""
    return {
        "tmux": {
            "target_session": "current",
            "target_window": "first",
            "target_pane": "first"
        },
        "daemon": {
            "enabled": False,
            "watch_files": [],
            "poll_interval": 1.0
        }
    }

# 一時的な隔離された環境でテストを実行
@pytest.fixture
def isolated_env(tmp_path):
    """隔離された環境でテストを実行"""
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(original_cwd)

# 非同期テストのデフォルトタイムアウトを設定
@pytest.fixture(scope="session")
def event_loop_policy():
    """イベントループポリシーを設定"""
    return asyncio.DefaultEventLoopPolicy()

# テストタイムアウトのグローバル設定
def pytest_configure(config):
    """pytest設定"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )