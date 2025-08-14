#!/usr/bin/env python3
"""
Tests for regex transformation functions in triggers
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from push_tmux.triggers import TriggerPattern


class TestRegexExtract:
    """Test regex_extract function"""

    def test_extract_simple_pattern(self):
        """Test extracting a simple pattern"""
        config = {
            "triggers": {
                "extract_trigger": {
                    "match": {"pattern": "session (.+)"},
                    "action": {
                        "template": "echo 'Session'",
                        "target_device": "{group1}",
                        "transforms": ["regex_extract([a-z]+)"],
                    },
                }
            }
        }

        trigger = TriggerPattern(config)
        actions = trigger.check_message("session test-123-prod", "source")
        # Extracts first lowercase word: "test"
        assert actions[0][1]["target_device"] == "test"

    def test_extract_with_group(self):
        """Test extracting a specific capture group"""
        config = {
            "triggers": {
                "extract_group": {
                    "match": {"pattern": "deploy (.+)"},
                    "action": {
                        "template": "deploy.sh",
                        "target_device": "{group1}",
                        "transforms": ["regex_extract(([a-z]+)-([0-9]+)-(\\w+), 3)"],
                    },
                }
            }
        }

        trigger = TriggerPattern(config)
        actions = trigger.check_message("deploy feature-123-beta", "source")
        # Extracts third group: "beta"
        assert actions[0][1]["target_device"] == "beta"

    def test_extract_email_domain(self):
        """Test extracting domain from email"""
        config = {
            "triggers": {
                "email_domain": {
                    "match": {"pattern": "from (.+)"},
                    "action": {
                        "template": "process.sh",
                        "target_device": "{group1}",
                        "transforms": ["regex_extract(@([^.]+), 1)"],
                    },
                }
            }
        }

        trigger = TriggerPattern(config)
        actions = trigger.check_message("from user@example.com", "source")
        # Extracts domain part: "example"
        assert actions[0][1]["target_device"] == "example"

    def test_extract_no_match(self):
        """Test extraction when pattern doesn't match"""
        config = {
            "triggers": {
                "no_match": {
                    "match": {"pattern": "text (.+)"},
                    "action": {
                        "template": "echo",
                        "target_device": "{group1}",
                        "transforms": ["regex_extract([0-9]+)"],
                    },
                }
            }
        }

        trigger = TriggerPattern(config)
        actions = trigger.check_message("text abc", "source")
        # No match, returns original
        assert actions[0][1]["target_device"] == "abc"


class TestRegexReplace:
    """Test regex_replace function"""

    def test_replace_simple_pattern(self):
        """Test replacing a simple pattern"""
        config = {
            "triggers": {
                "replace_trigger": {
                    "match": {"pattern": "session (.+)"},
                    "action": {
                        "template": "echo",
                        "target_device": "{group1}",
                        "transforms": ["regex_replace([0-9]+, XXX)"],
                    },
                }
            }
        }

        trigger = TriggerPattern(config)
        actions = trigger.check_message("session test-123-prod", "source")
        # Replaces numbers with XXX
        assert actions[0][1]["target_device"] == "test-XXX-prod"

    def test_replace_with_groups(self):
        """Test replacement with capture groups"""
        config = {
            "triggers": {
                "group_replace": {
                    "match": {"pattern": "env (.+)"},
                    "action": {
                        "template": "deploy.sh",
                        "target_device": "{group1}",
                        "transforms": ["regex_replace(([a-z]+)-([0-9]+), \\2_\\1)"],
                    },
                }
            }
        }

        trigger = TriggerPattern(config)
        actions = trigger.check_message("env feature-123", "source")
        # Swaps order: feature-123 -> 123_feature
        assert actions[0][1]["target_device"] == "123_feature"

    def test_replace_special_chars(self):
        """Test replacing special characters"""
        config = {
            "triggers": {
                "sanitize": {
                    "match": {"pattern": "name (.+)"},
                    "action": {
                        "template": "echo",
                        "target_device": "{group1}",
                        "transforms": ["regex_replace([^a-zA-Z0-9]+, _)"],
                    },
                }
            }
        }

        trigger = TriggerPattern(config)
        actions = trigger.check_message("name test@#$prod!&*", "source")
        # Replaces non-alphanumeric with underscore
        assert actions[0][1]["target_device"] == "test_prod_"

    def test_replace_multiple(self):
        """Test multiple replacements"""
        config = {
            "triggers": {
                "multi_replace": {
                    "match": {"pattern": "branch (.+)"},
                    "action": {
                        "template": "checkout.sh",
                        "target_device": "{group1}",
                        "transforms": [
                            "regex_replace(feature/, f_)",
                            "regex_replace(bugfix/, b_)",
                            "regex_replace(/(.+), _\\1)",
                        ],
                    },
                }
            }
        }

        trigger = TriggerPattern(config)
        actions = trigger.check_message("branch feature/new-ui", "source")
        # feature/new-ui -> f_new-ui
        assert actions[0][1]["target_device"] == "f_new-ui"

        actions = trigger.check_message("branch bugfix/issue-123", "source")
        # bugfix/issue-123 -> b_issue-123
        assert actions[0][1]["target_device"] == "b_issue-123"


class TestRegexMatch:
    """Test regex_match function for conditional values"""

    def test_match_with_conditional(self):
        """Test conditional return based on pattern match"""
        config = {
            "triggers": {
                "conditional": {
                    "match": {"pattern": "env (.+)"},
                    "action": {
                        "template": "echo",
                        "target_device": "{group1}",
                        "transforms": ["regex_match(prod, production, development)"],
                    },
                }
            }
        }

        trigger = TriggerPattern(config)

        # Matches "prod"
        actions = trigger.check_message("env prod-server", "source")
        assert actions[0][1]["target_device"] == "production"

        # Doesn't match "prod"
        actions = trigger.check_message("env dev-server", "source")
        assert actions[0][1]["target_device"] == "development"

    def test_match_filter(self):
        """Test filtering with regex_match"""
        config = {
            "triggers": {
                "filter": {
                    "match": {"pattern": "session (.+)"},
                    "action": {
                        "template": "echo",
                        "target_device": "{group1}",
                        "transforms": [
                            "regex_match(^[a-z]+$)"
                        ],  # Only lowercase letters
                    },
                }
            }
        }

        trigger = TriggerPattern(config)

        # Matches pattern
        actions = trigger.check_message("session test", "source")
        assert actions[0][1]["target_device"] == "test"

        # Doesn't match pattern (has numbers)
        actions = trigger.check_message("session test123", "source")
        assert actions[0][1]["target_device"] == ""


class TestComplexRegexChains:
    """Test complex chains of regex operations"""

    def test_extract_and_replace(self):
        """Test combining extract and replace"""
        config = {
            "triggers": {
                "complex": {
                    "match": {"pattern": "url (.+)"},
                    "action": {
                        "template": "fetch.sh",
                        "target_device": "{group1}",
                        "transforms": [
                            "regex_extract(https?://([^/]+), 1)",  # Extract domain
                            "regex_replace(\\., _)",  # Replace dots with underscores
                            "lower()",  # Convert to lowercase
                        ],
                    },
                }
            }
        }

        trigger = TriggerPattern(config)
        actions = trigger.check_message("url https://API.Example.COM/path", "source")
        # https://API.Example.COM/path -> API.Example.COM -> API_Example_COM -> api_example_com
        assert actions[0][1]["target_device"] == "api_example_com"

    def test_conditional_processing(self):
        """Test conditional processing based on content"""
        config = {
            "triggers": {
                "smart_router": {
                    "match": {"pattern": "route (.+)"},
                    "action": {
                        "template": "route.sh",
                        "target_device": "{group1}",
                        "transforms": [
                            "regex_match(^prod-, production, {group1})",  # If starts with prod-, use "production" else keep value
                            "regex_replace(-\\d+$,)",  # Remove trailing numbers
                            "truncate(15)",
                        ],
                    },
                }
            }
        }

        trigger = TriggerPattern(config)

        # Starts with prod- → changes to "production", then removes numbers → "production"
        actions = trigger.check_message("route prod-server-123", "source")
        assert actions[0][1]["target_device"] == "production"

        # Doesn't start with prod- → keeps value as "dev-server-456", removes trailing "-456"
        actions = trigger.check_message("route dev-server-456", "source")
        assert actions[0][1]["target_device"] == "dev-server"

    def test_version_extraction(self):
        """Test extracting version numbers"""
        config = {
            "triggers": {
                "version": {
                    "match": {"pattern": "deploy (.+)"},
                    "action": {
                        "template": "deploy.sh",
                        "target_device": "{group1}",
                        "transforms": [
                            "regex_extract(v?([0-9]+\\.[0-9]+), 1)",  # Extract version like 1.2 or v1.2
                            "prefix(version_)",
                            "regex_replace(\\., _)",  # Replace dots with underscores
                        ],
                    },
                }
            }
        }

        trigger = TriggerPattern(config)
        actions = trigger.check_message("deploy app-v2.5.3-beta", "source")
        # app-v2.5.3-beta -> 2.5 -> version_2.5 -> version_2_5
        assert actions[0][1]["target_device"] == "version_2_5"


class TestRegexEdgeCases:
    """Test edge cases and error handling"""

    def test_invalid_regex(self):
        """Test handling of invalid regex patterns"""
        config = {
            "triggers": {
                "invalid": {
                    "match": {"pattern": "test (.+)"},
                    "action": {
                        "template": "echo",
                        "target_device": "{group1}",
                        "transforms": ["regex_extract([invalid)"],  # Unclosed bracket
                    },
                }
            }
        }

        trigger = TriggerPattern(config)
        actions = trigger.check_message("test value", "source")
        # Should return original on error
        assert actions[0][1]["target_device"] == "value"

    def test_escaped_characters(self):
        """Test handling escaped characters in patterns"""
        config = {
            "triggers": {
                "escaped": {
                    "match": {"pattern": "path (.+)"},
                    "action": {
                        "template": "echo",
                        "target_device": "{group1}",
                        "transforms": [
                            "regex_replace(\\\\, /)"
                        ],  # Replace backslash with forward slash
                    },
                }
            }
        }

        trigger = TriggerPattern(config)
        actions = trigger.check_message("path C:\\Users\\test", "source")
        # C:\Users\test -> C:/Users/test
        assert actions[0][1]["target_device"] == "C:/Users/test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
