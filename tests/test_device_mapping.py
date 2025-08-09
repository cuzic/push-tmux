#!/usr/bin/env python3
"""
デバイスマッピング機能のテスト
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import os

# パスはconftest.pyで設定済み
import sys

from push_tmux.tmux import send_to_tmux


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
        
        # has-sessionが成功を返す
        async def mock_exec(*args, **kwargs):
            if 'has-session' in args:
                result = MagicMock()
                result.returncode = 0
                async def communicate():
                    return (b'', b'')
                result.communicate = communicate
                return result
            else:
                process = MagicMock()
                async def async_wait():
                    return None
                process.wait = async_wait
                return process
        
        mock_subprocess.side_effect = mock_exec
        
        await send_to_tmux(config, "test message", device_name="mobile-dev")
        
        # send-keysコマンドが実行される
        send_calls = [call for call in mock_subprocess.call_args_list if 'send-keys' in call[0]]
        assert len(send_calls) == 2  # メッセージとEnterキー
        assert "frontend:0.0" in send_calls[0][0][3]  # マップされたセッション名が使用される
    
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
        
        # has-sessionが成功を返す
        async def mock_exec(*args, **kwargs):
            if 'has-session' in args:
                result = MagicMock()
                result.returncode = 0
                async def communicate():
                    return (b'', b'')
                result.communicate = communicate
                return result
            else:
                process = MagicMock()
                async def async_wait():
                    return None
                process.wait = async_wait
                return process
        
        mock_subprocess.side_effect = mock_exec
        
        await send_to_tmux(config, "test message", device_name="backend-api")
        
        # send-keysコマンドが実行される
        send_calls = [call for call in mock_subprocess.call_args_list if 'send-keys' in call[0]]
        assert len(send_calls) == 2
        assert "backend:2.1" in send_calls[0][0][3]  # セッション:ウィンドウ.ペイン
    
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
        
        # has-sessionとlist-windows、list-panesが成功を返す
        async def mock_exec(*args, **kwargs):
            if 'has-session' in args:
                result = MagicMock()
                result.returncode = 0
                async def communicate():
                    return (b'', b'')
                result.communicate = communicate
                return result
            elif 'list-windows' in args:
                result = MagicMock()
                async def communicate():
                    return (b'0\n1\n2\n', b'')  # ウィンドウ0が最初
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
        
        await send_to_tmux(config, "test message", device_name="test-device")
        
        # send-keysコマンドが実行される
        send_calls = [call for call in mock_subprocess.call_args_list if 'send-keys' in call[0]]
        assert len(send_calls) == 2
        assert "test-session:0.0" in send_calls[0][0][3]  # 最初のウィンドウ・ペイン
    
    @pytest.mark.asyncio
    async def test_device_mapping_with_missing_session(self, mock_subprocess):
        """マッピングされたセッションが存在しない場合"""
        config = {
            "device_mapping": {
                "mobile-dev": "nonexistent"
            }
        }
        
        # すべてのhas-sessionが失敗を返す
        async def mock_exec(*args, **kwargs):
            if 'has-session' in args:
                result = MagicMock()
                result.returncode = 1  # セッションが存在しない
                async def communicate():
                    return (b'', b'')
                result.communicate = communicate
                return result
            elif 'display-message' in args:
                result = MagicMock()
                async def communicate():
                    return (b'current-session\n', b'')
                result.communicate = communicate
                return result
            else:
                process = MagicMock()
                async def async_wait():
                    return None
                process.wait = async_wait
                return process
        
        mock_subprocess.side_effect = mock_exec
        
        # TMUX環境変数を設定（現在のセッションにフォールバック）
        with patch.dict(os.environ, {"TMUX": "/tmp/tmux-1000/default,12345,0"}):
            await send_to_tmux(config, "test message", device_name="mobile-dev")
            
            # フォールバックしてデバイス名と同じセッションを探し、最終的に現在のセッションを使用
            send_calls = [call for call in mock_subprocess.call_args_list if 'send-keys' in call[0]]
            assert len(send_calls) == 2
            assert "current-session" in send_calls[0][0][3]
    
    @pytest.mark.asyncio
    async def test_device_name_as_session_default(self, mock_subprocess):
        """マッピングがない場合、デバイス名をセッション名として使用"""
        config = {}  # マッピングなし
        
        async def mock_exec(*args, **kwargs):
            if 'has-session' in args and 'project-a' in args:
                result = MagicMock()
                result.returncode = 0  # project-aセッションが存在
                async def communicate():
                    return (b'', b'')
                result.communicate = communicate
                return result
            else:
                process = MagicMock()
                async def async_wait():
                    return None
                process.wait = async_wait
                return process
        
        mock_subprocess.side_effect = mock_exec
        
        await send_to_tmux(config, "test message", device_name="project-a")
        
        # project-aセッションが使用される
        send_calls = [call for call in mock_subprocess.call_args_list if 'send-keys' in call[0]]
        assert len(send_calls) == 2
        assert "project-a:0.0" in send_calls[0][0][3]
    
    @pytest.mark.asyncio
    async def test_priority_explicit_config_over_mapping(self, mock_subprocess):
        """明示的なtmux.target_session設定がマッピングより優先される"""
        config = {
            "tmux": {
                "target_session": "explicit-session"
            },
            "device_mapping": {
                "test-device": "mapped-session"
            }
        }
        
        # 設定を返すモック
        process = MagicMock()
        async def async_wait():
            return None
        process.wait = async_wait
        mock_subprocess.return_value = process
        
        await send_to_tmux(config, "test message", device_name="test-device")
        
        # 明示的な設定が使用される
        send_calls = [call for call in mock_subprocess.call_args_list if 'send-keys' in call[0]]
        assert len(send_calls) == 2
        assert "explicit-session:0.0" in send_calls[0][0][3]
    
    @pytest.mark.asyncio
    async def test_no_device_name_uses_current_session(self, mock_subprocess):
        """デバイス名がない場合は現在のセッションを使用"""
        config = {}
        
        async def mock_exec(*args, **kwargs):
            if 'display-message' in args:
                result = MagicMock()
                async def communicate():
                    return (b'my-current-session\n', b'')
                result.communicate = communicate
                return result
            else:
                process = MagicMock()
                async def async_wait():
                    return None
                process.wait = async_wait
                return process
        
        mock_subprocess.side_effect = mock_exec
        
        # TMUX環境変数を設定
        with patch.dict(os.environ, {"TMUX": "/tmp/tmux-1000/default,12345,0"}):
            await send_to_tmux(config, "test message")  # device_nameなし
            
            send_calls = [call for call in mock_subprocess.call_args_list if 'send-keys' in call[0]]
            assert len(send_calls) == 2
            assert "my-current-session:0.0" in send_calls[0][0][3]
    
    @pytest.mark.asyncio
    async def test_error_when_no_session_found(self, mock_subprocess, capsys):
        """セッションが見つからない場合のエラー処理"""
        config = {}
        
        # すべてのhas-sessionが失敗
        async def mock_exec(*args, **kwargs):
            if 'has-session' in args:
                result = MagicMock()
                result.returncode = 1
                async def communicate():
                    return (b'', b'')
                result.communicate = communicate
                return result
            else:
                process = MagicMock()
                async def async_wait():
                    return None
                process.wait = async_wait
                return process
        
        mock_subprocess.side_effect = mock_exec
        
        # TMUX環境変数なし（tmux外で実行）
        with patch.dict(os.environ, {}, clear=True):
            await send_to_tmux(config, "test message", device_name="unknown-device")
            
            captured = capsys.readouterr()
            assert "エラー: tmuxセッション 'unknown-device' が見つかりません" in captured.err
            assert "以下のいずれかの対処を行ってください" in captured.err
            assert "tmuxセッション 'unknown-device' を作成する" in captured.err
            assert "config.tomlの[device_mapping]セクションでマッピングを設定する" in captured.err



def test_summary():
    """テストサマリーの表示"""
    print("""
デバイスマッピング機能のテスト
============================================================
以下の機能をテストします:
1. device_mappingセクションでのマッピング設定
2. 文字列形式のマッピング（セッションのみ指定）
3. 詳細形式のマッピング（セッション、ウィンドウ、ペイン指定）
4. デフォルト値の適用（ウィンドウ・ペインは"first"）
5. マッピングされたセッションが存在しない場合のフォールバック
6. デバイス名をデフォルトセッション名として使用
7. 優先順位の確認（明示的設定 > マッピング > デバイス名）
8. エラー処理とメッセージ表示
============================================================

実行コマンド:
  pytest tests/test_device_mapping.py -v
""")