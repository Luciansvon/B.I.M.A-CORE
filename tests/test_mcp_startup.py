import threading
import time
from pathlib import Path

from core import mcp_startup


def test_mcp_startup_returns_before_slow_initialization(monkeypatch) -> None:
    started = threading.Event()
    release = threading.Event()
    ready_with: list[object] = []
    manager = object()

    def _slow_init(config_path: Path, project_root: Path) -> object:
        started.set()
        release.wait(timeout=2)
        return manager

    monkeypatch.setattr(mcp_startup, "_init_manager", _slow_init)
    monkeypatch.setattr(mcp_startup.atexit, "register", lambda callback: callback)

    before = time.monotonic()
    thread = mcp_startup.start_mcp_clients_in_background(
        Path("config.json"),
        Path("."),
        ready_with.append,
    )
    elapsed = time.monotonic() - before

    assert started.wait(timeout=1)
    assert elapsed < 0.5
    assert thread.daemon is True
    assert thread.is_alive()
    assert ready_with == []

    release.set()
    thread.join(timeout=1)
    assert ready_with == [manager]


def test_mcp_startup_error_does_not_escape_background_thread(monkeypatch) -> None:
    def _failed_init(config_path: Path, project_root: Path) -> object:
        raise RuntimeError("server timeout")

    ready_with: list[object] = []
    monkeypatch.setattr(mcp_startup, "_init_manager", _failed_init)

    thread = mcp_startup.start_mcp_clients_in_background(
        Path("config.json"),
        Path("."),
        ready_with.append,
    )
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert ready_with == []
