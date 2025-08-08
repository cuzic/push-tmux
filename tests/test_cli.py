import os
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from click.testing import CliRunner

from push_tmux import cli


class TestMainCLI:
    """メインCLIのテスト"""
    
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