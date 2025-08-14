# Scripts Directory

This directory contains utility scripts for push-tmux installation and operation.

## Scripts

### Installation Scripts

- **install.sh** - Main installation script for push-tmux
- **install-wrapper.sh** - Wrapper script to install push-tmux command globally

### Utility Scripts

- **push-tmux-wrapper.sh** - Wrapper script for push-tmux execution
- **push-tmux-session** - Script for managing push-tmux sessions
- **ptmux** - Shortcut command for push-tmux

## Usage

### Installing push-tmux globally

```bash
# Install to user directory (~/.local/bin)
./install-wrapper.sh

# Install to system directory (/usr/local/bin)
sudo ./install-wrapper.sh /usr/local/bin
```

### Direct script execution

Most scripts are designed to be executed through the main `push-tmux` command after installation. Direct execution is not recommended unless for debugging purposes.

## Notes

- Scripts assume they are located in the `scripts/` directory relative to the project root
- Ensure executable permissions are set: `chmod +x scripts/*.sh`
- These scripts are maintained as part of the push-tmux project