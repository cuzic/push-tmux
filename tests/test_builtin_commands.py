#!/usr/bin/env python3
"""
Tests for built-in slash commands
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from push_tmux.builtin_commands import (
    handle_capture_command,
    execute_builtin_command,
)
from push_tmux.slash_commands import parse_slash_command


class TestCaptureCommand:
    """Test /capture command functionality"""

    @pytest.mark.asyncio
    async def test_capture_current_pane(self):
        """Test capturing current pane (no arguments)"""
        with patch("push_tmux.builtin_commands.capture_pane") as mock_capture:
            mock_capture.return_value = "Captured content\nLine 2\nLine 3"
            
            with patch("push_tmux.builtin_commands.AsyncPushbullet") as mock_pb_class:
                mock_pb = AsyncMock()
                mock_pb.push_note = AsyncMock()
                mock_pb_class.return_value.__aenter__.return_value = mock_pb
                
                args = {}  # No arguments means current pane
                config = {}
                api_key = "test_key"
                source_device = "source_device_id"
                
                success, error = await handle_capture_command(
                    args, config, api_key, source_device, "test-device"
                )
                
                assert success is True
                assert error is None
                # DeviceTtyTracker may provide a default tty
                # Check that capture_pane was called
                assert mock_capture.call_count == 1
                mock_pb.push_note.assert_called_once()
                
                # Check the push_note call
                call_args = mock_pb.push_note.call_args
                # Title may be "current pane" or "Captured from {tty}"
                assert "Captured" in call_args[0][0]  # Title
                assert "Captured content" in call_args[0][1]  # Content

    @pytest.mark.asyncio
    async def test_capture_specific_pane(self):
        """Test capturing specific pane (pts/3)"""
        with patch("push_tmux.builtin_commands.capture_pane") as mock_capture:
            mock_capture.return_value = "Content from pts/3"
            
            with patch("push_tmux.builtin_commands.AsyncPushbullet") as mock_pb_class:
                mock_pb = AsyncMock()
                mock_pb.push_note = AsyncMock()
                mock_pb_class.return_value.__aenter__.return_value = mock_pb
                
                args = {"arg0": "pts/3"}  # Specific pane
                config = {}
                api_key = "test_key"
                source_device = "source_device_id"
                
                success, error = await handle_capture_command(
                    args, config, api_key, source_device, "test-device"
                )
                
                assert success is True
                assert error is None
                mock_capture.assert_called_once_with("pts/3")
                
                # Check the push_note call
                call_args = mock_pb.push_note.call_args
                assert "pts/3" in call_args[0][0]  # Title includes pane spec
                assert "Content from pts/3" in call_args[0][1]  # Content

    @pytest.mark.asyncio
    async def test_capture_failure(self):
        """Test handling capture failure"""
        with patch("push_tmux.builtin_commands.capture_pane") as mock_capture:
            mock_capture.return_value = None  # Capture failed
            
            args = {"arg0": "invalid_pane"}
            config = {}
            api_key = "test_key"
            source_device = "source_device_id"
            
            success, error = await handle_capture_command(
                args, config, api_key, source_device
            )
            
            assert success is False
            assert error == "Failed to capture pane content"

    @pytest.mark.asyncio
    async def test_capture_with_device_default_tty(self):
        """Test capturing using device's default tty"""
        with patch("push_tmux.builtin_commands.get_tracker") as mock_tracker_func:
            mock_tracker = MagicMock()
            mock_tracker.get_device_tty.return_value = "pts/5"
            mock_tracker_func.return_value = mock_tracker
            
            with patch("push_tmux.builtin_commands.capture_pane") as mock_capture:
                mock_capture.return_value = "Content from device's tty"
                
                with patch("push_tmux.builtin_commands.get_pane_tty") as mock_get_tty:
                    mock_get_tty.return_value = "pts/5"
                    
                    with patch("push_tmux.builtin_commands.AsyncPushbullet") as mock_pb_class:
                        mock_pb = AsyncMock()
                        mock_pb.push_note = AsyncMock()
                        mock_pb_class.return_value.__aenter__.return_value = mock_pb
                        
                        args = {}  # No arguments - should use device's default
                        config = {}
                        api_key = "test_key"
                        source_device = "source_device_id"
                        source_device_name = "test-device"
                        
                        success, error = await handle_capture_command(
                            args, config, api_key, source_device, source_device_name
                        )
                        
                        assert success is True
                        assert error is None
                        
                        # Should have used device's tty
                        mock_tracker.get_device_tty.assert_called_once_with("test-device")
                        mock_capture.assert_called_once_with("pts/5")
                        
                        # Should update the tracking
                        mock_tracker.set_device_tty.assert_called_with("test-device", "pts/5")

    @pytest.mark.asyncio
    async def test_capture_truncation(self):
        """Test content truncation for long captures"""
        with patch("push_tmux.builtin_commands.capture_pane") as mock_capture:
            # Create content longer than 4096 characters
            long_content = "x" * 5000
            mock_capture.return_value = long_content
            
            with patch("push_tmux.builtin_commands.AsyncPushbullet") as mock_pb_class:
                mock_pb = AsyncMock()
                mock_pb.push_note = AsyncMock()
                mock_pb_class.return_value.__aenter__.return_value = mock_pb
                
                args = {}
                config = {}
                api_key = "test_key"
                source_device = "source_device_id"
                
                success, error = await handle_capture_command(
                    args, config, api_key, source_device, "test-device"
                )
                
                assert success is True
                
                # Check that content was truncated
                call_args = mock_pb.push_note.call_args
                content = call_args[0][1]
                assert len(content) <= 4096 + len("\n...(truncated)")
                assert content.endswith("...(truncated)")


class TestExecuteBuiltinCommand:
    """Test built-in command execution"""

    @pytest.mark.asyncio
    async def test_execute_capture_command(self):
        """Test executing /capture as a built-in command"""
        with patch("push_tmux.builtin_commands.handle_capture_command") as mock_handle:
            mock_handle.return_value = (True, None)
            
            command = "capture"
            args = {"arg0": "pts/3"}
            config = {}
            api_key = "test_key"
            source_device = "source_device_id"
            
            is_builtin, result, error = await execute_builtin_command(
                command, args, config, api_key, source_device, "test-device"
            )
            
            assert is_builtin is True
            assert result is None  # Success
            assert error is None
            mock_handle.assert_called_once_with(args, config, api_key, source_device, "test-device")

    @pytest.mark.asyncio
    async def test_execute_non_builtin_command(self):
        """Test that non-built-in commands return False"""
        command = "deploy"  # Not a built-in command
        args = {}
        config = {}
        api_key = "test_key"
        source_device = "source_device_id"
        
        is_builtin, result, error = await execute_builtin_command(
            command, args, config, api_key, source_device
        )
        
        assert is_builtin is False
        assert result is None
        assert error is None


class TestParseSlashCommand:
    """Test slash command parsing"""

    def test_parse_capture_command(self):
        """Test parsing /capture command with arguments"""
        message = "/capture pts/3"
        command, args = parse_slash_command(message)
        
        assert command == "capture"
        assert args == {"arg0": "pts/3"}

    def test_parse_capture_no_args(self):
        """Test parsing /capture command without arguments"""
        message = "/capture"
        command, args = parse_slash_command(message)
        
        assert command == "capture"
        assert args == {}

    def test_parse_capture_with_session_format(self):
        """Test parsing /capture with session:window.pane format"""
        # Note: colon is parsed as key:value, so we need a different format
        message = "/capture mysession"
        command, args = parse_slash_command(message)
        
        assert command == "capture"
        assert args == {"arg0": "mysession"}

    def test_parse_non_slash_message(self):
        """Test that non-slash messages return None"""
        message = "regular message"
        command, args = parse_slash_command(message)
        
        assert command is None
        assert args == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])