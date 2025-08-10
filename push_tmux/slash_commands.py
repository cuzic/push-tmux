#!/usr/bin/env python3
"""
Slash command parser and executor for push-tmux
"""
import re
import click
from typing import Dict, Any, Optional, Tuple, List
from .config import load_config


class SlashCommandParser:
    """Parse and execute slash commands from messages"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.commands = self._load_commands()
    
    def _load_commands(self) -> Dict[str, Dict[str, Any]]:
        """Load slash command definitions from config"""
        return self.config.get('slash_commands', {})
    
    def parse_message(self, message: str) -> Tuple[Optional[str], Dict[str, str]]:
        """
        Parse a message for slash commands
        Returns: (command_name, arguments) or (None, {}) if not a slash command
        """
        if not message.startswith('/'):
            return None, {}
        
        # Extract command and arguments
        parts = message.split(None, 1)
        if not parts:
            return None, {}
        
        command = parts[0][1:]  # Remove leading slash
        args_str = parts[1] if len(parts) > 1 else ""
        
        # Parse arguments (format: key:value or key=value)
        arguments = self._parse_arguments(args_str)
        
        return command, arguments
    
    def _parse_arguments(self, args_str: str) -> Dict[str, str]:
        """Parse command arguments in format: key:value or key=value"""
        arguments = {}
        if not args_str:
            return arguments
        
        # Match key:value or key=value patterns
        pattern = r'(\w+)[:=]([^\s]+)'
        matches = re.findall(pattern, args_str)
        
        for key, value in matches:
            arguments[key] = value
        
        # Also capture positional arguments
        # Remove key:value pairs first
        remaining = re.sub(pattern, '', args_str).strip()
        if remaining:
            # Split remaining text as positional arguments
            positionals = remaining.split()
            for i, val in enumerate(positionals):
                arguments[f'arg{i}'] = val
        
        return arguments
    
    def execute_command(self, command: str, arguments: Dict[str, str]) -> Optional[str]:
        """
        Execute a slash command based on config template
        Returns the expanded command string or None if command not found
        """
        if command not in self.commands:
            return None
        
        cmd_config = self.commands[command]
        template = cmd_config.get('template', '')
        defaults = cmd_config.get('defaults', {})
        
        # Merge defaults with provided arguments
        final_args = {**defaults, **arguments}
        
        # Expand template with arguments
        try:
            expanded = template.format(**final_args)
            return expanded
        except KeyError as e:
            click.echo(f"Missing required argument: {e}", err=True)
            return None
    
    def should_execute(self, command: str, device_name: str) -> bool:
        """
        Check if command should be executed based on conditions
        """
        if command not in self.commands:
            return False
        
        cmd_config = self.commands[command]
        
        # Check device restrictions
        allowed_devices = cmd_config.get('allowed_devices', [])
        if allowed_devices and device_name not in allowed_devices:
            return False
        
        # Check other conditions (can be extended)
        if cmd_config.get('disabled', False):
            return False
        
        return True
    
    def get_target_session(self, command: str, arguments: Dict[str, str]) -> Optional[str]:
        """
        Get target tmux session for the command
        """
        if command not in self.commands:
            return None
        
        cmd_config = self.commands[command]
        
        # Check if session is specified in arguments
        if 'session' in arguments:
            return arguments['session']
        
        # Use command-specific target session
        return cmd_config.get('target_session')


def expand_slash_command(message: str, config: Dict[str, Any], device_name: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Main entry point for slash command processing
    
    Args:
        message: The message to process
        config: Configuration dictionary
        device_name: Name of the device sending the message
    
    Returns:
        (is_slash_command, expanded_command, target_session)
    """
    parser = SlashCommandParser(config)
    
    command, arguments = parser.parse_message(message)
    if not command:
        return False, None, None
    
    if not parser.should_execute(command, device_name):
        click.echo(f"Command '/{command}' not allowed for device '{device_name}'")
        return True, None, None  # It's a slash command but shouldn't execute
    
    expanded = parser.execute_command(command, arguments)
    if not expanded:
        click.echo(f"Unknown command: /{command}")
        return True, None, None
    
    target_session = parser.get_target_session(command, arguments)
    
    return True, expanded, target_session


# Helper functions for trigger conditions
class TriggerConditions:
    """Manage trigger conditions for commands"""
    
    def __init__(self):
        self.executed_once = set()  # Track commands executed once
    
    def check_once_condition(self, command_id: str) -> bool:
        """Check if a command should execute only once"""
        if command_id in self.executed_once:
            return False
        self.executed_once.add(command_id)
        return True
    
    def reset_once_condition(self, command_id: str):
        """Reset the once condition for a command"""
        self.executed_once.discard(command_id)


# Global trigger conditions instance
_trigger_conditions = TriggerConditions()


def check_trigger_conditions(command: str, config: Dict[str, Any]) -> bool:
    """
    Check if trigger conditions are met for a command
    """
    if 'slash_commands' not in config:
        return True
    
    cmd_config = config['slash_commands'].get(command, {})
    
    # Check "once" condition
    if cmd_config.get('execute_once', False):
        command_id = f"{command}"
        return _trigger_conditions.check_once_condition(command_id)
    
    return True