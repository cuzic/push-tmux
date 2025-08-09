import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from push_tmux import get_device_name, load_config, save_config


class TestDeviceName:
    """get_device_name関数のテスト"""
    
    def test_get_device_name_from_env(self):
        """環境変数DEVICE_NAMEが設定されている場合"""
        with patch.dict(os.environ, {'DEVICE_NAME': 'my-custom-device'}):
            assert get_device_name() == "my-custom-device"
    
    def test_get_device_name_from_directory(self, tmp_path):
        """環境変数が設定されていない場合はディレクトリ名を使用"""
        # 一時ディレクトリに移動
        test_dir = tmp_path / "test-project"
        test_dir.mkdir()
        original_cwd = os.getcwd()
        
        try:
            os.chdir(test_dir)
            # DEVICE_NAMEを削除してディレクトリ名を使用させる
            with patch.dict(os.environ, {}, clear=True):
                assert get_device_name() == "test-project"
        finally:
            os.chdir(original_cwd)
    
    def test_get_device_name_precedence(self, tmp_path):
        """環境変数が優先される"""
        test_dir = tmp_path / "dir-device"
        test_dir.mkdir()
        original_cwd = os.getcwd()
        
        try:
            os.chdir(test_dir)
            with patch.dict(os.environ, {'DEVICE_NAME': 'env-device'}):
                assert get_device_name() == "env-device"
        finally:
            os.chdir(original_cwd)


class TestConfigManagement:
    """設定ファイル管理関数のテスト"""
    
    def test_load_config_file_not_exists(self, isolated_env):
        """設定ファイルが存在しない場合はデフォルト設定を返す"""
        config = load_config()
        # デフォルト設定が返されることを確認
        assert 'tmux' in config
        assert 'daemon' in config
        assert config['tmux']['target_window'] == 'first'
        assert config['tmux']['target_pane'] == 'first'
    
    def test_save_and_load_config(self, isolated_env):
        """設定の保存と読み込み"""
        test_config = {
            "tmux": {
                "target_session": "test-session",
                "target_window": "2",
                "target_pane": "1"
            },
            "custom": {
                "key": "value"
            }
        }
        
        save_config(test_config)
        loaded_config = load_config()
        
        # 保存した設定が読み込まれていることを確認
        assert loaded_config["tmux"]["target_session"] == "test-session"
        assert loaded_config["tmux"]["target_window"] == "2"
        assert loaded_config["tmux"]["target_pane"] == "1"
        assert loaded_config["custom"]["key"] == "value"
        # デフォルトのdaemon設定も追加されている
        assert 'daemon' in loaded_config
    
    def test_save_config_overwrites_existing(self, isolated_env):
        """既存の設定ファイルを上書き"""
        # 最初の設定を保存
        first_config = {"key1": "value1"}
        save_config(first_config)
        
        # 異なる設定で上書き
        second_config = {"key2": "value2"}
        save_config(second_config)
        
        # 新しい設定が読み込まれる
        loaded_config = load_config()
        assert loaded_config["key2"] == "value2"
        assert "key1" not in loaded_config
        # デフォルトのdaemon設定も追加されている
        assert 'daemon' in loaded_config
    
    def test_save_config_creates_file(self, isolated_env):
        """設定ファイルが作成される"""
        config_file = Path(isolated_env) / "config.toml"
        assert not config_file.exists()
        
        save_config({"test": "data"})
        assert config_file.exists()
    
    def test_load_config_invalid_toml(self, isolated_env):
        """無効なTOMLファイルの処理（デフォルト設定を返す）"""
        config_file = Path(isolated_env) / "config.toml"
        config_file.write_text("invalid toml content {[}")
        
        # 無効なTOMLファイルの場合はデフォルト設定を返す
        config = load_config()
        assert 'tmux' in config
        assert config['tmux']['target_session'] == 'current'
    
    def test_config_unicode_support(self, isolated_env):
        """Unicode文字を含む設定の保存と読み込み"""
        config = {
            "japanese": "日本語テスト",
            "emoji": "🚀✨",
            "special": "特殊文字: üöä"
        }
        
        save_config(config)
        loaded_config = load_config()
        
        # 保存した設定が正しく読み込まれていることを確認
        assert loaded_config["japanese"] == config["japanese"]
        assert loaded_config["emoji"] == config["emoji"]
        assert loaded_config["special"] == config["special"]
        assert loaded_config["japanese"] == "日本語テスト"
        assert loaded_config["emoji"] == "🚀✨"
        # デフォルトのdaemon設定も追加されている
        assert 'daemon' in loaded_config