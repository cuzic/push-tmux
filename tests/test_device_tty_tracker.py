#!/usr/bin/env python3
"""
Tests for device-tty tracking functionality
"""

import pytest
import tempfile
import json
from pathlib import Path
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from push_tmux.device_tty_tracker import DeviceTtyTracker


class TestDeviceTtyTracker:
    """Test DeviceTtyTracker class"""

    def test_extract_tty_from_title(self):
        """Test extracting tty from various title formats"""
        tracker = DeviceTtyTracker()
        
        # Test "on pts/3" format
        assert tracker.extract_tty_from_title("Captured from session on pts/3") == "pts/3"
        
        # Test "/dev/pts/3" format
        assert tracker.extract_tty_from_title("Message on /dev/pts/5") == "pts/5"
        
        # Test bracket format
        assert tracker.extract_tty_from_title("Output [pts/2]") == "pts/2"
        
        # Test @ format
        assert tracker.extract_tty_from_title("Command @pts/7") == "pts/7"
        
        # Test no tty in title
        assert tracker.extract_tty_from_title("Regular message") is None
        
        # Test case insensitive
        assert tracker.extract_tty_from_title("Message ON PTS/1") == "PTS/1"

    def test_device_tty_mapping(self):
        """Test device-tty mapping operations"""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            cache_file = f.name
        
        try:
            tracker = DeviceTtyTracker(cache_file)
            
            # Set device tty
            tracker.set_device_tty("phone", "pts/3")
            assert tracker.get_device_tty("phone") == "pts/3"
            
            # Update from title
            tty = tracker.update_device_tty("laptop", "Message on pts/5")
            assert tty == "pts/5"
            assert tracker.get_device_tty("laptop") == "pts/5"
            
            # Clear device tty
            tracker.clear_device_tty("phone")
            assert tracker.get_device_tty("phone") is None
            
            # Laptop should still be there
            assert tracker.get_device_tty("laptop") == "pts/5"
            
        finally:
            if os.path.exists(cache_file):
                os.unlink(cache_file)

    def test_persistence(self):
        """Test that mappings persist across instances"""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            cache_file = f.name
        
        try:
            # First instance
            tracker1 = DeviceTtyTracker(cache_file)
            tracker1.set_device_tty("device1", "pts/1")
            tracker1.set_device_tty("device2", "pts/2")
            
            # Second instance should load the same mappings
            tracker2 = DeviceTtyTracker(cache_file)
            assert tracker2.get_device_tty("device1") == "pts/1"
            assert tracker2.get_device_tty("device2") == "pts/2"
            
            # Update in second instance
            tracker2.set_device_tty("device3", "pts/3")
            
            # Third instance should see all updates
            tracker3 = DeviceTtyTracker(cache_file)
            assert tracker3.get_device_tty("device1") == "pts/1"
            assert tracker3.get_device_tty("device2") == "pts/2"
            assert tracker3.get_device_tty("device3") == "pts/3"
            
        finally:
            if os.path.exists(cache_file):
                os.unlink(cache_file)

    def test_update_device_tty_no_match(self):
        """Test updating device tty when no tty in title"""
        tracker = DeviceTtyTracker()
        
        result = tracker.update_device_tty("phone", "Regular message")
        assert result is None
        assert tracker.get_device_tty("phone") is None

    def test_normalization(self):
        """Test that /dev/pts/X is normalized to pts/X"""
        tracker = DeviceTtyTracker()
        
        # Extract and normalize
        tty = tracker.extract_tty_from_title("on /dev/pts/3")
        assert tty == "pts/3"
        
        # Update and normalize
        tracker.update_device_tty("device", "on /dev/pts/5")
        assert tracker.get_device_tty("device") == "pts/5"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])