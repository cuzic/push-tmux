#!/usr/bin/env python3
"""
Tests for slash command fallback functionality
"""
import pytest
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from push_tmux.slash_commands import expand_slash_command


class TestSlashCommandFallback:
    """Test slash command fallback behavior"""
    
    def test_undefined_command_with_fallback_enabled(self):
        """未定義コマンドがfallback有効時に通常メッセージとして処理される"""
        config = {
            'slash_commands_settings': {
                'fallback_undefined': True
            },
            'slash_commands': {
                'deploy': {'template': 'echo deploy'}
            }
        }
        
        # 未定義のコマンド /login をテスト
        is_slash, expanded, session = expand_slash_command("/login", config, "test-device")
        
        # fallback有効時は通常メッセージとして扱われる
        assert is_slash == False
        assert expanded is None
        assert session is None
    
    def test_undefined_command_with_fallback_disabled(self):
        """未定義コマンドがfallback無効時に無視される"""
        config = {
            'slash_commands_settings': {
                'fallback_undefined': False
            },
            'slash_commands': {
                'deploy': {'template': 'echo deploy'}
            }
        }
        
        # 未定義のコマンド /login をテスト
        with patch('click.echo') as mock_echo:
            is_slash, expanded, session = expand_slash_command("/login", config, "test-device")
        
        # fallback無効時はスラッシュコマンドとして扱われるが実行されない
        assert is_slash == True
        assert expanded is None
        assert session is None
        mock_echo.assert_called_with("Unknown command: /login")
    
    def test_undefined_command_with_no_settings(self):
        """設定がない場合のデフォルト動作（fallback有効）"""
        config = {
            'slash_commands': {
                'deploy': {'template': 'echo deploy'}
            }
        }
        
        # 未定義のコマンド /login をテスト
        is_slash, expanded, session = expand_slash_command("/login", config, "test-device")
        
        # デフォルトではfallbackが有効
        assert is_slash == False
        assert expanded is None
        assert session is None
    
    def test_defined_command_always_works(self):
        """定義済みコマンドは設定に関わらず動作する"""
        # fallback有効時
        config_enabled = {
            'slash_commands_settings': {
                'fallback_undefined': True
            },
            'slash_commands': {
                'deploy': {'template': 'echo deploy'}
            }
        }
        
        is_slash, expanded, session = expand_slash_command("/deploy", config_enabled, "test-device")
        assert is_slash == True
        assert expanded == "echo deploy"
        
        # fallback無効時
        config_disabled = {
            'slash_commands_settings': {
                'fallback_undefined': False
            },
            'slash_commands': {
                'deploy': {'template': 'echo deploy'}
            }
        }
        
        is_slash, expanded, session = expand_slash_command("/deploy", config_disabled, "test-device")
        assert is_slash == True
        assert expanded == "echo deploy"
    
    def test_non_slash_message_always_normal(self):
        """スラッシュで始まらないメッセージは常に通常メッセージ"""
        config = {
            'slash_commands_settings': {
                'fallback_undefined': True
            },
            'slash_commands': {}
        }
        
        is_slash, expanded, session = expand_slash_command("hello world", config, "test-device")
        
        assert is_slash == False
        assert expanded is None
        assert session is None
    
    def test_edge_cases(self):
        """エッジケースのテスト"""
        config = {
            'slash_commands_settings': {
                'fallback_undefined': True
            },
            'slash_commands': {}
        }
        
        # 空のスラッシュ
        is_slash, expanded, session = expand_slash_command("/", config, "test-device")
        assert is_slash == False
        
        # スラッシュの後にスペース
        is_slash, expanded, session = expand_slash_command("/ login", config, "test-device")
        assert is_slash == False
        
        # 特殊文字を含むコマンド
        is_slash, expanded, session = expand_slash_command("/@mention", config, "test-device")
        assert is_slash == False
        
        is_slash, expanded, session = expand_slash_command("/#hashtag", config, "test-device")
        assert is_slash == False
    
    def test_japanese_command(self):
        """日本語コマンドのテスト"""
        config = {
            'slash_commands_settings': {
                'fallback_undefined': True
            },
            'slash_commands': {}
        }
        
        is_slash, expanded, session = expand_slash_command("/日本語コマンド", config, "test-device")
        assert is_slash == False
    
    def test_command_with_arguments_fallback(self):
        """引数付き未定義コマンドのフォールバック"""
        config = {
            'slash_commands_settings': {
                'fallback_undefined': True
            },
            'slash_commands': {}
        }
        
        # 引数付きの未定義コマンド
        is_slash, expanded, session = expand_slash_command("/login user:admin pass:secret", config, "test-device")
        assert is_slash == False