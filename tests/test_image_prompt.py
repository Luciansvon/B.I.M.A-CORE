"""Tests untuk core/langgraph_nodes/image_prompt.py + _craft_image_prompt (seniman).

Bagian pure (parse/scrub/system prompt) di-test tanpa LLM.
Bagian _craft_image_prompt di-test dengan seniman_llm yang di-monkeypatch.
"""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.langgraph_nodes.image_prompt import (
    SLOP_TERMS,
    build_system_prompt,
    parse_crafted,
    scrub_slop,
)


# ---------- parse_crafted ----------

def test_parse_crafted_casual_tag():
    is_casual, prompt = parse_crafted("CASUAL|a warm plate of nasi goreng on a wooden table")
    assert is_casual is True
    assert prompt == "a warm plate of nasi goreng on a wooden table"


def test_parse_crafted_clean_tag():
    is_casual, prompt = parse_crafted("CLEAN|studio shot of a mechanical keyboard")
    assert is_casual is False
    assert prompt == "studio shot of a mechanical keyboard"


def test_parse_crafted_tag_case_insensitive_and_padded():
    is_casual, prompt = parse_crafted("  clean | studio shot ")
    assert is_casual is False
    assert prompt == "studio shot"


def test_parse_crafted_no_tag_falls_back_to_casual():
    is_casual, prompt = parse_crafted("just a plain prompt without tag")
    assert is_casual is True
    assert prompt == "just a plain prompt without tag"


def test_parse_crafted_unknown_tag_treated_as_prompt():
    is_casual, prompt = parse_crafted("WEIRD|something")
    assert is_casual is True
    assert prompt == "WEIRD|something"


def test_parse_crafted_strips_quotes_and_handles_empty():
    assert parse_crafted('"CASUAL|foo"') == (True, "foo")
    assert parse_crafted("") == (True, "")
    assert parse_crafted(None) == (True, "")


# ---------- scrub_slop ----------

def test_scrub_slop_removes_each_term():
    for term in SLOP_TERMS:
        out = scrub_slop(f"a photo of a chair, {term}, natural light")
        assert term.lower() not in out.lower()
        assert "a photo of a chair" in out
        assert "natural light" in out


def test_scrub_slop_case_insensitive():
    out = scrub_slop("MASTERPIECE, Ultra-Detailed photo of a table, 8K")
    lower = out.lower()
    assert "masterpiece" not in lower
    assert "ultra-detailed" not in lower
    assert "8k" not in lower
    assert "photo of a table" in out


def test_scrub_slop_cleans_leftover_commas_and_spaces():
    out = scrub_slop("a teak cabinet, masterpiece, 8k, in a workshop")
    assert ",," not in out
    assert "  " not in out
    assert out == "a teak cabinet, in a workshop"


def test_scrub_slop_word_boundary_no_false_positive():
    # '4k' gak boleh kena di dalam kata lain; 'cgi' jangan makan kata lain
    out = scrub_slop("a 14kg oak slab near the magic garden")
    assert "14kg" in out
    assert "magic garden" in out


def test_scrub_slop_preserves_clean_prompt():
    prompt = (
        "A candid smartphone photo of a carpenter sanding a teak table in a "
        "cluttered Jepara workshop, soft overcast light from the left, "
        "slight motion blur on his hand, subtle film grain."
    )
    assert scrub_slop(prompt) == prompt


def test_scrub_slop_empty_passthrough():
    assert scrub_slop("") == ""


# ---------- build_system_prompt ----------

def test_build_system_prompt_txt2img_markers():
    sys_prompt = build_system_prompt(has_ref=False)
    assert "CASUAL|" in sys_prompt and "CLEAN|" in sys_prompt
    assert "NARATIF" in sys_prompt
    assert "lensa" in sys_prompt.lower()
    assert "DILARANG" in sys_prompt
    assert "oversaturated" in sys_prompt
    # variasi resep biar output gak samey
    assert "VARIASIKAN" in sys_prompt


def test_build_system_prompt_img2img_focuses_on_change():
    sys_prompt = build_system_prompt(has_ref=True)
    assert "PERUBAHAN" in sys_prompt
    assert "referensi" in sys_prompt
    assert "CASUAL|" in sys_prompt and "CLEAN|" in sys_prompt
    assert sys_prompt != build_system_prompt(has_ref=False)


# ---------- _craft_image_prompt (mocked LLM) ----------

def _fake_llm(reply: str):
    llm = mock.Mock()
    llm.invoke.return_value = SimpleNamespace(content=reply)
    return llm


@pytest.mark.asyncio
async def test_craft_long_request_still_crafted(monkeypatch):
    """Request >120 char dulu di-skip — sekarang wajib tetep di-craft."""
    import core.langgraph_nodes.seniman as sn

    long_request = (
        "bikin gambar meja kerja kayu jati dengan laptop, kopi, dan serutan kayu "
        "berserakan, suasana pagi di bengkel jepara, ada cahaya masuk dari jendela "
        "sebelah kiri dan sedikit debu di udara"
    )
    assert len(long_request) > 120
    monkeypatch.setattr(sn, "seniman_llm", _fake_llm("CASUAL|a candid photo of a teak desk"))
    monkeypatch.delenv("IMAGE_GEN_STYLE_PREFIX", raising=False)

    out = await sn._craft_image_prompt(long_request)
    assert out == "a candid photo of a teak desk"
    assert sn.seniman_llm.invoke.call_count == 1


@pytest.mark.asyncio
async def test_craft_single_llm_call_no_second_classifier(monkeypatch):
    import core.langgraph_nodes.seniman as sn

    monkeypatch.setattr(sn, "seniman_llm", _fake_llm("CLEAN|studio shot of a keyboard"))
    monkeypatch.delenv("IMAGE_GEN_STYLE_PREFIX", raising=False)

    out = await sn._craft_image_prompt("keyboard mechanical")
    assert out == "studio shot of a keyboard"
    assert sn.seniman_llm.invoke.call_count == 1


@pytest.mark.asyncio
async def test_craft_style_prefix_only_for_casual(monkeypatch):
    import core.langgraph_nodes.seniman as sn

    monkeypatch.setenv("IMAGE_GEN_STYLE_PREFIX", "shot on Kodak Portra 400")

    monkeypatch.setattr(sn, "seniman_llm", _fake_llm("CASUAL|warung coffee on a rainy street"))
    out = await sn._craft_image_prompt("kopi di warung")
    assert out.startswith("shot on Kodak Portra 400, ")

    monkeypatch.setattr(sn, "seniman_llm", _fake_llm("CLEAN|studio shot of a gpu"))
    out = await sn._craft_image_prompt("gpu render")
    assert "Kodak" not in out


@pytest.mark.asyncio
async def test_craft_scrubs_slop_from_llm_output(monkeypatch):
    import core.langgraph_nodes.seniman as sn

    monkeypatch.setattr(
        sn, "seniman_llm",
        _fake_llm("CASUAL|a wooden chair, masterpiece, 8k, in morning light"),
    )
    monkeypatch.delenv("IMAGE_GEN_STYLE_PREFIX", raising=False)

    out = await sn._craft_image_prompt("kursi kayu")
    assert "masterpiece" not in out.lower()
    assert "8k" not in out.lower()
    assert "wooden chair" in out


@pytest.mark.asyncio
async def test_craft_falls_back_to_base_on_llm_error(monkeypatch):
    import core.langgraph_nodes.seniman as sn

    llm = mock.Mock()
    llm.invoke.side_effect = RuntimeError("boom")
    monkeypatch.setattr(sn, "seniman_llm", llm)

    out = await sn._craft_image_prompt("kursi kayu")
    assert out == "kursi kayu"


@pytest.mark.asyncio
async def test_craft_empty_request_passthrough(monkeypatch):
    import core.langgraph_nodes.seniman as sn

    llm = mock.Mock()
    monkeypatch.setattr(sn, "seniman_llm", llm)

    assert await sn._craft_image_prompt("") == ""
    assert await sn._craft_image_prompt("   ") == ""
    llm.invoke.assert_not_called()
