#!/usr/bin/env python3
"""
Auto device sync command tests
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from click.testing import CliRunner
from push_tmux.commands.auto_sync import auto_sync


class TestAutoSyncCommand:
    """auto-sync command tests"""

    def test_auto_sync_excludes_main(self):
        """Test that 'main' is excluded from sync operations"""
        runner = CliRunner()

        with patch("push_tmux.commands.auto_sync.get_api_key") as mock_get_api_key:
            mock_get_api_key.return_value = "test-api-key"

            with patch(
                "push_tmux.commands.auto_sync.get_all_sessions", new_callable=AsyncMock
            ) as mock_get_sessions:
                # main session exists but should be excluded
                mock_get_sessions.return_value = ["main", "session1"]

                mock_pb = AsyncMock()
                mock_device1 = {
                    "nickname": "session1",
                    "iden": "id1",
                    "manufacturer": "push-tmux",
                }
                mock_device2 = {
                    "nickname": "main",
                    "iden": "id2",
                    "manufacturer": "push-tmux",
                }
                mock_pb.get_devices = Mock(return_value=[mock_device1, mock_device2])

                with patch(
                    "push_tmux.commands.auto_sync.AsyncPushbullet"
                ) as mock_async_pb:
                    mock_async_pb.return_value.__aenter__.return_value = mock_pb

                    result = runner.invoke(auto_sync, ["--dry-run"])

                    assert result.exit_code == 0
                    assert "除外された項目 (1件)" in result.output
                    assert "main (同期をスキップ)" in result.output
                    # main should not appear in create or delete lists
                    assert "tmuxセッションとデバイスは既に同期しています" in result.output

    def test_auto_sync_already_synced(self):
        """Test when sessions and devices are already in sync"""
        runner = CliRunner()

        with patch("push_tmux.commands.auto_sync.get_api_key") as mock_get_api_key:
            mock_get_api_key.return_value = "test-api-key"

            with patch(
                "push_tmux.commands.auto_sync.get_all_sessions", new_callable=AsyncMock
            ) as mock_get_sessions:
                mock_get_sessions.return_value = ["session1", "session2"]

                mock_pb = AsyncMock()
                mock_device1 = {
                    "nickname": "session1",
                    "iden": "id1",
                    "manufacturer": "push-tmux",
                }
                mock_device2 = {
                    "nickname": "session2",
                    "iden": "id2",
                    "manufacturer": "push-tmux",
                }
                mock_pb.get_devices = Mock(return_value=[mock_device1, mock_device2])

                with patch(
                    "push_tmux.commands.auto_sync.AsyncPushbullet"
                ) as mock_async_pb:
                    mock_async_pb.return_value.__aenter__.return_value = mock_pb

                    result = runner.invoke(auto_sync)

                    assert result.exit_code == 0
                    assert "tmuxセッションとデバイスは既に同期しています" in result.output

    def test_auto_sync_needs_creation(self):
        """Test when sessions need device creation"""
        runner = CliRunner()

        with patch("push_tmux.commands.auto_sync.get_api_key") as mock_get_api_key:
            mock_get_api_key.return_value = "test-api-key"

            with patch(
                "push_tmux.commands.auto_sync.get_all_sessions", new_callable=AsyncMock
            ) as mock_get_sessions:
                mock_get_sessions.return_value = ["session1", "session2", "session3"]

                mock_pb = AsyncMock()
                mock_device1 = {
                    "nickname": "session1",
                    "iden": "id1",
                    "manufacturer": "push-tmux",
                }
                mock_pb.get_devices = Mock(return_value=[mock_device1])

                with patch(
                    "push_tmux.commands.auto_sync.AsyncPushbullet"
                ) as mock_async_pb:
                    mock_async_pb.return_value.__aenter__.return_value = mock_pb

                    result = runner.invoke(auto_sync, ["--dry-run"])

                    assert result.exit_code == 0
                    assert "作成するデバイス (2件)" in result.output
                    assert "session2" in result.output
                    assert "session3" in result.output
                    assert "削除するデバイスはありません" in result.output

    def test_auto_sync_needs_deletion(self):
        """Test when devices need deletion"""
        runner = CliRunner()

        with patch("push_tmux.commands.auto_sync.get_api_key") as mock_get_api_key:
            mock_get_api_key.return_value = "test-api-key"

            with patch(
                "push_tmux.commands.auto_sync.get_all_sessions", new_callable=AsyncMock
            ) as mock_get_sessions:
                mock_get_sessions.return_value = ["session1"]

                mock_pb = AsyncMock()
                mock_device1 = {
                    "nickname": "session1",
                    "iden": "id1",
                    "manufacturer": "push-tmux",
                }
                mock_device2 = {
                    "nickname": "orphan1",
                    "iden": "id2",
                    "manufacturer": "push-tmux",
                }
                mock_device3 = {
                    "nickname": "orphan2",
                    "iden": "id3",
                    "manufacturer": "push-tmux",
                }
                mock_pb.get_devices = Mock(
                    return_value=[mock_device1, mock_device2, mock_device3]
                )

                with patch(
                    "push_tmux.commands.auto_sync.AsyncPushbullet"
                ) as mock_async_pb:
                    mock_async_pb.return_value.__aenter__.return_value = mock_pb

                    result = runner.invoke(auto_sync, ["--dry-run"])

                    assert result.exit_code == 0
                    assert "作成するデバイスはありません" in result.output
                    assert "削除するデバイス (2件)" in result.output
                    assert "orphan1" in result.output
                    assert "orphan2" in result.output

    def test_auto_sync_needs_both(self):
        """Test when both creation and deletion are needed"""
        runner = CliRunner()

        with patch("push_tmux.commands.auto_sync.get_api_key") as mock_get_api_key:
            mock_get_api_key.return_value = "test-api-key"

            with patch(
                "push_tmux.commands.auto_sync.get_all_sessions", new_callable=AsyncMock
            ) as mock_get_sessions:
                mock_get_sessions.return_value = ["session1", "session2"]

                mock_pb = AsyncMock()
                mock_device1 = {
                    "nickname": "session1",
                    "iden": "id1",
                    "manufacturer": "push-tmux",
                }
                mock_device2 = {
                    "nickname": "orphan",
                    "iden": "id2",
                    "manufacturer": "push-tmux",
                }
                mock_pb.get_devices = Mock(return_value=[mock_device1, mock_device2])

                with patch(
                    "push_tmux.commands.auto_sync.AsyncPushbullet"
                ) as mock_async_pb:
                    mock_async_pb.return_value.__aenter__.return_value = mock_pb

                    result = runner.invoke(auto_sync, ["--dry-run"])

                    assert result.exit_code == 0
                    assert "作成するデバイス (1件)" in result.output
                    assert "session2" in result.output
                    assert "削除するデバイス (1件)" in result.output
                    assert "orphan" in result.output

    def test_auto_sync_executes_sync(self):
        """Test actual sync execution"""
        runner = CliRunner()

        with patch("push_tmux.commands.auto_sync.get_api_key") as mock_get_api_key:
            mock_get_api_key.return_value = "test-api-key"

            with patch(
                "push_tmux.commands.auto_sync.get_all_sessions", new_callable=AsyncMock
            ) as mock_get_sessions:
                mock_get_sessions.return_value = ["session1", "new_session"]

                mock_pb = AsyncMock()
                mock_device1 = {
                    "nickname": "session1",
                    "iden": "id1",
                    "manufacturer": "push-tmux",
                }
                mock_device2 = {
                    "nickname": "old_device",
                    "iden": "id2",
                    "manufacturer": "push-tmux",
                }
                mock_pb.get_devices = Mock(return_value=[mock_device1, mock_device2])
                # Mock creation
                mock_pb._async_post_data.return_value = {
                    "nickname": "new_session",
                    "iden": "id3",
                }
                # Mock deletion
                mock_pb._async_delete_data.return_value = None

                with patch(
                    "push_tmux.commands.auto_sync.AsyncPushbullet"
                ) as mock_async_pb:
                    mock_async_pb.return_value.__aenter__.return_value = mock_pb

                    result = runner.invoke(auto_sync)

                    assert result.exit_code == 0
                    assert "デバイス 'new_session' を作成しました" in result.output
                    assert "デバイス 'old_device' を削除しました" in result.output
                    assert "完了: 1件作成 (0件失敗), 1件削除 (0件失敗)" in result.output

    def test_auto_sync_partial_failure(self):
        """Test partial sync failure"""
        runner = CliRunner()

        with patch("push_tmux.commands.auto_sync.get_api_key") as mock_get_api_key:
            mock_get_api_key.return_value = "test-api-key"

            with patch(
                "push_tmux.commands.auto_sync.get_all_sessions", new_callable=AsyncMock
            ) as mock_get_sessions:
                mock_get_sessions.return_value = ["session1", "new1", "new2"]

                mock_pb = AsyncMock()
                mock_device1 = {
                    "nickname": "session1",
                    "iden": "id1",
                    "manufacturer": "push-tmux",
                }
                mock_device2 = {
                    "nickname": "orphan1",
                    "iden": "id2",
                    "manufacturer": "push-tmux",
                }
                mock_device3 = {
                    "nickname": "orphan2",
                    "iden": "id3",
                    "manufacturer": "push-tmux",
                }
                mock_pb.get_devices = Mock(
                    return_value=[mock_device1, mock_device2, mock_device3]
                )
                # First creation succeeds, second fails
                mock_pb._async_post_data.side_effect = [
                    {"nickname": "new1", "iden": "id4"},
                    Exception("Create error"),
                ]
                # First deletion succeeds, second fails
                mock_pb._async_delete_data.side_effect = [None, Exception("Delete error")]

                with patch(
                    "push_tmux.commands.auto_sync.AsyncPushbullet"
                ) as mock_async_pb:
                    mock_async_pb.return_value.__aenter__.return_value = mock_pb

                    result = runner.invoke(auto_sync)

                    assert result.exit_code == 0
                    assert "デバイス 'new1' を作成しました" in result.output
                    assert "デバイス 'new2' の作成に失敗しました" in result.output
                    assert "デバイス 'orphan1' を削除しました" in result.output
                    assert "デバイス 'orphan2' の削除に失敗しました" in result.output
                    assert "完了: 1件作成 (1件失敗), 1件削除 (1件失敗)" in result.output

    def test_auto_sync_ignores_non_push_tmux_devices(self):
        """Test that non-push-tmux devices are ignored"""
        runner = CliRunner()

        with patch("push_tmux.commands.auto_sync.get_api_key") as mock_get_api_key:
            mock_get_api_key.return_value = "test-api-key"

            with patch(
                "push_tmux.commands.auto_sync.get_all_sessions", new_callable=AsyncMock
            ) as mock_get_sessions:
                mock_get_sessions.return_value = ["session1"]

                mock_pb = AsyncMock()
                mock_device1 = {
                    "nickname": "session1",
                    "iden": "id1",
                    "manufacturer": "push-tmux",
                }
                mock_device2 = {
                    "nickname": "other-device",
                    "iden": "id2",
                    "manufacturer": "other",
                }
                mock_pb.get_devices = Mock(return_value=[mock_device1, mock_device2])

                with patch(
                    "push_tmux.commands.auto_sync.AsyncPushbullet"
                ) as mock_async_pb:
                    mock_async_pb.return_value.__aenter__.return_value = mock_pb

                    result = runner.invoke(auto_sync, ["--dry-run"])

                    assert result.exit_code == 0
                    assert "push-tmuxが作成したデバイス (1件)" in result.output
                    assert "session1" in result.output
                    # other-device should not be in the list
                    assert "tmuxセッションとデバイスは既に同期しています" in result.output

    def test_auto_sync_no_sessions(self):
        """Test when there are no tmux sessions"""
        runner = CliRunner()

        with patch("push_tmux.commands.auto_sync.get_api_key") as mock_get_api_key:
            mock_get_api_key.return_value = "test-api-key"

            with patch(
                "push_tmux.commands.auto_sync.get_all_sessions", new_callable=AsyncMock
            ) as mock_get_sessions:
                mock_get_sessions.return_value = []

                mock_pb = AsyncMock()
                mock_device1 = {
                    "nickname": "orphan",
                    "iden": "id1",
                    "manufacturer": "push-tmux",
                }
                mock_pb.get_devices = Mock(return_value=[mock_device1])

                with patch(
                    "push_tmux.commands.auto_sync.AsyncPushbullet"
                ) as mock_async_pb:
                    mock_async_pb.return_value.__aenter__.return_value = mock_pb

                    result = runner.invoke(auto_sync, ["--dry-run"])

                    assert result.exit_code == 0
                    assert "tmuxセッションが見つかりませんでした" in result.output
                    assert "削除するデバイス (1件)" in result.output
                    assert "orphan" in result.output
