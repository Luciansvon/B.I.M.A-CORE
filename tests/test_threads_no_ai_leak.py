"""Test anti-bocor disclaimer kemampuan AI ke postingan Threads.

Masalah nyata: pas diminta bikin postingan + gambar, LLM teks nyelipin penolakan
"gua gak bisa generate gambar, pake Midjourney/DALL-E/Canva" ke dalam draf.
"""
import core.threads_commands as tc


def test_clean_scrubs_capability_disclaimer():
    raw = (
        "Ayam geprek itu aslinya dari Jogja, tahun 2003 💀\n\n"
        "lu pikir siapa yang paling berjasa? ya ibu warung, bukan influencer.\n\n"
        "⚠️ Soal generate gambar , gua gak bisa bikin atau generate gambar ya. "
        "Gua cuma bisa nulis teks. Coba pake Midjourney, DALL·E, atau Canva AI buat visualnya!"
    )
    out = tc.clean_bima_text(raw)
    # Konten asli postingan tetap utuh
    assert "ayam geprek" in out.lower()
    assert "ibu warung" in out.lower()
    # Disclaimer kemampuan AI hilang total
    for bad in ("midjourney", "dall", "canva", "cuma bisa nulis teks", "soal generate gambar"):
        assert bad not in out.lower(), f"masih bocor: {bad}"


def test_clean_keeps_normal_post_untouched():
    normal = "Sore sore enaknya kopi susu sambil santai 🗿"
    assert tc.clean_bima_text(normal) == normal


def test_strip_image_request_removes_phrase():
    assert "gambar" not in tc._strip_image_request("ayam geprek bikin gambar juga").lower()
    assert "ayam geprek" in tc._strip_image_request("ayam geprek pake gambar").lower()


def test_strip_image_request_keeps_plain_topic():
    assert tc._strip_image_request("dolar naik") == "dolar naik"
