from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from core.arsip_commands import HELP_TEXT, handle_arsip_command
from teams import t3_arsip


@pytest.mark.asyncio
async def test_index_reports_incremental_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []

    def fake_index_vault(full_rebuild: bool = False) -> str:
        calls.append(full_rebuild)
        return (
            "SUCCESS|Index incremental selesai: "
            "0 file baru, 0 file diupdate, 54 file unchanged."
        )

    monkeypatch.setattr(t3_arsip, "index_vault", fake_index_vault)
    message = AsyncMock()

    handled = await handle_arsip_command(message, "index")

    assert handled is True
    assert calls == [False]
    assert "Index incremental selesai" in message.reply.await_args_list[-1].args[0]
    assert "SUCCESS|" not in message.reply.await_args_list[-1].args[0]


@pytest.mark.asyncio
async def test_reindex_full_requests_full_rebuild(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []

    def fake_index_vault(full_rebuild: bool = False) -> str:
        calls.append(full_rebuild)
        return "SUCCESS|Full rebuild selesai: 897 chunk dari 54 catatan."

    monkeypatch.setattr(t3_arsip, "index_vault", fake_index_vault)
    message = AsyncMock()

    handled = await handle_arsip_command(message, "reindex --full")

    assert handled is True
    assert calls == [True]
    assert "Full rebuild selesai" in message.reply.await_args_list[-1].args[0]


def test_help_distinguishes_index_linking_and_full_rebuild() -> None:
    assert "!arsip index" in HELP_TEXT
    assert "incremental" in HELP_TEXT
    assert "!arsip reindex --full" in HELP_TEXT
    assert "!arsip hubungkan" in HELP_TEXT


def test_vault_index_tool_describes_incremental_sync() -> None:
    assert "incremental" in t3_arsip.VaultIndexTool().description.lower()


def test_incremental_index_returns_truthful_skip_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    note = tmp_path / "Catatan.md"
    note.write_text("# Catatan\n\nIsi.", encoding="utf-8")

    class FakeTable:
        pass

    class FakeDB:
        def open_table(self, name: str) -> FakeTable:
            assert name == "vault"
            return FakeTable()

    monkeypatch.setattr(t3_arsip, "OBSIDIAN_PATH", str(tmp_path))
    monkeypatch.setattr(
        t3_arsip,
        "_read_existing_mtime",
        lambda: {str(note): note.stat().st_mtime},
    )
    monkeypatch.setattr(t3_arsip, "_table_exists", lambda: True)
    monkeypatch.setattr(t3_arsip, "_get_db", lambda: FakeDB())
    monkeypatch.setattr(t3_arsip, "_drop_legacy_table_if_needed", lambda: None)
    monkeypatch.setattr(t3_arsip, "_rebuild_bm25_index", lambda: None)

    result = t3_arsip._index_vault_unlocked()

    assert result == (
        "SUCCESS|Index incremental selesai: "
        "0 file baru, 0 file diupdate, 1 file unchanged."
    )
