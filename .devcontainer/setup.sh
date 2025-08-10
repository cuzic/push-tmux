#!/bin/bash
set -e

echo "🚀 Setting up push-tmux development environment..."

# Install uv (fast Python package manager)
echo "📦 Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.cargo/bin:$PATH"

# Add uv to PATH for future sessions
echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.zshrc

# Trust mise configuration
echo "🔧 Setting up mise..."
mise trust

# Install Python and dependencies via mise
echo "🐍 Installing Python and dependencies via mise..."
mise install

# Sync project dependencies with uv
echo "📚 Syncing project dependencies..."
uv sync --extra test

# Install pre-commit hooks if pre-commit is available
if command -v pre-commit >/dev/null 2>&1; then
    echo "🪝 Installing pre-commit hooks..."
    pre-commit install || echo "⚠️  Pre-commit installation skipped"
fi

# Create sample .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating sample .env file..."
    cat > .env << EOF
# Pushbullet API Token (required)
# Get yours from: https://www.pushbullet.com/#settings/account
PUSHBULLET_TOKEN=your_pushbullet_token_here

# Device name (optional - defaults to directory name)
# DEVICE_NAME=push-tmux-dev
EOF
    echo "✏️  Please edit .env and add your Pushbullet token"
fi

# Run tests to verify everything is working
echo "🧪 Running tests to verify setup..."
if uv run pytest --version >/dev/null 2>&1; then
    echo "✅ pytest is working"
    echo "🧪 Running quick test suite..."
    uv run pytest tests/ -x --tb=short || echo "⚠️  Some tests failed - this is expected without proper configuration"
else
    echo "❌ pytest is not working properly"
    exit 1
fi

# Set up tmux for testing
echo "🔄 Setting up tmux session for testing..."
if command -v tmux >/dev/null 2>&1; then
    # Create a test session if it doesn't exist
    if ! tmux has-session -t test-session 2>/dev/null; then
        tmux new-session -d -s test-session -c /workspaces/push-tmux
        echo "✅ Created test tmux session 'test-session'"
    else
        echo "✅ tmux session 'test-session' already exists"
    fi
fi

echo ""
echo "🎉 Development environment setup complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Edit .env and add your PUSHBULLET_TOKEN"
echo "   2. Run: uv run python -m push_tmux register"
echo "   3. Run: uv run python -m push_tmux listen"
echo "   4. Run tests: uv run pytest"
echo ""
echo "🔧 Useful commands:"
echo "   - Sync dependencies: uv sync --extra test"
echo "   - Run tests: uv run pytest"
echo "   - Run tests with coverage: uv run pytest --cov=push_tmux"
echo "   - Format code: uv run ruff format ."
echo "   - Lint code: uv run ruff check ."
echo "   - Type check: uv run mypy push_tmux/ --ignore-missing-imports"
echo ""