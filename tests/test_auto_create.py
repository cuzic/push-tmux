#!/usr/bin/env python3
"""
Auto device creation command tests
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from click.testing import CliRunner
from push_tmux.commands.auto_create import auto_create
from push_tmux.tmux import get_all_sessions


class TestGetAllSessions:
    """get_all_sessions function tests"""

    @pytest.mark.asyncio
    async def test_get_all_sessions_success(self):
        """Test successful session retrieval"""
        with patch("push_tmux.tmux._run_tmux_command") as mock_run:
            mock_run.return_value = (0, "session1\nsession2\nsession3", None)
            sessions = await get_all_sessions()
            assert sessions == ["session1", "session2", "session3"]
            mock_run.assert_called_once_with(
                ["list-sessions", "-F", "#{session_name}"], capture_output=True
            )

    @pytest.mark.asyncio
    async def test_get_all_sessions_empty(self):
        """Test empty session list"""
        with patch("push_tmux.tmux._run_tmux_command") as mock_run:
            mock_run.return_value = (0, "", None)
            sessions = await get_all_sessions()
            assert sessions == []

    @pytest.mark.asyncio
    async def test_get_all_sessions_error(self):
        """Test error handling"""
        with patch("push_tmux.tmux._run_tmux_command") as mock_run:
            mock_run.return_value = (1, None, "error")
            sessions = await get_all_sessions()
            assert sessions == []


class TestAutoCreateCommand:
    """auto-create command tests"""

    def test_auto_create_excludes_main_session(self):
        """Test that 'main' session is excluded from device creation"""
        runner = CliRunner()

        with patch("push_tmux.commands.auto_create.get_api_key") as mock_get_api_key:
            mock_get_api_key.return_value = "test-api-key"

            with patch(
                "push_tmux.commands.auto_create.get_all_sessions", new_callable=AsyncMock
            ) as mock_get_sessions:
                mock_get_sessions.return_value = ["main", "session1", "session2"]

                mock_pb = AsyncMock()
                mock_pb.get_devices = Mock(return_value=[])

                with patch(
                    "push_tmux.commands.auto_create.AsyncPushbullet"
                ) as mock_async_pb:
                    mock_async_pb.return_value.__aenter__.return_value = mock_pb

                    result = runner.invoke(auto_create, ["--dry-run"])

                    assert result.exit_code == 0
                    assert "除外されたセッション (1件)" in result.output
                    assert "main (デバイス作成をスキップ)" in result.output
                    # main should not be in missing sessions
                    assert "未登録のセッション (2件)" in result.output
                    assert "+ session1" in result.output or "session1" in result.output
                    assert "+ session2" in result.output or "session2" in result.output

    def test_auto_create_no_sessions(self):
        """Test when no tmux sessions exist"""
        runner = CliRunner()

        with patch("push_tmux.commands.auto_create.get_api_key") as mock_get_api_key:
            mock_get_api_key.return_value = "test-api-key"

            with patch("push_tmux.commands.auto_create.get_all_sessions") as mock_get_sessions:
                mock_get_sessions.return_value = []

                result = runner.invoke(auto_create)

                assert result.exit_code == 0
                assert "tmuxセッションが見つかりませんでした" in result.output

    def test_auto_create_all_registered(self):
        """Test when all sessions are already registered"""
        runner = CliRunner()

        with patch("push_tmux.commands.auto_create.get_api_key") as mock_get_api_key:
            mock_get_api_key.return_value = "test-api-key"

            with patch("push_tmux.commands.auto_create.get_all_sessions", new_callable=AsyncMock) as mock_get_sessions:
                # Use AsyncMock with return_value
                mock_get_sessions.return_value = ["session1", "session2"]

                mock_pb = AsyncMock()
                mock_device1 = {"nickname": "session1", "iden": "device1"}
                mock_device2 = {"nickname": "session2", "iden": "device2"}
                # get_devices is synchronous, not async
                mock_pb.get_devices = Mock(return_value=[mock_device1, mock_device2])

                with patch("push_tmux.commands.auto_create.AsyncPushbullet") as mock_async_pb:
                    mock_async_pb.return_value.__aenter__.return_value = mock_pb

                    result = runner.invoke(auto_create)

                    assert result.exit_code == 0
                    assert "全てのtmuxセッションに対応するデバイスが既に登録されています" in result.output

    def test_auto_create_dry_run(self):
        """Test dry-run mode"""
        runner = CliRunner()

        with patch("push_tmux.commands.auto_create.get_api_key") as mock_get_api_key:
            mock_get_api_key.return_value = "test-api-key"

            with patch("push_tmux.commands.auto_create.get_all_sessions", new_callable=AsyncMock) as mock_get_sessions:
                mock_get_sessions.return_value = ["session1", "session2", "session3"]

                mock_pb = AsyncMock()
                mock_device1 = {"nickname": "session1", "iden": "device1"}
                mock_pb.get_devices = Mock(return_value=[mock_device1])

                with patch("push_tmux.commands.auto_create.AsyncPushbullet") as mock_async_pb:
                    mock_async_pb.return_value.__aenter__.return_value = mock_pb

                    result = runner.invoke(auto_create, ["--dry-run"])

                    assert result.exit_code == 0
                    assert "[DRY RUN]" in result.output
                    assert "session2" in result.output
                    assert "session3" in result.output
                    # Verify no devices were created
                    assert not mock_pb._async_post_data.called

    def test_auto_create_creates_devices(self):
        """Test actual device creation"""
        runner = CliRunner()

        with patch("push_tmux.commands.auto_create.get_api_key") as mock_get_api_key:
            mock_get_api_key.return_value = "test-api-key"

            with patch("push_tmux.commands.auto_create.get_all_sessions", new_callable=AsyncMock) as mock_get_sessions:
                mock_get_sessions.return_value = ["session1", "session2"]

                mock_pb = AsyncMock()
                # No existing devices
                mock_pb.get_devices = Mock(return_value=[])
                # Mock device creation response
                mock_pb._async_post_data.side_effect = [
                    {"nickname": "session1", "iden": "new-device1"},
                    {"nickname": "session2", "iden": "new-device2"},
                ]

                with patch("push_tmux.commands.auto_create.AsyncPushbullet") as mock_async_pb:
                    mock_async_pb.return_value.__aenter__.return_value = mock_pb

                    result = runner.invoke(auto_create)

                    assert result.exit_code == 0
                    assert "デバイス 'session1' を作成しました" in result.output
                    assert "デバイス 'session2' を作成しました" in result.output
                    assert "完了: 2件作成, 0件失敗" in result.output

                    # Verify _async_post_data was called twice
                    assert mock_pb._async_post_data.call_count == 2

    def test_auto_create_partial_failure(self):
        """Test partial device creation failure"""
        runner = CliRunner()

        with patch("push_tmux.commands.auto_create.get_api_key") as mock_get_api_key:
            mock_get_api_key.return_value = "test-api-key"

            with patch("push_tmux.commands.auto_create.get_all_sessions", new_callable=AsyncMock) as mock_get_sessions:
                mock_get_sessions.return_value = ["session1", "session2"]

                mock_pb = AsyncMock()
                mock_pb.get_devices = Mock(return_value=[])
                # First succeeds, second fails
                mock_pb._async_post_data.side_effect = [
                    {"nickname": "session1", "iden": "new-device1"},
                    Exception("API error"),
                ]

                with patch("push_tmux.commands.auto_create.AsyncPushbullet") as mock_async_pb:
                    mock_async_pb.return_value.__aenter__.return_value = mock_pb

                    result = runner.invoke(auto_create)

                    assert result.exit_code == 0
                    assert "デバイス 'session1' を作成しました" in result.output
                    assert "デバイス 'session2' の作成に失敗しました" in result.output
                    assert "完了: 1件作成, 1件失敗" in result.output
