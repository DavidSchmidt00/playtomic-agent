# Docker Development Environment

This guide explains how to use the Docker-based development environment as an alternative to the devcontainer while the Antigravity devcontainer integration is broken.

## Why Docker?

The Docker setup provides:
- ✅ **No local Python/Node installation needed** - Everything runs in Docker
- ✅ **Same environment as devcontainer** - Uses identical base image and configuration
- ✅ **Easy to switch back** - When devcontainer is fixed, just use it again (no cleanup needed)
- ✅ **Convenient scripts** - PowerShell scripts for common development tasks

## Quick Start

> [!NOTE]
> The PowerShell convenience script (`scripts\docker-dev.ps1`) may require adjusting your execution policy. If you prefer to avoid that, you can use the `docker-compose` commands directly as shown below.

### 1. Build the Docker Image

```powershell
docker-compose build
```

This builds a Docker image based on the same configuration as your `.devcontainer/devcontainer.json`.

### 2. Start the Development Container

```powershell
docker-compose up -d
```

This starts the container in the background. Your project directory is mounted at `/workspace` inside the container.

### 3. Open a Shell

```powershell
docker-compose exec padel-agent-dev bash
```

This opens an interactive bash shell inside the container where you can run any command.

### Optional: Using the PowerShell Script

If you want to use the convenience script, you may need to adjust your PowerShell execution policy:

```powershell
# Option 1: Allow for current session only (recommended)
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process

# Option 2: Allow for current user (permanent)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Then use the script
.\scripts\docker-dev.ps1 build
.\scripts\docker-dev.ps1 up
.\scripts\docker-dev.ps1 shell
```

## Available Commands

The `docker-dev.ps1` script provides convenient shortcuts:

| Docker Compose Command | PowerShell Script | Description |
|------------------------|-------------------|-------------|
| `docker-compose build` | `.\scripts\docker-dev.ps1 build` | Build the Docker image |
| `docker-compose up -d` | `.\scripts\docker-dev.ps1 up` | Start the container (detached) |
| `docker-compose down` | `.\scripts\docker-dev.ps1 down` | Stop and remove the container |
| `docker-compose restart` | `.\scripts\docker-dev.ps1 restart` | Restart the container |
| `docker-compose exec padel-agent-dev bash` | `.\scripts\docker-dev.ps1 shell` | Open interactive shell |
| `docker-compose exec padel-agent-dev <cmd>` | `.\scripts\docker-dev.ps1 exec "<cmd>"` | Execute a command |
| `docker-compose exec padel-agent-dev pytest tests/ -v` | `.\scripts\docker-dev.ps1 test` | Run pytest |
| `docker-compose logs -f` | `.\scripts\docker-dev.ps1 logs` | Show container logs |
| `docker-compose ps` | `.\scripts\docker-dev.ps1 status` | Show container status |

## Common Development Tasks

### Running Tests

```powershell
# Run all tests
docker-compose exec padel-agent-dev pytest tests/ -v

# Run specific test file
docker-compose exec padel-agent-dev pytest tests/test_client.py -v

# Run with coverage
docker-compose exec padel-agent-dev pytest tests/ --cov=src/playtomic_agent --cov-report=html
```

### Running the Web UI

```powershell
docker-compose exec padel-agent-dev bash -c "cd web && npm install && npm run dev -- --host 0.0.0.0 --port 8080"
```

Then open your browser to [http://localhost:8080](http://localhost:8080)

Press `Ctrl+C` to stop.

### Running the API Server

```powershell
docker-compose exec padel-agent-dev uvicorn playtomic_agent.api:app --host 0.0.0.0 --port 8082 --reload
```

Then open your browser to [http://localhost:8082/docs](http://localhost:8082/docs) for the API documentation.

Press `Ctrl+C` to stop.

### Running LangGraph Dev Server

```powershell
docker-compose exec padel-agent-dev bash -c "cd src/playtomic_agent && langgraph dev --host 0.0.0.0 --port 8081
```

Then open LangGraph Studio and connect to [http://localhost:8081](http://localhost:8081)

Press `Ctrl+C` to stop.

### Code Formatting and Linting

```powershell
# Format code with black
docker-compose exec padel-agent-dev black src/ tests/

# Lint with ruff
docker-compose exec padel-agent-dev ruff check src/ tests/

# Type checking with mypy
docker-compose exec padel-agent-dev mypy src/
```

### Installing New Dependencies

If you add new dependencies to `pyproject.toml`:

```powershell
# Reinstall the package
docker-compose exec padel-agent-dev pip install -e .[dev]

# Or rebuild the image
docker-compose down
docker-compose build
docker-compose up -d
```

### Running the CLI

```powershell
docker-compose exec padel-agent-dev playtomic-agent --club-slug lemon-padel-club --date 2026-02-15
```

## How It Works

### File Synchronization

Your project directory (`c:\Users\davod\Documents\00_Projekte\padel-agent`) is mounted into the container at `/workspace`. This means:

- ✅ **Changes you make on Windows are immediately visible in the container**
- ✅ **Changes made in the container are immediately visible on Windows**
- ✅ **You can use your favorite Windows editor/IDE** (VS Code, PyCharm, etc.)

### Environment Variables

The container loads environment variables from your `.env` file automatically. Make sure you have:

```bash
GEMINI_API_KEY_FREE=your_free_tier_key
GEMINI_API_KEY_PAID=your_paid_tier_key
```

### Port Forwarding

The following ports are forwarded from the container to your Windows host:

- **8080** - Web UI (Vite dev server)
- **8081** - LangGraph dev server
- **8082** - FastAPI server

## Switching Back to Devcontainer

When the Antigravity devcontainer integration is fixed:

1. Stop the Docker container:
   ```powershell
   docker-compose down
   ```

2. Use the devcontainer feature in Antigravity as before

3. **No cleanup needed!** The Docker files can stay in your project - they won't interfere with devcontainer.

## Troubleshooting

### Container won't start

```powershell
# Check if container is running
docker-compose ps

# View logs
docker-compose logs -f

# Restart the container
docker-compose restart
```

### Port already in use

If you get a "port already in use" error, make sure no other services are using ports 8080, 8081, or 8082:

```powershell
# Check what's using a port (e.g., 8080)
netstat -ano | findstr :8080
```

### Changes not appearing in container

The volume mount should be automatic, but if you're having issues:

```powershell
# Restart the container
docker-compose restart

# Or rebuild from scratch
docker-compose down
docker-compose build
docker-compose up -d
```

### Python packages not found

If you get import errors:

```powershell
# Reinstall the package
docker-compose exec padel-agent-dev pip install -e .[dev]

# Verify installation
docker-compose exec padel-agent-dev bash -c "pip list | grep playtomic"
```

### Need to rebuild after dependency changes

```powershell
docker-compose down
docker-compose build
docker-compose up -d
```

## Comparison with Devcontainer

| Feature | Docker (this setup) | Devcontainer |
|---------|---------------------|--------------|
| Python/Node installation | ✅ In container | ✅ In container |
| Same base image | ✅ Yes | ✅ Yes |
| File synchronization | ✅ Volume mount | ✅ Volume mount |
| Environment variables | ✅ From .env | ✅ From .env |
| Port forwarding | ✅ 8080, 8081, 8082 | ✅ 8080, 8081, 8082 |
| IDE integration | ⚠️ Manual | ✅ Automatic |
| Convenience | ✅ PowerShell scripts | ✅ Built-in |

The main difference is that devcontainer provides tighter IDE integration, but this Docker setup gives you the same development environment while that integration is broken.
