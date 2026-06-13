"""Test hosting gambar berlapis (Catbox -> Discord CDN -> teks) buat Threads.

Ganti ketergantungan Cloudflare tunnel yang rapuh. Test ini deterministik —
provider di-mock, gak nyentuh jaringan.
"""
from unittest import mock

import pytest

import core.image_host as ih


@pytest.mark.asyncio
async def test_host_returns_none_when_file_missing(tmp_path):
    assert await ih.host_image_publicly(tmp_path / "nope.png") is None


@pytest.mark.asyncio
async def test_host_uses_catbox_first(tmp_path, monkeypatch):
    f = tmp_path / "img.png"
    f.write_bytes(b"x")
    monkeypatch.setattr(ih, "upload_to_catbox",
                        mock.AsyncMock(return_value="https://files.catbox.moe/a.png"))
    monkeypatch.setattr(ih, "upload_to_discord",
                        mock.AsyncMock(return_value="https://cdn.discordapp.com/x.png"))
    monkeypatch.setattr(ih, "_verify", mock.AsyncMock(return_value=True))

    url = await ih.host_image_publicly(f, client=object(), fallback_user_id="1")
    assert url == "https://files.catbox.moe/a.png"
    ih.upload_to_discord.assert_not_called()  # Catbox sukses → Discord gak dipanggil


@pytest.mark.asyncio
async def test_host_falls_back_to_discord(tmp_path, monkeypatch):
    f = tmp_path / "img.png"
    f.write_bytes(b"x")
    monkeypatch.setattr(ih, "upload_to_catbox", mock.AsyncMock(return_value=None))
    monkeypatch.setattr(ih, "upload_to_discord",
                        mock.AsyncMock(return_value="https://cdn.discordapp.com/x.png"))
    monkeypatch.setattr(ih, "_verify", mock.AsyncMock(return_value=True))

    url = await ih.host_image_publicly(f, client=object(), fallback_user_id="1")
    assert url == "https://cdn.discordapp.com/x.png"


@pytest.mark.asyncio
async def test_host_skips_dead_catbox_url_then_discord(tmp_path, monkeypatch):
    # Catbox balas URL tapi gak kejangkau → harus lanjut ke Discord.
    f = tmp_path / "img.png"
    f.write_bytes(b"x")
    monkeypatch.setattr(ih, "upload_to_catbox",
                        mock.AsyncMock(return_value="https://files.catbox.moe/dead.png"))
    monkeypatch.setattr(ih, "upload_to_discord",
                        mock.AsyncMock(return_value="https://cdn.discordapp.com/x.png"))

    async def fake_verify(url):
        return "discord" in url  # catbox dead, discord ok

    monkeypatch.setattr(ih, "_verify", fake_verify)
    url = await ih.host_image_publicly(f, client=object(), fallback_user_id="1")
    assert url == "https://cdn.discordapp.com/x.png"


@pytest.mark.asyncio
async def test_host_returns_none_when_all_fail(tmp_path, monkeypatch):
    f = tmp_path / "img.png"
    f.write_bytes(b"x")
    monkeypatch.setattr(ih, "upload_to_catbox", mock.AsyncMock(return_value=None))
    monkeypatch.setattr(ih, "upload_to_discord", mock.AsyncMock(return_value=None))

    url = await ih.host_image_publicly(f, client=object(), fallback_user_id="1")
    assert url is None
