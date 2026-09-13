import os
import shutil
from pathlib import Path

import pytest

from tools import file_organizer


def _old_file(path: Path, now: float, age: float = 600) -> None:
    path.write_text("data", encoding="utf-8")
    os.utime(path, (now - age, now - age))


def test_recent_output_is_not_moved(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    now = 2_000_000_000.0
    recent = tmp_path / "recent.pdf"
    old = tmp_path / "old.pdf"
    _old_file(recent, now, age=60)
    _old_file(old, now, age=600)
    monkeypatch.setattr(file_organizer, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(file_organizer.time, "time", lambda: now)

    summary = file_organizer.organize()

    assert recent.exists()
    assert not old.exists()
    assert summary == {"moved": 1, "skipped": 1, "errors": 0}


def test_move_failure_does_not_abort_remaining_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    now = 2_000_000_000.0
    broken = tmp_path / "a_broken.pdf"
    healthy = tmp_path / "b_healthy.pdf"
    _old_file(broken, now)
    _old_file(healthy, now)
    real_move = shutil.move

    def flaky_move(source: str, destination: str) -> str:
        if Path(source).name == broken.name:
            raise PermissionError("locked")
        return real_move(source, destination)

    monkeypatch.setattr(file_organizer, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(file_organizer.time, "time", lambda: now)
    monkeypatch.setattr(file_organizer.shutil, "move", flaky_move)

    summary = file_organizer.organize()

    assert broken.exists()
    assert not healthy.exists()
    assert summary == {"moved": 1, "skipped": 0, "errors": 1}
