"""Web agent entry point."""

import os
from pathlib import Path

import uvicorn

_LOG_CONFIG = str(Path(__file__).parent.parent / "uvicorn_log_config.json")


def main() -> None:
    """Entry point for the web-agent command."""
    uvicorn.run(
        "playtomic_agent.web.api:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
        log_config=_LOG_CONFIG,
    )
