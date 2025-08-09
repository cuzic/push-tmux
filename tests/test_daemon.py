#!/usr/bin/env python3
"""
daemon機能のテスト
"""
import pytest
import asyncio
import os
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock
from click.testing import CliRunner
import sys
import toml

# テストパス設定
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from push_tmux import cli
from push_tmux.config import load_config, save_config
from push_tmux.logging import setup_logging, log_daemon_event
from push_tmux.commands.daemon import daemon


class TestDaemonConfig:
    """daemon設定のテスト"""
    
    def test_default_config(self):
        """デフォルト設定の確認"""
        config = load_config()
        
        assert 'daemon' in config
        daemon_config = config['daemon']
        
        assert daemon_config['reload_interval'] == 1.0
        assert 'config.toml' in daemon_config['watch_files']
        assert '.env' in daemon_config['watch_files']
        assert '*.pyc' in daemon_config['ignore_patterns']
        
        # ログ設定の確認
        assert 'logging' in daemon_config
        logging_config = daemon_config['logging']
        assert logging_config['enable_reload_logs'] == True
        assert logging_config['log_level'] == 'INFO'
    
    def test_config_merge(self):
        """設定のマージ機能テスト"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            test_config = {
                'daemon': {
                    'reload_interval': 2.0,
                    'watch_files': ['custom.conf']
                }
            }
            toml.dump(test_config, f)
            temp_path = f.name
        
        try:
            # 一時的にCONFIG_FILEを変更
            import push_tmux
            original_config_file = push_tmux.CONFIG_FILE
            push_tmux.CONFIG_FILE = temp_path
            
            config = load_config()
            
            # カスタム設定が適用されているか確認
            assert config['daemon']['reload_interval'] == 2.0
            assert 'custom.conf' in config['daemon']['watch_files']
            
            # デフォルト値がマージされているか確認
            assert 'logging' in config['daemon']
            assert config['daemon']['logging']['log_level'] == 'INFO'
            
        finally:
            push_tmux.CONFIG_FILE = original_config_file
            os.unlink(temp_path)


class TestDaemonLogging:
    """daemon ログ機能のテスト"""
    
    def test_setup_logging_console(self):
        """コンソールログ設定のテスト"""
        config = {
            'daemon': {
                'logging': {
                    'log_level': 'DEBUG',
                    'log_file': ''
                }
            }
        }
        
        logger = setup_logging(config, is_daemon=True)
        
        assert logger.level == 10  # DEBUG level
        assert len(logger.handlers) > 0
    
    def test_setup_logging_file(self):
        """ファイルログ設定のテスト"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            log_file = f.name
        
        try:
            config = {
                'daemon': {
                    'logging': {
                        'log_level': 'WARNING',
                        'log_file': log_file
                    }
                }
            }
            
            logger = setup_logging(config, is_daemon=True)
            
            assert logger.level == 30  # WARNING level
            assert len(logger.handlers) >= 1
            
        finally:
            if os.path.exists(log_file):
                os.unlink(log_file)
    
    @patch('click.echo')
    @patch('logging.getLogger')
    def test_log_daemon_event(self, mock_get_logger, mock_echo):
        """daemon イベントログのテスト"""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        # 各種イベントタイプのテスト
        log_daemon_event('start', 'テストメッセージ')
        mock_logger.info.assert_called_with('プロセス開始: テストメッセージ')
        mock_echo.assert_called()
        
        log_daemon_event('error', 'エラーメッセージ')
        mock_logger.error.assert_called_with('エラー: エラーメッセージ')
        
        log_daemon_event('file_change', 'ファイル変更')
        mock_logger.info.assert_called_with('ファイル変更検知: ファイル変更')


class TestDaemonCommand:
    """daemon コマンドのテスト"""
    
    @patch('push_tmux.logging.setup_logging')
    @patch('push_tmux.logging.log_daemon_event')
    @patch('hupper.is_active')
    @patch('asyncio.run')
    def test_daemon_worker_mode(self, mock_asyncio_run, mock_is_active, mock_log, mock_setup_logging):
        """ワーカーモードのテスト"""
        mock_is_active.return_value = True
        
        runner = CliRunner()
        result = runner.invoke(cli, ['daemon', '--auto-route'])
        
        assert result.exit_code == 0
        mock_setup_logging.assert_called()
        mock_log.assert_called()
        mock_asyncio_run.assert_called()
    
    @patch('push_tmux.logging.setup_logging')
    @patch('push_tmux.logging.log_daemon_event')
    @patch('hupper.is_active')
    @patch('hupper.start_reloader')
    def test_daemon_monitor_mode(self, mock_start_reloader, mock_is_active, mock_log, mock_setup_logging):
        """監視モードのテスト"""
        mock_is_active.return_value = False
        mock_reloader = MagicMock()
        mock_start_reloader.return_value = mock_reloader
        
        # worker_main内でKeyboardInterruptを発生させてテストを終了
        with patch('asyncio.run', side_effect=KeyboardInterrupt):
            runner = CliRunner()
            result = runner.invoke(cli, ['daemon', '--debug', '--reload-interval', '2.0'])
            
            assert result.exit_code == 0
            mock_setup_logging.assert_called()
            mock_start_reloader.assert_called()
            mock_reloader.watch_files.assert_called()
    
    @patch('push_tmux.setup_logging')
    @patch('hupper.is_active')  
    def test_daemon_with_custom_options(self, mock_is_active, mock_setup_logging):
        """カスタムオプション付きdaemonコマンドのテスト"""
        mock_is_active.return_value = True
        
        with patch('asyncio.run') as mock_asyncio_run:
            runner = CliRunner()
            result = runner.invoke(cli, [
                'daemon', 
                '--device', 'test-device',
                '--reload-interval', '5.0',
                '--watch-files', 'custom.ini',
                '--watch-files', 'secrets.env'
            ])
            
            assert result.exit_code == 0
            mock_asyncio_run.assert_called()


class TestDaemonIntegration:
    """daemon 統合テスト"""
    
    @pytest.mark.asyncio
    async def test_daemon_worker_main_function(self):
        """daemon_worker_main 関数のテスト"""
        import push_tmux
        
        # テスト用パラメータを設定
        push_tmux._daemon_params = {
            'device': 'test-device',
            'all_devices': False,
            'auto_route': True,
            'debug': True
        }
        
        with patch('push_tmux.logging.setup_logging') as mock_setup_logging, \
             patch('push_tmux.logging.log_daemon_event') as mock_log, \
             patch('asyncio.run', side_effect=KeyboardInterrupt) as mock_run:
            
            from push_tmux.commands.daemon import daemon_worker_main
            daemon_worker_main()
            
            mock_setup_logging.assert_called()
            mock_log.assert_called()
            mock_run.assert_called()
    
    def test_daemon_error_handling(self):
        """daemon エラーハンドリングのテスト"""
        with patch('push_tmux.setup_logging'), \
             patch('push_tmux.log_daemon_event') as mock_log, \
             patch('hupper.is_active', return_value=True), \
             patch('asyncio.run', side_effect=Exception("テストエラー")):
            
            runner = CliRunner()
            result = runner.invoke(cli, ['daemon'])
            
            # エラーが発生してもプログラムが適切に終了することを確認
            assert result.exit_code != 0
            mock_log.assert_called()


if __name__ == '__main__':
    pytest.main([__file__])