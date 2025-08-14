#!/usr/bin/env python3
"""
Built-in slash commands for push-tmux
"""

import click
from typing import Dict, Any, Optional, Tuple
from asyncpushbullet import AsyncPushbullet
from .tmux import capture_pane, get_pane_tty
from .device_tty_tracker import get_tracker


async def handle_capture_command(
    args: Dict[str, str],
    config: Dict[str, Any],
    api_key: str,
    source_device_iden: str,
    source_device_name: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Handle /capture command to capture tmux pane content
    
    Args:
        args: Command arguments
        config: Configuration
        api_key: Pushbullet API key
        source_device_iden: Device ID to send reply to
        source_device_name: Name of the source device
    
    Returns:
        (success, error_message)
    """
    # Get pane specification from arguments
    pane_spec = args.get("arg0")  # First positional argument (e.g., pts/3)
    
    # If no pane specified, try to use device's associated tty
    if not pane_spec and source_device_name:
        tracker = get_tracker()
        device_tty = tracker.get_device_tty(source_device_name)
        if device_tty:
            pane_spec = device_tty
            click.echo(f"Using device's associated tty: {device_tty}")
    
    # Capture the pane content
    content = await capture_pane(pane_spec)
    
    if content is None:
        return False, "Failed to capture pane content"
    
    # Send the captured content back to the source device
    try:
        async with AsyncPushbullet(api_key) as pb:
            # Truncate if too long (Pushbullet has limits)
            max_length = 4096
            if len(content) > max_length:
                content = content[:max_length] + "\n...(truncated)"
            
            # Get the actual tty for the title
            actual_tty = await get_pane_tty(pane_spec) if pane_spec else None
            
            # Send as a note with tty info in title
            if actual_tty:
                title = f"Captured from {pane_spec or 'current pane'} on {actual_tty}"
            else:
                title = f"Captured from {pane_spec or 'current pane'}"
            
            await pb.push_note(title, content, device_iden=source_device_iden)
            
            # Update device-tty mapping from the title for future use
            if source_device_name and actual_tty:
                tracker = get_tracker()
                tracker.set_device_tty(source_device_name, actual_tty)
            
            click.echo(f"📸 Captured and sent {len(content)} characters to source device")
            return True, None
            
    except Exception as e:
        error_msg = f"Failed to send capture: {e}"
        click.echo(error_msg, err=True)
        return False, error_msg


async def execute_builtin_command(
    command: str,
    args: Dict[str, str],
    config: Dict[str, Any],
    api_key: str,
    source_device_iden: str,
    source_device_name: Optional[str] = None,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Execute a built-in command
    
    Args:
        command: Command name
        args: Command arguments
        config: Configuration
        api_key: Pushbullet API key
        source_device_iden: Device ID to send reply to
        source_device_name: Name of the source device
        
    Returns:
        (is_builtin, result_or_command, error_message)
        - is_builtin: True if this was a built-in command
        - result_or_command: For built-in commands, None on success; 
                            For regular commands, the expanded command string
        - error_message: Error message if any
    """
    # Check if it's a built-in command
    if command == "capture":
        success, error = await handle_capture_command(
            args, config, api_key, source_device_iden, source_device_name
        )
        return True, None if success else error, error
    
    # Not a built-in command
    return False, None, None