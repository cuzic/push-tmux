FROM mcr.microsoft.com/devcontainers/python:3.12-bookworm

# Install additional system packages
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
        # Build essentials
        build-essential \
        # Network tools for debugging
        curl \
        wget \
        netcat-openbsd \
        # tmux dependencies
        tmux \
        # Process monitoring
        htop \
        # JSON processing
        jq \
    && apt-get autoremove -y \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*

# Set up tmux configuration
RUN echo "set -g mouse on" >> /etc/tmux.conf \
    && echo "set -g history-limit 10000" >> /etc/tmux.conf \
    && echo "set -g default-terminal 'screen-256color'" >> /etc/tmux.conf

# Create workspace directory
RUN mkdir -p /workspaces/push-tmux

WORKDIR /workspaces/push-tmux