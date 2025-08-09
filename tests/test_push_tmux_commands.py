#!/usr/bin/env python3
"""
push_tmux.pyのコマンドのテスト
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from click.testing import CliRunner
import os
import tempfile
import json

import sys

import push_tmux
from push_tmux import cli


class TestMainCLI:
    """メインCLIのテスト (from test_cli.py)"""
    
    def test_cli_help(self, runner):
        """ヘルプメッセージの表示"""
        result = runner.invoke(cli, ["--help"])
        
        assert result.exit_code == 0
        assert "Pushbulletのメッセージをtmuxに送信するCLIツール" in result.output
        assert "Commands:" in result.output
        assert "register" in result.output
        assert "list-devices" in result.output
        assert "listen" in result.output
    
    def test_command_help(self, runner):
        """個別コマンドのヘルプ"""
        commands = ["register", "list-devices", "listen"]
        
        for cmd in commands:
            result = runner.invoke(cli, [cmd, "--help"])
            assert result.exit_code == 0
            assert "Usage:" in result.output
            assert cmd in result.output


class TestRegisterCommand:
    """registerコマンドのテスト"""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_register_no_api_key(self, runner):
        """APIキーがない場合のテスト"""
        with patch.dict(os.environ, {}, clear=True):
            result = runner.invoke(cli, ['register'])
            assert result.exit_code == 0
            assert "PUSHBULLET_TOKEN環境変数が設定されていません" in result.output
    
    def test_register_new_device(self, runner):
        """新規デバイス登録のテスト"""
        with patch.dict(os.environ, {'PUSHBULLET_TOKEN': 'test_token'}):
            with patch('push_tmux.commands.register.AsyncPushbullet') as MockPB:
                mock_pb = AsyncMock()
                mock_pb.get_devices = AsyncMock(return_value=[])
                mock_pb.create_device = AsyncMock(return_value={
                    'iden': 'new_device_id',
                    'nickname': 'test_device'
                })
                mock_pb.__aenter__ = AsyncMock(return_value=mock_pb)
                mock_pb.__aexit__ = AsyncMock()
                MockPB.return_value = mock_pb
                
                result = runner.invoke(cli, ['register', '--name', 'test_device'])
                assert result.exit_code == 0
                assert "デバイス 'test_device' を登録しました" in result.output
                assert "new_device_id" in result.output
    
    def test_register_existing_device(self, runner):
        """既存デバイスの場合のテスト"""
        with patch.dict(os.environ, {'PUSHBULLET_TOKEN': 'test_token'}):
            with patch('push_tmux.commands.register.AsyncPushbullet') as MockPB:
                existing_device = {
                    'iden': 'existing_id',
                    'nickname': 'test_device',
                    'created': 1234567890,
                    'modified': 1234567891
                }
                mock_pb = AsyncMock()
                mock_pb.get_devices = AsyncMock(return_value=[existing_device])
                mock_pb.__aenter__ = AsyncMock(return_value=mock_pb)
                mock_pb.__aexit__ = AsyncMock()
                MockPB.return_value = mock_pb
                
                result = runner.invoke(cli, ['register', '--name', 'test_device'])
                assert result.exit_code == 0
                assert "デバイス 'test_device' は既に登録されています" in result.output
                assert "existing_id" in result.output


class TestListDevicesCommand:
    """list-devicesコマンドのテスト"""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_list_devices_no_api_key(self, runner):
        """APIキーがない場合のテスト"""
        with patch.dict(os.environ, {}, clear=True):
            result = runner.invoke(cli, ['list-devices'])
            assert result.exit_code == 0
            assert "PUSHBULLET_TOKEN環境変数が設定されていません" in result.output
    
    def test_list_devices_empty(self, runner):
        """デバイスがない場合のテスト"""
        with patch.dict(os.environ, {'PUSHBULLET_TOKEN': 'test_token'}):
            with patch('push_tmux.commands.list_devices.AsyncPushbullet') as MockPB:
                mock_pb = AsyncMock()
                mock_pb.get_devices = AsyncMock(return_value=[])
                mock_pb.__aenter__ = AsyncMock(return_value=mock_pb)
                mock_pb.__aexit__ = AsyncMock()
                MockPB.return_value = mock_pb
                
                result = runner.invoke(cli, ['list-devices'])
                assert result.exit_code == 0
                assert "登録されているデバイスがありません" in result.output
    
    def test_list_devices_with_devices(self, runner):
        """デバイスがある場合のテスト"""
        with patch.dict(os.environ, {'PUSHBULLET_TOKEN': 'test_token'}):
            with patch('push_tmux.commands.list_devices.AsyncPushbullet') as MockPB:
                devices = [
                    {
                        'iden': 'dev1',
                        'nickname': 'Device 1',
                        'active': True,
                        'created': 1234567890,
                        'modified': 1234567891,
                        'manufacturer': 'Apple',
                        'model': 'iPhone'
                    },
                    {
                        'iden': 'dev2',
                        'active': False,
                        'created': 1234567892,
                        'modified': 1234567893
                    }
                ]
                mock_pb = AsyncMock()
                mock_pb.get_devices = AsyncMock(return_value=devices)
                mock_pb.__aenter__ = AsyncMock(return_value=mock_pb)
                mock_pb.__aexit__ = AsyncMock()
                MockPB.return_value = mock_pb
                
                result = runner.invoke(cli, ['list-devices'])
                assert result.exit_code == 0
                assert "Device 1" in result.output
                assert "dev1" in result.output
                assert "N/A" in result.output  # nickname for dev2
                assert "登録されているデバイス (2件)" in result.output


class TestDeleteDevicesCommand:
    """delete-devicesコマンドのテスト"""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_delete_single_device_by_name(self, runner):
        """名前指定での単一デバイス削除のテスト"""
        with patch.dict(os.environ, {'PUSHBULLET_TOKEN': 'test_token'}):
            with patch('push_tmux.commands.delete_devices.AsyncPushbullet') as MockPB:
                devices = [
                    {'iden': 'dev1', 'nickname': 'Device 1'},
                    {'iden': 'dev2', 'nickname': 'Device 2'}
                ]
                mock_pb = AsyncMock()
                mock_pb.get_devices = AsyncMock(return_value=devices)
                mock_pb.delete_device = AsyncMock()
                mock_pb.__aenter__ = AsyncMock(return_value=mock_pb)
                mock_pb.__aexit__ = AsyncMock()
                MockPB.return_value = mock_pb
                
                result = runner.invoke(cli, ['delete-devices', '--name', 'Device 1', '--yes'])
                assert result.exit_code == 0
                assert "デバイス 'Device 1' (ID: dev1) を削除しました" in result.output
                mock_pb.delete_device.assert_called_once_with('dev1')
    
    def test_delete_single_device_by_id(self, runner):
        """ID指定での単一デバイス削除のテスト"""
        with patch.dict(os.environ, {'PUSHBULLET_TOKEN': 'test_token'}):
            with patch('push_tmux.commands.delete_devices.AsyncPushbullet') as MockPB:
                devices = [
                    {'iden': 'dev1', 'nickname': 'Device 1'},
                    {'iden': 'dev2', 'nickname': 'Device 2'}
                ]
                mock_pb = AsyncMock()
                mock_pb.get_devices = AsyncMock(return_value=devices)
                mock_pb.delete_device = AsyncMock()
                mock_pb.__aenter__ = AsyncMock(return_value=mock_pb)
                mock_pb.__aexit__ = AsyncMock()
                MockPB.return_value = mock_pb
                
                result = runner.invoke(cli, ['delete-devices', '--id', 'dev2', '--yes'])
                assert result.exit_code == 0
                assert "デバイス 'Device 2' (ID: dev2) を削除しました" in result.output
                mock_pb.delete_device.assert_called_once_with('dev2')
    
    def test_delete_device_not_found(self, runner):
        """存在しないデバイスの削除テスト"""
        with patch.dict(os.environ, {'PUSHBULLET_TOKEN': 'test_token'}):
            with patch('push_tmux.commands.delete_devices.AsyncPushbullet') as MockPB:
                mock_pb = AsyncMock()
                mock_pb.get_devices = AsyncMock(return_value=[])
                mock_pb.__aenter__ = AsyncMock(return_value=mock_pb)
                mock_pb.__aexit__ = AsyncMock()
                MockPB.return_value = mock_pb
                
                result = runner.invoke(cli, ['delete-devices', '--name', 'NonExistent'])
                assert result.exit_code == 0
                assert "エラー: 名前 'NonExistent' のデバイスが見つかりません" in result.output



class TestListenCommand:
    """listenコマンドのテスト"""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_listen_no_api_key(self, runner):
        """APIキーがない場合のテスト"""
        with patch.dict(os.environ, {}, clear=True):
            result = runner.invoke(cli, ['listen'])
            assert result.exit_code == 0
            assert "PUSHBULLET_TOKEN環境変数が設定されていません" in result.output
    
    def test_listen_device_not_found(self, runner):
        """指定デバイスが見つからない場合のテスト"""
        with patch.dict(os.environ, {'PUSHBULLET_TOKEN': 'test_token'}):
            with patch('push_tmux.device.AsyncPushbullet') as MockPB:
                mock_pb = AsyncMock()
                mock_pb.get_devices = AsyncMock(return_value=[])
                mock_pb.__aenter__ = AsyncMock(return_value=mock_pb)
                mock_pb.__aexit__ = AsyncMock()
                MockPB.return_value = mock_pb
                
                result = runner.invoke(cli, ['listen', '--device', 'NonExistent'])
                assert result.exit_code == 0
                assert "エラー: デバイス 'NonExistent' が見つかりません" in result.output
    
    def test_listen_default_device_not_registered(self, runner):
        """デフォルトデバイスが登録されていない場合のテスト"""
        with patch.dict(os.environ, {'PUSHBULLET_TOKEN': 'test_token', 'DEVICE_NAME': 'test_device'}):
            with patch('push_tmux.device.AsyncPushbullet') as MockPB:
                mock_pb = AsyncMock()
                mock_pb.get_devices = AsyncMock(return_value=[])
                mock_pb.__aenter__ = AsyncMock(return_value=mock_pb)
                mock_pb.__aexit__ = AsyncMock()
                MockPB.return_value = mock_pb
                
                result = runner.invoke(cli, ['listen'])
                assert result.exit_code == 0
                assert "エラー: デバイス 'test_device' が見つかりません" in result.output
                assert "最初に `push-tmux register` でデバイスを登録してください" in result.output