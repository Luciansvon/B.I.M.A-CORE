"""Test hardening URL tunnel + fallback teks buat postingan gambar Threads.

Masalah nyata: postingan gambar gagal 400 ("Media download failed") karena
get_public_tunnel_url ngasih URL tunnel yang basi/mati (quick tunnel rotasi),
dan log-nya kotor ke-capture 'api.trycloudflare.com' (bukan URL tunnel).
"""
import pytest

import core.threads_scheduler as ts
import core.threads_commands as tc


def test_tunnel_url_picks_latest_real_tunnel(tmp_path):
    log = tmp_path / "tunnel-error.log"
    log.write_text(
        "INFO contacting https://api.trycloudflare.com\n"
        "INFO Your quick Tunnel https://shortly-scenarios-pac-ones.trycloudflare.com\n"
        "INFO restarted, new url https://owners-glossary-oops-land.trycloudflare.com\n",
        encoding="utf-8",
    )
    # Ambil tunnel asli TERBARU, bukan api.trycloudflare.com.
    assert ts.get_public_tunnel_url(log) == "https://owners-glossary-oops-land.trycloudflare.com"


def test_tunnel_url_none_when_only_api_noise(tmp_path):
    log = tmp_path / "tunnel-error.log"
    log.write_text("INFO https://api.trycloudflare.com only\n", encoding="utf-8")
    assert ts.get_public_tunnel_url(log) is None


def test_tunnel_url_none_when_log_missing(tmp_path):
    assert ts.get_public_tunnel_url(tmp_path / "nope.log") is None


@pytest.mark.asyncio
async def test_url_is_fetchable_empty_is_false():
    # URL kosong gak usah nyentuh jaringan, langsung False.
    assert await tc.url_is_fetchable("") is False
    assert await tc.url_is_fetchable(None) is False
