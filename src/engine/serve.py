"""Server runner for the Risk Engine FastAPI service.

Usage:
    python -m src.engine.serve [--host 127.0.0.1] [--port 8000] [--reload]
"""

from __future__ import annotations

import argparse
import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the Risk Engine FastAPI service via Uvicorn.")
    parser.add_argument("--host", default="127.0.0.1", help="Host address to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload on code changes")

    args = parser.parse_args()

    print(f"Starting Risk Engine API on http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop the server.")
    uvicorn.run(
        "src.engine.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
