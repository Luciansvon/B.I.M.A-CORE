"""Unit tests untuk tools/image_gen_tool.py — 9Router integration."""
import base64
from unittest import mock
from pathlib import Path
import pytest

from tools.image_gen_tool import ImageGenTool
from core.model_router import get_router_credentials


def test_image_gen_empty_prompt():
    tool = ImageGenTool()
    res = tool._run("")
    assert res.startswith("FAILED|Prompt kosong")


def test_image_gen_missing_api_key(monkeypatch):
    monkeypatch.delenv("NINEROUTER_API_KEY", raising=False)
    monkeypatch.delenv("ROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    tool = ImageGenTool()
    res = tool._run("gambar mobil terbang")
    assert res.startswith("FAILED|API Key router")


def test_image_gen_9router_success_b64(monkeypatch):
    monkeypatch.setenv("NINEROUTER_API_KEY", "dummy-9router-key")
    monkeypatch.setenv("NINEROUTER_BASE_URL", "http://127.0.0.1:20128/v1")

    # Mock OpenAI client images.generate
    dummy_b64 = base64.b64encode(b"FAKE_IMAGE_BYTES_12345").decode()

    mock_resp = mock.Mock()
    mock_item = mock.Mock()
    mock_item.b64_json = dummy_b64
    mock_item.url = None
    mock_resp.data = [mock_item]

    mock_client = mock.Mock()
    mock_client.images.generate.return_value = mock_resp

    monkeypatch.setattr("openai.OpenAI", mock.Mock(return_value=mock_client))

    tool = ImageGenTool()
    res = tool._run("kucing lucu")

    assert res.startswith("SUCCESS|")
    parts = res.split("|")
    saved_path = Path(parts[1])
    assert saved_path.exists()
    assert saved_path.read_bytes() == b"FAKE_IMAGE_BYTES_12345"
    assert "Gambar siap" in parts[2]

    # Cleanup test output
    saved_path.unlink(missing_ok=True)


def test_image_gen_9router_api_error(monkeypatch):
    monkeypatch.setenv("NINEROUTER_API_KEY", "dummy-9router-key")
    monkeypatch.setenv("NINEROUTER_BASE_URL", "http://127.0.0.1:20128/v1")

    mock_client = mock.Mock()
    mock_client.images.generate.side_effect = RuntimeError("Connection refused")

    monkeypatch.setattr("openai.OpenAI", mock.Mock(return_value=mock_client))

    tool = ImageGenTool()
    res = tool._run("robot tempur")
    assert res.startswith("FAILED|Image API call error:")
    assert "Connection refused" in res


def test_get_router_credentials():
    key, url = get_router_credentials()
    assert url.startswith("http")
    assert "20128" in url or "9router" in url.lower()
