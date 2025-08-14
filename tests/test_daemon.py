#!/usr/bin/env python3
"""
daemon機能のテスト
"""

import pytest
import os
import tempfile
import logging
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
import sys
import toml

# テストパス設定
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from push_tmux import cli
from push_tmux.config import load_config
from push_tmux.logging import setup_logging, log_daemon_event


class TestDaemonConfig:
    """daemon設定のテスト"""

    def test_default_config(self):
        """デフォルト設定の確認"""
        config = load_config()

        assert "daemon" in config
        daemon_config = config["daemon"]

        assert daemon_config["reload_interval"] == 1.0
        assert "config.toml" in daemon_config["watch_files"]
        assert ".env" in daemon_config["watch_files"]
        assert "*.pyc" in daemon_config["ignore_patterns"]

        # ログ設定の確認
        assert "logging" in daemon_config
        logging_config = daemon_config["logging"]
        assert logging_config["enable_reload_logs"]
        assert logging_config["log_level"] == "INFO"

    def test_config_merge(self):
        """設定のマージ機能テスト"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            test_config = {
                "daemon": {"reload_interval": 2.0, "watch_files": ["custom.conf"]}
            }
            toml.dump(test_config, f)
            temp_path = f.name

        try:
            # 一時的にCONFIG_FILEを変更
            from push_tmux import config as config_module

            original_config_file = config_module.CONFIG_FILE
            config_module.CONFIG_FILE = temp_path

            config = load_config()

            # カスタム設定が適用されているか確認
            assert config["daemon"]["reload_interval"] == 2.0
            assert "custom.conf" in config["daemon"]["watch_files"]

            # デフォルト値がマージされているか確認
            assert "logging" in config["daemon"]
            assert config["daemon"]["logging"]["log_level"] == "INFO"

        finally:
            config_module.CONFIG_FILE = original_config_file
            os.unlink(temp_path)


class TestDaemonLogging:
    """daemon ログ機能のテスト"""

    def test_setup_logging_console(self):
        """コンソールログ設定のテスト"""
        config = {"daemon": {"logging": {"log_level": "DEBUG", "log_file": ""}}}

        logger = setup_logging(config, is_daemon=True)

        assert logger.getEffectiveLevel() == 10  # DEBUG level
        # ルートロガーのハンドラーを確認
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) > 0

    def test_setup_logging_file(self):
        """ファイルログ設定のテスト"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            log_file = f.name

        try:
            config = {
                "daemon": {"logging": {"log_level": "WARNING", "log_file": log_file}}
            }

            logger = setup_logging(config, is_daemon=True)

            assert logger.getEffectiveLevel() == 30  # WARNING level
            # ルートロガーのハンドラーを確認
            root_logger = logging.getLogger()
            assert len(root_logger.handlers) >= 1

        finally:
            if os.path.exists(log_file):
                os.unlink(log_file)

    @patch("click.echo")
    @patch("logging.getLogger")
    def test_log_daemon_event(self, mock_get_logger, mock_echo):
        """daemon イベントログのテスト"""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # 各種イベントタイプのテスト
        log_daemon_event("start", "テストメッセージ")
        mock_logger.info.assert_called_with("プロセス開始: テストメッセージ")
        mock_echo.assert_called()

        log_daemon_event("error", "エラーメッセージ")
        mock_logger.error.assert_called_with("エラー: エラーメッセージ")

        log_daemon_event("file_change", "ファイル変更")
        mock_logger.info.assert_called_with("ファイル変更検知: ファイル変更")


class TestDaemonCommand:
    """daemon コマンドのテスト"""

    @patch("push_tmux.commands.start.setup_logging")
    @patch("push_tmux.commands.start.log_daemon_event")
    @patch("push_tmux.commands.start._run_listener_iteration")
    def test_daemon_worker_mode(self, mock_run_listener, mock_log, mock_setup_logging):
        """ワーカーモードのテスト"""
        # _run_listener_iterationでKeyboardInterruptを発生させてテストを終了
        mock_run_listener.side_effect = KeyboardInterrupt

        runner = CliRunner()
        runner.invoke(cli, ["start", "--daemon", "--auto-route"])

        # start --daemonコマンドではsetup_loggingとlog_daemon_eventが呼ばれる
        mock_setup_logging.assert_called()
        mock_log.assert_called()

    @patch("push_tmux.commands.start.setup_logging")
    @patch("push_tmux.commands.start.log_daemon_event")
    @patch("push_tmux.commands.start._run_listener_iteration")
    def test_daemon_monitor_mode(self, mock_run_listener, mock_log, mock_setup_logging):
        """監視モードのテスト"""
        mock_run_listener.side_effect = KeyboardInterrupt  # テスト終了のため

        runner = CliRunner()
        runner.invoke(
            cli, ["start", "--daemon", "--debug", "--reload-interval", "2.0"]
        )

        mock_setup_logging.assert_called()
        mock_log.assert_called()

    @patch("push_tmux.commands.start.setup_logging")
    @patch("push_tmux.commands.start._run_listener_iteration")
    def test_daemon_with_custom_options(self, mock_run_listener, mock_setup_logging):
        """カスタムオプション付きdaemonコマンドのテスト"""
        mock_run_listener.side_effect = KeyboardInterrupt  # テスト終了のため

        runner = CliRunner()
        runner.invoke(
            cli,
            [
                "start",
                "--daemon",
                "--device",
                "test-device",
                "--reload-interval",
                "5.0",
                "--watch-files",
                "custom.ini",
                "--watch-files",
                "secrets.env",
            ],
        )

        mock_setup_logging.assert_called()


class TestDaemonIntegration:
    """daemon 統合テスト"""

    def test_daemon_worker_main_function(self):
        """デーモンワーカーのメイン関数のテスト"""
        # 環境変数を設定
        test_env = {
            "PUSH_TMUX_DEVICE": "test-device",
            "PUSH_TMUX_ALL_DEVICES": "0",
            "PUSH_TMUX_AUTO_ROUTE": "1",
            "PUSH_TMUX_DEBUG": "1",
        }

        with (
            patch.dict(os.environ, test_env),
            patch("push_tmux.commands.daemon_worker.log_daemon_event") as mock_log,
            patch("asyncio.run", side_effect=KeyboardInterrupt) as mock_run,
        ):
            from push_tmux.commands.daemon_worker import main

            main()

            mock_log.assert_called()
            mock_run.assert_called()

    def test_daemon_error_handling(self):
        """daemon エラーハンドリングのテスト"""
        with (
            patch("push_tmux.commands.start.setup_logging"),
            patch("push_tmux.commands.start.log_daemon_event") as mock_log,
            patch("push_tmux.commands.start._run_listener_iteration") as mock_listener,
        ):
            # _run_listener_iterationでKeyboardInterruptを発生させる
            mock_listener.side_effect = KeyboardInterrupt

            runner = CliRunner()
            runner.invoke(cli, ["start", "--daemon"])

            # log_daemon_eventが呼ばれることを確認（daemon開始時に呼ばれる）
            mock_log.assert_called()


if __name__ == "__main__":
    pytest.main([__file__])
