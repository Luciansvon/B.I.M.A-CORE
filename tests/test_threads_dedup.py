"""Tests untuk perbaikan loop approval komentar Threads.

Bug yang dicegah:
  - Komentar yang ditolak/timeout gak pernah ditandai 'replied' → scanner (tiap
    5 menit) nge-prompt komentar yang sama selamanya. Fix: simpan reply_id di
    setiap keputusan terminal (termasuk tolak/timeout).
  - Konteks draf global bisa bocor antar-request → jangan simpan global.
"""
from unittest import mock

import pytest

import core.threads_commands as tc


def test_module_has_no_cross_request_draft_context_store():
    assert not hasattr(tc, "_draft_contexts")


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
    monkeypatch.setattr(
        tc,
        "request_permission_with_revision",
        mock.AsyncMock(return_value=(False, None)),
    )
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
