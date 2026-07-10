from pathlib import Path

import pytest

from core import tts


@pytest.mark.asyncio
async def test_f5_uses_isolated_voice_python(monkeypatch, tmp_path: Path) -> None:
    worker_python = tmp_path / "voice-python"
    worker_python.touch()
    output_wav = tmp_path / "voice.wav"
    captured: dict = {}

    class FakeProcess:
        returncode = 0

        async def communicate(self):
            output_wav.write_bytes(b"RIFF")
            return b"", b""

    async def fake_create_subprocess_exec(*command, **kwargs):
        captured["command"] = command
        return FakeProcess()

    monkeypatch.setattr(tts, "_voice_worker_python", lambda: worker_python)
    monkeypatch.setattr(tts.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    assert await tts._synthesize_f5("halo", output_wav) is True
    assert captured["command"][0] == str(worker_python)


def test_voice_worker_manifest_does_not_include_browser_or_crewai() -> None:
    project_root = Path(__file__).resolve().parent.parent
    manifest = (project_root / "services" / "voice" / "pyproject.toml").read_text(
        encoding="utf-8"
    )

    assert "browser-use" not in manifest.lower()
    assert "crewai" not in manifest.lower()
