"""Readiness probe for the AgentMemory service managed by PM2."""

import socket


AGENTMEMORY_HOST = "127.0.0.1"
AGENTMEMORY_PORT = 3111


def _port_already_listening(
    host: str = AGENTMEMORY_HOST,
    port: int = AGENTMEMORY_PORT,
) -> bool:
    """Return True when the AgentMemory REST port accepts connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        try:
            return sock.connect_ex((host, port)) == 0
        except OSError:
            return False


def agentmemory_is_ready() -> bool:
    """Report readiness without spawning or installing external processes."""
    return _port_already_listening()
