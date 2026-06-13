"""Test fix revisi minimal-edit Threads.

Masalah: pas Bima cuma minta ganti emoji, reviser malah nulis ulang seluruh
postingan. Fix-nya nambahin aturan MINIMAL EDIT di prompt apply_smart_revision.
Test ini deterministik (LLM dipalsukan) jadi gak nyentuh jaringan.
"""
import pytest

import core.threads_commands as tc


class _FakeResp:
    def __init__(self, content: str):
        self.content = content


class _FakeLLM:
    """LLM palsu: balas string kosong utk deteksi browsing, draft utk revisi."""

    def __init__(self):
        self.captured: list[str] = []

    def invoke(self, messages):
        sys_content = messages[0].content
        self.captured.append(sys_content)
        if "Analisis apakah feedback" in sys_content:
            return _FakeResp("")  # gak minta browsing baru
        return _FakeResp("<draft>sore sore enaknya kopi susu sambil santai 🗿</draft>")


@pytest.mark.asyncio
async def test_revision_prompt_carries_minimal_edit_rule(monkeypatch):
    fake = _FakeLLM()
    monkeypatch.setattr(tc, "threads_llm", fake)

    draft = "Sore sore enaknya kopi susu sambil santai 😭"
    result = await tc.apply_smart_revision(draft, "ganti emoji jadi 🗿")

    # Prompt revisi (panggilan terakhir) wajib memuat aturan minimal-edit + draf asal.
    revision_prompt = fake.captured[-1]
    assert "MINIMAL EDIT" in revision_prompt
    assert draft in revision_prompt

    # Hasil diekstrak bersih dari tag <draft>...</draft>.
    assert result == "sore sore enaknya kopi susu sambil santai 🗿"
    assert "<draft>" not in result and "</draft>" not in result
