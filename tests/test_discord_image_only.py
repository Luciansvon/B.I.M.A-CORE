import pytest

from core.discord_attachment_policy import (
    has_supported_image_attachment,
    image_only_prompt,
)
from core.langgraph_nodes.intent_classifier import classify_intent


def test_supported_image_attachment_is_accepted_without_caption() -> None:
    assert has_supported_image_attachment(["photo.PNG"])
    assert has_supported_image_attachment(["design.webp"])


def test_non_image_attachment_does_not_bypass_empty_message_gate() -> None:
    assert not has_supported_image_attachment(["report.pdf"])
    assert not has_supported_image_attachment(["malware.exe"])


def test_image_only_prompt_routes_directly_to_visual() -> None:
    prompt = image_only_prompt("")
    teams, confidence, label = classify_intent(prompt, has_attachment=True)

    assert prompt == "analisis gambar ini"
    assert teams == ["visual"]
    assert confidence >= 0.85
    assert label == "analisis attachment"


def test_existing_caption_is_preserved() -> None:
    assert image_only_prompt("cek detail sambungannya") == "cek detail sambungannya"


@pytest.mark.asyncio
async def test_image_only_visual_node_calls_analyzer_without_crewai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.langgraph_nodes import visual as visual_module

    calls: list[str] = []

    class FakeAnalyzer:
        def run(self, image_path: str) -> str:
            calls.append(image_path)
            return "hasil vision"

    class ForbiddenCrew:
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise AssertionError("CrewAI tidak boleh dipanggil untuk image-only")

    monkeypatch.setattr(visual_module, "ImageAnalyzerTool", FakeAnalyzer)
    monkeypatch.setattr(visual_module, "Crew", ForbiddenCrew)

    result = await visual_module.visual_node(
        {
            "user_request": (
                "analisis gambar ini\n\n[ATTACHMENT] https://cdn.example/image.png"
                "\n\n[FILE_PATHS] /tmp/discord_image.png"
            ),
            "attachment_paths": ["/tmp/discord_image.png"],
            "realtime_context": "",
        }
    )

    assert calls == ["/tmp/discord_image.png"]
    assert result["messages"][0].content == "hasil vision"
    assert result["is_finished"] is True
