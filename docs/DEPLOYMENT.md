# Deployment Guide

This guide explains how to deploy the Padel Agent to public hosting.

## Architecture

We use a **Single Container** architecture for simplest hosting:
1.  **Frontend**: Built with Vite (React) into static files.
2.  **Backend**: Python FastAPI.
3.  **Runtime**: The Python backend serves the API *and* the static frontend files from a single Docker container.

## Option 1: Railway (Recommended)

This is the easiest way to host. Railway will build the `Dockerfile.prod` automatically.

### Prerequisites
1.  A GitHub account with this repository pushed.
2.  A [Railway](https://railway.app/) account.

### Steps
1.  **New Project**: Go to Railway Dashboard -> "New Project" -> "Deploy from GitHub repo".
2.  **Select Repo**: Choose `padel-agent`.
3.  **Configure**:
    *   Railway should auto-detect the `Dockerfile` (it might pick the dev one by default).
    *   Go to **Settings** -> **Build** -> **Dockerfile Path**. Change it to `Dockerfile.prod`.
    *   **Health Check Path**: Set to `/health`.
    *   **Restart Policy**: Always.
4.  **Variables**:
    *   Go to **Variables**.
    *   Add `GEMINI_API_KEY`: Paste your API key.
    > [!WARNING]
    > Ensure that your environment variables do NOT contain comments (lines starting with `#` are fine, but inline comments like `KEY=VALUE # comment` can cause issues in some Docker environments).
5.  **Domain**:
    *   Go to **Settings** -> **Networking** -> **Generate Domain** (e.g. `padel-agent-production.up.railway.app`).
    *   Or "Custom Domain" to link `padelagent.de`.

## Option 2: Local Production Test

You can simulate the production environment locally using Docker Compose.

1.  **Build and Run**:
    ```bash
    docker-compose -f docker-compose.prod.yml up --build
    ```
2.  **Access**:
    Open [http://localhost:8080](http://localhost:8080).
    *   The frontend should load.
    *   Chat should work (calls `/api/chat`).

## Option 3: VPS (Strato / Hetzner)

If you have a Linux VPS with Docker installed.

1.  **Upload Code**: `git clone ...` or `scp`.
2.  **Run**:
    ```bash
    docker-compose -f docker-compose.prod.yml up -d --build
    ```
3.  **SSL**: You will need a reverse proxy like Caddy or Nginx to handle HTTPS and forward to port 8080.

### Caddy Example (Caddyfile)
```
padelagent.de {
    reverse_proxy localhost:8080
}
```
