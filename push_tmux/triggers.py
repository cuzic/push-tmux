#!/usr/bin/env python3
"""
Pattern-based trigger system for push-tmux
"""

import re
import click
import logging
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timedelta


class TriggerPattern:
    """Manage pattern-based triggers"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.triggers = self._load_triggers()
        self.cooldowns = {}  # Track last execution times
        self.execution_counts = {}  # Track execution counts per hour

    def _load_triggers(self) -> Dict[str, Dict[str, Any]]:
        """Load trigger definitions from config"""
        return self.config.get("triggers", {})

    def check_message(
        self, message: str, source_device: str
    ) -> List[Tuple[str, Dict[str, Any]]]:
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
                    action = self._prepare_action(
                        message, source_device, trigger_config
                    )
                    if action:
                        matched_triggers.append((trigger_name, action))
                        self._update_execution_tracking(trigger_name)

        return matched_triggers

    def _match_trigger(
        self, message: str, source_device: str, trigger_config: Dict[str, Any]
    ) -> bool:
        """Check if message matches trigger pattern"""
        match_config = trigger_config.get("match", {})

        # Check pattern
        pattern = match_config.get("pattern")
        if not pattern:
            return False

        # Check device filter
        from_devices = match_config.get("from_devices", [])
        if from_devices and source_device not in from_devices:
            return False

        # Perform pattern matching
        case_sensitive = match_config.get("case_sensitive", False)
        flags = 0 if case_sensitive else re.IGNORECASE

        if match_config.get("regex", True):
            # Regular expression matching
            try:
                match = re.search(pattern, message, flags)
                if match:
                    # Store match groups for later use
                    trigger_config["_match"] = match
                    trigger_config["_match_groups"] = match.groups()
                    trigger_config["_match_dict"] = match.groupdict()
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

    def _check_conditions(
        self, trigger_name: str, trigger_config: Dict[str, Any]
    ) -> bool:
        """Check if trigger conditions are met"""
        conditions = trigger_config.get("conditions", {})

        # Check cooldown
        cooldown = conditions.get("cooldown", 0)
        if cooldown > 0:
            last_execution = self.cooldowns.get(trigger_name)
            if last_execution and (datetime.now() - last_execution).total_seconds() < cooldown:
                return False

        # Check max executions per hour
        max_per_hour = conditions.get("max_per_hour", 0)
        if max_per_hour > 0:
            current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
            hour_key = f"{trigger_name}_{current_hour.isoformat()}"

            # Clean old entries
            self._clean_old_execution_counts()

            count = self.execution_counts.get(hour_key, 0)
            if count >= max_per_hour:
                return False

        # Check execute_once
        if conditions.get("execute_once", False):
            if trigger_name in self.cooldowns:
                return False  # Already executed once

        return True

    def _prepare_action(
        self, message: str, source_device: str, trigger_config: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Prepare action configuration with expanded variables"""
        action_config = trigger_config.get("action", {})
        if not action_config:
            return None

        # Prepare variables for template expansion
        variables = {
            "message": message,
            "source_device": source_device,
            "timestamp": datetime.now().isoformat(),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M:%S"),
        }

        # Add regex match groups if available
        if "_match" in trigger_config:
            match = trigger_config["_match"]
            variables["match"] = match.group(0)  # Full match
            variables["match_text"] = match.group(0)  # Alias

            # Named groups
            if trigger_config.get("_match_dict"):
                variables.update(trigger_config["_match_dict"])

            # Numbered groups
            for i, group in enumerate(trigger_config.get("_match_groups", [])):
                variables[f"group{i + 1}"] = group

        # Expand template
        template = action_config.get("template", "")
        try:
            expanded_template = template.format(**variables)
        except KeyError as e:
            click.echo(f"Missing variable in template: {e}", err=True)
            return None

        # Get target device for tmux session
        target_device = action_config.get("target_device")
        if target_device:
            # Expand variables in target device name
            try:
                target_device = target_device.format(**variables)
            except KeyError:
                pass  # Keep original if expansion fails

            # Apply transformations
            target_device = self._apply_transformations(
                target_device, action_config, variables
            )

        return {
            "command": expanded_template,
            "target_device": target_device,  # This will be used as target session
            "variables": variables,  # Include for debugging/logging
        }

    def _apply_transformations(
        self, value: str, action_config: Dict[str, Any], variables: Dict[str, Any]
    ) -> str:
        """Apply transformations like mapping and string functions to a value"""
        if not value:
            return value

        # Apply mapping table if defined
        mapping = action_config.get("mapping", {})
        if mapping and value in mapping:
            value = mapping[value]

        # Apply string functions if defined
        transforms = action_config.get("transforms", [])
        for transform in transforms:
            value = self._apply_string_function(value, transform, variables)

        return value

    def _apply_string_function(
        self, value: str, transform: str, variables: Dict[str, Any]
    ) -> str:
        """Apply a string function transformation"""
        try:
            # Parse function call format: func(args)
            if "(" not in transform or ")" not in transform:
                return value

            func_name = transform[: transform.index("(")].strip()
            args_str = transform[
                transform.index("(") + 1 : transform.rindex(")")
            ].strip()

            # Handle different functions
            if func_name == "substr":
                # substr(start, length) or substr(start)
                args = [arg.strip() for arg in args_str.split(",")]
                if len(args) >= 1:
                    start = self._resolve_arg(args[0], variables)
                    if len(args) >= 2:
                        length = self._resolve_arg(args[1], variables)
                        return value[start : start + length]
                    else:
                        return value[start:]

            elif func_name == "lower":
                return value.lower()

            elif func_name == "upper":
                return value.upper()

            elif func_name == "replace":
                # replace(old, new)
                args = [arg.strip().strip("\"'") for arg in args_str.split(",", 1)]
                if len(args) >= 2:
                    return value.replace(args[0], args[1])

            elif func_name == "prefix":
                # prefix(string)
                prefix_str = args_str.strip("\"'")
                return prefix_str + value

            elif func_name == "suffix":
                # suffix(string)
                suffix_str = args_str.strip("\"'")
                return value + suffix_str

            elif func_name == "truncate":
                # truncate(length)
                length = self._resolve_arg(args_str, variables)
                return value[:length]

            elif func_name == "regex_extract":
                # regex_extract(pattern, group_num=0)
                args = self._parse_regex_args(args_str)
                if len(args) >= 1:
                    pattern = args[0]
                    group_num = int(args[1]) if len(args) > 1 else 0
                    match = re.search(pattern, value)
                    if match:
                        try:
                            return match.group(group_num)
                        except IndexError:
                            return match.group(0)
                    return value  # Return original if no match

            elif func_name == "regex_replace":
                # regex_replace(pattern, replacement)
                args = self._parse_regex_args(args_str)
                if len(args) >= 2:
                    pattern = args[0]
                    replacement = args[1]
                    return re.sub(pattern, replacement, value)

            elif func_name == "regex_match":
                # regex_match(pattern, true_value, false_value)
                args = self._parse_regex_args(args_str)
                if len(args) >= 3:
                    pattern = args[0]
                    true_val = args[1]
                    false_val = args[2]

                    # Expand variables in true/false values
                    try:
                        true_val = (
                            true_val.format(**variables)
                            if "{" in true_val
                            else true_val
                        )
                    except (KeyError, ValueError):
                        pass
                    try:
                        false_val = (
                            false_val.format(**variables)
                            if "{" in false_val
                            else false_val
                        )
                    except (KeyError, ValueError):
                        pass

                    if re.search(pattern, value):
                        return true_val
                    else:
                        return false_val
                elif len(args) >= 1:
                    # Return original if matches, empty if not
                    pattern = args[0]
                    if re.search(pattern, value):
                        return value
                    else:
                        return ""

        except Exception as e:
            click.echo(f"Error applying transform '{transform}': {e}", err=True)

        return value

    def _parse_regex_args(
        self, args_str: str, variables: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Parse arguments for regex functions, handling escaped commas"""
        args = []
        current_arg = []
        in_quotes = False
        escape_next = False
        has_comma = False

        for char in args_str:
            if escape_next:
                current_arg.append(char)
                escape_next = False
            elif char == "\\":
                escape_next = True
                current_arg.append(char)  # Keep backslash for regex
            elif char in ('"', "'"):
                in_quotes = not in_quotes
            elif char == "," and not in_quotes:
                args.append("".join(current_arg).strip().strip("\"'"))
                current_arg = []
                has_comma = True
            else:
                current_arg.append(char)

        # Add the last argument
        if current_arg or has_comma:
            args.append("".join(current_arg).strip().strip("\"'"))

        return args

    def _resolve_arg(self, arg: str, variables: Dict[str, Any]) -> int:
        """Resolve an argument that might be a number or variable"""
        arg = arg.strip()

        # Try as integer
        try:
            return int(arg)
        except ValueError:
            pass

        # Try as variable reference
        if arg in variables:
            try:
                return int(variables[arg])
            except (ValueError, TypeError):
                pass

        return 0

    def _update_execution_tracking(self, trigger_name: str):
        """Update execution tracking for cooldown and rate limiting"""
        # Update cooldown
        self.cooldowns[trigger_name] = datetime.now()

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
            parts = key.rsplit("_", 1)
            if len(parts) == 2:
                try:
                    timestamp = datetime.fromisoformat(parts[1])
                    if timestamp < cutoff_time:
                        keys_to_remove.append(key)
                except ValueError:
                    pass

        for key in keys_to_remove:
            del self.execution_counts[key]


async def process_trigger_actions(
    actions: List[Tuple[str, Dict[str, Any]]], config: Dict[str, Any]
):
    """
    Process trigger actions (execute commands in tmux)

    Args:
        actions: List of (trigger_name, action_config) tuples
        config: Application configuration
    """
    from .tmux import send_to_tmux

    for trigger_name, action in actions:
        command = action.get("command")
        # Use target_device as the target session (device name maps to tmux session)
        target_session = action.get("target_device")

        # Execute command in tmux
        if command:
            click.echo(f"Trigger '{trigger_name}' fired: {command[:50]}...")
            await send_to_tmux(config, command, target_session)


def check_triggers(
    message: str, source_device: str, config: Dict[str, Any]
) -> List[Tuple[str, Dict[str, Any]]]:
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
