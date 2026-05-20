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
import openai
from PIL import Image, ImageDraw, ImageFont
from openai import OpenAI
from pydantic import BaseModel, Field

from config import VISUAL_MODEL_NAME

logger = logging.getLogger("bima_core.furniture_qc")

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
QC_MODEL = VISUAL_MODEL_NAME  # single source of truth: config.py
MAX_PAGES = int(os.environ.get("QC_MAX_PAGES", "6"))
TARGET_WIDTH_PX = int(os.environ.get("QC_TARGET_WIDTH_PX", "2048"))
MAX_FILE_MB = int(os.environ.get("QC_MAX_FILE_MB", "20"))
DISCORD_MSG_LIMIT = 1900  # safety margin di bawah 2000

# Retry hanya untuk error transient (network/5xx/rate-limit). 4xx auth/bad-request
# gak masuk akal di-retry — biar fail fast & jelas penyebabnya.
_RETRYABLE_EXC = (
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.RateLimitError,
    openai.InternalServerError,
)

QC_SYSTEM_PROMPT = """Kamu reviewer senior gambar kerja furniture 15 tahun di workshop.

Tugas: cek gambar kerja yg dilampirkan (1+ halaman, urut sesuai urutan attachment), identifikasi issue yg bikin produksi salah / bingung. Untuk SETIAP issue, kasih juga koordinat bounding box di halaman bersangkutan supaya bisa ditandain visual.

Sekalian extract:
- **TITLE BLOCK** — drawing#, judul, revisi, scale, author, tanggal (kalau ada di kop gambar)
- **BOM** — daftar part dengan ukuran w×h, tebal, qty, material (kalau jelas terbaca di table BOM atau dimensi label)

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

BOM RULES:
- Cuma extract part yang JELAS terbaca dimensinya di gambar/tabel BOM. JANGAN ngarang.
- Unit dimensi = mm (default). Kalau gambar pake cm/inch, convert ke mm.
- Material biar konsisten pake key salah satu: "plywood_18mm" | "plywood_12mm" | "mdf_18mm" | "mdf_12mm" | "solid_jati" | "solid_mahoni" | "other" (atau null kalau gak jelas).
- Kalau BOM ga kelihatan/ga jelas → keluarin array kosong, bukan halusinasi.

OUTPUT — JSON object strict, tanpa markdown fence:
{
  "overall_verdict": "approved" | "needs_revision" | "rejected",
  "summary": "1-2 kalimat ringkas",
  "title_block": {
    "drawing_number": "JM-024" | null,
    "title": "Lemari Pakaian 2-Pintu" | null,
    "revision": "Rev.3" | null,
    "scale": "1:20" | null,
    "author": "Bima" | null,
    "date": "2026-05-15" | null
  } | null,
  "issues": [
    {"severity": "critical|warning|info", "category": "dimensi|sambungan|view|material|lain",
     "location": "bagian mana di gambar (deskripsi human-readable)",
     "page": 1, "bbox": [0.12, 0.34, 0.56, 0.78],
     "issue": "apa yg salah/kurang", "suggestion": "cara fix"}
  ],
  "praise": ["hal yg udah bagus, kalau ada"],
  "bom": [
    {"name": "top panel", "width": 600, "height": 400, "thickness": 18,
     "qty": 2, "material": "plywood_18mm"}
  ]
}
"""

QC_DIFF_SYSTEM_PROMPT = """Kamu reviewer senior furniture drawing 15 tahun. Tugas: bandingin 2 revisi gambar kerja (REV_A vs REV_B) yg dilampirkan urut.

Attachment urutannya: halaman REV_A dulu (1..N_a), terus halaman REV_B (N_a+1..N_a+N_b).

Identifikasi PERUBAHAN spesifik:
- Dimensi yang berubah (mention angka lama → angka baru kalau kelihatan)
- Part yang ditambah / dihapus
- View baru / hilang
- BOM item yang shift (qty / material / hardware)
- Detail sambungan yang berubah
- Material / finishing yang berganti

LEVEL:
- **major** — perubahan dimensi >5%, part di-add/remove, sambungan ganti tipe, material ganti
- **minor** — perubahan cosmetic, label, info catatan, finishing tone

OUTPUT — JSON object strict tanpa markdown fence:
{
  "summary": "1-2 kalimat ringkas overall change",
  "overall_change_level": "minor" | "moderate" | "major",
  "rev_a_pages": <int, jumlah halaman REV_A>,
  "rev_b_pages": <int, jumlah halaman REV_B>,
  "changes": [
    {"severity": "major|minor", "category": "dimensi|part|view|bom|sambungan|material|lain",
     "page_a": 1, "page_b": 1,
     "what_changed": "deskripsi spesifik perubahan, mention angka lama → angka baru kalau ada"}
  ]
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


class TitleBlock(BaseModel):
    drawing_number: str | None = None
    title: str | None = None
    revision: str | None = None
    scale: str | None = None
    author: str | None = None
    date: str | None = None


class BomPart(BaseModel):
    name: str
    width: float  # mm
    height: float  # mm
    thickness: float | None = None  # mm
    qty: int = 1
    material: str | None = None  # plywood_18mm / mdf_18mm / solid_jati / ...


class QCResult(BaseModel):
    overall_verdict: str
    summary: str
    issues: list[QCIssue] = Field(default_factory=list)
    praise: list[str] = Field(default_factory=list)
    title_block: TitleBlock | None = None
    bom: list[BomPart] = Field(default_factory=list)


class QCDiffChange(BaseModel):
    severity: str  # major | minor
    category: str
    page_a: int = 0
    page_b: int = 0
    what_changed: str


class QCDiffResult(BaseModel):
    summary: str
    overall_change_level: str = "minor"  # minor | moderate | major
    rev_a_pages: int = 0
    rev_b_pages: int = 0
    changes: list[QCDiffChange] = Field(default_factory=list)


# === Harga material per m² (IDR) dari env, fallback ke default reasonable ===
def _load_material_prices() -> dict[str, float]:
    """Format env: `QC_PRICES=plywood_18mm:120000,mdf_18mm:85000,...`"""
    defaults = {
        "plywood_18mm": 120000.0,
        "plywood_12mm": 95000.0,
        "plywood_9mm": 80000.0,
        "mdf_18mm": 85000.0,
        "mdf_12mm": 70000.0,
        "solid_jati": 850000.0,
        "solid_mahoni": 450000.0,
        "other": 100000.0,
    }
    raw = os.environ.get("QC_PRICES", "").strip()
    if not raw:
        return defaults
    prices = dict(defaults)
    for pair in raw.split(","):
        pair = pair.strip()
        if ":" not in pair:
            continue
        k, v = pair.split(":", 1)
        try:
            prices[k.strip()] = float(v.strip())
        except ValueError:
            continue
    return prices


_MATERIAL_PRICES_PER_M2 = _load_material_prices()
_PRICE_FALLBACK = _MATERIAL_PRICES_PER_M2.get("other", 100000.0)


def _estimate_cost_from_bom(bom: list[BomPart]) -> dict:
    """Calc material cost estimate dari BOM. Return breakdown + total IDR."""
    breakdown: dict[str, dict] = {}
    total_cost = 0.0
    total_area_m2 = 0.0
    for part in bom:
        if part.width <= 0 or part.height <= 0 or part.qty <= 0:
            continue
        area_m2 = (part.width * part.height / 1_000_000.0) * part.qty
        mat_key = (part.material or "other").lower()
        price = _MATERIAL_PRICES_PER_M2.get(mat_key, _PRICE_FALLBACK)
        cost = area_m2 * price
        total_area_m2 += area_m2
        total_cost += cost
        slot = breakdown.setdefault(
            mat_key, {"area_m2": 0.0, "cost": 0.0, "parts": 0}
        )
        slot["area_m2"] += area_m2
        slot["cost"] += cost
        slot["parts"] += part.qty
    return {
        "total_idr": total_cost,
        "total_area_m2": total_area_m2,
        "breakdown": breakdown,
    }


# === BOM cache file — dipake `!cutlist last` ===
_BOM_CACHE_FILE = OUTPUT_DIR / ".last_qc_bom.json"


def save_last_bom(filename: str, bom: list[BomPart], title_block: TitleBlock | None) -> None:
    """Tulis BOM ke cache file. Best-effort, gagal log debug."""
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        import time
        payload = {
            "filename": filename,
            "saved_at": int(time.time()),
            "title_block": title_block.model_dump() if title_block else None,
            "bom": [p.model_dump() for p in bom],
        }
        _BOM_CACHE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        logger.info(f"[qc] BOM cached → {_BOM_CACHE_FILE.name} ({len(bom)} parts)")
    except Exception as e:
        logger.debug(f"[qc] save_last_bom skip: {e}")


def load_last_bom() -> dict | None:
    """Return last cached BOM payload atau None kalau gak ada / corrupt."""
    if not _BOM_CACHE_FILE.exists():
        return None
    try:
        data = json.loads(_BOM_CACHE_FILE.read_text())
        return data if isinstance(data, dict) and data.get("bom") else None
    except Exception as e:
        logger.debug(f"[qc] load_last_bom corrupt: {e}")
        return None


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


def _parse_dxf_facts(dxf_bytes: bytes) -> dict:
    """Extract ground-truth facts dari DXF (akurasi 100% — beda sama vision yg bisa halu).

    Return dict: layers, dimensions, texts, blocks. Dipake jadi konteks tambahan
    ke vision LLM supaya gak salah baca angka.
    """
    import tempfile
    import ezdxf

    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False, mode="wb") as f:
        f.write(dxf_bytes)
        temp_path = f.name
    try:
        doc = ezdxf.readfile(temp_path)
        msp = doc.modelspace()

        layers = [
            l.dxf.name for l in doc.layers
            if l.dxf.name not in ("0", "Defpoints")
        ]
        dimensions: list[dict] = []
        texts: list[dict] = []
        inserts: list[str] = []

        for e in msp:
            t = e.dxftype()
            if t == "DIMENSION":
                try:
                    measurement = e.get_measurement()
                except Exception:
                    measurement = None
                override = getattr(e.dxf, "text", "") or ""
                dimensions.append({
                    "measurement": measurement,
                    "override_text": override if override not in ("", "<>") else None,
                    "layer": e.dxf.layer,
                })
            elif t in ("TEXT", "MTEXT"):
                try:
                    content = e.dxf.text if t == "TEXT" else e.text
                except Exception:
                    content = ""
                if content and content.strip():
                    texts.append({"text": content.strip()[:200], "layer": e.dxf.layer})
            elif t == "INSERT":
                try:
                    inserts.append(e.dxf.name)
                except Exception:
                    pass

        # Aggregate INSERT counts (block reuse — biasanya hardware/handle)
        block_counts: dict[str, int] = {}
        for name in inserts:
            block_counts[name] = block_counts.get(name, 0) + 1

        return {
            "drawing_units": doc.header.get("$INSUNITS", "unknown"),
            "layers": layers[:30],
            "dimension_count": len(dimensions),
            "dimensions": dimensions[:50],
            "text_labels": texts[:50],
            "block_inserts": [
                {"name": n, "qty": q}
                for n, q in sorted(block_counts.items(), key=lambda x: -x[1])
            ][:30],
        }
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


def _dxf_to_png_bytes(dxf_bytes: bytes) -> list[bytes]:
    """Render DXF modelspace ke PNG via matplotlib backend. Return single-page list."""
    import tempfile
    import ezdxf
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False, mode="wb") as f:
        f.write(dxf_bytes)
        temp_path = f.name
    try:
        doc = ezdxf.readfile(temp_path)
        msp = doc.modelspace()

        fig = Figure(figsize=(14, 10), dpi=160)
        FigureCanvasAgg(fig)
        ax = fig.add_subplot(1, 1, 1)
        ax.set_aspect("equal")
        ctx = RenderContext(doc)
        backend = MatplotlibBackend(ax)
        Frontend(ctx, backend).draw_layout(msp, finalize=True)

        buf = BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
        return [buf.getvalue()]
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


# Severity → RGB normalized [0,1] (format PyMuPDF & juga buat pillow lewat *255)
_SEV_RGB_NORM = {
    "critical": (0.86, 0.15, 0.15),
    "warning": (0.92, 0.70, 0.03),
    "info": (0.14, 0.39, 0.92),
}


def _annotate_pdf(pdf_bytes: bytes, result: QCResult) -> bytes:
    """Tulis rect + sticky note annotations LANGSUNG ke PDF asli.

    Tukang buka di Acrobat/PDF viewer → klik sticky note → baca issue detail
    + suggestion fix. Lebih clean dari kirim PNG markup terpisah.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        for page_idx, page in enumerate(doc):
            page_num = page_idx + 1
            if page_num > MAX_PAGES:
                break
            page_issues = [
                i for i in result.issues
                if i.page == page_num and i.bbox and len(i.bbox) == 4
            ]
            rect = page.rect

            for idx, issue in enumerate(page_issues, start=1):
                stroke = _SEV_RGB_NORM.get(issue.severity, (0.5, 0.5, 0.5))

                x0_n, y0_n, x1_n, y1_n = issue.bbox
                x0_n = max(0.0, min(1.0, x0_n))
                y0_n = max(0.0, min(1.0, y0_n))
                x1_n = max(0.0, min(1.0, x1_n))
                y1_n = max(0.0, min(1.0, y1_n))
                if x0_n > x1_n:
                    x0_n, x1_n = x1_n, x0_n
                if y0_n > y1_n:
                    y0_n, y1_n = y1_n, y0_n

                bbox_rect = fitz.Rect(
                    x0_n * rect.width, y0_n * rect.height,
                    x1_n * rect.width, y1_n * rect.height,
                )

                title = f"#{idx} [{issue.severity.upper()}] {issue.category}"

                rect_annot = page.add_rect_annot(bbox_rect)
                rect_annot.set_colors(stroke=stroke)
                rect_annot.set_border(width=2)
                rect_annot.set_info(title=title, content=issue.issue)
                rect_annot.update()

                parts = [
                    title,
                    f"Lokasi: {issue.location}",
                    f"Issue: {issue.issue}",
                ]
                if issue.suggestion:
                    parts.append(f"Fix: {issue.suggestion}")
                note_text = "\n".join(parts)

                text_annot = page.add_text_annot(
                    fitz.Point(bbox_rect.x0, bbox_rect.y0), note_text
                )
                text_annot.set_colors(stroke=stroke)
                text_annot.set_info(title="Anisa QC", content=note_text)
                text_annot.update()

        return doc.tobytes()
    finally:
        doc.close()


def _file_to_b64_pages(file_bytes: bytes, filename: str) -> list[str]:
    """Helper: render file → list of base64 PNG pages. Reused buat diff mode."""
    fl = filename.lower()
    if fl.endswith(".pdf"):
        return _pdf_to_images_b64(file_bytes)
    if fl.endswith((".png", ".jpg", ".jpeg", ".webp")):
        return [_image_to_b64(file_bytes)]
    if fl.endswith(".dxf"):
        pngs = _dxf_to_png_bytes(file_bytes)
        return [base64.b64encode(p).decode() for p in pngs]
    raise ValueError(f"Format gak didukung: {filename}")


async def review_diff_from_bytes(
    files: list[tuple[bytes, str]],
) -> QCDiffResult:
    """Compare 2 revisions. files = [(bytes, filename), (bytes, filename)].

    Halaman REV_A dulu, terus REV_B. Vision LLM jelas distinguish via prompt meta.
    """
    if len(files) != 2:
        raise ValueError("Diff mode butuh tepat 2 attachment (rev_a + rev_b)")

    pages_per_file: list[list[str]] = []
    for fbytes, fname in files:
        pages = await asyncio.to_thread(_file_to_b64_pages, fbytes, fname)
        if not pages:
            raise ValueError(f"Tidak ada halaman bisa dibaca: {fname}")
        pages_per_file.append(pages)

    n_a = len(pages_per_file[0])
    n_b = len(pages_per_file[1])
    all_pages = pages_per_file[0] + pages_per_file[1]

    content_parts: list[dict] = [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}}
        for img in all_pages
    ]
    diff_meta = f"\n\nMeta: REV_A = halaman 1..{n_a}, REV_B = halaman {n_a + 1}..{n_a + n_b}."
    content_parts.append({"type": "text", "text": QC_DIFF_SYSTEM_PROMPT + diff_meta})

    client = OpenAI(
        api_key=os.environ.get("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
    )

    import stamina

    @stamina.retry(on=_RETRYABLE_EXC, attempts=3, wait_initial=2, wait_max=15)
    def _call_vision():
        return client.chat.completions.create(
            model=QC_MODEL,
            messages=[{"role": "user", "content": content_parts}],
            max_tokens=3000,
            response_format={"type": "json_object"},
        )

    completion = await asyncio.to_thread(_call_vision)
    raw = (completion.choices[0].message.content or "").strip()
    if raw.startswith("```"):
        raw = (
            raw.removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"[qc-diff] JSON parse fail: {e}\nRaw: {raw[:500]}")
        raise ValueError(f"Model balikin JSON invalid: {e}")
    return QCDiffResult(**data)


def format_diff_for_discord(result: QCDiffResult, name_a: str, name_b: str) -> str:
    """Format QCDiffResult → markdown Discord/WA-friendly."""
    level_emoji = {
        "major": "🚨", "moderate": "⚠️", "minor": "💡"
    }.get(result.overall_change_level, "❓")

    lines = [
        f"# {level_emoji} QC Diff: **{result.overall_change_level.upper()} CHANGE**",
        "",
        f"_REV_A: `{name_a}` ({result.rev_a_pages} hal) → REV_B: `{name_b}` ({result.rev_b_pages} hal)_",
        "",
        f"_{result.summary}_",
        "",
    ]

    if not result.changes:
        lines.append("**Gak ada perubahan signifikan ke-detect.**")
        return "\n".join(lines)

    by_sev: dict[str, list[QCDiffChange]] = {"major": [], "minor": []}
    for c in result.changes:
        by_sev.setdefault(c.severity, []).append(c)

    if by_sev.get("major"):
        lines.append(f"## 🚨 Major ({len(by_sev['major'])})")
        for c in by_sev["major"]:
            lines.append(
                f"- **[{c.category}]** p{c.page_a}→p{c.page_b}: {c.what_changed}"
            )
        lines.append("")

    if by_sev.get("minor"):
        lines.append(f"## 💡 Minor ({len(by_sev['minor'])})")
        for c in by_sev["minor"]:
            lines.append(
                f"- **[{c.category}]** p{c.page_a}→p{c.page_b}: {c.what_changed}"
            )

    return "\n".join(lines)


def _make_markup_artifacts(
    result: QCResult, images_b64: list[str], pdf_bytes: bytes | None
) -> list[tuple[str, bytes]]:
    """Dispatcher: PDF input → 1 annotated PDF. Image input → N markup PNGs.

    Return: list of (filename_suggestion, file_bytes). Bisa kosong kalau gak ada bbox.
    """
    has_bbox = any(i.bbox for i in result.issues)
    if not has_bbox:
        return []

    if pdf_bytes:
        try:
            return [("qc_marked.pdf", _annotate_pdf(pdf_bytes, result))]
        except Exception as e:
            logger.warning(f"[qc] anotasi PDF gagal, fallback ke PNG: {e}")

    if images_b64:
        markup_pngs = _render_markup_per_page(images_b64, result)
        return [(f"qc_markup_p{i + 1}.png", png) for i, png in enumerate(markup_pngs)]

    return []


async def _review_from_bytes(
    file_bytes: bytes, filename: str
) -> tuple[QCResult, list[str], bytes | None]:
    """Core review: bytes → render → vision API → parse.

    Dipakai bareng oleh Discord (URL download) dan WA (local file).
    Return: (QCResult, images_b64 per halaman, pdf_bytes_or_None).
        pdf_bytes != None hanya kalau input PDF — caller bisa pakai buat anotasi native.
    """
    fname = filename.lower()
    pdf_bytes: bytes | None = None
    dxf_facts: dict | None = None
    if fname.endswith(".pdf"):
        images_b64 = _pdf_to_images_b64(file_bytes)
        content_type = "image/png"
        pdf_bytes = file_bytes
    elif fname.endswith((".png", ".jpg", ".jpeg", ".webp")):
        images_b64 = [_image_to_b64(file_bytes)]
        ext = fname.rsplit(".", 1)[-1]
        content_type = f"image/{'jpeg' if ext == 'jpg' else ext}"
    elif fname.endswith(".dxf"):
        # DXF: hybrid — render PNG buat vision + parse facts buat ground truth
        dxf_facts = await asyncio.to_thread(_parse_dxf_facts, file_bytes)
        pngs = await asyncio.to_thread(_dxf_to_png_bytes, file_bytes)
        images_b64 = [base64.b64encode(p).decode() for p in pngs]
        content_type = "image/png"
        logger.info(
            f"[qc] DXF facts: {len(dxf_facts.get('layers', []))} layers, "
            f"{dxf_facts.get('dimension_count', 0)} dimensions, "
            f"{len(dxf_facts.get('text_labels', []))} texts"
        )
    else:
        raise ValueError(f"Format tidak didukung: {filename} (pakai PDF/PNG/JPG/WEBP/DXF)")

    if not images_b64:
        raise ValueError("Tidak ada halaman/image yg bisa dibaca dari file")

    content_parts: list[dict] = [
        {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{img}"}}
        for img in images_b64
    ]
    content_parts.append({"type": "text", "text": QC_SYSTEM_PROMPT})

    # DXF: kasih ground-truth fakta ke vision LLM — akurasi dimensi 100%, gak halu
    if dxf_facts is not None:
        facts_blob = json.dumps(dxf_facts, indent=2, default=str)
        content_parts.append({
            "type": "text",
            "text": (
                "\n\n=== FAKTA DXF (GROUND TRUTH — JANGAN KONTRADIKSI) ===\n"
                f"{facts_blob}\n\n"
                "Gunakan data dimensi & layer di atas buat verify drawing. "
                "Cek apakah ada part yg ke-render tanpa DIMENSION entity (= flag missing dimensi). "
                "Cek konsistensi naming layer vs BOM."
            ),
        })

    client = OpenAI(
        api_key=os.environ.get("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
    )

    import stamina

    @stamina.retry(on=_RETRYABLE_EXC, attempts=3, wait_initial=2, wait_max=15)
    def _call_vision():
        return client.chat.completions.create(
            model=QC_MODEL,
            messages=[{"role": "user", "content": content_parts}],
            max_tokens=4000,  # BOM + title_block extraction butuh ruang ekstra
            response_format={"type": "json_object"},
        )

    completion = await asyncio.to_thread(_call_vision)
    raw = (completion.choices[0].message.content or "").strip()
    # Beberapa model tetap bungkus markdown fence — strip ```json ... ``` atau ``` ... ```
    if raw.startswith("```"):
        raw = (
            raw.removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"[qc] JSON parse fail: {e}\nRaw: {raw[:500]}")
        raise ValueError(f"Model balikin JSON invalid: {e}")

    return QCResult(**data), images_b64, pdf_bytes


async def review_attachment(
    attachment_url: str, attachment_filename: str
) -> tuple[QCResult, list[str], bytes | None]:
    """Download attachment dari URL (Discord) lalu review."""
    async with httpx.AsyncClient(timeout=60) as cx:
        resp = await cx.get(attachment_url, follow_redirects=True)
        resp.raise_for_status()
        file_bytes = resp.content
    return await _review_from_bytes(file_bytes, attachment_filename)


async def review_local_file(
    filepath: str, filename: str | None = None
) -> tuple[QCResult, list[str], bytes | None]:
    """Review file dari local disk (WA bridge — file udah didownload)."""
    p = Path(filepath)
    if not p.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {filepath}")
    file_bytes = p.read_bytes()
    return await _review_from_bytes(file_bytes, filename or p.name)


def _format_title_block(tb: TitleBlock | None) -> list[str]:
    """Render title block jadi 1-3 baris ringkas, atau kosong kalau gak ada data."""
    if tb is None:
        return []
    fields = [
        ("Drawing#", tb.drawing_number),
        ("Title", tb.title),
        ("Rev", tb.revision),
        ("Scale", tb.scale),
        ("Author", tb.author),
        ("Date", tb.date),
    ]
    present = [f"**{k}**: {v}" for k, v in fields if v]
    if not present:
        return []
    return ["📑 " + " · ".join(present), ""]


def _format_bom_section(bom: list[BomPart]) -> list[str]:
    """Render BOM + cost estimate. Kosong kalau bom kosong."""
    if not bom:
        return []
    lines = [f"## 📦 BOM ({len(bom)} part)"]
    for p in bom:
        thick = f"×{p.thickness:.0f}mm" if p.thickness else ""
        mat = f" [{p.material}]" if p.material else ""
        lines.append(f"- `{p.name}` {p.width:.0f}×{p.height:.0f}{thick} qty {p.qty}{mat}")

    cost = _estimate_cost_from_bom(bom)
    lines.append("")
    lines.append(
        f"💰 **Material cost estimate**: ~Rp {cost['total_idr']:,.0f}  "
        f"({cost['total_area_m2']:.2f} m² total)"
    )
    if cost["breakdown"]:
        for mat, info in sorted(cost["breakdown"].items(), key=lambda x: -x[1]["cost"]):
            lines.append(
                f"  - {mat}: {info['parts']} part, {info['area_m2']:.2f} m² → "
                f"Rp {info['cost']:,.0f}"
            )
    lines.append("")
    lines.append("_💡 Pakai `!cutlist last` buat optimize cutting layout dari BOM ini._")
    lines.append("")
    return lines


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
    ]
    lines.extend(_format_title_block(result.title_block))
    lines.append(f"_{result.summary}_")
    lines.append("")

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
        lines.append("")

    lines.extend(_format_bom_section(result.bom))

    return "\n".join(lines)


QC_HELP_TEXT = (
    "📋 **`!qc` — Furniture Drawing QC**\n"
    "• `!qc` + PDF/PNG/JPG/DXF → review (dimensi, sambungan, view, BOM, cost estimate)\n"
    "• `!qc diff` + 2 attachment → bandingin rev_a vs rev_b\n"
    "\n"
    "💡 DXF: ground-truth dimensi (akurasi 100%).\n"
    "💡 PDF: balikan PDF marked-up dgn sticky note — buka di Acrobat.\n"
    "💡 BOM auto-extract → lanjut `!cutlist last` buat cutting plan.\n"
    "⚠️ Test pakai project pribadi. JANGAN drawing client/perusahaan."
)


async def handle_qc_wa(message_text: str, attachment_paths: list[str]) -> dict:
    """WA entry point untuk `!qc`. Return dict siap-balik buat WA bridge.

    Skema sama dengan response /chat di wa_server.py — bridge JS auto-handle
    `response` (text) + `output_files` (markup PNGs jadi attachment WA).
    """
    base = {"status": "ok", "voice_file": None, "voice_mode": None, "output_files": []}

    # Diff mode: `!qc diff` + 2 attachments → bandingin rev_a vs rev_b
    SUPPORTED = (".pdf", ".png", ".jpg", ".jpeg", ".webp", ".dxf")
    if message_text.lower().lstrip("!/ ").startswith("qc diff"):
        diff_targets = [p for p in attachment_paths if p.lower().endswith(SUPPORTED)][:2]
        if len(diff_targets) < 2:
            return {
                **base,
                "response": (
                    "❌ `!qc diff` butuh **2 attachment** (rev_a + rev_b).\n"
                    "Upload 2 PDF/PNG/JPG/DXF, urut yg lama dulu lalu yg baru."
                ),
            }
        try:
            files = [(Path(p).read_bytes(), Path(p).name) for p in diff_targets]
            diff = await review_diff_from_bytes(files)
        except Exception as e:
            logger.exception("[qc-wa-diff] gagal")
            return {**base, "response": f"❌ Diff gagal: `{e}`"}
        name_a, name_b = Path(diff_targets[0]).name, Path(diff_targets[1]).name
        text = format_diff_for_discord(diff, name_a, name_b)
        logger.info(
            f"[qc-wa-diff] done: {name_a} vs {name_b} → "
            f"{diff.overall_change_level} ({len(diff.changes)} changes)"
        )
        return {**base, "response": text}

    if not attachment_paths:
        return {**base, "response": QC_HELP_TEXT}

    # Pilih attachment pertama yang format-nya didukung (skip audio dll)
    target = next((p for p in attachment_paths if p.lower().endswith(SUPPORTED)), None)
    if target is None:
        return {
            **base,
            "response": "❌ Format file gak didukung. Pakai PDF/PNG/JPG/WEBP buat gambar kerja.",
        }

    p = Path(target)
    if not p.exists():
        return {**base, "response": f"❌ File gak ketemu di server: `{target}`"}

    size_mb = p.stat().st_size / 1024 / 1024
    if size_mb > MAX_FILE_MB:
        return {
            **base,
            "response": f"❌ File terlalu besar ({size_mb:.1f} MB). Max {MAX_FILE_MB} MB.",
        }

    try:
        result, images_b64, pdf_bytes = await review_local_file(str(p))
    except Exception as e:
        logger.exception("[qc-wa] gagal review")
        return {**base, "response": f"❌ Gagal review `{p.name}`: `{e}`"}

    text = format_result_for_discord(result)  # markdown-style, kompat sama WA juga

    output_files: list[str] = []
    try:
        artifacts = await asyncio.to_thread(
            _make_markup_artifacts, result, images_b64, pdf_bytes
        )
        if artifacts:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            slug = os.urandom(4).hex()
            for sugg_name, blob in artifacts:
                out_path = OUTPUT_DIR / f"qc_wa_{slug}_{sugg_name}"
                out_path.write_bytes(blob)
                output_files.append(str(out_path))
    except Exception as e:
        logger.warning(f"[qc-wa] markup gagal (text reply tetep kirim): {e}")

    _log_qc_session(f"!qc {p.name}", result)
    if result.bom:
        save_last_bom(p.name, result.bom, result.title_block)

    logger.info(
        f"[qc-wa] done: {p.name} → {result.overall_verdict} "
        f"({len(result.issues)} issues, {len(result.bom)} BOM parts)"
    )
    return {**base, "response": text, "output_files": output_files[:10]}


def _log_qc_session(perintah: str, result: "QCResult") -> None:
    """Persist QC outcome ke T1 session log biar history-able lewat manager memory.

    Best-effort — gagal log gak boleh ganggu user reply.
    """
    try:
        from teams.t1_manager import simpan_sesi
        hasil = (
            f"[QC] verdict={result.overall_verdict} "
            f"issues={len(result.issues)} (crit={sum(1 for i in result.issues if i.severity == 'critical')}). "
            f"{result.summary}"
        )
        simpan_sesi(perintah, hasil)
    except Exception as e:
        logger.debug(f"[qc] simpan_sesi skip: {e}")


async def _review_one_discord_attachment(message, att) -> None:
    """Review 1 Discord attachment + kirim reply (text + markup)."""
    if att.size and att.size > MAX_FILE_MB * 1024 * 1024:
        await message.reply(
            f"❌ `{att.filename}` terlalu besar "
            f"({att.size / 1024 / 1024:.1f} MB). Max {MAX_FILE_MB} MB."
        )
        return

    progress = await message.reply(f"🔍 Lagi review `{att.filename}`... (~10-30 detik)")
    try:
        result, images_b64, pdf_bytes = await review_attachment(att.url, att.filename)
        text = format_result_for_discord(result)
        if len(text) > DISCORD_MSG_LIMIT:
            text = text[: DISCORD_MSG_LIMIT - 30] + "\n\n... _(terpotong)_"
        await progress.edit(content=text)

        try:
            artifacts = await asyncio.to_thread(
                _make_markup_artifacts, result, images_b64, pdf_bytes
            )
            files = [
                discord.File(BytesIO(blob), filename=fname)
                for fname, blob in artifacts
            ][:10]  # Discord max 10 attachments
            if files:
                caption = (
                    f"🖍 PDF marked-up (sticky note + box) — buka di Acrobat: `{att.filename}`"
                    if pdf_bytes else
                    f"🖍 Markup visual buat `{att.filename}`:"
                )
                await message.channel.send(
                    content=caption,
                    files=files,
                    reference=message,
                )
        except Exception as e:
            logger.warning(f"[qc] markup gagal (text reply tetep kirim): {e}")

        _log_qc_session(f"!qc {att.filename}", result)
        if result.bom:
            save_last_bom(att.filename, result.bom, result.title_block)
        logger.info(
            f"[qc] done: {att.filename} → {result.overall_verdict} "
            f"({len(result.issues)} issues, {len(result.bom)} BOM parts)"
        )
    except Exception as e:
        logger.exception("[qc] gagal review")
        await progress.edit(content=f"❌ Gagal review `{att.filename}`: `{e}`")


async def handle_qc_command(message, bot_client=None) -> None:
    """Discord `!qc` handler.

    Usage:
        `!qc` + 1+ attachment → review per file
        `!qc diff` + 2 attachment → bandingin rev_a vs rev_b
    """
    if not message.attachments:
        await message.reply(QC_HELP_TEXT)
        return

    SUPPORTED = (".pdf", ".png", ".jpg", ".jpeg", ".webp", ".dxf")
    targets = [
        att for att in message.attachments
        if att.filename.lower().endswith(SUPPORTED)
    ]
    if not targets:
        await message.reply(
            "❌ Gak ada attachment yg format-nya didukung. Pakai PDF/PNG/JPG/WEBP."
        )
        return

    # Diff mode
    body_lower = (message.content or "").lower().lstrip("!/ ")
    if body_lower.startswith("qc diff"):
        if len(targets) < 2:
            await message.reply(
                "❌ `!qc diff` butuh **2 attachment** (rev_a + rev_b). "
                "Urut yg lama dulu lalu yg baru."
            )
            return
        att_a, att_b = targets[0], targets[1]
        progress = await message.reply(
            f"🔄 Lagi diff `{att_a.filename}` vs `{att_b.filename}`... (~15-40 detik)"
        )
        try:
            async with httpx.AsyncClient(timeout=60) as cx:
                bytes_a = (await cx.get(att_a.url, follow_redirects=True)).content
                bytes_b = (await cx.get(att_b.url, follow_redirects=True)).content
            diff = await review_diff_from_bytes(
                [(bytes_a, att_a.filename), (bytes_b, att_b.filename)]
            )
            text = format_diff_for_discord(diff, att_a.filename, att_b.filename)
            if len(text) > DISCORD_MSG_LIMIT:
                text = text[: DISCORD_MSG_LIMIT - 30] + "\n\n... _(terpotong)_"
            await progress.edit(content=text)
            logger.info(
                f"[qc-diff] done: {att_a.filename} vs {att_b.filename} → "
                f"{diff.overall_change_level} ({len(diff.changes)} changes)"
            )
        except Exception as e:
            logger.exception("[qc-diff] gagal")
            await progress.edit(content=f"❌ Diff gagal: `{e}`")
        return

    skipped = len(message.attachments) - len(targets)
    if skipped:
        await message.reply(f"ℹ️ Skip {skipped} file format gak didukung, review {len(targets)} sisanya...")

    for att in targets:
        await _review_one_discord_attachment(message, att)
