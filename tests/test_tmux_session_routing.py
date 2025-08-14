#!/usr/bin/env python3
"""
tmuxセッションルーティングのテスト
デバイス名と同じ名前のtmuxセッションにメッセージが送信されることを確認
"""

import pytest
import os
from unittest.mock import patch, AsyncMock

from push_tmux.tmux import send_to_tmux
from test_helpers import create_tmux_mock, assert_send_keys_called


class TestTmuxSessionRouting:
    """tmuxセッションルーティングのテスト"""

    @pytest.mark.asyncio
    async def test_device_name_to_session_mapping(self):
        """デバイス名がtmuxセッション名として使用されるか"""
        config = {}
        message = "test message"
        device_name = "push-tmux"

        with patch(
            "push_tmux.tmux.asyncio.create_subprocess_exec", new_callable=AsyncMock
        ) as mock_exec:
            # push-tmuxセッションが存在する
            mock_exec.side_effect = create_tmux_mock(existing_sessions=["push-tmux"])

            with patch("push_tmux.tmux.click.echo"):
                await send_to_tmux(config, message, device_name=device_name)

            # send-keysが正しいセッションに送信されたか確認
            assert_send_keys_called(mock_exec, "push-tmux:0.0", message)

    @pytest.mark.asyncio
    async def test_fallback_to_current_session(self):
        """デバイス名のセッションが存在しない場合、現在のセッションにフォールバック"""
        config = {}
        message = "test message"
        device_name = "non-existent"

        with patch(
            "push_tmux.tmux.asyncio.create_subprocess_exec", new_callable=AsyncMock
        ) as mock_exec:
            # non-existentセッションは存在しないが、currentセッションは存在
            mock_exec.side_effect = create_tmux_mock(
                existing_sessions=[],  # non-existentは存在しない
                current_session="current-session",
            )

            with patch("push_tmux.tmux.click.echo"):
                with patch.dict(os.environ, {"TMUX": "/tmp/tmux-1000/default,12345,0"}):
                    await send_to_tmux(config, message, device_name=device_name)

            # 現在のセッションが使われる
            assert_send_keys_called(mock_exec, "current-session:0.0", message)

    @pytest.mark.asyncio
    async def test_config_override(self):
        """設定ファイルでセッションが指定されている場合"""
        config = {
            "tmux": {
                "default_target_session": "specified-session",
                "target_window": "1",
                "target_pane": "2",
            }
        }
        message = "test message"
        device_name = "device"

        with patch(
            "push_tmux.tmux.asyncio.create_subprocess_exec", new_callable=AsyncMock
        ) as mock_exec:
            # specified-sessionが存在する
            mock_exec.side_effect = create_tmux_mock(
                existing_sessions=["specified-session"]
            )

            with patch("push_tmux.tmux.click.echo"):
                await send_to_tmux(config, message, device_name=device_name)

            # 設定で指定されたセッションが使われる
            assert_send_keys_called(mock_exec, "specified-session:1.2", message)

    @pytest.mark.asyncio
    async def test_no_device_name(self):
        """デバイス名が指定されていない場合"""
        config = {}
        message = "test message"

        with patch(
            "push_tmux.tmux.asyncio.create_subprocess_exec", new_callable=AsyncMock
        ) as mock_exec:
            # 現在のセッションを使用
            mock_exec.side_effect = create_tmux_mock(current_session="default-session")

            with patch("push_tmux.tmux.click.echo"):
                with patch.dict(os.environ, {"TMUX": "/tmp/tmux-1000/default,12345,0"}):
                    await send_to_tmux(config, message)

            # 現在のセッションが使われる
            assert_send_keys_called(mock_exec, "default-session:0.0", message)

    @pytest.mark.asyncio
    async def test_multiple_sessions(self):
        """複数のセッションが存在する場合、正しいセッションが選択される"""
        config = {}
        message = "test message"
        device_name = "target-session"

        with patch(
            "push_tmux.tmux.asyncio.create_subprocess_exec", new_callable=AsyncMock
        ) as mock_exec:
            # 複数のセッションが存在するが、target-sessionを使用
            mock_exec.side_effect = create_tmux_mock(
                existing_sessions=["session1", "session2", "target-session", "session3"]
            )

            with patch("push_tmux.tmux.click.echo"):
                await send_to_tmux(config, message, device_name=device_name)

            # 指定されたセッションが使われる
            assert_send_keys_called(mock_exec, "target-session:0.0", message)
