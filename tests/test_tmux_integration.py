import asyncio
import os
from unittest.mock import MagicMock, call, patch

import pytest

from push_tmux.tmux import send_to_tmux


class TestSendToTmux:
    """tmux送信機能のテスト"""
    
    @pytest.mark.asyncio
    async def test_send_to_tmux_default_session(self, mock_subprocess, mock_tmux_env, sample_config):
        """デフォルトセッション（環境変数から）への送信"""
        # 各tmuxコマンドのモック
        async def mock_exec(*args, **kwargs):
            if 'display-message' in args:
                # display-message コマンドのモック
                result = MagicMock()
                async def communicate():
                    return (b'test-session\n', b'')
                result.communicate = communicate
                return result
            elif 'list-windows' in args:
                # list-windows コマンドのモック（最初のウィンドウは1）
                result = MagicMock()
                async def communicate():
                    return (b'1\n2\n3\n', b'')
                result.communicate = communicate
                return result
            elif 'list-panes' in args:
                # list-panes コマンドのモック（最初のペインは2）
                result = MagicMock()
                async def communicate():
                    return (b'2\n3\n', b'')
                result.communicate = communicate
                return result
            else:
                # send-keys コマンドのモック
                process = MagicMock()
                async def async_wait():
                    return None
                process.wait = async_wait
                return process
        
        mock_subprocess.side_effect = mock_exec
        
        config = {}  # 空の設定でデフォルト値を使用
        
        await send_to_tmux(config, "test message")
        
        # tmux コマンドが5回呼ばれる（display-message、list-windows、list-panes、send-keys x2）
        assert mock_subprocess.call_count == 5
        
        # display-message呼び出し確認
        assert any('display-message' in str(call) for call in mock_subprocess.call_args_list)
        
        # list-windows呼び出し確認
        assert any('list-windows' in str(call) for call in mock_subprocess.call_args_list)
        
        # list-panes呼び出し確認
        assert any('list-panes' in str(call) for call in mock_subprocess.call_args_list)
        
        # send-keysメッセージ送信（実際の最初のウィンドウ1、ペイン2を使用）
        send_calls = [call for call in mock_subprocess.call_args_list if 'send-keys' in call[0]]
        assert len(send_calls) == 2
        assert "test-session:1.2" in send_calls[0][0][3]
        assert send_calls[0][0][4] == "test message"
        assert send_calls[1][0][4] == "C-m"
    
    @pytest.mark.asyncio
    async def test_send_to_tmux_custom_session(self, mock_subprocess, sample_config):
        """カスタムセッションへの送信"""
        config = {
            "tmux": {
                "target_session": "my-session",
                "target_window": "2",
                "target_pane": "1"
            }
        }
        
        await send_to_tmux(config, "custom message")
        
        first_call = mock_subprocess.call_args_list[0]
        assert "my-session:2.1" in first_call[0][3]
        assert first_call[0][4] == "custom message"
    
    @pytest.mark.asyncio
    async def test_send_to_tmux_no_tmux_env(self, mock_subprocess, capsys):
        """TMUX環境変数が設定されていない場合"""
        # TMUX環境変数を削除
        with patch.dict(os.environ, {}, clear=True):
            config = {
                "tmux": {
                    "target_session": None,
                    "target_window": "0",
                    "target_pane": "0"
                }
            }
            
            await send_to_tmux(config, "test message")
            
            # tmux send-keysが呼ばれない
            mock_subprocess.assert_not_called()
            
            # エラーメッセージの確認
            captured = capsys.readouterr()
            assert "エラー: tmuxセッション" in captured.err
            assert "config.toml" in captured.err
    
    @pytest.mark.asyncio
    async def test_send_to_tmux_command_not_found(self, capsys):
        """tmuxコマンドが見つからない場合"""
        config = {
            "tmux": {
                "target_session": "test",
                "target_window": "0",
                "target_pane": "0"
            }
        }
        
        with patch("push_tmux.tmux.asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.side_effect = FileNotFoundError()
            
            await send_to_tmux(config, "test message")
            
            captured = capsys.readouterr()
            assert "エラー: 'tmux'コマンドが見つかりません" in captured.err
    
    @pytest.mark.asyncio
    async def test_send_to_tmux_generic_error(self, capsys):
        """tmux実行中の一般的なエラー"""
        config = {
            "tmux": {
                "target_session": "test",
                "target_window": "0",
                "target_pane": "0"
            }
        }
        
        with patch("push_tmux.tmux.asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.side_effect = Exception("Unexpected error")
            
            await send_to_tmux(config, "test message")
            
            captured = capsys.readouterr()
            assert "tmuxコマンドの実行中にエラーが発生しました: Unexpected error" in captured.err
    
    @pytest.mark.asyncio
    async def test_send_to_tmux_special_characters(self, mock_subprocess):
        """特殊文字を含むメッセージの送信"""
        config = {
            "tmux": {
                "target_session": "test",
                "target_window": "0",
                "target_pane": "0"
            }
        }
        
        special_message = "Hello 'world' \"test\" $USER `ls` && echo"
        await send_to_tmux(config, special_message)
        
        first_call = mock_subprocess.call_args_list[0]
        assert first_call[0][4] == special_message
    
    @pytest.mark.asyncio
    async def test_send_to_tmux_unicode(self, mock_subprocess):
        """Unicode文字を含むメッセージの送信"""
        config = {
            "tmux": {
                "target_session": "test",
                "target_window": "0",
                "target_pane": "0"
            }
        }
        
        unicode_message = "こんにちは 🚀 世界"
        await send_to_tmux(config, unicode_message)
        
        first_call = mock_subprocess.call_args_list[0]
        assert first_call[0][4] == unicode_message
    
    @pytest.mark.asyncio
    async def test_send_to_tmux_empty_message(self, mock_subprocess):
        """空のメッセージの送信"""
        config = {
            "tmux": {
                "target_session": "test",
                "target_window": "0",
                "target_pane": "0"
            }
        }
        
        await send_to_tmux(config, "")
        
        # 空のメッセージでも送信される
        assert mock_subprocess.call_count == 2
        first_call = mock_subprocess.call_args_list[0]
        assert first_call[0][4] == ""
    
    @pytest.mark.asyncio
    async def test_send_to_tmux_with_defaults(self, mock_subprocess):
        """デフォルト値での送信"""
        # 各tmuxコマンドのモック
        async def mock_exec(*args, **kwargs):
            if 'display-message' in args:
                result = MagicMock()
                async def communicate():
                    return (b'current-session\n', b'')
                result.communicate = communicate
                return result
            elif 'list-windows' in args:
                result = MagicMock()
                async def communicate():
                    return (b'0\n1\n', b'')  # ウィンドウ0が最初
                result.communicate = communicate
                return result
            elif 'list-panes' in args:
                result = MagicMock()
                async def communicate():
                    return (b'0\n1\n', b'')  # ペイン0が最初
                result.communicate = communicate
                return result
            else:
                process = MagicMock()
                async def async_wait():
                    return None
                process.wait = async_wait
                return process
        
        mock_subprocess.side_effect = mock_exec
        
        config = {}  # tmux設定なし
        
        # TMUX環境変数を設定
        with patch.dict(os.environ, {"TMUX": "/tmp/tmux-1000/default,12345,0"}):
            await send_to_tmux(config, "test with defaults")
            
            # send-keysコマンドを確認
            send_calls = [call for call in mock_subprocess.call_args_list if 'send-keys' in call[0]]
            # デフォルト値が使用される
            assert "current-session:0.0" in send_calls[0][0][3]  # window 0, pane 0