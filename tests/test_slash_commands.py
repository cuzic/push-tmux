#!/usr/bin/env python3
"""
Tests for slash command functionality
"""
import pytest
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from push_tmux.slash_commands import (
    SlashCommandParser,
    expand_slash_command,
    check_trigger_conditions,
    TriggerConditions
)


class TestSlashCommandParser:
    """Test SlashCommandParser class"""
    
    def test_parse_simple_command(self):
        """Test parsing a simple slash command"""
        parser = SlashCommandParser({})
        command, args = parser.parse_message("/deploy")
        assert command == "deploy"
        assert args == {}
    
    def test_parse_command_with_colon_args(self):
        """Test parsing command with colon-separated arguments"""
        parser = SlashCommandParser({})
        command, args = parser.parse_message("/deploy branch:feature env:staging")
        assert command == "deploy"
        assert args == {"branch": "feature", "env": "staging"}
    
    def test_parse_command_with_equal_args(self):
        """Test parsing command with equal-separated arguments"""
        parser = SlashCommandParser({})
        command, args = parser.parse_message("/build target=web env=production")
        assert command == "build"
        assert args == {"target": "web", "env": "production"}
    
    def test_parse_command_with_mixed_args(self):
        """Test parsing command with mixed argument formats"""
        parser = SlashCommandParser({})
        command, args = parser.parse_message("/test path:tests/unit verbose options=--coverage")
        assert command == "test"
        assert args == {"path": "tests/unit", "options": "--coverage", "arg0": "verbose"}
    
    def test_parse_non_slash_command(self):
        """Test that non-slash commands return None"""
        parser = SlashCommandParser({})
        command, args = parser.parse_message("regular message")
        assert command is None
        assert args == {}
    
    def test_execute_command_with_template(self):
        """Test executing a command with template expansion"""
        config = {
            "slash_commands": {
                "deploy": {
                    "template": "git checkout {branch} && deploy {env}",
                    "defaults": {"branch": "main", "env": "production"}
                }
            }
        }
        parser = SlashCommandParser(config)
        
        # With custom arguments
        result = parser.execute_command("deploy", {"branch": "feature", "env": "staging"})
        assert result == "git checkout feature && deploy staging"
        
        # With defaults
        result = parser.execute_command("deploy", {})
        assert result == "git checkout main && deploy production"
    
    def test_execute_unknown_command(self):
        """Test executing an unknown command returns None"""
        parser = SlashCommandParser({})
        result = parser.execute_command("unknown", {})
        assert result is None
    
    def test_should_execute_with_device_restrictions(self):
        """Test device restriction checking"""
        config = {
            "slash_commands": {
                "restart": {
                    "template": "systemctl restart nginx",
                    "allowed_devices": ["server", "production"]
                }
            }
        }
        parser = SlashCommandParser(config)
        
        # Allowed device
        assert parser.should_execute("restart", "server") is True
        
        # Not allowed device
        assert parser.should_execute("restart", "laptop") is False
        
        # Unknown command
        assert parser.should_execute("unknown", "server") is False
    
    def test_should_execute_disabled_command(self):
        """Test disabled command checking"""
        config = {
            "slash_commands": {
                "dangerous": {
                    "template": "rm -rf /",
                    "disabled": True
                }
            }
        }
        parser = SlashCommandParser(config)
        assert parser.should_execute("dangerous", "any") is False
    
    def test_get_target_session(self):
        """Test getting target session for command"""
        config = {
            "slash_commands": {
                "monitor": {
                    "template": "htop",
                    "target_session": "monitoring"
                }
            }
        }
        parser = SlashCommandParser(config)
        
        # From config
        session = parser.get_target_session("monitor", {})
        assert session == "monitoring"
        
        # Override from arguments
        session = parser.get_target_session("monitor", {"session": "custom"})
        assert session == "custom"
        
        # Unknown command
        session = parser.get_target_session("unknown", {})
        assert session is None


class TestExpandSlashCommand:
    """Test expand_slash_command function"""
    
    @patch('push_tmux.slash_commands.click')
    def test_expand_valid_command(self, mock_click):
        """Test expanding a valid slash command"""
        config = {
            "slash_commands": {
                "build": {
                    "template": "npm build {env}",
                    "defaults": {"env": "dev"}
                }
            }
        }
        
        is_slash, expanded, session = expand_slash_command("/build env:prod", config, "laptop")
        assert is_slash is True
        assert expanded == "npm build prod"
        assert session is None
    
    @patch('push_tmux.slash_commands.click')
    def test_expand_non_slash_command(self, mock_click):
        """Test that regular messages are not processed"""
        config = {}
        is_slash, expanded, session = expand_slash_command("regular message", config, "laptop")
        assert is_slash is False
        assert expanded is None
        assert session is None
    
    @patch('push_tmux.slash_commands.click')
    def test_expand_restricted_command(self, mock_click):
        """Test command restricted by device"""
        config = {
            "slash_commands": {
                "restart": {
                    "template": "sudo reboot",
                    "allowed_devices": ["server"]
                }
            }
        }
        
        is_slash, expanded, session = expand_slash_command("/restart", config, "laptop")
        assert is_slash is True
        assert expanded is None  # Not executed due to restriction
        assert session is None
        mock_click.echo.assert_called_with("Command '/restart' not allowed for device 'laptop'")
    
    @patch('push_tmux.slash_commands.click')
    def test_expand_with_target_session(self, mock_click):
        """Test command with target session"""
        config = {
            "slash_commands": {
                "log": {
                    "template": "tail -f /var/log/app.log",
                    "target_session": "monitoring"
                }
            }
        }
        
        is_slash, expanded, session = expand_slash_command("/log", config, "server")
        assert is_slash is True
        assert expanded == "tail -f /var/log/app.log"
        assert session == "monitoring"


class TestTriggerConditions:
    """Test TriggerConditions class"""
    
    def test_once_condition(self):
        """Test execute_once condition"""
        conditions = TriggerConditions()
        
        # First execution should be allowed
        assert conditions.check_once_condition("test_cmd") is True
        
        # Second execution should be blocked
        assert conditions.check_once_condition("test_cmd") is False
        
        # Different command should be allowed
        assert conditions.check_once_condition("other_cmd") is True
        
        # Reset and check again
        conditions.reset_once_condition("test_cmd")
        assert conditions.check_once_condition("test_cmd") is True


class TestCheckTriggerConditions:
    """Test check_trigger_conditions function"""
    
    def test_no_conditions(self):
        """Test command with no conditions"""
        config = {
            "slash_commands": {
                "simple": {
                    "template": "echo hello"
                }
            }
        }
        assert check_trigger_conditions("simple", config) is True
    
    def test_execute_once_condition(self):
        """Test execute_once condition"""
        from push_tmux.slash_commands import _trigger_conditions
        _trigger_conditions.executed_once.clear()
        
        config = {
            "slash_commands": {
                "backup": {
                    "template": "backup.sh",
                    "execute_once": True
                }
            }
        }
        
        # First check should pass
        assert check_trigger_conditions("backup", config) is True
        
        # Second check should fail
        assert check_trigger_conditions("backup", config) is False
        
        # Clean up
        _trigger_conditions.executed_once.clear()


class TestIntegration:
    """Integration tests for slash commands"""
    
    @patch('push_tmux.slash_commands.click')
    def test_full_command_flow(self, mock_click):
        """Test complete command processing flow"""
        config = {
            "slash_commands": {
                "deploy": {
                    "template": "cd {path} && git pull && docker-compose up -d {service}",
                    "defaults": {"path": "/app", "service": "web"},
                    "allowed_devices": ["server", "staging"],
                    "target_session": "deploy"
                }
            }
        }
        
        # Valid command from allowed device
        is_slash, expanded, session = expand_slash_command(
            "/deploy path:/myapp service:api",
            config,
            "server"
        )
        assert is_slash is True
        assert expanded == "cd /myapp && git pull && docker-compose up -d api"
        assert session == "deploy"
        
        # Same command from restricted device
        is_slash, expanded, session = expand_slash_command(
            "/deploy",
            config,
            "laptop"
        )
        assert is_slash is True
        assert expanded is None
        assert session is None
    
    def test_complex_argument_parsing(self):
        """Test complex argument parsing scenarios"""
        parser = SlashCommandParser({})
        
        # Multiple formats in one command
        command, args = parser.parse_message(
            "/ssh user:admin host=192.168.1.1 verbose port:2222"
        )
        assert command == "ssh"
        assert args == {
            "user": "admin",
            "host": "192.168.1.1",
            "port": "2222",
            "arg0": "verbose"
        }
        
        # Empty command
        command, args = parser.parse_message("/")
        assert command == ""
        assert args == {}
        
        # Command with special characters in values
        command, args = parser.parse_message(
            "/notify message:Hello_World subject=Test-123"
        )
        assert command == "notify"
        assert args == {
            "message": "Hello_World",
            "subject": "Test-123"
        }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])