import json
from pathlib import Path
from unittest.mock import patch

import pytest

from teams import t6_lifestyle
from teams.t6_lifestyle import ScheduleManagerTool


@pytest.fixture
def schedule_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    fake_module = tmp_path / "teams" / "t6_lifestyle.py"
    fake_module.parent.mkdir()
    monkeypatch.setattr(t6_lifestyle, "__file__", str(fake_module))
    return tmp_path / "vault_index" / "schedule.json"


def _seed(path: Path, items: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items), encoding="utf-8")


def test_delete_unique_schedule_requires_and_honors_approval(
    schedule_path: Path,
) -> None:
    _seed(schedule_path, ["2026-07-13 Meeting klien", "2026-07-14 Kuliah"])
    with patch("core.permission_gate.check_permission_sync", return_value=True) as gate:
        result = ScheduleManagerTool()._run("delete|meeting klien")

    assert "dihapus" in result.lower()
    assert json.loads(schedule_path.read_text(encoding="utf-8")) == [
        "2026-07-14 Kuliah"
    ]
    gate.assert_called_once()


def test_delete_ambiguous_schedule_does_not_mutate(
    schedule_path: Path,
) -> None:
    original = ["Meeting klien A", "Meeting klien B"]
    _seed(schedule_path, original)
    with patch("core.permission_gate.check_permission_sync") as gate:
        result = ScheduleManagerTool()._run("delete|meeting")

    assert "lebih dari satu" in result.lower()
    assert json.loads(schedule_path.read_text(encoding="utf-8")) == original
    gate.assert_not_called()


@pytest.mark.parametrize("command", ["delete|meeting", "clear|"])
def test_destructive_schedule_action_denial_does_not_mutate(
    schedule_path: Path,
    command: str,
) -> None:
    original = ["Meeting klien", "Kuliah"]
    _seed(schedule_path, original)
    with patch("core.permission_gate.check_permission_sync", return_value=False):
        result = ScheduleManagerTool()._run(command)

    assert "ditolak" in result.lower()
    assert json.loads(schedule_path.read_text(encoding="utf-8")) == original


@pytest.mark.parametrize("command", ["add|", "delete|", "add", "delete"])
def test_schedule_action_requires_nonempty_data(
    schedule_path: Path,
    command: str,
) -> None:
    result = ScheduleManagerTool()._run(command)

    assert "format" in result.lower()
