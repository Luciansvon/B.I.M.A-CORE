"""Tests for the lightweight Anisa operational snapshot."""

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.operational_status import (
    collect_snapshot,
    determine_overall,
    is_snapshot_fresh,
    sanitize_error,
    write_snapshot_atomic,
)


def test_overall_priority():
    assert determine_overall(["healthy", "degraded"]) == "degraded"
    assert determine_overall(["degraded", "down"]) == "down"


def test_snapshot_stale_after_90_seconds():
    now = datetime.now(timezone.utc)
    fresh = {"updated_at": (now - timedelta(seconds=89)).isoformat()}
    stale = {"updated_at": (now - timedelta(seconds=91)).isoformat()}

    assert is_snapshot_fresh(fresh, now=now)
    assert not is_snapshot_fresh(stale, now=now)


def test_error_is_sanitized():
    text = "Authorization: Bearer secret-token OPENROUTER_API_KEY=secret"

    result = sanitize_error(text)

    assert "secret-token" not in result
    assert "OPENROUTER_API_KEY=secret" not in result


def test_atomic_write_creates_valid_json(tmp_path):
    target = tmp_path / "anisa_status.json"

    write_snapshot_atomic(target, {"schema_version": 1})

    assert json.loads(target.read_text(encoding="utf-8"))["schema_version"] == 1
    assert not list(tmp_path.glob("*.tmp"))


def test_collect_snapshot_keeps_partial_results_when_probe_fails(tmp_path):
    snapshot = collect_snapshot(
        project_root=tmp_path,
        pm2_reader=lambda: {"anisa-v3": {"status": "online"}},
        metrics_reader=lambda: {
            "cpu_percent": 10.0,
            "ram_percent": 20.0,
            "disk_percent": 30.0,
        },
        health_reader=lambda: (_ for _ in ()).throw(TimeoutError()),
        git_reader=lambda: {"commit": "abc1234", "dirty": False},
        error_reader=lambda: None,
    )

    assert snapshot["health"]["backend"] == "unreachable"
    assert snapshot["overall"] == "down"
    assert snapshot["services"]["anisa-v3"]["status"] == "online"


def test_status_collector_supports_one_shot_cli():
    project_root = Path(__file__).resolve().parent.parent

    result = subprocess.run(
        [sys.executable, "scripts/status_collector.py", "--once"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert (project_root / "runtime" / "anisa_status.json").is_file()
