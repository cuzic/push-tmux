#!/usr/bin/env python3
"""
Tests for timer command functionality
"""

import pytest
import asyncio
import time
from unittest.mock import patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from push_tmux.slash_commands import SlashCommandParser, expand_slash_command


class TestSlashCommandDelay:
    """Test delay functionality in slash commands"""

    def test_get_delay_from_config(self):
        """設定から遅延時間を取得"""
        config = {
            "slash_commands": {
                "timer": {"template": 'echo "done"', "delay_seconds": 10}
            }
        }
        parser = SlashCommandParser(config)
        delay = parser.get_delay("timer", {})
        assert delay == 10

    def test_get_delay_from_arguments(self):
        """引数から遅延時間を取得（設定を上書き）"""
        config = {
            "slash_commands": {
                "timer": {"template": 'echo "done"', "delay_seconds": 10}
            }
        }
        parser = SlashCommandParser(config)
        delay = parser.get_delay("timer", {"delay": "30"})
        assert delay == 30

    def test_get_delay_no_config(self):
        """設定がない場合はNone"""
        config = {"slash_commands": {"deploy": {"template": "git pull"}}}
        parser = SlashCommandParser(config)
        delay = parser.get_delay("deploy", {})
        assert delay is None

    def test_get_delay_invalid_value(self):
        """無効な値のハンドリング"""
        config = {
            "slash_commands": {
                "timer": {"template": 'echo "done"', "delay_seconds": 10}
            }
        }
        parser = SlashCommandParser(config)

        # 非数値 → デフォルト値
        delay = parser.get_delay("timer", {"delay": "abc"})
        assert delay == 10

        # 負の値 → 0
        delay = parser.get_delay("timer", {"delay": "-5"})
        assert delay == 0

        # 極端に大きい値 → 上限値（24時間）
        delay = parser.get_delay("timer", {"delay": "999999"})
        assert delay == 86400

        # 小数 → 整数に変換
        delay = parser.get_delay("timer", {"delay": "5.5"})
        assert delay == 5

        # 空文字列 → デフォルト値
        delay = parser.get_delay("timer", {"delay": ""})
        assert delay == 10


class TestExpandSlashCommandWithDelay:
    """Test expand_slash_command with delay support"""

    def test_expand_with_delay(self):
        """遅延時間を含む戻り値"""
        config = {
            "slash_commands": {
                "timer": {
                    "template": 'echo "{message}"',
                    "defaults": {"message": "Done!"},
                    "delay_seconds": 10,
                }
            }
        }
        result = expand_slash_command("/timer", config, "device")

        # 4要素のタプルが返される
        assert len(result) == 4
        is_slash, cmd, session, delay = result

        assert is_slash
        assert cmd == 'echo "Done!"'
        assert delay == 10

    def test_expand_without_delay(self):
        """遅延なしコマンド（既存機能）"""
        config = {
            "slash_commands": {"deploy": {"template": "git pull", "defaults": {}}}
        }
        result = expand_slash_command("/deploy", config, "device")

        # 4要素のタプルが返される
        assert len(result) == 4
        is_slash, cmd, session, delay = result

        assert is_slash
        assert cmd == "git pull"
        assert delay is None

    def test_expand_with_delay_argument(self):
        """引数で遅延時間を指定"""
        config = {
            "slash_commands": {
                "timer": {
                    "template": 'echo "{message}"',
                    "defaults": {"message": "Done!"},
                    "delay_seconds": 10,
                }
            }
        }
        result = expand_slash_command(
            "/timer delay:30 message:Custom", config, "device"
        )

        is_slash, cmd, session, delay = result

        assert is_slash
        assert cmd == 'echo "Custom"'
        assert delay == 30  # 引数が優先される

    def test_backward_compatibility(self):
        """後方互換性の確認"""
        config = {"slash_commands": {"test": {"template": "echo test"}}}

        # 3要素でもアンパック可能（Pythonの仕様により最後の要素は無視される）
        result = expand_slash_command("/test", config, "device")
        is_slash, cmd, session, delay = result

        # 既存コマンドは遅延なし
        assert delay is None


class TestDelayedExecution:
    """Test delayed execution functionality"""

    @pytest.mark.asyncio
    async def test_delayed_execution_basic(self):
        """基本的な遅延実行"""
        from push_tmux.commands.listen import delayed_execution

        config = {}
        command = 'echo "test"'
        target = "test-session"

        with patch("push_tmux.commands.listen.send_to_tmux") as mock_send:
            mock_send.return_value = asyncio.Future()
            mock_send.return_value.set_result(None)

            start_time = time.time()
            await delayed_execution(2, config, command, target)
            elapsed = time.time() - start_time

            # 2秒以上経過していること
            assert elapsed >= 2
            mock_send.assert_called_once_with(config, command, target)

    @pytest.mark.asyncio
    async def test_multiple_timers(self):
        """複数タイマーの並行実行"""
        from push_tmux.commands.listen import delayed_execution

        with patch("push_tmux.commands.listen.send_to_tmux") as mock_send:
            mock_send.return_value = asyncio.Future()
            mock_send.return_value.set_result(None)

            # 3つのタイマーを同時に開始
            tasks = [
                asyncio.create_task(delayed_execution(1, {}, "cmd1", "session")),
                asyncio.create_task(delayed_execution(2, {}, "cmd2", "session")),
                asyncio.create_task(delayed_execution(3, {}, "cmd3", "session")),
            ]

            start_time = time.time()
            await asyncio.gather(*tasks)
            elapsed = time.time() - start_time

            # 並行実行なので3秒程度で完了
            assert 3 <= elapsed < 4
            assert mock_send.call_count == 3

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """エラーハンドリング"""
        from push_tmux.commands.listen import delayed_execution

        config = {}

        with patch(
            "push_tmux.commands.listen.send_to_tmux",
            side_effect=Exception("tmux error"),
        ):
            with patch("click.echo") as mock_echo:
                # エラーが発生してもクラッシュしない
                await delayed_execution(0, config, "cmd", "session")

                # エラーメッセージが出力される
                assert mock_echo.called
