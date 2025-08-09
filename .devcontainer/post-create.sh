#!/bin/bash
set -e

echo "🔧 Setting up Push-tmux development environment..."

# Trust and install mise dependencies
if command -v mise &> /dev/null; then
    echo "📦 Setting up mise..."
    mise trust
    mise install
fi

# Install Python dependencies with uv
if command -v uv &> /dev/null; then
    echo "📦 Installing Python dependencies with uv..."
    uv pip install -e ".[test]"
else
    echo "⚠️  uv not found, falling back to pip..."
    pip install -e ".[test]"
fi

# Set up pre-commit hooks if available
if command -v pre-commit &> /dev/null && [ -f .pre-commit-config.yaml ]; then
    echo "🪝 Installing pre-commit hooks..."
    pre-commit install
fi

# Create .env file template if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env template..."
    cat > .env << 'EOF'
# Pushbullet API Configuration
PUSHBULLET_TOKEN=your_pushbullet_api_token_here

# Optional: Override device name (defaults to current directory name)
# DEVICE_NAME=my-custom-device-name

# Optional: Debug mode
# DEBUG=true
EOF
    echo "⚠️  Please update .env with your Pushbullet API token"
fi

# Create config.toml template if it doesn't exist
if [ ! -f config.toml ]; then
    echo "📝 Creating config.toml template..."
    cat > config.toml << 'EOF'
[tmux]
# Target tmux session configuration
# Use "current" to auto-detect from $TMUX environment variable
target_session = "current"
target_window = "first"
target_pane = "first"

[logging]
# Logging configuration
level = "INFO"
format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
EOF
fi

# Set up tmux session for testing
echo "🖥️  Setting up tmux test session..."
tmux new-session -d -s test-session 2>/dev/null || true

# Configure git (if not already configured)
if ! git config --get user.email &> /dev/null; then
    echo "📧 Configuring git user..."
    git config --global user.email "developer@example.com"
    git config --global user.name "Developer"
fi

# Run initial tests to verify setup
echo "🧪 Running quick test to verify setup..."
python -m pytest tests/test_utils.py -v --tb=short || echo "⚠️  Some tests failed - this is expected if API tokens are not configured"

echo "✅ DevContainer setup complete!"
echo ""
echo "📚 Quick Start Guide:"
echo "  1. Update .env with your Pushbullet API token"
echo "  2. Run 'push-tmux register' to register this device"
echo "  3. Run 'push-tmux listen' to start receiving messages"
echo "  4. Run 'pytest' to run all tests"
echo ""
echo "📖 See USAGE.md for detailed instructions"