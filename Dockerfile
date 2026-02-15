# Use the same base image as devcontainer
FROM mcr.microsoft.com/devcontainers/python:1-3.13-bullseye

# Install Node.js using nvm (more reliable than nodesource)
# This matches the approach used by devcontainer features
ARG NODE_VERSION=lts/*
RUN su vscode -c "umask 0002 && . /usr/local/share/nvm/nvm.sh && nvm install ${NODE_VERSION} 2>&1"

# Set working directory
WORKDIR /workspace

# Copy only necessary files for dependency installation first (better caching)
COPY pyproject.toml .
COPY README.md .
# Copy source directory (required for editable install)
COPY src/ ./src/

# Install Python dependencies (matching devcontainer postCreateCommand)
# This layer will be cached unless pyproject.toml or src changes
RUN pip3 install -e .[dev]

# Copy the rest of the project files
COPY . .


# Set environment variables (matching devcontainer)
ENV PYTHONPATH="${PYTHONPATH}:/workspace/src"

# Keep container running for interactive development
CMD ["sleep", "infinity"]

# Switch to non-root user
USER vscode
