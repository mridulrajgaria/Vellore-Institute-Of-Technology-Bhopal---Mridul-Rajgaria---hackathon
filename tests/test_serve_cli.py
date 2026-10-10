import socket
import pytest
from unittest.mock import patch
from src.engine.serve import build_parser, parse_args, is_port_in_use, main


def test_serve_cli_default_args():
    args = parse_args([])
    assert args.host == "127.0.0.1"
    assert args.port == 8000
    assert args.reload is False


def test_serve_cli_custom_port_and_host():
    args = parse_args(["--host", "0.0.0.0", "--port", "8005", "--reload"])
    assert args.host == "0.0.0.0"
    assert args.port == 8005
    assert args.reload is True


def test_serve_cli_port_in_use_message(capsys):
    # Bind a socket to a free ephemeral port so it is definitely in use
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        _, bound_port = s.getsockname()

        assert is_port_in_use("127.0.0.1", bound_port) is True

        with pytest.raises(SystemExit) as exc_info:
            main(["--port", str(bound_port)])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        expected_msg = f"port {bound_port} is in use, run: python -m src.engine.serve --port {bound_port + 1}"
        assert expected_msg in captured.out
