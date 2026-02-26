#!/usr/bin/env bash
set -e

# ensure we operate from the workspace root regardless of cwd
cd "$(dirname "$0")/.."

sudo chown -R vscode:vscode /home/vscode/.claude || true

# Fix node_modules permissions if needed (volume mount may be owned by root)
[ -d web/node_modules ] && sudo chown -R vscode:vscode web/node_modules || true

# Install Python dependencies (editable mode with dev extras)
# run from workspace root so pyproject.toml is visible
pip3 install -e ".[dev]"

# Install frontend dependencies
cd web && npm install && cd ..

# Activate pre-commit hooks so they run on every commit
pre-commit install

# Install Railway CLI
curl -fsSL https://railway.app/install.sh | sudo sh
