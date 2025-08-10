#!/usr/bin/env python3
"""
Pattern-based trigger system for push-tmux
"""
import re
import time
import click
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timedelta
from .config import load_config


class TriggerPattern:
    """Manage pattern-based triggers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.triggers = self._load_triggers()
        self.cooldowns = {}  # Track last execution times
        self.execution_counts = {}  # Track execution counts per hour
    
    def _load_triggers(self) -> Dict[str, Dict[str, Any]]:
        """Load trigger definitions from config"""
        return self.config.get('triggers', {})
    
    def check_message(self, message: str, source_device: str) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Check if message matches any trigger patterns
        
        Args:
            message: The incoming message
            source_device: The device that sent the message
            
        Returns:
            List of (trigger_name, action_config) tuples for matched triggers
        """
        matched_triggers = []
        
        for trigger_name, trigger_config in self.triggers.items():
            if self._match_trigger(message, source_device, trigger_config):
                if self._check_conditions(trigger_name, trigger_config):
                    action = self._prepare_action(message, source_device, trigger_config)
                    if action:
                        matched_triggers.append((trigger_name, action))
                        self._update_execution_tracking(trigger_name)
        
        return matched_triggers
    
    def _match_trigger(self, message: str, source_device: str, trigger_config: Dict[str, Any]) -> bool:
        """Check if message matches trigger pattern"""
        match_config = trigger_config.get('match', {})
        
        # Check pattern
        pattern = match_config.get('pattern')
        if not pattern:
            return False
        
        # Check device filter
        from_devices = match_config.get('from_devices', [])
        if from_devices and source_device not in from_devices:
            return False
        
        # Perform pattern matching
        case_sensitive = match_config.get('case_sensitive', False)
        flags = 0 if case_sensitive else re.IGNORECASE
        
        if match_config.get('regex', True):
            # Regular expression matching
            try:
                match = re.search(pattern, message, flags)
                if match:
                    # Store match groups for later use
                    trigger_config['_match'] = match
                    trigger_config['_match_groups'] = match.groups()
                    trigger_config['_match_dict'] = match.groupdict()
                    return True
            except re.error:
                click.echo(f"Invalid regex pattern in trigger: {pattern}", err=True)
                return False
        else:
            # Simple string matching
            if case_sensitive:
                return pattern in message
            else:
                return pattern.lower() in message.lower()
        
        return False
    
    def _check_conditions(self, trigger_name: str, trigger_config: Dict[str, Any]) -> bool:
        """Check if trigger conditions are met"""
        conditions = trigger_config.get('conditions', {})
        
        # Check cooldown
        cooldown = conditions.get('cooldown', 0)
        if cooldown > 0:
            last_execution = self.cooldowns.get(trigger_name, 0)
            if time.time() - last_execution < cooldown:
                return False
        
        # Check max executions per hour
        max_per_hour = conditions.get('max_per_hour', 0)
        if max_per_hour > 0:
            current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
            hour_key = f"{trigger_name}_{current_hour.isoformat()}"
            
            # Clean old entries
            self._clean_old_execution_counts()
            
            count = self.execution_counts.get(hour_key, 0)
            if count >= max_per_hour:
                return False
        
        # Check execute_once
        if conditions.get('execute_once', False):
            if trigger_name in self.cooldowns:
                return False  # Already executed once
        
        return True
    
    def _prepare_action(self, message: str, source_device: str, trigger_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Prepare action configuration with expanded variables"""
        action_config = trigger_config.get('action', {})
        if not action_config:
            return None
        
        # Prepare variables for template expansion
        variables = {
            'message': message,
            'source_device': source_device,
            'timestamp': datetime.now().isoformat(),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M:%S'),
        }
        
        # Add regex match groups if available
        if '_match' in trigger_config:
            match = trigger_config['_match']
            variables['match'] = match.group(0)  # Full match
            variables['match_text'] = match.group(0)  # Alias
            
            # Named groups
            if trigger_config.get('_match_dict'):
                variables.update(trigger_config['_match_dict'])
            
            # Numbered groups
            for i, group in enumerate(trigger_config.get('_match_groups', [])):
                variables[f'group{i+1}'] = group
        
        # Expand template
        template = action_config.get('template', '')
        try:
            expanded_template = template.format(**variables)
        except KeyError as e:
            click.echo(f"Missing variable in template: {e}", err=True)
            return None
        
        # Prepare Pushbullet target device
        target_device = action_config.get('target_device')
        if target_device:
            # Expand variables in target device name
            try:
                target_device = target_device.format(**variables)
            except KeyError:
                pass  # Keep original if expansion fails
        
        # Prepare tmux target session
        target_session = action_config.get('target_session')
        if target_session:
            try:
                target_session = target_session.format(**variables)
            except KeyError:
                pass
        
        return {
            'command': expanded_template,
            'target_device': target_device,
            'target_session': target_session,
            'send_to_pushbullet': action_config.get('send_to_pushbullet', False),
            'pushbullet_title': action_config.get('pushbullet_title', 'Trigger Alert'),
            'variables': variables  # Include for debugging/logging
        }
    
    def _update_execution_tracking(self, trigger_name: str):
        """Update execution tracking for cooldown and rate limiting"""
        # Update cooldown
        self.cooldowns[trigger_name] = time.time()
        
        # Update hourly count
        current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
        hour_key = f"{trigger_name}_{current_hour.isoformat()}"
        self.execution_counts[hour_key] = self.execution_counts.get(hour_key, 0) + 1
    
    def _clean_old_execution_counts(self):
        """Remove execution count entries older than 1 hour"""
        current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
        cutoff_time = current_hour - timedelta(hours=1)
        
        keys_to_remove = []
        for key in self.execution_counts:
            # Extract timestamp from key
            parts = key.rsplit('_', 1)
            if len(parts) == 2:
                try:
                    timestamp = datetime.fromisoformat(parts[1])
                    if timestamp < cutoff_time:
                        keys_to_remove.append(key)
                except ValueError:
                    pass
        
        for key in keys_to_remove:
            del self.execution_counts[key]


async def process_trigger_actions(actions: List[Tuple[str, Dict[str, Any]]], config: Dict[str, Any], api_key: str = None):
    """
    Process trigger actions (execute commands and send Pushbullet messages)
    
    Args:
        actions: List of (trigger_name, action_config) tuples
        config: Application configuration
        api_key: Pushbullet API key (optional, for sending responses)
    """
    from .tmux import send_to_tmux
    
    for trigger_name, action in actions:
        command = action.get('command')
        target_session = action.get('target_session')
        
        # Execute command in tmux
        if command:
            click.echo(f"Trigger '{trigger_name}' fired: {command[:50]}...")
            await send_to_tmux(config, command, target_session)
        
        # Send Pushbullet notification if configured
        if action.get('send_to_pushbullet') and api_key:
            await _send_pushbullet_response(api_key, action)


async def _send_pushbullet_response(api_key: str, action: Dict[str, Any]):
    """Send a response via Pushbullet"""
    from asyncpushbullet import AsyncPushbullet
    
    target_device = action.get('target_device')
    title = action.get('pushbullet_title', 'Trigger Alert')
    body = action.get('command', '')
    
    try:
        async with AsyncPushbullet(api_key) as pb:
            # Find target device if specified
            target_iden = None
            if target_device:
                devices = pb.get_devices()
                for device in devices:
                    if device.nickname == target_device or device.iden == target_device:
                        target_iden = device.iden
                        break
                
                if not target_iden:
                    click.echo(f"Target device '{target_device}' not found", err=True)
                    return
            
            # Send the notification
            await pb.async_push_note(title, body, device_iden=target_iden)
            click.echo(f"Sent Pushbullet notification to {target_device or 'all devices'}")
            
    except Exception as e:
        click.echo(f"Failed to send Pushbullet notification: {e}", err=True)


def check_triggers(message: str, source_device: str, config: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Main entry point for trigger checking
    
    Args:
        message: The incoming message
        source_device: The device that sent the message
        config: Application configuration
        
    Returns:
        List of matched trigger actions
    """
    trigger_pattern = TriggerPattern(config)
    return trigger_pattern.check_message(message, source_device)