FROM python:3.14

# Prevent Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Keep Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1

# Create a non-root user (optional but recommended for devcontainers)
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME

# Install git and other basics if needed (python images are usually minimal)
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

USER $USERNAME
