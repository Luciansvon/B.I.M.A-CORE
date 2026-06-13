"""Tests untuk perbaikan loop approval komentar Threads & LRU context store.

Bug yang dicegah:
  - Komentar yang ditolak/timeout gak pernah ditandai 'replied' → scanner (tiap
    5 menit) nge-prompt komentar yang sama selamanya. Fix: simpan reply_id di
    setiap keputusan terminal (termasuk tolak/timeout).
  - _draft_contexts dict tumbuh tanpa batas → memory leak. Fix: LRU bounded.
"""
from unittest import mock

import pytest

import core.threads_commands as tc


def test_bounded_context_store_evicts_oldest():
    store = tc._BoundedContextStore(max_size=3)
    store["a"] = "1"
    store["b"] = "2"
    store["c"] = "3"
    store["d"] = "4"  # harus buang "a" (paling lama)
    assert "a" not in store
    assert list(store.keys()) == ["b", "c", "d"]
    assert len(store) == 3


def test_bounded_context_store_reinsert_refreshes_lru():
    store = tc._BoundedContextStore(max_size=2)
    store["a"] = "1"
    store["b"] = "2"
    store["a"] = "1b"  # akses ulang "a" → jadi paling baru
    store["c"] = "3"   # harus buang "b", bukan "a"
    assert "b" not in store
    assert "a" in store and store["a"] == "1b"


def test_module_draft_contexts_is_bounded():
    # _draft_contexts global harus instance bounded store, bukan dict biasa.
    assert isinstance(tc._draft_contexts, tc._BoundedContextStore)


@pytest.mark.asyncio
async def test_rejected_comment_is_marked_replied(monkeypatch):
    """Saat approval ditolak/timeout (approved=False), reply_id WAJIB disimpan
    supaya scanner gak nge-prompt komentar yang sama berulang."""
    saved = []

    monkeypatch.setattr(tc, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "dummy-token")
    monkeypatch.setattr(tc, "_save_replied_comment", lambda rid: saved.append(rid))
    monkeypatch.setattr(tc, "evaluate_auto_reply",
                        mock.AsyncMock(return_value=(False, "")))
    monkeypatch.setattr(tc, "generate_bima_draft",
                        mock.AsyncMock(return_value="draf balasan"))
    # request_permission diimpor ke namespace threads_commands
    monkeypatch.setattr(tc, "request_permission", mock.AsyncMock(return_value=False))
    # cegah panggilan jaringan ke agentmemory
    monkeypatch.setattr("core.agentmemory_client.recall",
                        mock.AsyncMock(return_value=None), raising=False)

    result = await tc.reply_to_comment_flow(
        reply_id="comment_123",
        reply_text="halo bro keren nih",
        reply_username="someuser",
        post_text="postingan gua",
        user_id="42",
        client=None,
    )

    assert "comment_123" in saved, "reply_id harus ditandai replied walau ditolak"
    assert "dibatalkan" in result.lower()


@pytest.mark.asyncio
async def test_spam_comment_is_marked_replied(monkeypatch):
    """Komentar spam/toxic langsung di-skip dan ditandai replied (gak re-prompt)."""
    saved = []
    monkeypatch.setattr(tc, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "dummy-token")
    monkeypatch.setattr(tc, "_save_replied_comment", lambda rid: saved.append(rid))

    result = await tc.reply_to_comment_flow(
        reply_id="spam_1",
        reply_text="PROMO MURAH ready stock klik link wa sekarang",
        reply_username="spammer",
        post_text="postingan gua",
        user_id="42",
        client=None,
    )

    assert "spam_1" in saved
    assert "spam" in result.lower() or "toxic" in result.lower()
