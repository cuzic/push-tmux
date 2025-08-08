import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner


@pytest.fixture
def runner():
    """CLIテスト用のClick CliRunner"""
    return CliRunner()


@pytest.fixture
def temp_config_file(tmp_path):
    """一時的な設定ファイルのパス"""
    config_file = tmp_path / "config.toml"
    return str(config_file)


@pytest.fixture
def mock_env(monkeypatch):
    """環境変数のモック"""
    def set_env(**kwargs):
        for key, value in kwargs.items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, value)
    return set_env


# Pushbullet関連のモックは削除


@pytest.fixture
def mock_tmux_env(monkeypatch):
    """tmux環境変数のモック"""
    monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,12345,0")
    return "/tmp/tmux-1000/default"


@pytest.fixture
def mock_subprocess():
    """asyncio.create_subprocess_execのモック"""
    with patch("push_tmux.asyncio.create_subprocess_exec") as mock:
        process = MagicMock()
        async def async_wait():
            return None
        process.wait = async_wait
        mock.return_value = process
        yield mock


@pytest.fixture
def sample_config():
    """サンプル設定データ"""
    return {
        "tmux": {
            "target_session": "main",
            "target_window": "1",
            "target_pane": "0"
        }
    }


@pytest.fixture
def sample_push_note():
    """サンプルのPushbullet noteプッシュ"""
    return {
        "type": "note",
        "title": "Test Title",
        "body": "Test message body",
        "dismissed": False
    }


@pytest.fixture
def sample_push_non_note():
    """note以外のPushbulletプッシュ"""
    return {
        "type": "link",
        "title": "Test Link",
        "url": "https://example.com",
        "dismissed": False
    }


@pytest.fixture(autouse=True)
def reset_modules():
    """各テストの前後でモジュールの状態をリセット"""
    yield
    # クリーンアップが必要な場合はここに記述


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """独立したテスト環境を作成"""
    # 一時ディレクトリを作業ディレクトリに設定
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    
    # 設定ファイルのパスを一時ディレクトリに変更
    monkeypatch.setattr("push_tmux.CONFIG_FILE", str(tmp_path / "config.toml"))
    
    yield tmp_path
    
    # 元の作業ディレクトリに戻す
    os.chdir(original_cwd)