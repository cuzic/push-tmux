#!/usr/bin/env python3
"""
デバイスマッピング機能のテスト
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, call
import os

# パスはconftest.pyで設定済み
import sys

from push_tmux.tmux import send_to_tmux
from test_helpers import create_tmux_mock, assert_send_keys_called


class TestDeviceMapping:
    """デバイスマッピング機能のテスト"""
    
    @pytest.mark.asyncio
    async def test_device_mapping_with_existing_session(self, mock_subprocess):
        """マッピングされたセッションが存在する場合（文字列形式）"""
        config = {
            "device_mapping": {
                "mobile-dev": "frontend"
            }
        }
        
        # frontendセッションは存在する
        mock_subprocess.side_effect = create_tmux_mock(existing_sessions=['frontend'])
        
        # click.echoをモック
        with patch('push_tmux.tmux.click.echo') as mock_echo:
            await send_to_tmux(config, "test message", device_name="mobile-dev")
            
        
        # send-keysコマンドが正しく実行されたことを確認
        assert_send_keys_called(mock_subprocess, "frontend:0.0", "test message")
    
    @pytest.mark.asyncio
    async def test_device_mapping_with_detailed_format(self, mock_subprocess):
        """詳細なマッピング形式（セッション、ウィンドウ、ペイン指定）"""
        config = {
            "device_mapping": {
                "backend-api": {
                    "session": "backend",
                    "window": "2",
                    "pane": "1"
                }
            }
        }
        
        # backendセッションは存在する
        mock_subprocess.side_effect = create_tmux_mock(existing_sessions=['backend'])
        
        # click.echoをモック
        with patch('push_tmux.tmux.click.echo'):
            await send_to_tmux(config, "test message", device_name="backend-api")
        
        # send-keysコマンドが正しく実行されたことを確認
        assert_send_keys_called(mock_subprocess, "backend:2.1", "test message")
    
    @pytest.mark.asyncio
    async def test_device_mapping_with_first_defaults(self, mock_subprocess):
        """詳細形式でウィンドウ・ペインを省略（firstがデフォルト）"""
        config = {
            "device_mapping": {
                "test-device": {
                    "session": "test-session"
                    # windowとpaneは省略 → "first"がデフォルト
                }
            }
        }
        
        # test-sessionは存在する
        mock_subprocess.side_effect = create_tmux_mock(existing_sessions=['test-session'])
        
        # click.echoをモック
        with patch('push_tmux.tmux.click.echo'):
            await send_to_tmux(config, "test message", device_name="test-device")
        
        # send-keysコマンドが正しく実行されたことを確認
        assert_send_keys_called(mock_subprocess, "test-session:0.0", "test message")
    
    @pytest.mark.asyncio
    async def test_device_mapping_with_missing_session(self, mock_subprocess):
        """マッピングされたセッションが存在しない場合"""
        config = {
            "device_mapping": {
                "mobile-dev": "nonexistent"
            },
            "tmux": {
                "default_target_session": "fallback"
            }
        }
        
        # fallbackセッションは存在するが、nonexistentは存在しない
        mock_subprocess.side_effect = create_tmux_mock(existing_sessions=['fallback'])
        
        # セッションが存在しないのでfallbackが使われる
        with patch('push_tmux.tmux.click.echo') as mock_echo:
            await send_to_tmux(config, "test message", device_name="mobile-dev")
            
            # 警告メッセージが表示されたことを確認
            warning_calls = [call for call in mock_echo.call_args_list if '警告' in str(call)]
            assert len(warning_calls) > 0
        
        # fallbackセッションが使われたことを確認
        send_calls = [call for call in mock_subprocess.call_args_list if 'send-keys' in str(call)]
        assert len(send_calls) == 2
        assert 'fallback' in send_calls[0][0][3]
    
    @pytest.mark.asyncio
    async def test_device_name_as_session_default(self, mock_subprocess):
        """use_device_name_as_sessionがtrueの場合（デフォルト）"""
        config = {
            "tmux": {
                "use_device_name_as_session": True
            }
        }
        
        # project-aセッションが存在する
        mock_subprocess.side_effect = create_tmux_mock(existing_sessions=['project-a'])
        
        # click.echoをモック
        with patch('push_tmux.tmux.click.echo'):
            await send_to_tmux(config, "test message", device_name="project-a")
        
        # send-keysコマンドが正しく実行されたことを確認
        assert_send_keys_called(mock_subprocess, "project-a:0.0", "test message")
    
    @pytest.mark.asyncio
    async def test_priority_explicit_config_over_mapping(self, mock_subprocess):
        """マッピングが最優先される"""
        config = {
            "device_mapping": {
                "test-device": "mapped-session"
            },
            "tmux": {
                "default_target_session": "default-session"
            }
        }
        
        # mapped-sessionが存在する
        mock_subprocess.side_effect = create_tmux_mock(existing_sessions=['mapped-session'])
        
        # click.echoをモック
        with patch('push_tmux.tmux.click.echo'):
            await send_to_tmux(config, "test message", device_name="test-device")
        
        # mapped-sessionが使われることを確認（マッピングが優先）
        assert_send_keys_called(mock_subprocess, "mapped-session:0.0", "test message")
    
    @pytest.mark.asyncio
    async def test_no_device_name_uses_current_session(self, mock_subprocess):
        """デバイス名なしの場合、現在のセッションを使用"""
        config = {}
        
        # 現在のセッションが存在する
        mock_subprocess.side_effect = create_tmux_mock(current_session='current-session')
        
        # TMUX環境変数が設定されている場合
        with patch.dict(os.environ, {'TMUX': '/tmp/tmux-1000/default,12345,0'}), \
             patch('push_tmux.tmux.click.echo'):
            await send_to_tmux(config, "test message")  # device_nameなし
        
        # current-sessionが使われる
        assert_send_keys_called(mock_subprocess, "current-session:0.0", "test message")
    
    @pytest.mark.asyncio
    async def test_error_when_no_session_found(self, mock_subprocess):
        """セッションが見つからない場合のエラー処理"""
        config = {}
        
        # カスタムモック - セッションが全く存在しない
        async def no_sessions_mock(*args, **kwargs):
            if 'has-session' in args:
                result = MagicMock()
                result.wait = AsyncMock(return_value=1)  # セッション存在しない
                result.returncode = 1
                return result
            elif 'display-message' in args:
                result = MagicMock()
                result.returncode = 1
                result.communicate = AsyncMock(return_value=(b'', b'error: no current session'))
                return result
            else:
                result = MagicMock()
                result.wait = AsyncMock(return_value=0)
                return result
        
        mock_subprocess.side_effect = no_sessions_mock
        
        # セッションが見つからない場合
        with patch('push_tmux.tmux.click.echo') as mock_echo:
            await send_to_tmux(config, "test message", device_name="unknown-device")
            
            # エラーメッセージが表示されたことを確認
            error_or_warning_calls = [call for call in mock_echo.call_args_list 
                                     if 'エラー' in str(call) or '警告' in str(call)]
            assert len(error_or_warning_calls) > 0
        
        # send-keysは実行されない
        send_calls = [call for call in mock_subprocess.call_args_list if 'send-keys' in str(call)]
        assert len(send_calls) == 0


def test_summary():
    """テスト全体の概要を表示"""
    print("\n=== Device Mapping Tests Summary ===")
    print("✓ マッピングされたセッションへの送信")
    print("✓ 詳細マッピング（window/pane指定）")
    print("✓ デフォルト値の処理")
    print("✓ フォールバック処理")
    print("✓ エラーハンドリング")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])