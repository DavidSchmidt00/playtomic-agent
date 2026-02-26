# Deployment Guide

This guide explains how to deploy the Padel Agent to Railway.

## Architecture

- **Web Agent**: React frontend (built with Vite) + Python FastAPI backend, served from a single Docker container (`Dockerfile.prod`).
- **WhatsApp Agent**: Python-only background worker (`Dockerfile.whatsapp`), no HTTP port, connects to WhatsApp via neonize.

Both run as separate Railway services in the same project.

---

## Web Agent

Railway builds `Dockerfile.prod` automatically on every push to `main`.

### Setup

1. **New Project**: Railway Dashboard → **New Project** → **Deploy from GitHub repo** → select `padel-agent`.
2. **Dockerfile**: Settings → Build → **Dockerfile Path**: `Dockerfile.prod`.
3. **Health Check**: Settings → Deploy → **Health Check Path**: `/health`.
4. **Variables**: Add `GEMINI_API_KEY` (and optionally `DEFAULT_TIMEZONE`, `GOOGLE_GENAI_USE_VERTEXAI`).
5. **Domain**: Settings → Networking → **Generate Domain** or add a custom domain.

> [!WARNING]
> Environment variables must not contain inline comments (`KEY=VALUE # comment` breaks some Docker environments).

---

## WhatsApp Agent

The WhatsApp agent is a **background worker** (no HTTP port). It needs:
- A persistent **Volume** for the WhatsApp session and per-user state.
- A one-time **QR code scan** on first start to link a phone number.

### Setup

1. In the Railway project, click **New** → **GitHub Repo** (same repo) → **cancel** the auto-deploy immediately.
2. Settings → Build → **Dockerfile Path**: `Dockerfile.whatsapp`.
3. Settings → Deploy → **Networking**: leave all options off (no public domain, no port).
4. Settings → Deploy → **Restart Policy**: Always.
5. **Volumes** → **New Volume** → **Mount Path**: `/app/data`.
6. **Variables**: same `GEMINI_API_KEY`, `DEFAULT_TIMEZONE`, `GOOGLE_GENAI_USE_VERTEXAI` as the web agent.

### First-run QR scan

1. Trigger a deploy (push a commit or **Deploy Now** in the dashboard).
2. Open **Deploy Logs** in real time — a QR code will be printed as ASCII art.
3. On your phone: **WhatsApp** → **Linked Devices** → **Link a device** → scan the code.
4. The session is saved to the volume. The agent logs a successful connection.

> [!TIP]
> The QR code expires after ~60 seconds. Restart the service to get a fresh one.

### Ongoing operation

After the first scan, redeploys reconnect silently using the saved session — no re-scan needed.

```bash
# Tail live logs via Railway CLI
railway logs --service whatsapp-agent
```
