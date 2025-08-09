# push-tmux

A CLI tool to send Pushbullet messages to specific tmux sessions

## Overview

push-tmux is a tool that automatically sends messages received via Pushbullet to tmux sessions. By using different device names for each directory, you can manage messages on a per-project basis.

### Key Features

- 📱 **Device-based Message Routing** - Use different devices for each project
- 🔄 **Auto-restart Daemon Mode** - Process monitoring and automatic recovery on failure (NEW!)
- 🎯 **Auto-routing** - Automatically send messages to tmux sessions with matching device names
- 📝 **Detailed Logging** - Support for debugging and troubleshooting
- ⚙️ **Flexible Configuration** - Detailed configuration in TOML format

## Quick Start

### Directory-based Workflow

The recommended workflow when working on a specific project directory (e.g., `1on1-ver2`).

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
push-tmux register
# => Device 'webapp' has been registered.
```

#### 4. Start tmux Session
```bash
# Start new tmux session
tmux new-session -s webapp

# Or attach to existing session
tmux attach -t webapp
```

#### 5. Start Listening in tmux
```bash
# Run inside tmux session (traditional method)
push-tmux listen
# => Listening as device 'webapp' (ID: xxx).

# Or run in daemon mode (recommended)
push-tmux daemon
# => Running with auto-restart capability
```

#### 6. Send Messages
Send a message to the "webapp" device from another device (e.g., smartphone) via Pushbullet, and it will automatically be typed into the first window/first pane of the current tmux session.

## How It Works

1. **Device Identification**: Different device names for each directory enable per-project message routing
2. **Message Filtering**: Ignores broadcast messages, processes only device-specific messages
3. **tmux Integration**: Received messages are automatically sent to the current tmux session

### Default Behavior

- **Target Session**: 
  1. Explicit setting in `config.toml` `[tmux].target_session` (highest priority)
  2. Mapping configuration in `[device_mapping]` section
  3. tmux session with same name as device name (default)
  4. Current tmux session (when run inside tmux)
- **Target Window**: First window in the session (by index order, default)
- **Target Pane**: First pane in the window (by index order, default)

## Configuration

### Environment Variables (.env file)

```bash
# Pushbullet API key (required)
PUSHBULLET_TOKEN=o.xxxxxxxxxxxxxxxxxxxxx

# Device name (defaults to current directory name if omitted)
DEVICE_NAME=my-project
```

### config.toml (Optional)

Customize detailed behavior with the configuration file. See `config-example.toml` for reference.

```toml
[tmux]
# target_session = "main"   # Defaults to session with same name as device
# target_window = "1"       # Defaults to first window if omitted
# target_pane = "0"         # Defaults to first pane if omitted

[device_mapping]
# Device name to tmux target mapping
# Simple format (session only)
"project-a" = "dev-session"    # project-a device → dev-session

# Detailed format (session, window, pane)
[device_mapping."mobile-app"]
session = "frontend"    # Session name (required)
window = "2"           # Window index (defaults to "first")
pane = "0"            # Pane index (defaults to "first")

[daemon]
reload_interval = 1.0       # File watch interval (seconds)
watch_files = ["config.toml", ".env"]  # Files to watch

[daemon.logging]
log_level = "INFO"          # Log level
log_file = ""              # Log file path (empty for stdout)
```

## Commands

### Device Management
```bash
# Register device
push-tmux register
push-tmux register --name custom-device

# List devices
push-tmux list-devices

# Delete device
push-tmux delete-device --name device-name
push-tmux delete-device --id device-id
```

### Message Reception
```bash
# Listen with current device name (traditional method)
push-tmux listen

# Listen as specific device
push-tmux listen --device other-device

# Run in debug mode
push-tmux listen --debug

# Auto-routing mode (NEW!)
push-tmux listen --auto-route
```

### Daemon Mode (NEW!)
```bash
# Run in daemon mode (with auto-restart)
push-tmux daemon

# Daemon with auto-routing
push-tmux daemon --auto-route

# Custom watch interval
push-tmux daemon --reload-interval 5.0

# Watch additional files
push-tmux daemon --watch-files myconfig.ini --watch-files secrets.env

# Debug mode
push-tmux daemon --debug
```

### Testing
```bash
# Send message directly to tmux (for testing)
push-tmux send-key "test message"
push-tmux send-key "test" --session mysession --window 0 --pane 1
```

## Practical Examples

### Per-Project Setup

```bash
# Project A
cd ~/projects/project-a
echo "DEVICE_NAME=project-a" > .env
push-tmux register
tmux new -s project-a
push-tmux daemon  # Receives only project-a messages (with auto-restart)

# Project B (in another terminal)
cd ~/projects/project-b
echo "DEVICE_NAME=project-b" > .env
push-tmux register
tmux new -s project-b
push-tmux daemon  # Receives only project-b messages (with auto-restart)
```

### Device Mapping Example

When you want to use different device names and tmux session names:

```toml
# config.toml
[device_mapping]
# Simple format (session only)
"mobile-dev" = "frontend"      # mobile-dev device → frontend session

# Detailed format (specify window and pane)
[device_mapping."backend-api"]
session = "backend"
window = "1"        # Second window (index 1)
pane = "2"         # Third pane (index 2)

[device_mapping."db-admin"]
session = "database"
window = "first"    # First window (default)
pane = "first"     # First pane (default)
```

```bash
# Working in frontend session
tmux new -s frontend
cd ~/projects/mobile-app
export DEVICE_NAME=mobile-dev
push-tmux register
push-tmux listen  # Receives mobile-dev messages in frontend session

# For backend-api, messages go to backend session window 1, pane 2
cd ~/projects/api
export DEVICE_NAME=backend-api
push-tmux register
push-tmux listen  # Messages sent to specific window/pane
```

### Auto-routing Mode (NEW!)

Useful when handling multiple projects simultaneously:

```bash
# Receive messages for all devices and
# automatically send to tmux sessions with matching names
push-tmux daemon --auto-route

# Prepare sessions
tmux new -s project-a -d
tmux new -s project-b -d
tmux new -s project-c -d

# Messages for each device will be automatically sent to corresponding sessions
```

### Scripting

```bash
#!/bin/bash
# start-project.sh

PROJECT_NAME=$(basename $(pwd))
export DEVICE_NAME=$PROJECT_NAME

# Register device
push-tmux register

# Start tmux session
tmux new-session -d -s $PROJECT_NAME

# Start push-tmux daemon (with auto-restart)
tmux send-keys -t $PROJECT_NAME "push-tmux daemon" C-m

# Attach to session
tmux attach -t $PROJECT_NAME
```

### Run as systemd Service

Suitable for production deployment:

```bash
# /etc/systemd/system/push-tmux.service
[Unit]
Description=Push-tmux daemon
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/project
Environment=PUSHBULLET_TOKEN=your-token
ExecStart=/path/to/venv/bin/push-tmux daemon --auto-route
Restart=always

[Install]
WantedBy=multi-user.target
```

## Troubleshooting

### Messages Not Being Received

1. Verify device is registered correctly
   ```bash
   push-tmux list-devices
   ```

2. Confirm you're sending to the correct device
   - Broadcast messages are ignored
   - Select specific device when sending

3. Check API key is configured correctly
   ```bash
   cat .env | grep PUSHBULLET_TOKEN
   ```

### Messages Not Sent to tmux

1. Verify you're running inside tmux
   ```bash
   echo $TMUX  # Should have value if inside tmux
   ```

2. Check target session/window/pane exists
   ```bash
   tmux list-sessions
   tmux list-windows
   tmux list-panes
   ```

### Daemon Restarting Frequently

1. Check logs
   ```bash
   # Run in debug mode
   push-tmux daemon --debug
   ```

2. Adjust watch interval
   ```bash
   # Increase watch interval
   push-tmux daemon --reload-interval 5.0
   ```

3. Check watched files
   - Ensure frequently changing files (like logs) are not being watched
   - Configure exclusions in `config.toml` with `ignore_patterns`

## Installation

```bash
# Clone repository
git clone https://github.com/cuzic/push-tmux.git
cd push-tmux

# Install dependencies (uv recommended)
uv pip install -e .

# Or using pip
pip install -e .
```

## Requirements

- Python 3.10+
- tmux
- Pushbullet account and API key

## Security

- Add `.env` file to `.gitignore` to exclude from version control
- Manage API keys via environment variables, never hardcode in source
- Use hard-to-guess names like project names for device names

## Documentation

- [DAEMON.md](DAEMON.md) - Detailed daemon mode documentation
- [config-example.toml](config-example.toml) - Sample configuration file
- [CLAUDE.md](CLAUDE.md) - Developer guide

## Language

- [日本語版 README](README.ja.md)

## License

MIT