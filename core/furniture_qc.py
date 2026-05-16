"""Furniture working drawing QC reviewer.

Pipeline:
    Discord `!qc` + PDF/image attachment
        → download → PDF→image (PyMuPDF) → Gemini Flash vision (OpenRouter)
        → JSON parse → Pydantic validate → text reply + markup PNG attachment.

Cuma buat sample/project pribadi. JANGAN upload drawing client/perusahaan
(data lewat OpenRouter + Google server).
"""
import asyncio
import base64
import json
import logging
import os
from io import BytesIO
from pathlib import Path

import discord
import fitz  # PyMuPDF
import httpx
from PIL import Image, ImageDraw, ImageFont
from openai import OpenAI
from pydantic import BaseModel, Field

logger = logging.getLogger("bima_core.furniture_qc")

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
QC_MODEL = "google/gemini-3-flash-preview"  # sama kayak visual_llm di config.py
MAX_PAGES = 6
TARGET_WIDTH_PX = 2048
MAX_FILE_MB = 20
DISCORD_MSG_LIMIT = 1900  # safety margin di bawah 2000

QC_SYSTEM_PROMPT = """Kamu reviewer senior gambar kerja furniture 15 tahun di workshop.

Tugas: cek gambar kerja yg dilampirkan (1+ halaman, urut sesuai urutan attachment), identifikasi issue yg bikin produksi salah / bingung. Untuk SETIAP issue, kasih juga koordinat bounding box di halaman bersangkutan supaya bisa ditandain visual.

CHECKLIST PRIORITAS:
1. **DIMENSI** — tiap part wajib ada ukuran panjang × lebar × tebal. Flag part tanpa dimensi.
2. **DETAIL SAMBUNGAN** — sambungan (dovetail/mortise-tenon/dowel/screw/biscuit) wajib ada callout / section view. Flag sambungan tanpa detail.
3. **VIEW** — minimum 3 view (depan/samping/atas) atau isometric/section. Flag kalau cuma 1 view.
4. **MATERIAL & BOM** — jenis kayu, finishing, hardware (screw/hinge/handle), kuantitas. Flag yg missing.

LEVEL SEVERITY:
- **critical** — bakal bikin produksi salah/gagal
- **warning** — produksi bisa nebak tapi rentan misinterpretasi
- **info** — saran improvement

BOUNDING BOX:
- "page" = nomor halaman 1-indexed (1, 2, 3, ...) sesuai urutan attachment.
- "bbox" = [x0, y0, x1, y1] dalam koordinat normalized 0.0-1.0 dari halaman tsb.
  x0/y0 = pojok kiri-atas area issue, x1/y1 = pojok kanan-bawah.
  Kasih null kalau lokasi ga jelas / issue bersifat global ke halaman.

OUTPUT — JSON object strict, tanpa markdown fence:
{
  "overall_verdict": "approved" | "needs_revision" | "rejected",
  "summary": "1-2 kalimat ringkas",
  "issues": [
    {"severity": "critical|warning|info", "category": "dimensi|sambungan|view|material|lain",
     "location": "bagian mana di gambar (deskripsi human-readable)",
     "page": 1, "bbox": [0.12, 0.34, 0.56, 0.78],
     "issue": "apa yg salah/kurang", "suggestion": "cara fix"}
  ],
  "praise": ["hal yg udah bagus, kalau ada"]
}
"""


SEVERITY_COLORS: dict[str, tuple[int, int, int]] = {
    "critical": (220, 38, 38),     # red
    "warning": (234, 179, 8),       # amber
    "info": (37, 99, 235),          # blue
}

_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/DejaVuSans-Bold.ttf",
]


class QCIssue(BaseModel):
    severity: str
    category: str
    location: str
    issue: str
    suggestion: str = ""
    page: int = 1
    bbox: list[float] | None = None  # [x0, y0, x1, y1] normalized 0.0-1.0


class QCResult(BaseModel):
    overall_verdict: str
    summary: str
    issues: list[QCIssue] = Field(default_factory=list)
    praise: list[str] = Field(default_factory=list)


def _load_font(size: int) -> ImageFont.ImageFont:
    for p in _FONT_PATHS:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _pil_to_png_bytes(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _render_markup_per_page(images_b64: list[str], result: QCResult) -> list[bytes]:
    """Overlay bbox + label per issue ke halaman gambar asli.

    Return: list PNG bytes per halaman (semua halaman, tanpa atau dengan markup).
    """
    out: list[bytes] = []
    font_label = _load_font(22)

    for page_idx, img_b64 in enumerate(images_b64, start=1):
        img = Image.open(BytesIO(base64.b64decode(img_b64))).convert("RGB")
        W, H = img.size
        draw = ImageDraw.Draw(img)

        page_issues = [
            i for i in result.issues
            if i.page == page_idx and i.bbox and len(i.bbox) == 4
        ]

        for idx, issue in enumerate(page_issues, start=1):
            color = SEVERITY_COLORS.get(issue.severity, (128, 128, 128))

            # Clamp bbox ke [0,1] lalu konversi ke pixel
            x0_n, y0_n, x1_n, y1_n = issue.bbox
            x0 = int(max(0.0, min(1.0, x0_n)) * W)
            y0 = int(max(0.0, min(1.0, y0_n)) * H)
            x1 = int(max(0.0, min(1.0, x1_n)) * W)
            y1 = int(max(0.0, min(1.0, y1_n)) * H)
            if x0 > x1:
                x0, x1 = x1, x0
            if y0 > y1:
                y0, y1 = y1, y0

            # Box outline tebal
            draw.rectangle([x0, y0, x1, y1], outline=color, width=5)

            # Label badge di atas box (atau di bawah kalau ga muat)
            sev_short = {"critical": "CRT", "warning": "WRN", "info": "INF"}.get(issue.severity, "?")
            label = f"#{idx} {sev_short} · {issue.category}"

            try:
                tb = draw.textbbox((0, 0), label, font=font_label)
                tw = tb[2] - tb[0] + 14
                th = tb[3] - tb[1] + 8
            except Exception:
                tw, th = len(label) * 11 + 14, 28

            ly = y0 - th - 4 if y0 - th - 4 >= 0 else y1 + 4
            lx = x0
            if lx + tw > W:
                lx = max(0, W - tw)

            draw.rectangle([lx, ly, lx + tw, ly + th], fill=color)
            draw.text((lx + 7, ly + 4), label, font=font_label, fill=(255, 255, 255))

        out.append(_pil_to_png_bytes(img))

    return out


def _pdf_to_images_b64(pdf_bytes: bytes) -> list[str]:
    """Render PDF pages ke base64-encoded PNG. Cap MAX_PAGES untuk kontrol biaya."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images_b64: list[str] = []
    try:
        for page_num, page in enumerate(doc):
            if page_num >= MAX_PAGES:
                logger.warning(f"[qc] PDF >{MAX_PAGES} hal, hanya proses {MAX_PAGES} pertama")
                break
            zoom = TARGET_WIDTH_PX / page.rect.width if page.rect.width else 1
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            images_b64.append(base64.b64encode(pix.tobytes("png")).decode())
    finally:
        doc.close()
    return images_b64


def _image_to_b64(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode()


async def review_attachment(
    attachment_url: str, attachment_filename: str
) -> tuple[QCResult, list[str]]:
    """Download attachment → render → vision API → parse.

    Return: (QCResult, images_b64 per halaman) — caller bisa pakai images_b64
    buat render markup overlay.
    """
    async with httpx.AsyncClient(timeout=60) as cx:
        resp = await cx.get(attachment_url, follow_redirects=True)
        resp.raise_for_status()
        file_bytes = resp.content

    fname = attachment_filename.lower()
    if fname.endswith(".pdf"):
        images_b64 = _pdf_to_images_b64(file_bytes)
        content_type = "image/png"
    elif fname.endswith((".png", ".jpg", ".jpeg", ".webp")):
        images_b64 = [_image_to_b64(file_bytes)]
        ext = fname.rsplit(".", 1)[-1]
        content_type = f"image/{'jpeg' if ext == 'jpg' else ext}"
    else:
        raise ValueError(f"Format tidak didukung: {attachment_filename} (pakai PDF/PNG/JPG/WEBP)")

    if not images_b64:
        raise ValueError("Tidak ada halaman/image yg bisa dibaca dari file")

    content_parts: list[dict] = [
        {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{img}"}}
        for img in images_b64
    ]
    content_parts.append({"type": "text", "text": QC_SYSTEM_PROMPT})

    client = OpenAI(
        api_key=os.environ.get("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
    )

    import stamina

    @stamina.retry(on=Exception, attempts=3, wait_initial=2, wait_max=15)
    def _call_vision():
        return client.chat.completions.create(
            model=QC_MODEL,
            messages=[{"role": "user", "content": content_parts}],
            max_tokens=2500,
            response_format={"type": "json_object"},
        )

    completion = await asyncio.to_thread(_call_vision)
    raw = (completion.choices[0].message.content or "").strip()
    # Beberapa model tetap bungkus markdown — bersihin
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1] if "```" in raw[3:] else raw[3:]
        if raw.startswith("json\n") or raw.startswith("json "):
            raw = raw[5:]
        raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"[qc] JSON parse fail: {e}\nRaw: {raw[:500]}")
        raise ValueError(f"Model balikin JSON invalid: {e}")

    return QCResult(**data), images_b64


def format_result_for_discord(result: QCResult) -> str:
    """Format QCResult ke markdown Discord-readable."""
    verdict_emoji = {
        "approved": "✅",
        "needs_revision": "⚠️",
        "rejected": "🚨",
    }.get(result.overall_verdict, "❓")

    lines = [
        f"# {verdict_emoji} QC: **{result.overall_verdict.upper()}**",
        "",
        f"_{result.summary}_",
        "",
    ]

    by_severity = {"critical": [], "warning": [], "info": []}
    for i in result.issues:
        by_severity.setdefault(i.severity, []).append(i)

    section_emoji = {"critical": "🚨", "warning": "⚠️", "info": "💡"}
    section_label = {"critical": "Critical", "warning": "Warning", "info": "Info"}

    if not result.issues:
        lines.append("**Ga ada issue ditemukan.**")
        lines.append("")

    for sev in ("critical", "warning", "info"):
        items = by_severity.get(sev, [])
        if not items:
            continue
        lines.append(f"## {section_emoji[sev]} {section_label[sev]} ({len(items)})")
        for i in items:
            lines.append(f"- **[{i.category}] {i.location}** — {i.issue}")
            if i.suggestion:
                lines.append(f"  💡 _{i.suggestion}_")
        lines.append("")

    if result.praise:
        lines.append("## 👍 Udah bagus")
        for p in result.praise:
            lines.append(f"- {p}")

    return "\n".join(lines)


async def handle_qc_command(message, bot_client=None) -> None:
    """Discord `!qc` handler.

    Usage: kirim `!qc` di Discord dgn PDF/PNG/JPG attachment.
    """
    if not message.attachments:
        await message.reply(
            "📋 **`!qc` — Furniture Drawing QC**\n"
            "Upload PDF/PNG/JPG gambar kerja sebagai attachment, lalu ketik `!qc`.\n"
            "Anisa cek dimensi, detail sambungan, view, dan BOM.\n"
            "⚠️ Test pakai project pribadi aja. JANGAN drawing client/perusahaan."
        )
        return

    att = message.attachments[0]
    if att.size > MAX_FILE_MB * 1024 * 1024:
        await message.reply(f"❌ File terlalu besar ({att.size / 1024 / 1024:.1f} MB). Max {MAX_FILE_MB} MB.")
        return

    progress = await message.reply(f"🔍 Lagi review `{att.filename}`... (~10-30 detik)")
    try:
        result, images_b64 = await review_attachment(att.url, att.filename)
        text = format_result_for_discord(result)
        if len(text) > DISCORD_MSG_LIMIT:
            text = text[: DISCORD_MSG_LIMIT - 30] + "\n\n... _(terpotong)_"
        await progress.edit(content=text)

        # Render markup overlay per halaman (kalau ada issue dengan bbox)
        has_bbox = any(i.bbox for i in result.issues)
        if has_bbox and images_b64:
            try:
                markup_pngs = await asyncio.to_thread(_render_markup_per_page, images_b64, result)
                files = [
                    discord.File(BytesIO(png), filename=f"qc_markup_p{i+1}.png")
                    for i, png in enumerate(markup_pngs)
                ][:10]  # Discord max 10 attachments
                if files:
                    await message.channel.send(
                        content=f"🖍 Markup visual buat `{att.filename}`:",
                        files=files,
                        reference=message,
                    )
            except Exception as e:
                logger.warning(f"[qc] markup render gagal (text reply tetep kirim): {e}")

        logger.info(f"[qc] done: {att.filename} → {result.overall_verdict} ({len(result.issues)} issues)")
    except Exception as e:
        logger.exception("[qc] gagal review")
        await progress.edit(content=f"❌ Gagal review `{att.filename}`: `{e}`")
