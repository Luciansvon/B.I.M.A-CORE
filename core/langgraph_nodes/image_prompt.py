"""Image prompt crafting — photographer-brief style + anti-slop guard.

Dipakai `seniman.py` (_craft_image_prompt) buat ekspand request user jadi
prompt naratif ala fotografer, lalu scrub sisa keyword slop dari output LLM.

Riset dasar (Jul 2026):
- Google DeepMind Nano Banana prompt guide: deskripsi naratif satu adegan
  (subjek + setting + action + komposisi + cahaya) >> daftar keyword.
- Sweet spot 2-4 kalimat (~40-90 kata); kamera/lensa spesifik ("85mm f/1.4")
  adalah sinyal photorealism paling kuat.
- Anti AI-look: larang quality-keyword spam (masterpiece/8k/ultra-detailed),
  minta tekstur natural (visible pores, matte) + 1-2 imperfeksi natural,
  warna jangan oversaturated, variasikan resep antar-request.
"""
from __future__ import annotations

import re

# Keyword spam yang justru men-trigger gaya "AI slop" di image model modern.
# Ini safety net deterministik — larangan utamanya udah ada di system prompt,
# tapi LLM kecil kadang tetep bocor. Hanya frasa teknis yang aman dihapus
# tanpa merusak kalimat (adjective umum kayak "stunning" diserahkan ke LLM).
SLOP_TERMS: tuple[str, ...] = (
    "hyperrealistic",
    "hyper-realistic",
    "hyper realistic",
    "ultra-realistic",
    "ultra realistic",
    "ultra-detailed",
    "ultra detailed",
    "masterpiece",
    "award-winning",
    "award winning",
    "trending on artstation",
    "unreal engine",
    "octane render",
    "3d render",
    "cgi",
    "8k",
    "4k",
    "hdr",
)

_SLOP_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(t) for t in SLOP_TERMS) + r")\b",
    re.IGNORECASE,
)

_TXT2IMG_SYSTEM = (
    "Kamu prompt-engineer image generation yang menulis seperti fotografer profesional "
    "menulis brief pemotretan.\n\n"
    "LANGKAH 1 — Klasifikasikan request user:\n"
    "- CASUAL: keseharian (makanan, kopi, jalanan, kamar, workshop, orang candid, suasana rumah)\n"
    "- CLEAN: tech/profesional (gadget, produk premium, UI/UX, hardware, setup rapi, infografis)\n\n"
    "LANGKAH 2 — Tulis prompt final dalam Bahasa Inggris sebagai DESKRIPSI NARATIF satu adegan "
    "(2-4 kalimat, 40-90 kata). BUKAN daftar keyword. Wajib mencakup:\n"
    "- Subjek dengan detail material/tekstur/kondisi yang spesifik\n"
    "- Setting dan apa yang sedang terjadi\n"
    "- Komposisi/framing (angle, jarak, off-center boleh)\n"
    "- Kamera + lensa spesifik (contoh: '35mm f/1.8', '85mm portrait lens', 'smartphone camera')\n"
    "- Cahaya: sumber + arah + kualitas (contoh: 'soft overcast light from a window on the left')\n"
    "- 1-2 imperfeksi natural (slight motion blur, uneven lighting, subtle film grain, "
    "background clutter, fingerprints, dust)\n\n"
    "Gaya per kategori:\n"
    "- CASUAL → candid snapshot: smartphone camera atau 35mm film (Kodak Portra 400 / Fujifilm "
    "Superia), pencahayaan natural tidak merata, framing santai\n"
    "- CLEAN → studio product photography: softbox lighting, permukaan matte, sharp focus, "
    "background minimalis\n\n"
    "VARIASIKAN resep tiap request — ganti-ganti waktu (golden hour, overcast, siang terik, "
    "indoor malam), arah cahaya, dan angle. Jangan pakai formula yang sama terus.\n\n"
    "DILARANG memakai kata/frasa berikut (bikin hasil keliatan AI): hyperrealistic, masterpiece, "
    "8k, 4k, HDR, ultra-detailed, ultra-realistic, award-winning, stunning, breathtaking, "
    "perfect, flawless, pristine, 3D render, CGI, unreal engine, octane, trending on artstation.\n"
    "Kalau ada manusia: sebut 'natural skin texture, visible pores' — jangan smooth/airbrushed.\n"
    "Warna: natural, tidak oversaturated.\n\n"
    "Output HANYA satu baris dengan format: CASUAL|<prompt> atau CLEAN|<prompt>. "
    "No preamble, no quotes."
)

_IMG2IMG_SYSTEM = (
    "Kamu prompt-engineer untuk image-to-image model. User kasih gambar referensi + request "
    "perubahan. Kamu menulis seperti fotografer profesional menulis brief retouch/reshoot.\n\n"
    "LANGKAH 1 — Klasifikasikan request user:\n"
    "- CASUAL: keseharian (makanan, kopi, jalanan, kamar, workshop, orang candid, suasana rumah)\n"
    "- CLEAN: tech/profesional (gadget, produk premium, UI/UX, hardware, setup rapi, infografis)\n\n"
    "LANGKAH 2 — Tulis prompt final dalam Bahasa Inggris (2-4 kalimat, 40-90 kata) yang FOKUS "
    "PADA PERUBAHAN dari gambar referensi, sambil mempertahankan identitas subjek, karakter "
    "cahaya, dan tekstur asli referensi. Sebut eksplisit apa yang berubah dan apa yang "
    "dipertahankan. Pertahankan tekstur natural (visible pores, material grain) — jangan "
    "smooth/airbrushed, warna jangan oversaturated.\n\n"
    "DILARANG memakai kata/frasa berikut: hyperrealistic, masterpiece, 8k, 4k, HDR, "
    "ultra-detailed, ultra-realistic, award-winning, stunning, breathtaking, perfect, flawless, "
    "pristine, 3D render, CGI, unreal engine, octane, trending on artstation.\n\n"
    "Output HANYA satu baris dengan format: CASUAL|<prompt> atau CLEAN|<prompt>. "
    "No preamble, no quotes."
)


def build_system_prompt(has_ref: bool = False) -> str:
    """System prompt buat prompt-expander LLM (txt2img atau img2img)."""
    return _IMG2IMG_SYSTEM if has_ref else _TXT2IMG_SYSTEM


def parse_crafted(raw: str) -> tuple[bool, str]:
    """Parse output LLM `CASUAL|<prompt>` / `CLEAN|<prompt>` → (is_casual, prompt).

    Fallback: kalau tag gak ada / gak dikenal, treat seluruh raw sebagai prompt
    dengan is_casual=True (perilaku default lama).
    """
    cleaned = (raw or "").strip().strip('"').strip("'")
    if "|" in cleaned:
        tag, rest = cleaned.split("|", 1)
        tag = tag.strip().upper()
        if tag == "CASUAL":
            return True, rest.strip()
        if tag == "CLEAN":
            return False, rest.strip()
    return True, cleaned


def scrub_slop(prompt: str) -> str:
    """Hapus sisa keyword slop dari prompt + rapikan koma/spasi bekas hapusan."""
    if not prompt:
        return prompt
    scrubbed = _SLOP_RE.sub("", prompt)
    # Rapikan bekas hapusan: ", , " / spasi dobel / koma gantung
    scrubbed = re.sub(r"\s*,\s*(?=,)", "", scrubbed)
    scrubbed = re.sub(r"\s{2,}", " ", scrubbed)
    scrubbed = re.sub(r"\s+,", ",", scrubbed)
    scrubbed = re.sub(r"^[\s,]+|[\s,]+$", "", scrubbed)
    return scrubbed
