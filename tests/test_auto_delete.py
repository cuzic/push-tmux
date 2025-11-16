#!/usr/bin/env python3
"""
Auto device deletion command tests
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from click.testing import CliRunner
from push_tmux.commands.auto_delete import auto_delete


class TestAutoDeleteCommand:
    """auto-delete command tests"""

    def test_auto_delete_no_sessions(self):
        """Test when no tmux sessions exist"""
        runner = CliRunner()

        with patch("push_tmux.commands.auto_delete.get_api_key") as mock_get_api_key:
            mock_get_api_key.return_value = "test-api-key"

            with patch(
                "push_tmux.commands.auto_delete.get_all_sessions",
                new_callable=AsyncMock,
            ) as mock_get_sessions:
                mock_get_sessions.return_value = []

                mock_pb = AsyncMock()
                mock_device1 = {
                    "nickname": "device1",
                    "iden": "id1",
                    "manufacturer": "push-tmux",
                }
                mock_pb.get_devices = Mock(return_value=[mock_device1])

                with patch(
                    "push_tmux.commands.auto_delete.AsyncPushbullet"
                ) as mock_async_pb:
                    mock_async_pb.return_value.__aenter__.return_value = mock_pb

                    result = runner.invoke(auto_delete, ["--dry-run"])

                    assert result.exit_code == 0
                    assert "tmuxセッションが見つかりませんでした" in result.output
                    assert "孤立したデバイス (1件)" in result.output

    def test_auto_delete_no_orphaned_devices(self):
        """Test when all devices have corresponding sessions"""
        runner = CliRunner()

        with patch("push_tmux.commands.auto_delete.get_api_key") as mock_get_api_key:
            mock_get_api_key.return_value = "test-api-key"

            with patch(
                "push_tmux.commands.auto_delete.get_all_sessions",
                new_callable=AsyncMock,
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
                    "push_tmux.commands.auto_delete.AsyncPushbullet"
                ) as mock_async_pb:
                    mock_async_pb.return_value.__aenter__.return_value = mock_pb

                    result = runner.invoke(auto_delete)

                    assert result.exit_code == 0
                    assert (
                        "全てのデバイスに対応するtmuxセッションが存在します" in result.output
                    )

    def test_auto_delete_dry_run(self):
        """Test dry-run mode"""
        runner = CliRunner()

        with patch("push_tmux.commands.auto_delete.get_api_key") as mock_get_api_key:
            mock_get_api_key.return_value = "test-api-key"

            with patch(
                "push_tmux.commands.auto_delete.get_all_sessions",
                new_callable=AsyncMock,
            ) as mock_get_sessions:
                mock_get_sessions.return_value = ["session1"]

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
                    "push_tmux.commands.auto_delete.AsyncPushbullet"
                ) as mock_async_pb:
                    mock_async_pb.return_value.__aenter__.return_value = mock_pb

                    result = runner.invoke(auto_delete, ["--dry-run"])

                    assert result.exit_code == 0
                    assert "[DRY RUN]" in result.output
                    assert "orphan" in result.output
                    # Verify no devices were deleted
                    assert not mock_pb._async_delete_data.called

    def test_auto_delete_deletes_orphaned_devices(self):
        """Test actual device deletion"""
        runner = CliRunner()

        with patch("push_tmux.commands.auto_delete.get_api_key") as mock_get_api_key:
            mock_get_api_key.return_value = "test-api-key"

            with patch(
                "push_tmux.commands.auto_delete.get_all_sessions",
                new_callable=AsyncMock,
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
                mock_pb._async_delete_data.return_value = None

                with patch(
                    "push_tmux.commands.auto_delete.AsyncPushbullet"
                ) as mock_async_pb:
                    mock_async_pb.return_value.__aenter__.return_value = mock_pb

                    result = runner.invoke(auto_delete)

                    assert result.exit_code == 0
                    assert "デバイス 'orphan1' を削除しました" in result.output
                    assert "デバイス 'orphan2' を削除しました" in result.output
                    assert "完了: 2件削除, 0件失敗" in result.output

                    # Verify _async_delete_data was called twice
                    assert mock_pb._async_delete_data.call_count == 2

    def test_auto_delete_partial_failure(self):
        """Test partial deletion failure"""
        runner = CliRunner()

        with patch("push_tmux.commands.auto_delete.get_api_key") as mock_get_api_key:
            mock_get_api_key.return_value = "test-api-key"

            with patch(
                "push_tmux.commands.auto_delete.get_all_sessions",
                new_callable=AsyncMock,
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
                # First succeeds, second fails
                mock_pb._async_delete_data.side_effect = [None, Exception("API error")]

                with patch(
                    "push_tmux.commands.auto_delete.AsyncPushbullet"
                ) as mock_async_pb:
                    mock_async_pb.return_value.__aenter__.return_value = mock_pb

                    result = runner.invoke(auto_delete)

                    assert result.exit_code == 0
                    assert "デバイス 'orphan1' を削除しました" in result.output
                    assert "デバイス 'orphan2' の削除に失敗しました" in result.output
                    assert "完了: 1件削除, 1件失敗" in result.output

    def test_auto_delete_only_push_tmux_devices(self):
        """Test that only push-tmux devices are deleted by default"""
        runner = CliRunner()

        with patch("push_tmux.commands.auto_delete.get_api_key") as mock_get_api_key:
            mock_get_api_key.return_value = "test-api-key"

            with patch(
                "push_tmux.commands.auto_delete.get_all_sessions",
                new_callable=AsyncMock,
            ) as mock_get_sessions:
                mock_get_sessions.return_value = []

                mock_pb = AsyncMock()
                mock_device1 = {
                    "nickname": "push-tmux-device",
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
                    "push_tmux.commands.auto_delete.AsyncPushbullet"
                ) as mock_async_pb:
                    mock_async_pb.return_value.__aenter__.return_value = mock_pb

                    result = runner.invoke(auto_delete, ["--dry-run"])

                    assert result.exit_code == 0
                    assert "push-tmux-device" in result.output
                    # other-device should not be in orphaned list
                    assert "孤立したデバイス (1件)" in result.output

    def test_auto_delete_all_devices(self):
        """Test --all flag includes non-push-tmux devices"""
        runner = CliRunner()

        with patch("push_tmux.commands.auto_delete.get_api_key") as mock_get_api_key:
            mock_get_api_key.return_value = "test-api-key"

            with patch(
                "push_tmux.commands.auto_delete.get_all_sessions",
                new_callable=AsyncMock,
            ) as mock_get_sessions:
                mock_get_sessions.return_value = []

                mock_pb = AsyncMock()
                mock_device1 = {
                    "nickname": "push-tmux-device",
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
                    "push_tmux.commands.auto_delete.AsyncPushbullet"
                ) as mock_async_pb:
                    mock_async_pb.return_value.__aenter__.return_value = mock_pb

                    result = runner.invoke(auto_delete, ["--all", "--dry-run"])

                    assert result.exit_code == 0
                    assert "全てのデバイス (2件)を対象にします" in result.output
                    assert "push-tmux-device" in result.output
                    assert "other-device" in result.output
                    assert "孤立したデバイス (2件)" in result.output

    def test_auto_delete_no_target_devices(self):
        """Test when there are no target devices"""
        runner = CliRunner()

        with patch("push_tmux.commands.auto_delete.get_api_key") as mock_get_api_key:
            mock_get_api_key.return_value = "test-api-key"

            with patch(
                "push_tmux.commands.auto_delete.get_all_sessions",
                new_callable=AsyncMock,
            ) as mock_get_sessions:
                mock_get_sessions.return_value = ["session1"]

                mock_pb = AsyncMock()
                # Only non-push-tmux devices
                mock_device1 = {
                    "nickname": "other-device",
                    "iden": "id1",
                    "manufacturer": "other",
                }
                mock_pb.get_devices = Mock(return_value=[mock_device1])

                with patch(
                    "push_tmux.commands.auto_delete.AsyncPushbullet"
                ) as mock_async_pb:
                    mock_async_pb.return_value.__aenter__.return_value = mock_pb

                    result = runner.invoke(auto_delete)

                    assert result.exit_code == 0
                    assert "対象デバイスがありません" in result.output
