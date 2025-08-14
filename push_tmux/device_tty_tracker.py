#!/usr/bin/env python3
"""
Track device-to-tty mappings for push-tmux
"""

import re
import json
import os
from typing import Dict, Optional
from pathlib import Path


class DeviceTtyTracker:
    """Track which tty each device is associated with"""
    
    def __init__(self, cache_file: Optional[str] = None):
        """
        Initialize the tracker
        
        Args:
            cache_file: Path to cache file for persistent storage
        """
        if cache_file is None:
            cache_dir = Path.home() / ".cache" / "push-tmux"
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = cache_dir / "device_tty_map.json"
        
        self.cache_file = Path(cache_file)
        self.mappings: Dict[str, str] = self._load_mappings()
    
    def _load_mappings(self) -> Dict[str, str]:
        """Load mappings from cache file"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}
    
    def _save_mappings(self) -> None:
        """Save mappings to cache file"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.mappings, f, indent=2)
        except IOError:
            pass  # Fail silently if can't save cache
    
    def extract_tty_from_title(self, title: str) -> Optional[str]:
        """
        Extract tty/pts from a message title
        
        Args:
            title: Message title that may contain "on pts/X" or similar
            
        Returns:
            The tty string (e.g., "pts/3") or None if not found
        """
        # Match patterns like "on pts/3", "on /dev/pts/3", etc.
        patterns = [
            r'on\s+(pts/\d+)',  # "on pts/3"
            r'on\s+(/dev/pts/\d+)',  # "on /dev/pts/3"
            r'\[(pts/\d+)\]',  # "[pts/3]"
            r'@(pts/\d+)',  # "@pts/3"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                tty = match.group(1)
                # Normalize to just "pts/X" format
                if tty.startswith('/dev/'):
                    tty = tty.replace('/dev/', '')
                return tty
        
        return None
    
    def update_device_tty(self, device_name: str, title: str) -> Optional[str]:
        """
        Update the tty mapping for a device based on a message title
        
        Args:
            device_name: Name of the device
            title: Message title that may contain tty info
            
        Returns:
            The extracted tty or None if not found
        """
        tty = self.extract_tty_from_title(title)
        if tty:
            self.mappings[device_name] = tty
            self._save_mappings()
        return tty
    
    def get_device_tty(self, device_name: str) -> Optional[str]:
        """
        Get the last known tty for a device
        
        Args:
            device_name: Name of the device
            
        Returns:
            The tty string or None if not known
        """
        return self.mappings.get(device_name)
    
    def set_device_tty(self, device_name: str, tty: str) -> None:
        """
        Manually set the tty for a device
        
        Args:
            device_name: Name of the device
            tty: The tty string (e.g., "pts/3")
        """
        self.mappings[device_name] = tty
        self._save_mappings()
    
    def clear_device_tty(self, device_name: str) -> None:
        """
        Clear the tty mapping for a device
        
        Args:
            device_name: Name of the device
        """
        if device_name in self.mappings:
            del self.mappings[device_name]
            self._save_mappings()


# Global tracker instance
_tracker = DeviceTtyTracker()


def get_tracker() -> DeviceTtyTracker:
    """Get the global device-tty tracker instance"""
    return _tracker