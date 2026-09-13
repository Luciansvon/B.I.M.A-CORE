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

import random
import re

# Kumpulan variasi dinamis untuk disuntikkan ke peracik prompt gambar agar tidak monoton:
LIGHTING_VARIATIONS: tuple[str, ...] = (
    "soft overcast natural daylight from a side window",
    "warm golden hour sunlight with gentle elongated shadows",
    "bright natural midday daylight with crisp clean shadows",
    "dim cozy warm incandescent room light with gentle shadows",
    "cool blue-hour evening twilight with subtle ambient window glow",
    "directional side-lighting revealing rich material texture",
    "morning dawn sunlight casting gentle diffuse gradients",
    "subtle rainy day indoor lighting with soft ambient tones",
)

ANGLE_VARIATIONS: tuple[str, ...] = (
    "eye-level casual viewpoint",
    "slightly low-angle perspective looking gently upward",
    "gentle high-angle shot looking downward at a slight tilt",
    "intimate close-up emphasizing tactile material details",
    "candid slightly off-center handheld snapshot framing",
    "wide environmental composition showing lived-in surrounding space",
    "over-the-shoulder casual point of view",
)

TEXTURE_IMPERFECTION_VARIATIONS: tuple[str, ...] = (
    "subtle natural film grain and slight motion blur on movements",
    "gentle dust motes visible in light beam, authentic everyday clutter",
    "subtle lens flare, genuine lived-in background context",
    "light reflections on surfaces, natural uneven lighting",
    "organic handheld camera feel, gentle natural shadow falloff",
    "tactile realistic textures on surfaces with subtle imperfections",
)

LENS_VARIATIONS: tuple[str, ...] = (
    "smartphone camera (approx 26mm equivalent)",
    "35mm documentary film lens",
    "50mm natural eye-level lens with organic depth",
    "85mm portrait lens with soft natural background separation",
    "compact 28mm street camera snapshot",
)

THREADS_LOCAL_VARIATIONS: tuple[str, ...] = (
    "warung kopi pinggir jalan with plastic chairs and warm fluorescent bulb",
    "small Indonesian home office room with ceramic tile floor and louvre window",
    "cluttered desk in a kost room with charger cables and electric fan",
    "terrace of an Indonesian house in the afternoon with potted plants",
    "small workshop with tools and sawdust under afternoon tropical heat",
    "cozy living room corner with batik curtain and natural side window light",
)

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


_THREADS_SYSTEM = (
    "Kamu prompt-engineer visual untuk postingan Threads. Input: teks draf postingan. "
    "Tugas: tulis SATU image prompt Bahasa Inggris supaya hasilnya keliatan seperti foto asli "
    "yang dijepret orang Indonesia pakai HP — bukan gambar AI.\n\n"
    "WAJIB — setting Indonesia:\n"
    "- Adegan harus jelas berlokasi di Indonesia (sebut 'in Indonesia' atau kota/konteks "
    "lokalnya di prompt): rumah/kost/ruko/kantor/warung/teras lokal — BUKAN interior gaya "
    "Amerika/Eropa (no colonial wooden desks, no autumn/winter windows).\n"
    "- Pakai 2-3 detail lokal yang relevan sama isi postingan: lantai keramik putih, jendela "
    "nako/teralis, dinding cat polos, kipas angin, galon air, stop kontak + kabel semrawut, "
    "gorden, motor parkir, gelas belimbing, kursi plastik, cahaya tropis terik/lembab.\n"
    "- Kalau ada orang: orang Indonesia/Asia Tenggara, pakaian kasual lokal.\n\n"
    "Gaya foto — AMATIR, bukan fotografer pro (2-4 kalimat, 40-90 kata):\n"
    "- Wajib terasa 'casual amateur smartphone snapshot, handheld': dijepret buru-buru sambil "
    "lewat, bukan di-setting. Framing boleh agak miring/kepotong, fokus kadang meleset dikit.\n"
    "- Sebut cahaya apa adanya: sumber + arah + kualitas (siang tropis terik, mendung, lampu "
    "neon warung, lampu kamar kekuningan, subuh) — cahaya seadanya di lokasi, bukan lighting "
    "yang diatur.\n"
    "- 1-2 imperfeksi natural (slight motion blur, uneven lighting, subtle grain, barang "
    "berantakan, jendela overexposed).\n"
    "- VARIASIKAN resep tiap post (waktu, arah cahaya, angle) — jangan formula sama terus.\n\n"
    "DILARANG:\n"
    "- Istilah fotografi profesional: studio lighting, softbox, cinematic, bokeh, 85mm, "
    "f/1.4, professional photography, dramatic lighting, rule of thirds, golden hour "
    "portrait. Ini bikin hasil keliatan foto pro yang di-setting = keliatan AI.\n"
    "- Teks/tulisan TERBACA di mana pun dalam gambar — no signage, no mug/kaos bertulisan, "
    "no poster berteks. Tambahkan eksplisit di prompt: 'no readable text anywhere'.\n"
    "- Kata-kata: hyperrealistic, masterpiece, 8k, 4k, HDR, ultra-detailed, ultra-realistic, "
    "award-winning, stunning, breathtaking, perfect, flawless, pristine, 3D render, CGI, "
    "unreal engine, octane, trending on artstation.\n"
    "- Warna oversaturated.\n\n"
    "Contoh:\n"
    "Postingan: \"Jumat sore gini baru sadar meja gua doang yang makin berantakan tiap jam "
    "pulang deket\"\n"
    "Prompt: \"A casual smartphone snapshot of a cluttered work desk in a small Indonesian "
    "home office, white ceramic tile floor and plain painted wall visible, papers and "
    "tangled charger cables around an old laptop, warm late-afternoon tropical sunlight "
    "coming through a louvre window on the right, slightly off-center framing with subtle "
    "grain, no readable text anywhere\"\n\n"
    "Output HANYA teks prompt Bahasa Inggris tersebut, satu baris, no preamble, no quotes."
)


def get_dynamic_creative_cues(is_threads: bool = False) -> str:
    """Hasilkan arahan kreatif acak agar output prompt gambar bervariasi dan tidak seragam."""
    lighting = random.choice(LIGHTING_VARIATIONS)
    angle = random.choice(ANGLE_VARIATIONS)
    imperfection = random.choice(TEXTURE_IMPERFECTION_VARIATIONS)
    lens = random.choice(LENS_VARIATIONS)

    if is_threads:
        local_vibe = random.choice(THREADS_LOCAL_VARIATIONS)
        return (
            f"\n\nPANDUAN VARIASI DINAMIS (eksplorasi arah visual unik ini):\n"
            f"- Setting lokal: {local_vibe}\n"
            f"- Karakter cahaya: {lighting}\n"
            f"- Sudut/Framing: {angle}\n"
            f"- Imperfeksi alami: {imperfection}"
        )

    return (
        f"\n\nPANDUAN VARIASI DINAMIS (eksplorasi arah visual unik ini):\n"
        f"- Karakter cahaya: {lighting}\n"
        f"- Sudut/Komposisi: {angle}\n"
        f"- Pilihan lensa/kamera: {lens}\n"
        f"- Imperfeksi alami: {imperfection}"
    )


def build_system_prompt(has_ref: bool = False, dynamic: bool = True) -> str:
    """System prompt buat prompt-expander LLM (txt2img atau img2img)."""
    base = _IMG2IMG_SYSTEM if has_ref else _TXT2IMG_SYSTEM
    if dynamic:
        return f"{base}{get_dynamic_creative_cues(is_threads=False)}"
    return base


def build_threads_system_prompt(dynamic: bool = True) -> str:
    """System prompt buat image prompt generator postingan Threads.

    Beda dari txt2img biasa: input-nya draf postingan (bukan request langsung),
    wajib grounding setting Indonesia, dan larangan keras teks terbaca di gambar.
    Output LLM: prompt polos tanpa tag CASUAL|CLEAN.
    """
    if dynamic:
        return f"{_THREADS_SYSTEM}{get_dynamic_creative_cues(is_threads=True)}"
    return _THREADS_SYSTEM


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
