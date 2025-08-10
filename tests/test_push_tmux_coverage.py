#!/usr/bin/env python3
"""
push_tmux.pyの追加テスト（カバレッジ向上用）
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from click.testing import CliRunner
import os

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from push_tmux import cli
from push_tmux.config import load_config, save_config, get_device_name, CONFIG_FILE
from push_tmux.tmux import send_to_tmux


class TestConfigFunctions:
    """設定関連関数のテスト"""
    
    def test_load_config_with_file(self):
        """設定ファイルが存在する場合"""
        config_data = {"tmux": {"default_target_session": "test"}}
        
        with patch('push_tmux.config.CONFIG_FILE', 'test_config.toml'):
            with patch('push_tmux.config.toml.load', return_value=config_data):
                config = load_config()
                # tmux設定が正しく読み込まれていることを確認
                assert config['tmux']['default_target_session'] == 'test'
                # デフォルトのtarget_sessionが保持されていることを確認
                assert config['tmux']['target_session'] == 'current'
                # デフォルトのdaemon設定が追加されていることを確認
                assert 'daemon' in config
                assert config['daemon']['reload_interval'] == 1.0
    
    def test_save_config(self):
        """設定の保存"""
        config_data = {"tmux": {"target_session": "test"}}
        
        m = mock_open()
        with patch('builtins.open', m):
            save_config(config_data)
            
        # ファイルが開かれた
        m.assert_called_once_with(CONFIG_FILE, 'w', encoding='utf-8')
        
        # データが書き込まれた
        handle = m()
        written_data = ''.join(call.args[0] for call in handle.write.call_args_list)
        assert "target_session" in written_data
        assert "test" in written_data
    
    def test_get_device_name_from_env(self):
        """環境変数からデバイス名を取得"""
        with patch.dict(os.environ, {'DEVICE_NAME': 'my_device'}):
            assert get_device_name() == 'my_device'
    
    def test_get_device_name_from_directory(self):
        """ディレクトリ名からデバイス名を取得"""
        with patch.dict(os.environ, {}, clear=True):
            with patch('os.getcwd', return_value='/home/user/my_project'):
                assert get_device_name() == 'my_project'


class TestSendToTmux:
    """send_to_tmux関数のテスト"""
    
    @pytest.mark.asyncio
    async def test_send_to_tmux_current_session(self):
        """現在のセッションへの送信"""
        config = {}
        message = "test message"
        
        with patch.dict(os.environ, {'TMUX': '/tmp/tmux-1000/default,12345,0'}):
            mock_result = MagicMock()
            mock_result.communicate = AsyncMock(return_value=(b'test_session\n', b''))
            
            with patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_exec:
                mock_exec.return_value = mock_result
                mock_exec.return_value.wait = AsyncMock()
                
                await send_to_tmux(config, message)
                
                # tmux display-messageが呼ばれた
                assert any('display-message' in str(call) for call in mock_exec.call_args_list)
    
    @pytest.mark.asyncio
    async def test_send_to_tmux_specific_session(self):
        """特定のセッションへの送信"""
        from test_helpers import create_tmux_mock
        
        config = {
            'tmux': {
                'default_target_session': 'my_session',
                'target_window': '1',
                'target_pane': '0'
            }
        }
        message = "test message"
        
        with patch('push_tmux.tmux.asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_exec:
            # my_sessionが存在するようにモック
            mock_exec.side_effect = create_tmux_mock(existing_sessions=['my_session'])
            
            await send_to_tmux(config, message)
            
            # send-keysが呼ばれた
            calls = mock_exec.call_args_list
            send_keys_calls = [call for call in calls if 'send-keys' in str(call)]
            assert len(send_keys_calls) == 2  # メッセージとEnterキーで2回
            
            # ターゲットが正しい
            for call in send_keys_calls:
                args = call[0]
                if 'send-keys' in args:
                    target_idx = args.index('-t') + 1
                    assert 'my_session:1.0' in args[target_idx]
    
    @pytest.mark.asyncio
    async def test_send_to_tmux_no_tmux_env(self):
        """TMUX環境変数がない場合"""
        config = {}
        message = "test"
        
        with patch.dict(os.environ, {}, clear=True):
            with patch('click.echo') as mock_echo:
                await send_to_tmux(config, message)
                
                # エラーメッセージが表示された
                error_calls = [call for call in mock_echo.call_args_list 
                              if 'エラー' in str(call)]
                assert len(error_calls) > 0
                assert any('tmuxセッション' in str(call) 
                          for call in error_calls)


class TestSendCommand:
    """send コマンドの追加テスト"""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_send_key_with_config_update(self, runner):
        """設定を更新してsend実行"""
        with patch('push_tmux.commands.send_key.load_config', return_value={}):
            with patch('push_tmux.commands.send.send_to_tmux', new_callable=AsyncMock) as mock_send:
                runner.invoke(cli, ['send', 'test', 
                                            '--session', 'my_session',
                                            '--window', '2',
                                            '--pane', '1'])
                
                # send_to_tmuxが呼ばれた
                mock_send.assert_called_once()
                config = mock_send.call_args[0][0]
                
                # 設定が更新された
                assert config['tmux']['target_session'] == 'my_session'
                assert config['tmux']['target_window'] == '2'
                assert config['tmux']['target_pane'] == '1'


class TestRegisterCommand:
    """registerコマンドの追加テスト"""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_register_with_exception(self, runner):
        """例外が発生した場合"""
        with patch.dict(os.environ, {'PUSHBULLET_TOKEN': 'test_token'}):
            with patch('push_tmux.commands.register.AsyncPushbullet') as MockPB:
                mock_pb = AsyncMock()
                mock_pb.get_devices = MagicMock(side_effect=Exception("Network error"))
                mock_pb.__aenter__ = AsyncMock(return_value=mock_pb)
                mock_pb.__aexit__ = AsyncMock()
                MockPB.return_value = mock_pb
                
                result = runner.invoke(cli, ['register'])
                assert result.exit_code == 0
                assert "デバイス登録中にエラーが発生しました" in result.output
                assert "Network error" in result.output


class TestListDevicesCommand:
    """list-devicesコマンドの追加テスト"""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_list_devices_with_exception(self, runner):
        """例外が発生した場合"""
        with patch.dict(os.environ, {'PUSHBULLET_TOKEN': 'test_token'}):
            with patch('push_tmux.commands.list_devices.AsyncPushbullet') as MockPB:
                mock_pb = AsyncMock()
                mock_pb.get_devices = MagicMock(side_effect=Exception("API error"))
                mock_pb.__aenter__ = AsyncMock(return_value=mock_pb)
                mock_pb.__aexit__ = AsyncMock()
                MockPB.return_value = mock_pb
                
                result = runner.invoke(cli, ['list-devices'])
                assert result.exit_code == 0
                assert "デバイス一覧取得中にエラーが発生しました" in result.output
                assert "API error" in result.output