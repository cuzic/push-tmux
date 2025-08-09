# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

push-tmux is a CLI tool that receives Pushbullet messages and automatically sends them to specific tmux sessions. It enables project-based message routing by using different device names for different directories/projects.

## Key Architecture

### Core Components

1. **push_tmux.py** - Main CLI application with Click-based commands
2. **async_pushbullet.py** - Custom async Pushbullet client and WebSocket listener

### Device-Directory Mapping Strategy
The tool uses a unique approach where each project directory can have its own Pushbullet device:
- Device name defaults to current directory name (`os.path.basename(os.getcwd())`)
- Can be overridden with `DEVICE_NAME` environment variable
- Messages sent to specific devices are routed only to that device's listener

### Message Flow
1. **Registration**: Each directory registers as a unique Pushbullet device
2. **Listening**: WebSocket connection filters messages by target device ID
3. **Routing**: Only device-specific messages are processed (broadcast messages are ignored)
4. **Execution**: Messages are sent to tmux via `tmux send-keys` command

### tmux Integration Logic
- **Session detection**: Uses `$TMUX` environment variable and `tmux display-message`
- **Target resolution**: Dynamically finds first available window/pane if not configured
- **Fallback**: Uses explicit session/window/pane from `config.toml` if tmux detection fails

## Development Commands

### Prerequisites
This project uses **mise** for Python version management and **uv** for fast package management.

```bash
# Install mise (if not already installed)
curl https://mise.run | sh

# Install project dependencies (mise will auto-install Python 3.12 and uv)
mise install

# Activate the environment
mise trust  # Allow mise to manage this project
```

### Setup and Installation
```bash
# Install dependencies (uv is preferred and configured via mise)
uv pip install -e .

# Install with development dependencies
uv pip install -e ".[test]"

# Alternative: using pip (not recommended)
pip install -e .
```

### Testing
```bash
# Run all tests with coverage (uv ensures fast dependency resolution)
uv run pytest

# Run tests with detailed coverage report
uv run pytest --cov=push_tmux --cov=async_pushbullet --cov-report=html

# Run specific test file
uv run pytest tests/test_device_targeting.py

# Run specific test method
uv run pytest tests/test_device_targeting.py::test_device_targeting_logic

# Run tests in parallel
uv run pytest -n auto

# Run unit tests only (skip integration tests)
uv run pytest -m "not integration"

# Run integration tests only
uv run pytest tests/integration/ -v

# Alternative: direct pytest (requires manual environment activation)
pytest
```

### Code Quality
```bash
# Format code (if ruff is configured)
uv run ruff format .

# Lint code (if ruff is configured)  
uv run ruff check .

# Type checking (if mypy is configured)
uv run mypy push_tmux.py async_pushbullet.py
```

### Running Commands
```bash
# Run the CLI tool directly
uv run python -m push_tmux --help

# Or with the installed script
push-tmux --help

# Run specific commands
uv run python -m push_tmux register
uv run python -m push_tmux listen
```

## Tool Configuration

### mise Configuration (`.mise.toml`)
- **Python version**: 3.12 (automatically installed)
- **uv**: Latest version for fast package management
- **Virtual environment**: Auto-created in `.venv/` directory

### uv Benefits in This Project
- **Fast dependency resolution**: Much faster than pip for complex dependency trees
- **Reliable lockfile**: `uv.lock` ensures reproducible builds across environments
- **Built-in virtual environment management**: Works seamlessly with mise

## Configuration Management

### Environment Variables (`.env` file)
- `PUSHBULLET_TOKEN` - Required API token
- `DEVICE_NAME` - Optional device name override

### Runtime Configuration (`config.toml`)
```toml
[tmux]
target_session = "session_name"  # or "current"
target_window = "window_index"   # or "first" 
target_pane = "pane_index"       # or "first"
```

## CLI Command Structure

All commands are defined in `push_tmux.py` using Click decorators:

- `register` - Register current directory as Pushbullet device
- `list-devices` - Show all registered devices
- `delete-devices` - Interactive multi-select device deletion (replaces old delete-device)
- `listen` - Start WebSocket listener for incoming messages  
- `send-key` - Test utility to send messages directly to tmux

## Critical Implementation Details

### Message Filtering Logic
The core filtering happens in the `listen` command's `on_push` handler:
```python
# Only process 'note' type messages
if push.get('type') != 'note':
    return

# Get target device from message  
target_device = push.get('target_device_iden')

# Ignore broadcast messages (no target_device)
if not target_device:
    return

# Only process if message targets this device
if target_device != target_device_iden:
    return
```

### Async WebSocket Handling
The `AsyncPushbulletListener` class handles WebSocket connections and message parsing. Key methods:
- `_handle_tickle()` - Fetches recent pushes when notified
- `run()` - Main WebSocket event loop with reconnection logic

### tmux Session Resolution
The `send_to_tmux()` function has complex logic for determining the target:
1. Check explicit config.toml settings
2. If "current", detect from `$TMUX` environment variable
3. Use `tmux display-message` to get current session name
4. Find first available window/pane if not specified
5. Construct target string as `session:window.pane`

## Testing Strategy

### Test Organization
- `tests/test_device_targeting.py` - Core message filtering logic
- `tests/test_async_pushbullet.py` - API client functionality  
- `tests/test_push_tmux_commands.py` - CLI command behavior
- `tests/test_tmux_integration.py` - tmux interaction mocking
- `tests/test_utils.py` - Utility functions (config, device naming)

### Key Test Patterns
- Mock `AsyncPushbullet` with `AsyncMock` for API calls
- Use `click.testing.CliRunner` for CLI command testing
- Mock `asyncio.create_subprocess_exec` for tmux command testing
- Environment variable patching with `patch.dict(os.environ)`

## Security Considerations

- API keys are loaded from environment variables only
- Device IDs are validated before message processing
- No sensitive data is logged or stored in git-tracked files
- WebSocket connections include proper error handling and reconnection logic

## Common Development Patterns

### Adding New CLI Commands
1. Create async function with business logic
2. Add Click command decorator with options
3. Create wrapper function that calls `asyncio.run()`
4. Add comprehensive tests in appropriate test file

### Extending Message Processing
1. Modify the `on_push` handler in `listen` command
2. Add filtering logic before `send_to_tmux()` call
3. Update tests in `test_device_targeting.py`

### tmux Integration Changes
1. Modify `send_to_tmux()` function
2. Update session/window/pane resolution logic
3. Add tests with mocked subprocess calls