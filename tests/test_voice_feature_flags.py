from pathlib import Path

import pytest


def test_stt_disabled_by_default_does_not_load_model(monkeypatch, tmp_path):
    from core import stt

    monkeypatch.delenv("ENABLE_STT", raising=False)
    monkeypatch.setattr(stt, "_get_model", lambda: pytest.fail("STT model loaded"))
    audio = tmp_path / "voice.ogg"
    audio.write_bytes(b"audio")

    assert stt.transcribe_audio(str(audio)) == ""


@pytest.mark.asyncio
async def test_tts_disabled_by_default_does_not_start_worker(monkeypatch):
    from core import tts

    monkeypatch.delenv("ENABLE_TTS", raising=False)

    async def fail_worker(_text: str, _output: Path) -> bool:
        pytest.fail("TTS worker started")

    monkeypatch.setattr(tts, "_synthesize_f5", fail_worker)

    assert await tts.synthesize_voice("halo") is None

