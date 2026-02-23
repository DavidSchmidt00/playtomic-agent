#!/usr/bin/env pwsh
# Docker Development Environment Helper Script
# Usage: .\scripts\docker-dev.ps1 <command> [args]

param(
    [Parameter(Position=0)]
    [string]$Command = "help",
    
    [Parameter(Position=1, ValueFromRemainingArguments=$true)]
    [string[]]$Args
)

$ErrorActionPreference = "Stop"

function Show-Help {
    Write-Host @"
Docker Development Environment Helper

Usage: .\scripts\docker-dev.ps1 <command> [args]

Commands:
  build         Build the Docker image
  up            Start the development container (detached)
  down          Stop and remove the container
  restart       Restart the container
  shell         Open an interactive shell in the container
  exec <cmd>    Execute a command in the container
  test          Run pytest inside the container
  web           Start the web UI (port 8080)
  api           Start the FastAPI server (port 8082)
  langgraph     Start LangGraph dev server (port 8081)
  logs          Show container logs
  status        Show container status
  help          Show this help message

Examples:
  .\scripts\docker-dev.ps1 build
  .\scripts\docker-dev.ps1 up
  .\scripts\docker-dev.ps1 shell
  .\scripts\docker-dev.ps1 exec "python --version"
  .\scripts\docker-dev.ps1 test
  .\scripts\docker-dev.ps1 web
"@
}

function Invoke-DockerCompose {
    param([string[]]$Arguments)
    docker-compose @Arguments
}

switch ($Command.ToLower()) {
    "build" {
        Write-Host "Building Docker image..." -ForegroundColor Cyan
        Invoke-DockerCompose @("build")
    }
    
    "up" {
        Write-Host "Starting development container..." -ForegroundColor Cyan
        Invoke-DockerCompose @("up", "-d")
        Write-Host "Container started! Use '.\scripts\docker-dev.ps1 shell' to access it." -ForegroundColor Green
    }
    
    "down" {
        Write-Host "Stopping development container..." -ForegroundColor Cyan
        Invoke-DockerCompose @("down")
    }
    
    "restart" {
        Write-Host "Restarting development container..." -ForegroundColor Cyan
        Invoke-DockerCompose @("restart")
    }
    
    "shell" {
        Write-Host "Opening shell in container..." -ForegroundColor Cyan
        Invoke-DockerCompose @("exec", "padel-agent-dev", "bash")
    }
    
    "exec" {
        if ($Args.Count -eq 0) {
            Write-Host "Error: exec command requires arguments" -ForegroundColor Red
            Write-Host "Usage: .\scripts\docker-dev.ps1 exec `"<command>`"" -ForegroundColor Yellow
            exit 1
        }
        $execCmd = $Args -join " "
        Invoke-DockerCompose @("exec", "padel-agent-dev", "bash", "-c", $execCmd)
    }
    
    "test" {
        Write-Host "Running tests in container..." -ForegroundColor Cyan
        Invoke-DockerCompose @("exec", "padel-agent-dev", "pytest", "tests/", "-v")
    }
    
    "web" {
        Write-Host "Starting web UI on port 8080..." -ForegroundColor Cyan
        Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
        Invoke-DockerCompose @("exec", "padel-agent-dev", "bash", "-c", "cd web && npm install && npm run dev -- --host 0.0.0.0 --port 8080")
    }
    
    "api" {
        Write-Host "Starting FastAPI server on port 8082..." -ForegroundColor Cyan
        Write-Host "API docs will be available at http://localhost:8082/docs" -ForegroundColor Yellow
        Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
        Invoke-DockerCompose @("exec", "padel-agent-dev", "uvicorn", "playtomic_agent.api:app", "--host", "0.0.0.0", "--port", "8082", "--reload")
    }
    
    "langgraph" {
        Write-Host "Starting LangGraph dev server on port 8081..." -ForegroundColor Cyan
        Write-Host "LangGraph Studio will be available at http://localhost:8081" -ForegroundColor Yellow
        Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
        Invoke-DockerCompose @("exec", "padel-agent-dev", "bash", "-c", "cd src/playtomic_agent && langgraph dev --host 0.0.0.0 --port 8081")
    }
    
    "logs" {
        Invoke-DockerCompose @("logs", "-f", "padel-agent-dev")
    }
    
    "status" {
        Write-Host "Container status:" -ForegroundColor Cyan
        Invoke-DockerCompose @("ps")
    }
    
    "help" {
        Show-Help
    }
    
    default {
        Write-Host "Unknown command: $Command" -ForegroundColor Red
        Write-Host ""
        Show-Help
        exit 1
    }
}
