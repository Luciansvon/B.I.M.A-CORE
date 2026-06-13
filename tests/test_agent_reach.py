"""Regression tests untuk tools/agent_reach_tool.XReachTool.

Fokus: jalur fallback gak boleh nge-raise (CrewAI tool wajib return str).
Dulu ada UnboundLocalError karena variabel `e` direferensikan setelah blok
except-nya kelar (Python 3 menghapus nama exception begitu except selesai).
"""
import subprocess
import types
from unittest import mock

import httpx
import pytest

from tools.agent_reach_tool import XReachTool


def _fake_completed(stdout: str) -> types.SimpleNamespace:
    return types.SimpleNamespace(stdout=stdout, stderr="", returncode=0)


def test_fallback_returns_str_when_cli_raises_and_no_rapidapi(monkeypatch):
    """CLI raise + RAPIDAPI_KEY kosong → return string, bukan UnboundLocalError."""
    monkeypatch.setenv("RAPIDAPI_KEY", "")
    with mock.patch("subprocess.run", side_effect=FileNotFoundError("no cli")):
        out = XReachTool()._run("japandi furniture")
    assert isinstance(out, str)
    assert "RAPIDAPI_KEY" in out
    assert "no cli" in out  # pesan error CLI ikut terbawa


def test_fallback_returns_str_when_cli_empty_and_no_rapidapi(monkeypatch):
    """CLI sukses tapi kosong (gak raise) + RAPIDAPI_KEY kosong → tetap return string.

    Ini menguji cli_err default — dulu jalur ini UnboundLocalError karena `e`
    gak pernah ke-assign.
    """
    monkeypatch.setenv("RAPIDAPI_KEY", "")
    with mock.patch("subprocess.run", return_value=_fake_completed("[]")):
        out = XReachTool()._run("ai agent 2026")
    assert isinstance(out, str)
    assert "RAPIDAPI_KEY" in out


def test_fallback_returns_str_when_all_paths_fail(monkeypatch):
    """CLI raise + kedua RapidAPI endpoint raise → return ringkasan error, bukan raise."""
    monkeypatch.setenv("RAPIDAPI_KEY", "dummy-key")
    with mock.patch("subprocess.run", side_effect=FileNotFoundError("no cli")), \
            mock.patch("httpx.get", side_effect=httpx.ConnectError("boom")):
        out = XReachTool()._run("desk setup")
    assert isinstance(out, str)
    assert "Gagal scrape" in out
    assert "no cli" in out  # Error CLI tetap dilaporkan, bukan UnboundLocalError
