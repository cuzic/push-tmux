"""
pytest設定ファイル
環境変数のモックとタイムアウト設定
"""
import os
import pytest
import asyncio
from unittest.mock import patch

# テスト用のPushbullet APIトークンを設定
@pytest.fixture(autouse=True)
def mock_env_vars():
    """環境変数をモック"""
    with patch.dict(os.environ, {
        'PUSHBULLET_TOKEN': 'test_token_12345',
        'DEVICE_NAME': 'test_device'
    }):
        yield

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