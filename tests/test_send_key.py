import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from click.testing import CliRunner

from push_tmux import cli


class TestSendKeyCommand:
    """send-keyコマンドのテスト"""
    
    @patch('push_tmux.commands.send_key.send_to_tmux')
    @patch('push_tmux.commands.send_key.load_config')
    def test_send_key_basic(self, mock_load_config, mock_send_to_tmux, runner):
        """基本的なメッセージ送信"""
        mock_load_config.return_value = {}
        mock_send_to_tmux.return_value = AsyncMock()
        
        result = runner.invoke(cli, ["send-key", "Hello tmux"])
        
        assert result.exit_code == 0
        mock_load_config.assert_called_once()
        mock_send_to_tmux.assert_called_once_with({}, "Hello tmux")
    
    @patch('push_tmux.commands.send_key.send_to_tmux')
    @patch('push_tmux.commands.send_key.load_config')
    def test_send_key_with_session(self, mock_load_config, mock_send_to_tmux, runner):
        """セッション指定でのメッセージ送信"""
        mock_load_config.return_value = {}
        mock_send_to_tmux.return_value = AsyncMock()
        
        result = runner.invoke(cli, ["send-key", "Test message", "--session", "my-session"])
        
        assert result.exit_code == 0
        mock_load_config.assert_called_once()
        expected_config = {'tmux': {'target_session': 'my-session'}}
        mock_send_to_tmux.assert_called_once_with(expected_config, "Test message")
    
    @patch('push_tmux.commands.send_key.send_to_tmux')
    @patch('push_tmux.commands.send_key.load_config')
    def test_send_key_with_window(self, mock_load_config, mock_send_to_tmux, runner):
        """ウィンドウ指定でのメッセージ送信"""
        mock_load_config.return_value = {}
        mock_send_to_tmux.return_value = AsyncMock()
        
        result = runner.invoke(cli, ["send-key", "Test message", "--window", "2"])
        
        assert result.exit_code == 0
        mock_load_config.assert_called_once()
        expected_config = {'tmux': {'target_window': '2'}}
        mock_send_to_tmux.assert_called_once_with(expected_config, "Test message")
    
    @patch('push_tmux.commands.send_key.send_to_tmux')
    @patch('push_tmux.commands.send_key.load_config')
    def test_send_key_with_pane(self, mock_load_config, mock_send_to_tmux, runner):
        """ペイン指定でのメッセージ送信"""
        mock_load_config.return_value = {}
        mock_send_to_tmux.return_value = AsyncMock()
        
        result = runner.invoke(cli, ["send-key", "Test message", "--pane", "1"])
        
        assert result.exit_code == 0
        mock_load_config.assert_called_once()
        expected_config = {'tmux': {'target_pane': '1'}}
        mock_send_to_tmux.assert_called_once_with(expected_config, "Test message")
    
    @patch('push_tmux.commands.send_key.send_to_tmux')
    @patch('push_tmux.commands.send_key.load_config')
    def test_send_key_with_all_options(self, mock_load_config, mock_send_to_tmux, runner):
        """全オプション指定でのメッセージ送信"""
        mock_load_config.return_value = {"tmux": {"target_session": "default"}}
        mock_send_to_tmux.return_value = AsyncMock()
        
        result = runner.invoke(cli, [
            "send-key", "Complex message",
            "--session", "test-session",
            "--window", "3",
            "--pane", "2"
        ])
        
        assert result.exit_code == 0
        mock_load_config.assert_called_once()
        expected_config = {
            'tmux': {
                'target_session': 'test-session',
                'target_window': '3',
                'target_pane': '2'
            }
        }
        mock_send_to_tmux.assert_called_once_with(expected_config, "Complex message")
    
    @patch('push_tmux.commands.send_key.send_to_tmux')
    @patch('push_tmux.commands.send_key.load_config')
    def test_send_key_with_special_characters(self, mock_load_config, mock_send_to_tmux, runner):
        """特殊文字を含むメッセージ送信"""
        mock_load_config.return_value = {}
        mock_send_to_tmux.return_value = AsyncMock()
        
        result = runner.invoke(cli, ["send-key", "echo 'Hello \"World\" $USER'"])
        
        assert result.exit_code == 0
        mock_send_to_tmux.assert_called_once_with({}, "echo 'Hello \"World\" $USER'")
    
    @patch('push_tmux.commands.send_key.send_to_tmux')
    @patch('push_tmux.commands.send_key.load_config')
    def test_send_key_with_unicode(self, mock_load_config, mock_send_to_tmux, runner):
        """Unicode文字を含むメッセージ送信"""
        mock_load_config.return_value = {}
        mock_send_to_tmux.return_value = AsyncMock()
        
        result = runner.invoke(cli, ["send-key", "こんにちは 🚀 世界"])
        
        assert result.exit_code == 0
        mock_send_to_tmux.assert_called_once_with({}, "こんにちは 🚀 世界")
    
    @patch('push_tmux.commands.send_key.send_to_tmux')
    @patch('push_tmux.commands.send_key.load_config')
    def test_send_key_with_empty_message(self, mock_load_config, mock_send_to_tmux, runner):
        """空のメッセージ送信"""
        mock_load_config.return_value = {}
        mock_send_to_tmux.return_value = AsyncMock()
        
        result = runner.invoke(cli, ["send-key", ""])
        
        assert result.exit_code == 0
        mock_send_to_tmux.assert_called_once_with({}, "")
    
    @patch('push_tmux.commands.send_key.send_to_tmux')
    @patch('push_tmux.commands.send_key.load_config')
    def test_send_key_with_existing_config(self, mock_load_config, mock_send_to_tmux, runner):
        """既存の設定がある場合のオプション上書き"""
        mock_load_config.return_value = {
            "tmux": {
                "target_session": "old-session",
                "target_window": "0",
                "target_pane": "0"
            }
        }
        mock_send_to_tmux.return_value = AsyncMock()
        
        result = runner.invoke(cli, ["send-key", "Override test", "--session", "new-session"])
        
        assert result.exit_code == 0
        mock_load_config.assert_called_once()
        expected_config = {
            "tmux": {
                "target_session": "new-session",
                "target_window": "0",
                "target_pane": "0"
            }
        }
        mock_send_to_tmux.assert_called_once_with(expected_config, "Override test")
    
    def test_send_key_help(self, runner):
        """ヘルプメッセージの表示"""
        result = runner.invoke(cli, ["send-key", "--help"])
        
        assert result.exit_code == 0
        assert "指定されたメッセージを直接tmuxに送信します（テスト用）" in result.output
        assert "--session" in result.output
        assert "--window" in result.output
        assert "--pane" in result.output
        assert "MESSAGE" in result.output
    
    @patch('push_tmux.commands.send_key.send_to_tmux')
    @patch('push_tmux.commands.send_key.load_config')
    def test_send_key_multiline_message(self, mock_load_config, mock_send_to_tmux, runner):
        """複数行のメッセージ送信"""
        mock_load_config.return_value = {}
        mock_send_to_tmux.return_value = AsyncMock()
        
        multiline_message = "line1\nline2\nline3"
        result = runner.invoke(cli, ["send-key", multiline_message])
        
        assert result.exit_code == 0
        mock_send_to_tmux.assert_called_once_with({}, multiline_message)
    
    @patch('push_tmux.commands.send_key.send_to_tmux')
    @patch('push_tmux.commands.send_key.load_config')
    def test_send_key_command_execution(self, mock_load_config, mock_send_to_tmux, runner):
        """コマンド実行のテスト"""
        mock_load_config.return_value = {}
        mock_send_to_tmux.return_value = AsyncMock()
        
        # シェルコマンドをメッセージとして送信
        result = runner.invoke(cli, ["send-key", "ls -la"])
        
        assert result.exit_code == 0
        mock_send_to_tmux.assert_called_once_with({}, "ls -la")