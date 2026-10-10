"""Server runner for the Risk Engine FastAPI service.

Usage:
    python -m src.engine.serve [--host 127.0.0.1] [--port 8000] [--reload]
"""

from __future__ import annotations

import argparse
import socket
import sys
from typing import List, Optional
import uvicorn


def is_port_in_use(host: str, port: int) -> bool:
    """Check whether a port is already bound on host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def build_parser() -> argparse.ArgumentParser:
    """Build command line argument parser."""
    parser = argparse.ArgumentParser(description="Start the Risk Engine FastAPI service via Uvicorn.")
    parser.add_argument("--host", default="127.0.0.1", help="Host address to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload on code changes")
    return parser


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = build_parser()
    return parser.parse_args(args)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)

    if is_port_in_use(args.host, args.port):
        print(f"port {args.port} is in use, run: python -m src.engine.serve --port {args.port + 1}")
        sys.exit(1)

    print(f"Starting Risk Engine API on http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop the server.")
    try:
        uvicorn.run(
            "src.engine.api:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level="info",
        )
    except OSError as e:
        if "address already in use" in str(e).lower() or getattr(e, "errno", None) in (98, 10048):
            print(f"port {args.port} is in use, run: python -m src.engine.serve --port {args.port + 1}")
            sys.exit(1)
        raise


if __name__ == "__main__":
    main()
