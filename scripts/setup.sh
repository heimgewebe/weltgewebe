#!/bin/bash
set -euo pipefail

# Function to check if a command exists
command_exists() {
  command -v "$1" > /dev/null 2>&1
}

# Install rustup if not installed
if ! command_exists rustup; then
  echo "Rustup not found. Installing..."
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
  # Add cargo to path for the current session
  . "$HOME/.cargo/env"
else
  echo "Rustup is already installed."
fi

# Install just if not installed
if ! command_exists just; then
  echo "just not found. Installing..."
  cargo install just
else
  echo "just is already installed."
fi

# Install cargo-deny if not installed
if ! command_exists cargo-deny; then
  echo "cargo-deny not found. Installing..."
  cargo install cargo-deny
else
  echo "cargo-deny is already installed."
fi

echo "Setup complete. All required tools are installed."
