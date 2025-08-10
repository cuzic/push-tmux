#!/usr/bin/env python3
"""
Tests for trigger transformation features (mapping and string functions)
"""
import pytest
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from push_tmux.triggers import TriggerPattern


class TestMappingTable:
    """Test mapping table functionality"""
    
    def test_simple_mapping(self):
        """Test simple mapping table"""
        config = {
            "triggers": {
                "map_trigger": {
                    "match": {"pattern": "from (\\w+)"},
                    "action": {
                        "template": "echo 'Processing'",
                        "target_device": "{group1}",
                        "mapping": {
                            "dev": "development",
                            "prod": "production",
                            "test": "testing"
                        }
                    }
                }
            }
        }
        
        trigger = TriggerPattern(config)
        
        # Test mapping
        actions = trigger.check_message("from dev", "source")
        assert len(actions) == 1
        assert actions[0][1]['target_device'] == "development"
        
        actions = trigger.check_message("from prod", "source")
        assert len(actions) == 1
        assert actions[0][1]['target_device'] == "production"
        
        # Test unmapped value (stays the same)
        actions = trigger.check_message("from staging", "source")
        assert len(actions) == 1
        assert actions[0][1]['target_device'] == "staging"
    
    def test_mapping_with_source_device(self):
        """Test mapping with source device variable"""
        config = {
            "triggers": {
                "device_map": {
                    "match": {"pattern": "alert"},
                    "action": {
                        "template": "alert.sh",
                        "target_device": "{source_device}",
                        "mapping": {
                            "mobile": "mobile-alerts",
                            "server": "server-monitoring",
                            "laptop": "laptop-notifications"
                        }
                    }
                }
            }
        }
        
        trigger = TriggerPattern(config)
        
        actions = trigger.check_message("alert", "mobile")
        assert actions[0][1]['target_device'] == "mobile-alerts"
        
        actions = trigger.check_message("alert", "server")
        assert actions[0][1]['target_device'] == "server-monitoring"


class TestStringFunctions:
    """Test string transformation functions"""
    
    def test_lower_upper_functions(self):
        """Test lower and upper case transformations"""
        config = {
            "triggers": {
                "case_trigger": {
                    "match": {"pattern": "process (\\w+)"},
                    "action": {
                        "template": "echo 'Processing'",
                        "target_device": "{group1}",
                        "transforms": ["lower()"]
                    }
                }
            }
        }
        
        trigger = TriggerPattern(config)
        actions = trigger.check_message("process TEST", "source")
        assert actions[0][1]['target_device'] == "test"
        
        # Test upper
        config['triggers']['case_trigger']['action']['transforms'] = ["upper()"]
        trigger = TriggerPattern(config)
        actions = trigger.check_message("process test", "source")
        assert actions[0][1]['target_device'] == "TEST"
    
    def test_substr_function(self):
        """Test substring function"""
        config = {
            "triggers": {
                "substr_trigger": {
                    "match": {"pattern": "session (\\w+)"},
                    "action": {
                        "template": "echo 'Session'",
                        "target_device": "{group1}",
                        "transforms": ["substr(0, 3)"]
                    }
                }
            }
        }
        
        trigger = TriggerPattern(config)
        actions = trigger.check_message("session development", "source")
        assert actions[0][1]['target_device'] == "dev"
        
        # Test substr with only start
        config['triggers']['substr_trigger']['action']['transforms'] = ["substr(4)"]
        trigger = TriggerPattern(config)
        actions = trigger.check_message("session testing", "source")
        assert actions[0][1]['target_device'] == "ing"
    
    def test_replace_function(self):
        """Test replace function"""
        config = {
            "triggers": {
                "replace_trigger": {
                    "match": {"pattern": "env:(\\S+)"},
                    "action": {
                        "template": "deploy.sh",
                        "target_device": "{group1}",
                        "transforms": ["replace(-, _)"]
                    }
                }
            }
        }
        
        trigger = TriggerPattern(config)
        actions = trigger.check_message("env:prod-server-01", "source")
        assert actions[0][1]['target_device'] == "prod_server_01"
    
    def test_prefix_suffix_functions(self):
        """Test prefix and suffix functions"""
        config = {
            "triggers": {
                "prefix_trigger": {
                    "match": {"pattern": "to (\\w+)"},
                    "action": {
                        "template": "route.sh",
                        "target_device": "{group1}",
                        "transforms": ["prefix(session_)"]
                    }
                }
            }
        }
        
        trigger = TriggerPattern(config)
        actions = trigger.check_message("to monitor", "source")
        assert actions[0][1]['target_device'] == "session_monitor"
        
        # Test suffix
        config['triggers']['prefix_trigger']['action']['transforms'] = ["suffix(_logs)"]
        trigger = TriggerPattern(config)
        actions = trigger.check_message("to server", "source")
        assert actions[0][1]['target_device'] == "server_logs"
    
    def test_truncate_function(self):
        """Test truncate function"""
        config = {
            "triggers": {
                "truncate_trigger": {
                    "match": {"pattern": "name:(\\S+)"},
                    "action": {
                        "template": "process.sh",
                        "target_device": "{group1}",
                        "transforms": ["truncate(8)"]
                    }
                }
            }
        }
        
        trigger = TriggerPattern(config)
        actions = trigger.check_message("name:verylongsessionname", "source")
        assert actions[0][1]['target_device'] == "verylong"
    
    def test_multiple_transforms(self):
        """Test applying multiple transformations in sequence"""
        config = {
            "triggers": {
                "multi_transform": {
                    "match": {"pattern": "deploy (\\S+)"},
                    "action": {
                        "template": "deploy.sh",
                        "target_device": "{group1}",
                        "transforms": [
                            "lower()",
                            "replace(-, _)",
                            "prefix(deploy_)",
                            "truncate(15)"
                        ]
                    }
                }
            }
        }
        
        trigger = TriggerPattern(config)
        actions = trigger.check_message("deploy PROD-SERVER-01", "source")
        # PROD-SERVER-01 -> prod-server-01 -> prod_server_01 -> deploy_prod_server_01 -> deploy_prod_ser
        assert actions[0][1]['target_device'] == "deploy_prod_ser"


class TestCombinedFeatures:
    """Test combining mapping and transforms"""
    
    def test_mapping_then_transform(self):
        """Test applying mapping first, then transforms"""
        config = {
            "triggers": {
                "combined": {
                    "match": {"pattern": "env (\\w+)"},
                    "action": {
                        "template": "deploy.sh",
                        "target_device": "{group1}",
                        "mapping": {
                            "dev": "development",
                            "prod": "production"
                        },
                        "transforms": ["substr(0, 4)", "upper()"]
                    }
                }
            }
        }
        
        trigger = TriggerPattern(config)
        actions = trigger.check_message("env dev", "source")
        # dev -> development -> deve -> DEVE
        assert actions[0][1]['target_device'] == "DEVE"
        
        actions = trigger.check_message("env prod", "source")
        # prod -> production -> prod -> PROD
        assert actions[0][1]['target_device'] == "PROD"
    
    def test_complex_routing(self):
        """Test complex routing with multiple capture groups"""
        config = {
            "triggers": {
                "router": {
                    "match": {"pattern": "(\\w+)@(\\w+):(\\w+)"},
                    "action": {
                        "template": "route_command.sh",
                        "target_device": "{group2}_{group3}",
                        "mapping": {
                            "db_backup": "database-backup",
                            "web_logs": "webserver-logs"
                        },
                        "transforms": ["lower()"]
                    }
                }
            }
        }
        
        trigger = TriggerPattern(config)
        actions = trigger.check_message("admin@db:backup", "source")
        # db_backup -> database-backup (via mapping) -> database-backup (already lower)
        assert actions[0][1]['target_device'] == "database-backup"
        
        actions = trigger.check_message("user@web:logs", "source")
        # web_logs -> webserver-logs (via mapping) -> webserver-logs (already lower)
        assert actions[0][1]['target_device'] == "webserver-logs"
        
        actions = trigger.check_message("test@app:debug", "source")
        # app_debug -> app_debug (no mapping) -> app_debug
        assert actions[0][1]['target_device'] == "app_debug"


class TestErrorHandling:
    """Test error handling in transformations"""
    
    def test_invalid_transform_syntax(self):
        """Test handling of invalid transform syntax"""
        config = {
            "triggers": {
                "invalid": {
                    "match": {"pattern": "test"},
                    "action": {
                        "template": "test.sh",
                        "target_device": "session",
                        "transforms": ["invalid_function"]  # Missing parentheses
                    }
                }
            }
        }
        
        trigger = TriggerPattern(config)
        actions = trigger.check_message("test", "source")
        # Should return unchanged value
        assert actions[0][1]['target_device'] == "session"
    
    def test_invalid_substr_args(self):
        """Test substr with invalid arguments"""
        config = {
            "triggers": {
                "substr_invalid": {
                    "match": {"pattern": "test (\\w+)"},
                    "action": {
                        "template": "test.sh",
                        "target_device": "{group1}",
                        "transforms": ["substr(abc, def)"]  # Non-numeric args
                    }
                }
            }
        }
        
        trigger = TriggerPattern(config)
        actions = trigger.check_message("test session", "source")
        # Should handle gracefully and return empty or original
        # With invalid args, substr returns from position 0 (which gives the full string)
        assert actions[0][1]['target_device'] in ["session", "", ""]  # May vary based on error handling


if __name__ == "__main__":
    pytest.main([__file__, "-v"])