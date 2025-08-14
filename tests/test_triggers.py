#!/usr/bin/env python3
"""
Tests for pattern-based trigger functionality
"""

import pytest
import time
from unittest.mock import patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from push_tmux.triggers import TriggerPattern, check_triggers, process_trigger_actions


class TestTriggerPattern:
    """Test TriggerPattern class"""

    def test_simple_pattern_match(self):
        """Test simple pattern matching"""
        config = {
            "triggers": {
                "error_trigger": {
                    "match": {"pattern": "ERROR", "case_sensitive": False},
                    "action": {"template": "handle_error.sh"},
                }
            }
        }

        trigger = TriggerPattern(config)

        # Should match
        actions = trigger.check_message("ERROR: Something failed", "device1")
        assert len(actions) == 1
        assert actions[0][0] == "error_trigger"
        assert actions[0][1]["command"] == "handle_error.sh"

        # Case insensitive match
        actions = trigger.check_message("error occurred", "device1")
        assert len(actions) == 1

        # No match
        actions = trigger.check_message("All is well", "device1")
        assert len(actions) == 0

    def test_regex_pattern_with_groups(self):
        """Test regex pattern with capture groups"""
        config = {
            "triggers": {
                "deploy_trigger": {
                    "match": {"pattern": r"deploy (\w+) to (\w+)", "regex": True},
                    "action": {"template": "deploy.sh {group1} {group2}"},
                }
            }
        }

        trigger = TriggerPattern(config)
        actions = trigger.check_message("deploy feature-xyz to staging", "device1")

        # Note: feature-xyz contains a dash, which doesn't match \w+
        # Let's test with valid input
        actions = trigger.check_message("deploy feature to staging", "device1")
        assert len(actions) == 1
        assert actions[0][1]["command"] == "deploy.sh feature staging"

    def test_device_filtering(self):
        """Test device-based filtering"""
        config = {
            "triggers": {
                "admin_trigger": {
                    "match": {
                        "pattern": "admin command",
                        "from_devices": ["admin", "superuser"],
                    },
                    "action": {"template": "admin_action.sh"},
                }
            }
        }

        trigger = TriggerPattern(config)

        # Allowed device
        actions = trigger.check_message("admin command", "admin")
        assert len(actions) == 1

        # Not allowed device
        actions = trigger.check_message("admin command", "regular_user")
        assert len(actions) == 0

    def test_cooldown_condition(self):
        """Test cooldown period"""
        config = {
            "triggers": {
                "rate_limited": {
                    "match": {"pattern": "trigger"},
                    "action": {"template": "action.sh"},
                    "conditions": {"cooldown": 1},  # 1 second cooldown
                }
            }
        }

        trigger = TriggerPattern(config)

        # First trigger should work
        actions = trigger.check_message("trigger", "device1")
        assert len(actions) == 1

        # Second trigger immediately should be blocked
        actions = trigger.check_message("trigger", "device1")
        assert len(actions) == 0

        # After cooldown, should work again
        time.sleep(1.1)
        actions = trigger.check_message("trigger", "device1")
        assert len(actions) == 1

    def test_max_per_hour_condition(self):
        """Test max executions per hour"""
        config = {
            "triggers": {
                "hourly_limited": {
                    "match": {"pattern": "alert"},
                    "action": {"template": "alert.sh"},
                    "conditions": {"max_per_hour": 2},
                }
            }
        }

        trigger = TriggerPattern(config)

        # First two should work
        assert len(trigger.check_message("alert", "device1")) == 1
        assert len(trigger.check_message("alert", "device1")) == 1

        # Third should be blocked
        assert len(trigger.check_message("alert", "device1")) == 0

    def test_execute_once_condition(self):
        """Test execute_once condition"""
        config = {
            "triggers": {
                "once_only": {
                    "match": {"pattern": "initialize"},
                    "action": {"template": "init.sh"},
                    "conditions": {"execute_once": True},
                }
            }
        }

        trigger = TriggerPattern(config)

        # First execution should work
        assert len(trigger.check_message("initialize", "device1")) == 1

        # All subsequent executions should be blocked
        assert len(trigger.check_message("initialize", "device1")) == 0
        assert len(trigger.check_message("initialize", "device1")) == 0

    def test_template_variable_expansion(self):
        """Test template variable expansion"""
        config = {
            "triggers": {
                "variable_test": {
                    "match": {"pattern": "test (.+)"},
                    "action": {
                        "template": "log '{message}' from {source_device} at {timestamp} - matched: {match_text} - group: {group1}"
                    },
                }
            }
        }

        trigger = TriggerPattern(config)

        with patch("push_tmux.triggers.datetime") as mock_datetime:
            mock_datetime.now.return_value.isoformat.return_value = (
                "2024-01-01T12:00:00"
            )
            mock_datetime.now.return_value.strftime.side_effect = [
                "2024-01-01",
                "12:00:00",
            ]

            actions = trigger.check_message("test something", "mydevice")

            assert len(actions) == 1
            command = actions[0][1]["command"]
            assert "'test something' from mydevice" in command
            assert "matched: test something" in command
            assert "group: something" in command

    def test_target_device_expansion(self):
        """Test target device name expansion for tmux session routing"""
        config = {
            "triggers": {
                "notify_trigger": {
                    "match": {"pattern": "alert"},
                    "action": {
                        "template": "handle_alert.sh",
                        "target_device": "{source_device}_alerts",
                    },
                }
            }
        }

        trigger = TriggerPattern(config)
        actions = trigger.check_message("alert", "monitor")

        assert len(actions) == 1
        action = actions[0][1]
        assert action["target_device"] == "monitor_alerts"

    def test_target_device_with_capture_group(self):
        """Test target device using capture groups"""
        config = {
            "triggers": {
                "session_trigger": {
                    "match": {"pattern": "run in (.+)"},
                    "action": {
                        "template": "echo 'Running'",
                        "target_device": "{group1}",
                    },
                }
            }
        }

        trigger = TriggerPattern(config)
        actions = trigger.check_message("run in monitoring", "device1")

        assert len(actions) == 1
        assert actions[0][1]["target_device"] == "monitoring"


class TestProcessTriggerActions:
    """Test process_trigger_actions function"""

    @pytest.mark.asyncio
    @patch("push_tmux.tmux.send_to_tmux")
    @patch("push_tmux.triggers.click")
    async def test_execute_command(self, mock_click, mock_send_to_tmux):
        """Test executing trigger command in tmux"""
        mock_send_to_tmux.return_value = None

        actions = [
            (
                "test_trigger",
                {"command": "test_command.sh", "target_device": "test_device"},
            )
        ]

        await process_trigger_actions(actions, {})

        mock_send_to_tmux.assert_called_once_with({}, "test_command.sh", "test_device")
        mock_click.echo.assert_called()


class TestCheckTriggers:
    """Test check_triggers function"""

    def test_check_triggers_integration(self):
        """Test full trigger checking flow"""
        config = {
            "triggers": {
                "test_trigger": {
                    "match": {"pattern": "trigger (\\w+)", "from_devices": ["allowed"]},
                    "action": {
                        "template": "process {group1}",
                        "target_device": "device_{group1}",
                    },
                    "conditions": {"cooldown": 0},
                }
            }
        }

        # Should match
        actions = check_triggers("trigger test", "allowed", config)
        assert len(actions) == 1
        assert actions[0][0] == "test_trigger"
        assert actions[0][1]["command"] == "process test"
        assert actions[0][1]["target_device"] == "device_test"

        # Wrong device
        actions = check_triggers("trigger test", "not_allowed", config)
        assert len(actions) == 0

        # No match
        actions = check_triggers("no match", "allowed", config)
        assert len(actions) == 0


class TestComplexPatterns:
    """Test complex pattern scenarios"""

    def test_multiple_triggers(self):
        """Test multiple triggers matching same message"""
        config = {
            "triggers": {
                "error_log": {
                    "match": {"pattern": "ERROR"},
                    "action": {"template": "log_error.sh"},
                },
                "critical_alert": {
                    "match": {"pattern": "CRITICAL"},
                    "action": {"template": "alert_critical.sh"},
                },
                "any_problem": {
                    "match": {"pattern": "ERROR|WARNING|CRITICAL"},
                    "action": {"template": "handle_problem.sh"},
                },
            }
        }

        trigger = TriggerPattern(config)

        # Message matching multiple triggers
        actions = trigger.check_message("ERROR: CRITICAL failure", "device1")
        assert len(actions) == 3

        trigger_names = [action[0] for action in actions]
        assert "error_log" in trigger_names
        assert "critical_alert" in trigger_names
        assert "any_problem" in trigger_names

    def test_named_capture_groups(self):
        """Test regex with named capture groups"""
        config = {
            "triggers": {
                "named_groups": {
                    "match": {
                        "pattern": r"(?P<action>\w+) (?P<target>\w+) on (?P<server>\w+)",
                        "regex": True,
                    },
                    "action": {
                        "template": "{action}_handler.sh --target={target} --server={server}"
                    },
                }
            }
        }

        trigger = TriggerPattern(config)
        actions = trigger.check_message("restart database on production", "device1")

        assert len(actions) == 1
        assert (
            actions[0][1]["command"]
            == "restart_handler.sh --target=database --server=production"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
