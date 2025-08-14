#!/usr/bin/env python3
"""
tmux統合テスト
"""

import os
from unittest.mock import patch

import pytest

from push_tmux.tmux import send_to_tmux
from test_helpers import create_tmux_mock, assert_send_keys_called


class TestSendToTmux:
    """tmux送信機能のテスト"""

    @pytest.mark.asyncio
    async def test_send_to_tmux_default_session(self, mock_subprocess, mock_tmux_env):
        """デフォルトセッション（環境変数から）への送信"""
        # 現在のセッションを使用
        mock_subprocess.side_effect = create_tmux_mock(
            current_session="test-session",
            windows="1\n2\n3",  # 最初のウィンドウは1
            panes="2\n3",  # 最初のペインは2
        )

        config = {}  # 空の設定でデフォルト値を使用

        # click.echoをモック
        with patch("push_tmux.tmux.click.echo"):
            await send_to_tmux(config, "test message")

        # send-keysが正しく呼ばれたことを確認
        assert_send_keys_called(mock_subprocess, "test-session:1.2", "test message")

    @pytest.mark.asyncio
    async def test_send_to_tmux_custom_session(self, mock_subprocess):
        """カスタムセッションへの送信"""
        config = {
            "tmux": {
                "default_target_session": "my-session",
                "target_window": "2",
                "target_pane": "1",
            }
        }

        # my-sessionが存在する
        mock_subprocess.side_effect = create_tmux_mock(existing_sessions=["my-session"])

        with patch("push_tmux.tmux.click.echo"):
            await send_to_tmux(config, "custom message")

        # カスタム設定が使われる
        assert_send_keys_called(mock_subprocess, "my-session:2.1", "custom message")

    @pytest.mark.asyncio
    async def test_send_to_tmux_command_not_found(self, mock_subprocess):
        """tmuxコマンドが見つからない場合"""
        # FileNotFoundErrorを発生させる
        mock_subprocess.side_effect = FileNotFoundError("tmux not found")

        config = {"tmux": {"default_target_session": "test"}}

        with patch("push_tmux.tmux.click.echo") as mock_echo:
            await send_to_tmux(config, "test message")

            # エラーメッセージが表示される
            error_calls = [
                call
                for call in mock_echo.call_args_list
                if "err" in str(call) or "エラー" in str(call)
            ]
            assert len(error_calls) > 0

    @pytest.mark.asyncio
    async def test_send_to_tmux_generic_error(self, mock_subprocess):
        """一般的なエラーが発生した場合"""
        # Exceptionを発生させる
        mock_subprocess.side_effect = Exception("Something went wrong")

        config = {"tmux": {"default_target_session": "test"}}

        with patch("push_tmux.tmux.click.echo") as mock_echo:
            await send_to_tmux(config, "test message")

            # エラーメッセージが表示される
            error_calls = [
                call
                for call in mock_echo.call_args_list
                if "err" in str(call) or "エラー" in str(call)
            ]
            assert len(error_calls) > 0

    @pytest.mark.asyncio
    async def test_send_to_tmux_special_characters(self, mock_subprocess):
        """特殊文字を含むメッセージの送信"""
        config = {"tmux": {"default_target_session": "test"}}

        # testセッションが存在する
        mock_subprocess.side_effect = create_tmux_mock(existing_sessions=["test"])

        special_message = "echo 'Hello \"World\"' && ls -la | grep test"

        with patch("push_tmux.tmux.click.echo"):
            await send_to_tmux(config, special_message)

        # 特殊文字がそのまま送信される
        send_calls = [
            call for call in mock_subprocess.call_args_list if "send-keys" in str(call)
        ]
        assert len(send_calls) == 2
        assert send_calls[0][0][4] == special_message

    @pytest.mark.asyncio
    async def test_send_to_tmux_unicode(self, mock_subprocess):
        """Unicode文字を含むメッセージの送信"""
        config = {"tmux": {"default_target_session": "test"}}

        # testセッションが存在する
        mock_subprocess.side_effect = create_tmux_mock(existing_sessions=["test"])

        unicode_message = "こんにちは 世界 🌍 Hello"

        with patch("push_tmux.tmux.click.echo"):
            await send_to_tmux(config, unicode_message)

        # Unicode文字がそのまま送信される
        send_calls = [
            call for call in mock_subprocess.call_args_list if "send-keys" in str(call)
        ]
        assert len(send_calls) == 2
        assert send_calls[0][0][4] == unicode_message

    @pytest.mark.asyncio
    async def test_send_to_tmux_empty_message(self, mock_subprocess):
        """空のメッセージの処理"""
        config = {"tmux": {"default_target_session": "test"}}

        # testセッションが存在する
        mock_subprocess.side_effect = create_tmux_mock(existing_sessions=["test"])

        with patch("push_tmux.tmux.click.echo"):
            await send_to_tmux(config, "")

        # 空のメッセージでも送信される
        send_calls = [
            call for call in mock_subprocess.call_args_list if "send-keys" in str(call)
        ]
        assert len(send_calls) == 2
        assert send_calls[0][0][4] == ""

    @pytest.mark.asyncio
    async def test_send_to_tmux_with_defaults(self, mock_subprocess):
        """デフォルト設定での送信"""
        config = {"tmux": {"target_window": "first", "target_pane": "first"}}

        # 現在のセッションを使用
        mock_subprocess.side_effect = create_tmux_mock(
            current_session="current", windows="0\n1", panes="0\n1"
        )

        with patch("push_tmux.tmux.click.echo"):
            with patch.dict(os.environ, {"TMUX": "/tmp/tmux-1000/default,12345,0"}):
                await send_to_tmux(config, "default message")

        # firstが0に解決される
        assert_send_keys_called(mock_subprocess, "current:0.0", "default message")
