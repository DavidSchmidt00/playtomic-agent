#!/usr/bin/env bash
set -e

# Fix node_modules permissions (volume mount may be owned by root)
sudo chown -R vscode:vscode web/node_modules || true

# Install Python dependencies (editable mode with dev extras)
pip3 install -e ".[dev]"

# Install frontend dependencies
cd web && npm install && cd ..

# Activate pre-commit hooks so they run on every commit
pre-commit install
