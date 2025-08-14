#!/usr/bin/env python3
"""
push_tmux.pyのコマンドのテスト
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from click.testing import CliRunner
import os


from push_tmux import cli


class TestMainCLI:
    """メインCLIのテスト (from test_cli.py)"""

    def test_cli_help(self, runner):
        """ヘルプメッセージの表示"""
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "Pushbulletのメッセージをtmuxに送信するCLIツール" in result.output
        assert "Commands:" in result.output
        assert "device" in result.output
        assert "start" in result.output
        assert "send" in result.output

    def test_command_help(self, runner):
        """個別コマンドのヘルプ"""
        commands = ["device", "start", "send"]

        for cmd in commands:
            result = runner.invoke(cli, [cmd, "--help"])
            assert result.exit_code == 0
            assert "Usage:" in result.output


class TestDeviceCommands:
    """device サブコマンドのテスト"""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_register_no_api_key(self, runner):
        """APIキーがない場合のテスト"""
        with patch.dict(os.environ, {}, clear=True):
            result = runner.invoke(cli, ["device", "register"])
            assert result.exit_code == 0
            assert "PUSHBULLET_TOKEN環境変数が設定されていません" in result.output

    def test_register_new_device(self, runner):
        """新規デバイス登録のテスト"""
        with patch.dict(os.environ, {"PUSHBULLET_TOKEN": "test_token"}):
            with patch("push_tmux.commands.register.AsyncPushbullet") as MockPB:
                mock_pb = AsyncMock()
                mock_pb.get_devices = MagicMock(return_value=[])  # 同期メソッド
                mock_pb.async_new_device = AsyncMock(
                    return_value={"iden": "new_device_id", "nickname": "test_device"}
                )
                mock_pb.__aenter__ = AsyncMock(return_value=mock_pb)
                mock_pb.__aexit__ = AsyncMock()
                MockPB.return_value = mock_pb

                result = runner.invoke(
                    cli, ["device", "register", "--name", "test_device"]
                )
                assert result.exit_code == 0
                assert "デバイス 'test_device' を登録しました" in result.output
                assert "new_device_id" in result.output

    def test_register_existing_device(self, runner):
        """既存デバイスの場合のテスト"""
        with patch.dict(os.environ, {"PUSHBULLET_TOKEN": "test_token"}):
            with patch("push_tmux.commands.register.AsyncPushbullet") as MockPB:
                existing_device = {
                    "iden": "existing_id",
                    "nickname": "test_device",
                    "created": 1234567890,
                    "modified": 1234567891,
                }
                mock_pb = AsyncMock()
                mock_pb.get_devices = MagicMock(
                    return_value=[existing_device]
                )  # 同期メソッド
                mock_pb.__aenter__ = AsyncMock(return_value=mock_pb)
                mock_pb.__aexit__ = AsyncMock()
                MockPB.return_value = mock_pb

                result = runner.invoke(
                    cli, ["device", "register", "--name", "test_device"]
                )
                assert result.exit_code == 0
                assert "デバイス 'test_device' は既に登録されています" in result.output
                assert "existing_id" in result.output


class TestDeviceListCommand:
    """device list コマンドのテスト"""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_list_devices_no_api_key(self, runner):
        """APIキーがない場合のテスト"""
        with patch.dict(os.environ, {}, clear=True):
            result = runner.invoke(cli, ["device", "list"])
            assert result.exit_code == 0
            assert "PUSHBULLET_TOKEN環境変数が設定されていません" in result.output

    def test_list_devices_empty(self, runner):
        """デバイスがない場合のテスト"""
        with patch.dict(os.environ, {"PUSHBULLET_TOKEN": "test_token"}):
            with patch("push_tmux.commands.list_devices.AsyncPushbullet") as MockPB:
                mock_pb = AsyncMock()
                mock_pb.get_devices = MagicMock(return_value=[])  # 同期メソッド
                mock_pb.__aenter__ = AsyncMock(return_value=mock_pb)
                mock_pb.__aexit__ = AsyncMock()
                MockPB.return_value = mock_pb

                result = runner.invoke(cli, ["device", "list"])
                assert result.exit_code == 0
                assert "登録されているデバイスがありません" in result.output

    def test_list_devices_with_devices(self, runner):
        """デバイスがある場合のテスト"""
        with patch.dict(os.environ, {"PUSHBULLET_TOKEN": "test_token"}):
            with patch("push_tmux.commands.list_devices.AsyncPushbullet") as MockPB:
                devices = [
                    {
                        "iden": "dev1",
                        "nickname": "Device 1",
                        "active": True,
                        "created": 1234567890,
                        "modified": 1234567891,
                        "manufacturer": "Apple",
                        "model": "iPhone",
                    },
                    {
                        "iden": "dev2",
                        "active": False,
                        "created": 1234567892,
                        "modified": 1234567893,
                    },
                ]
                mock_pb = AsyncMock()
                mock_pb.get_devices = MagicMock(return_value=devices)  # 同期メソッド
                mock_pb.__aenter__ = AsyncMock(return_value=mock_pb)
                mock_pb.__aexit__ = AsyncMock()
                MockPB.return_value = mock_pb

                result = runner.invoke(cli, ["device", "list"])
                assert result.exit_code == 0
                assert "Device 1" in result.output
                assert "dev1" in result.output
                assert "N/A" in result.output  # nickname for dev2
                assert "登録されているデバイス (2件)" in result.output


class TestDeviceDeleteCommand:
    """device delete コマンドのテスト"""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_delete_single_device_by_name(self, runner):
        """名前指定での単一デバイス削除のテスト"""
        with patch.dict(os.environ, {"PUSHBULLET_TOKEN": "test_token"}):
            with patch("push_tmux.commands.delete_devices.AsyncPushbullet") as MockPB:
                devices = [
                    {"iden": "dev1", "nickname": "Device 1"},
                    {"iden": "dev2", "nickname": "Device 2"},
                ]
                mock_pb = AsyncMock()
                mock_pb.get_devices = MagicMock(return_value=devices)  # 同期メソッド
                mock_pb.async_remove_device = AsyncMock()
                mock_pb.__aenter__ = AsyncMock(return_value=mock_pb)
                mock_pb.__aexit__ = AsyncMock()
                MockPB.return_value = mock_pb

                result = runner.invoke(
                    cli, ["device", "delete", "--name", "Device 1", "--yes"]
                )
                assert result.exit_code == 0
                assert "デバイス 'Device 1' (ID: dev1) を削除しました" in result.output
                mock_pb.async_remove_device.assert_called_once()

    def test_delete_single_device_by_id(self, runner):
        """ID指定での単一デバイス削除のテスト"""
        with patch.dict(os.environ, {"PUSHBULLET_TOKEN": "test_token"}):
            with patch("push_tmux.commands.delete_devices.AsyncPushbullet") as MockPB:
                devices = [
                    {"iden": "dev1", "nickname": "Device 1"},
                    {"iden": "dev2", "nickname": "Device 2"},
                ]
                mock_pb = AsyncMock()
                mock_pb.get_devices = MagicMock(return_value=devices)  # 同期メソッド
                mock_pb.async_remove_device = AsyncMock()
                mock_pb.__aenter__ = AsyncMock(return_value=mock_pb)
                mock_pb.__aexit__ = AsyncMock()
                MockPB.return_value = mock_pb

                result = runner.invoke(
                    cli, ["device", "delete", "--id", "dev2", "--yes"]
                )
                assert result.exit_code == 0
                assert "デバイス 'Device 2' (ID: dev2) を削除しました" in result.output
                mock_pb.async_remove_device.assert_called_once()

    def test_delete_device_not_found(self, runner):
        """存在しないデバイスの削除テスト"""
        with patch.dict(os.environ, {"PUSHBULLET_TOKEN": "test_token"}):
            with patch("push_tmux.commands.delete_devices.AsyncPushbullet") as MockPB:
                mock_pb = AsyncMock()
                mock_pb.get_devices = MagicMock(return_value=[])  # 同期メソッド
                mock_pb.__aenter__ = AsyncMock(return_value=mock_pb)
                mock_pb.__aexit__ = AsyncMock()
                MockPB.return_value = mock_pb

                result = runner.invoke(
                    cli, ["device", "delete", "--name", "NonExistent"]
                )
                assert result.exit_code == 0
                assert (
                    "エラー: 名前 'NonExistent' のデバイスが見つかりません"
                    in result.output
                )


class TestStartCommand:
    """start コマンドのテスト"""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_listen_no_api_key(self, runner):
        """APIキーがない場合のテスト"""
        with patch.dict(os.environ, {}, clear=True):
            result = runner.invoke(cli, ["start", "--once"])
            assert result.exit_code == 0
            assert "PUSHBULLET_TOKEN環境変数が設定されていません" in result.output

    def test_listen_device_not_found(self, runner):
        """指定デバイスが見つからない場合のテスト"""
        with patch.dict(os.environ, {"PUSHBULLET_TOKEN": "test_token"}):
            with patch("push_tmux.device.AsyncPushbullet") as MockPB:
                mock_pb = AsyncMock()
                mock_pb.get_devices = MagicMock(return_value=[])  # 同期メソッド
                mock_pb.__aenter__ = AsyncMock(return_value=mock_pb)
                mock_pb.__aexit__ = AsyncMock()
                MockPB.return_value = mock_pb

                result = runner.invoke(
                    cli, ["start", "--once", "--device", "NonExistent"]
                )
                assert result.exit_code == 0
                assert (
                    "エラー: デバイス 'NonExistent' が見つかりません" in result.output
                )

    def test_listen_default_device_not_registered(self, runner):
        """デフォルトデバイスが登録されていない場合のテスト"""
        with patch.dict(
            os.environ, {"PUSHBULLET_TOKEN": "test_token", "DEVICE_NAME": "test_device"}
        ):
            with (
                patch("push_tmux.device.AsyncPushbullet") as MockPB1,
                patch("push_tmux.commands.listen.AsyncPushbullet") as MockPB2,
            ):
                mock_pb = AsyncMock()
                mock_pb.get_devices = MagicMock(return_value=[])  # 同期メソッド
                mock_pb.__aenter__ = AsyncMock(return_value=mock_pb)
                mock_pb.__aexit__ = AsyncMock()
                MockPB1.return_value = mock_pb
                MockPB2.return_value = mock_pb

                result = runner.invoke(cli, ["start", "--once", "--no-auto-route"])
                assert result.exit_code == 0
                assert (
                    "エラー: デバイス 'test_device' が見つかりません" in result.output
                )
