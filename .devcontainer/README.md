# DevContainer for push-tmux

This DevContainer provides a complete development environment for push-tmux with all necessary tools pre-installed.

## What's Included

### Core Tools
- **Python 3.12** - Latest stable Python version
- **mise** - Version manager for Python and other tools (as specified in CLAUDE.md)
- **uv** - Fast Python package manager (as specified in CLAUDE.md)
- **tmux** - Terminal multiplexer (required for testing the project)

### Development Tools
- **ruff** - Fast Python linter and formatter
- **mypy** - Static type checker
- **pytest** - Testing framework
- **Git** - Version control
- **GitHub CLI** - GitHub integration

### VS Code Extensions
- Python language support with Pylance
- Ruff integration for formatting and linting
- MyPy type checker
- TOML file support
- Git integration with GitLens
- Error highlighting
- Environment file support

## Quick Start

1. **Open in DevContainer**
   - Use VS Code's "Reopen in Container" command
   - Or clone and use "Open Folder in Container"

2. **Automatic Setup**
   - Dependencies are automatically installed via `setup.sh`
   - Test tmux session is created
   - Sample `.env` file is generated

3. **Configure Environment**
   ```bash
   # Edit .env file with your Pushbullet token
   PUSHBULLET_TOKEN=your_token_here
   ```

4. **Verify Setup**
   ```bash
   # Run tests
   uv run pytest
   
   # Try the CLI
   uv run python -m push_tmux --help
   ```

## Development Workflow

### Testing
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=push_tmux --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_tmux.py -v
```

### Code Quality
```bash
# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Type checking
uv run mypy push_tmux/ --ignore-missing-imports
```

### Running the Application
```bash
# Register a device
uv run python -m push_tmux register

# Start listening for messages
uv run python -m push_tmux listen

# Run in daemon mode
uv run python -m push_tmux daemon
```

## Environment Variables

The DevContainer automatically creates a sample `.env` file. You need to:

1. Get a Pushbullet API token from https://www.pushbullet.com/#settings/account
2. Edit `.env` and replace `your_pushbullet_token_here` with your actual token

## Tmux Integration

A test tmux session named `test-session` is automatically created for testing. You can:

```bash
# List tmux sessions
tmux ls

# Attach to test session
tmux attach -t test-session

# Create new session for testing
tmux new-session -d -s my-test-session
```

## Troubleshooting

### Python Environment Issues
```bash
# Resync dependencies
uv sync --extra test

# Check Python version
python --version
mise current python
```

### mise/uv Issues
```bash
# Reinstall tools
mise install
source ~/.zshrc
```

### Test Failures
```bash
# Clean and resync
rm -rf .pytest_cache __pycache__ .venv
mise install
uv sync --extra test
```

## Container Details

- **Base Image**: `mcr.microsoft.com/devcontainers/python:3.12-bookworm`
- **User**: `vscode` (non-root)
- **Shell**: zsh with Oh My Zsh
- **Python Path**: Configured to use project virtual environment