# push-tmux

[![CI](https://github.com/cuzic/push-tmux/workflows/CI/badge.svg)](https://github.com/cuzic/push-tmux/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/cuzic/push-tmux/branch/master/graph/badge.svg)](https://codecov.io/gh/cuzic/push-tmux)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

A CLI tool to send Pushbullet messages to specific tmux sessions

## Overview

push-tmux is a tool that automatically sends messages received via Pushbullet to tmux sessions. By using different device names for each directory, you can manage messages on a per-project basis.

### Key Features

- 📱 **Device-based Message Routing** - Use different devices for each project
- 🔄 **Auto-restart Daemon Mode** - Process monitoring and automatic recovery on failure
- 🎯 **Auto-routing** - Automatically send messages to tmux sessions with matching device names
- 📝 **Detailed Logging** - Support for debugging and troubleshooting
- ⚙️ **Flexible Configuration** - Detailed configuration in TOML format
- 🚀 **Modular Architecture** - Improved maintainability with package structure
- 📦 **Standard Libraries** - Uses reliable external libraries like asyncpushbullet

## Quick Start

### 1. Quick Setup

```bash
# 1. Python environment setup
mise trust && mise install

# 2. Register devices (multiple devices can be registered)
push-tmux device register  # Registers device with current directory name

# 3. Create tmux sessions (with same names as registered devices)
tmux new-session -s device-name -d  # Can create multiple

# 4. Start listener (automatically handles all devices)
push-tmux start  # Auto-routing mode is default
```

### 2. Directory-based Workflow

The recommended workflow when working on a specific project directory (e.g., `webapp`).

#### 1. Navigate to Project Directory
```bash
cd ~/projects/webapp
```

#### 2. Set Device Name via Environment Variable
```bash
# Set in .env file
echo "DEVICE_NAME=webapp" >> .env

# Or set as environment variable
export DEVICE_NAME=webapp
```

Note: If `DEVICE_NAME` is not set, the current directory name will be used automatically as the device name.

#### 3. Register Device
```bash
push-tmux device register
# => Device 'webapp' has been registered.
```

#### 4. Start tmux Session
```bash
# Start new tmux session
tmux new-session -s webapp

# Or attach to existing session
tmux attach -t webapp
```

#### 5. Start Listener
```bash
# Default: Auto-routing mode (handles all devices' messages)
push-tmux start
# => Starting in auto-routing mode

# To receive only specific device's messages
push-tmux start --no-auto-route
# => Listening as device 'webapp' (ID: xxx)

# Run in daemon mode (recommended, with auto-restart)
push-tmux start --daemon
# => Running in auto-routing mode as daemon
```

#### 6. Send Messages
Send a message to any registered device from another device (e.g., smartphone) via Pushbullet, and it will automatically be typed into the corresponding tmux session.

## Global Installation

To make `push-tmux` available from any directory:

```bash
# Install to ~/.local/bin (make sure it's in your PATH)
./scripts/install-wrapper.sh

# Or install to system-wide location (requires sudo)
sudo ./scripts/install-wrapper.sh /usr/local/bin
```

After installation, you can run `push-tmux` from anywhere:

```bash
cd /any/directory
push-tmux device register
push-tmux start
push-tmux --help
```

**Note:** The wrapper scripts automatically handle project path resolution and dependency management using `uv`.

## Development Environment

### Using DevContainer (Recommended)

This project includes a complete DevContainer configuration for instant development setup:

```bash
# Clone the repository
git clone <repository-url>
cd push-tmux

# Open in VS Code and use "Reopen in Container"
# Or use GitHub Codespaces
```

The DevContainer includes:
- **Python 3.12** with mise and uv pre-configured
- **All development tools**: ruff, pyright, pytest, tmux
- **VS Code extensions** for Python development
- **Automatic setup** of dependencies and test environment

### Manual Setup

If you prefer manual setup:

```bash
# Install mise and uv
curl https://mise.run | sh
curl -LsSf https://astral.sh/uv/install.sh | sh

# Setup environment
mise trust && mise install
uv sync --extra test

# Run tests
uv run pytest
```

## CI/CD Pipeline

This project uses GitHub Actions for continuous integration and deployment:

### 🔄 **Workflows**

- **CI Pipeline** (`ci.yml`) - Comprehensive testing on push/PR
  - Multi-job testing: unit tests, integration tests, build checks
  - Code quality: ruff formatting/linting, pyright type checking
  - Security scanning with safety and bandit
  - Coverage reporting with Codecov integration

- **PR Check** (`pr-check.yml`) - Fast feedback for pull requests
  - Quick linting and formatting checks
  - Targeted test execution
  - PR analysis with change statistics

- **Dependencies** (`dependencies.yml`) - Automated maintenance
  - Weekly dependency updates via PRs
  - Security vulnerability scanning
  - Automated issue creation for security alerts

### 🛡️ **Quality Gates**

All workflows use **mise** for unified tool management:
```yaml
- name: Install mise
  uses: jdx/mise-action@v2
- name: Set up Python and uv with mise
  run: |
    mise trust
    mise install  # Installs both Python and uv via .mise.toml
    uv sync --extra test
```

## How It Works

1. **Device Identification**: Different device names for each directory enable per-project message routing
2. **Message Filtering**: Processes device-specific messages and routes them appropriately
3. **tmux Integration**: Received messages are automatically sent to the corresponding tmux session

### Session Resolution Priority

The tmux session is determined in the following order:

1. **`[device_mapping]` explicit mapping** (highest priority)
2. **Device name matching** (when `use_device_name_as_session=true`, default)
3. **`default_target_session` setting** (fallback)
4. **Current tmux session** (last resort)

## Configuration

### Environment Variables (.env file)

```bash
# Pushbullet API key (required)
PUSHBULLET_TOKEN=o.xxxxxxxxxxxxxxxxxxxxx

# Device name (defaults to current directory name if omitted)
DEVICE_NAME=my-project
```

### config.toml (Optional)

Customize detailed behavior with the configuration file. See `config.toml.example` for reference.

```toml
[tmux]
use_device_name_as_session = true  # Use tmux session with same name as device (default: true)
# default_target_session = "main"   # Fallback default session name
# target_window = "1"               # Window index (defaults to first window)
# target_pane = "0"                 # Pane index (defaults to first pane)
enter_delay = 0.5                   # Delay before sending Enter key (seconds)

[device_mapping]
# Device name to tmux session mappings

# Simple mapping (session only)
"mobile-dev" = "frontend"      # mobile-dev device → frontend session

# Detailed mapping (session, window, pane)
[device_mapping."backend-api"]
session = "backend"
window = "1"        # Second window (index 1)
pane = "2"         # Third pane (index 2)
```

## Commands

### Device Management
```bash
# Register device
push-tmux device register
push-tmux device register --name custom-device

# List devices
push-tmux device list

# Delete devices (interactive selection)
push-tmux device delete

# Delete specific device
push-tmux device delete --name device-name
push-tmux device delete --id device-id
```

### Message Reception
```bash
# Default: Auto-routing mode (handles all devices)
push-tmux start

# Receive only current device's messages
push-tmux start --no-auto-route

# Listen as specific device
push-tmux start --device other-device

# Receive all devices' messages (no routing)
push-tmux start --all-devices

# Debug mode
push-tmux start --debug
```

### Daemon Mode
```bash
# Default: Auto-routing daemon mode
push-tmux start --daemon

# Daemon for current device only
push-tmux start --daemon --no-auto-route

# Receive all devices' messages
push-tmux start --daemon --all-devices

# Custom reload interval
push-tmux start --daemon --reload-interval 5.0

# Watch additional files
push-tmux start --daemon --watch-files myconfig.ini --watch-files secrets.env

# Debug mode
push-tmux start --daemon --debug
```

### Test
```bash
# Send message directly to tmux (for testing)
push-tmux send "test message"
push-tmux send "test" --session mysession --window 0 --pane 1
```

## Practical Examples

### Multi-Project Setup

```bash
# Project A
cd ~/projects/project-a
echo "DEVICE_NAME=project-a" > .env
push-tmux device register
tmux new -s project-a
push-tmux start --daemon  # Receives only project-a messages (with auto-restart)

# Project B (in another terminal)
cd ~/projects/project-b
echo "DEVICE_NAME=project-b" > .env
push-tmux device register
tmux new -s project-b
push-tmux start --daemon  # Receives only project-b messages (with auto-restart)
```

### Auto-Routing Mode

Useful when handling multiple projects simultaneously:

```bash
# Receive messages for all devices and
# automatically send to matching tmux sessions
push-tmux start --daemon

# Prepare sessions
tmux new -s project-a -d
tmux new -s project-b -d
tmux new -s project-c -d

# Messages to each device are automatically sent to corresponding sessions
```

### Device Mapping Usage

When you want to use different device names and tmux session names:

```toml
# config.toml
[device_mapping]
# Simple mapping (session only)
"mobile-dev" = "frontend"      # mobile-dev device → frontend session

# Detailed mapping (specify window and pane)
[device_mapping."backend-api"]
session = "backend"
window = "1"        # Second window (index 1)
pane = "2"         # Third pane (index 2)
```

```bash
# Work in frontend session
tmux new -s frontend
cd ~/projects/mobile-app
export DEVICE_NAME=mobile-dev
push-tmux device register
push-tmux start  # mobile-dev messages received in frontend session
```

### Scripting

```bash
#!/bin/bash
# start-project.sh

PROJECT_NAME=$(basename $(pwd))
export DEVICE_NAME=$PROJECT_NAME

# Register device
push-tmux device register

# Start tmux session
tmux new-session -d -s $PROJECT_NAME

# Start push-tmux start --daemon (with auto-restart)
tmux send-keys -t $PROJECT_NAME "push-tmux start --daemon" C-m

# Attach to session
tmux attach -t $PROJECT_NAME
```

## Troubleshooting

### Messages Not Being Received

1. Check if device is registered correctly
   ```bash
   push-tmux device list
   ```

2. Verify you're sending to the correct device
   - Broadcast messages are ignored
   - Select specific device when sending

3. Check API key is set correctly
   ```bash
   cat .env | grep PUSHBULLET_TOKEN
   ```

### Messages Not Sent to tmux

1. Verify you're in a tmux session
   ```bash
   echo $TMUX  # Should have value if inside tmux
   ```

2. Check target session/window/pane exists
   ```bash
   tmux list-sessions
   tmux list-windows
   tmux list-panes
   ```

### Slow Applications (like Claude Code)

Adjust the Enter key delay in config.toml:
```toml
[tmux]
enter_delay = 1.0  # Increase delay for slow applications
```

## Installation

```bash
# Clone repository
git clone https://github.com/cuzic/push-tmux.git
cd push-tmux

# Set up mise environment (auto-installs Python 3.12 and dependencies)
mise trust
mise install

# Install development dependencies
uv pip install -e ".[test]"

# Regular installation
uv pip install -e .
```

## Requirements

- Python 3.12+ (via mise configuration)
- tmux
- Pushbullet account and API key
- mise (Python environment management)
- uv (fast package manager)

## Security

- Add `.env` file to `.gitignore` to prevent version control
- Manage API keys via environment variables, never hardcode in code
- Use hard-to-guess device names like project names

## Documentation

- [DAEMON.md](DAEMON.md) - Detailed daemon mode documentation
- [config.toml.example](config.toml.example) - Sample configuration file
- [CLAUDE.md](CLAUDE.md) - Developer guide

## Language

- [日本語 README](README.ja.md)

## License

MIT