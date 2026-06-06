"""Cutting list optimizer — 2D bin packing buat panel kayu/plywood.

Pipeline: text BOM input → rectpack MaxRectsBssf → layout per sheet + efisiensi.
Plus visualization: matplotlib render layout per sheet sebagai PNG (1 file grid).

Default panel size dari env `CUTLIST_DEFAULT_PANEL` (format `WxH` mm),
fallback 2440x1220 (lembaran plywood/MDF Indo standar).
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

logger = logging.getLogger("bima_core.cutlist")

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"


def _parse_default_panel() -> tuple[float, float]:
    raw = os.environ.get("CUTLIST_DEFAULT_PANEL", "2440x1220")
    try:
        w_s, h_s = raw.lower().split("x", 1)
        return float(w_s), float(h_s)
    except (ValueError, AttributeError):
        logger.warning(f"[cutlist] CUTLIST_DEFAULT_PANEL='{raw}' invalid, pakai 2440x1220")
        return 2440.0, 1220.0


DEFAULT_PANEL = _parse_default_panel()

_PANEL_RE = re.compile(
    r"panel\s*[:=]\s*([\d.]+)\s*[x×]\s*([\d.]+)", re.IGNORECASE
)
_PART_RE = re.compile(
    r"^\s*[-•*]?\s*(.+?)\s+([\d.]+)\s*[x×]\s*([\d.]+)\s*(?:[x×]\s*(\d+))?\s*$",
    re.IGNORECASE,
)

CUTLIST_HELP_TEXT = (
    "🪚 **`!cutlist` — Cutting List Optimizer**\n"
    "Format (multi-line, qty optional):\n"
    "```\n"
    "!cutlist\n"
    "panel: 2440x1220\n"
    "top 600x400 x2\n"
    "side 800x300 x4\n"
    "back 580x380\n"
    "```\n"
    f"Default panel: {DEFAULT_PANEL[0]:.0f}×{DEFAULT_PANEL[1]:.0f}mm "
    "(override pakai `panel: WxH` di baris pertama).\n"
    "Output: text layout + PNG visualization (1 file grid per sheet).\n"
    "Pakai `!cutlist last` buat solve dari BOM auto-extracted `!qc` terakhir."
)


@dataclass
class CutPart:
    name: str
    width: float
    height: float
    qty: int


@dataclass
class _PackedRect:
    name: str
    x: float
    y: float
    width: float
    height: float


@dataclass
class CutlistOutput:
    text: str
    png_bytes: bytes | None = None
    sheets_count: int = 0
    efficiency_pct: float = 0.0


def parse_cutlist_input(
    text: str, default_panel: tuple[float, float] = DEFAULT_PANEL
) -> tuple[tuple[float, float], list[CutPart]]:
    """Parse text body jadi (panel_size, parts). Raise ValueError kalau gak ada parts."""
    panel = default_panel
    parts: list[CutPart] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        m = _PANEL_RE.search(line)
        if m:
            panel = (float(m.group(1)), float(m.group(2)))
            continue
        m = _PART_RE.match(line)
        if m:
            name = m.group(1).strip().rstrip(":")
            w = float(m.group(2))
            h = float(m.group(3))
            qty = int(m.group(4)) if m.group(4) else 1
            if w <= 0 or h <= 0 or qty <= 0:
                continue
            # Cek KEDUA dimensi: part harus muat di panel (rotation diizinkan,
            # jadi cukup cek min dimension part ≤ min panel dan max ≤ max)
            part_min, part_max = min(w, h), max(w, h)
            panel_min, panel_max = min(panel[0], panel[1]), max(panel[0], panel[1])
            if part_min > panel_min or part_max > panel_max:
                raise ValueError(
                    f"Part `{name}` {w:.0f}×{h:.0f} lebih besar dari panel "
                    f"{panel[0]:.0f}×{panel[1]:.0f} — gak akan muat."
                )
            parts.append(CutPart(name=name, width=w, height=h, qty=qty))
    if not parts:
        raise ValueError(
            "Gak ada parts yg bisa di-parse. Format per baris: `nama <w>x<h> x<qty>`"
        )
    return panel, parts


def _solve_internal(
    panel: tuple[float, float], parts: list[CutPart]
) -> tuple[list[list[_PackedRect]], int, int, float]:
    """Run rectpack. Return (sheets, total_parts, packed_count, total_part_area)."""
    from rectpack import newPacker, MaxRectsBssf

    packer = newPacker(pack_algo=MaxRectsBssf, rotation=True)
    rid_to_name: dict[int, str] = {}
    rid = 0
    total_parts = 0
    total_part_area = 0.0
    for part in parts:
        for _ in range(part.qty):
            packer.add_rect(part.width, part.height, rid=rid)
            rid_to_name[rid] = part.name
            rid += 1
            total_parts += 1
            total_part_area += part.width * part.height

    panel_area = panel[0] * panel[1]
    min_sheets = max(1, int(total_part_area / panel_area) + 1)
    for _ in range(min_sheets + 5):
        packer.add_bin(panel[0], panel[1])
    packer.pack()

    sheets: list[list[_PackedRect]] = []
    packed_count = 0
    for abin in packer:
        rects = list(abin)
        if not rects:
            continue
        sheet = [
            _PackedRect(
                name=rid_to_name.get(r.rid, "?"),
                x=r.x, y=r.y, width=r.width, height=r.height,
            )
            for r in rects
        ]
        sheets.append(sheet)
        packed_count += len(sheet)
    return sheets, total_parts, packed_count, total_part_area


def _format_text(
    panel: tuple[float, float],
    sheets: list[list[_PackedRect]],
    total_parts: int,
    packed_count: int,
    total_part_area: float,
) -> str:
    """Build markdown summary dari structured solver result."""
    sheets_used = len(sheets)
    unplaced = total_parts - packed_count
    panel_area = panel[0] * panel[1]
    total_sheet_area = sheets_used * panel_area
    efficiency = (total_part_area / total_sheet_area * 100) if total_sheet_area else 0.0

    header = [
        "🪚 **Cutting List Result**",
        f"Panel: {panel[0]:.0f}×{panel[1]:.0f}mm",
        f"Total parts: {total_parts}  •  Packed: {packed_count}"
        + (f"  •  ⚠️ Unplaced: {unplaced}" if unplaced else ""),
        f"Sheets dipake: **{sheets_used}**",
        f"Efisiensi material: **{efficiency:.1f}%**",
    ]
    sheets_lines: list[str] = []
    for idx, sheet in enumerate(sheets, start=1):
        sheets_lines.append(
            f"\n**Sheet {idx}** ({panel[0]:.0f}×{panel[1]:.0f}mm) — {len(sheet)} part"
        )
        for r in sheet:
            sheets_lines.append(
                f"- `{r.name}` @ ({r.x:.0f}, {r.y:.0f}) → "
                f"{r.width:.0f}×{r.height:.0f}"
            )
    return "\n".join(header + sheets_lines)


def _render_layout_png(
    panel: tuple[float, float],
    sheets: list[list[_PackedRect]],
    packed_count: int,
    total_parts: int,
    efficiency_pct: float,
) -> bytes:
    """Render multi-sheet cutting layout sebagai 1 PNG grid. Pakai matplotlib Agg backend."""
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    import matplotlib.patches as patches
    import matplotlib.cm as cm

    n = len(sheets)
    if n == 0:
        return b""

    cols = 1 if n == 1 else 2
    rows = (n + cols - 1) // cols
    panel_w, panel_h = panel

    fig = Figure(figsize=(cols * 8, rows * 5), dpi=120)
    FigureCanvasAgg(fig)

    cmap = cm.get_cmap("tab20")

    for idx, sheet_rects in enumerate(sheets):
        ax = fig.add_subplot(rows, cols, idx + 1)
        margin = max(panel_w, panel_h) * 0.04
        ax.set_xlim(-margin, panel_w + margin)
        ax.set_ylim(panel_h + margin, -margin)  # invert Y, drawing convention
        ax.set_aspect("equal")
        ax.set_title(
            f"Sheet {idx + 1} — {panel_w:.0f}×{panel_h:.0f}mm ({len(sheet_rects)} part)",
            fontsize=11, weight="bold",
        )

        ax.add_patch(patches.Rectangle(
            (0, 0), panel_w, panel_h,
            linewidth=2.5, edgecolor="black", facecolor="#fafafa", zorder=1,
        ))

        for i, r in enumerate(sheet_rects):
            color = cmap(i % 20)
            ax.add_patch(patches.Rectangle(
                (r.x, r.y), r.width, r.height,
                linewidth=1, edgecolor="black",
                facecolor=color, alpha=0.75, zorder=2,
            ))
            # Auto-scale font berdasarkan ukuran rect — kecil = font kecil
            font_dim = min(r.width, r.height)
            fontsize = max(6, min(11, int(font_dim / 50)))
            ax.text(
                r.x + r.width / 2, r.y + r.height / 2,
                f"{r.name}\n{r.width:.0f}×{r.height:.0f}",
                ha="center", va="center", fontsize=fontsize, weight="bold",
                zorder=3,
            )
        ax.set_xlabel("mm", fontsize=9)
        ax.tick_params(labelsize=8)
        ax.grid(True, alpha=0.25, linestyle="--", zorder=0)

    fig.suptitle(
        f"Cutting Layout — {packed_count}/{total_parts} parts, {efficiency_pct:.1f}% efficient",
        fontsize=14, weight="bold", y=0.995,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.97])

    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    return buf.getvalue()


def solve_cutlist_full(
    panel: tuple[float, float], parts: list[CutPart]
) -> CutlistOutput:
    """Pack parts + render visualization. Return CutlistOutput dgn text + PNG bytes."""
    sheets, total_parts, packed_count, total_part_area = _solve_internal(panel, parts)
    text = _format_text(panel, sheets, total_parts, packed_count, total_part_area)
    panel_area = panel[0] * panel[1]
    total_sheet_area = len(sheets) * panel_area
    efficiency = (total_part_area / total_sheet_area * 100) if total_sheet_area else 0.0

    png_bytes: bytes | None = None
    try:
        png_bytes = _render_layout_png(panel, sheets, packed_count, total_parts, efficiency)
    except Exception as e:
        logger.warning(f"[cutlist] viz render gagal (text reply tetep kirim): {e}")

    return CutlistOutput(
        text=text, png_bytes=png_bytes,
        sheets_count=len(sheets), efficiency_pct=efficiency,
    )


def solve_cutlist(panel: tuple[float, float], parts: list[CutPart]) -> str:
    """Backward-compat wrapper: text-only output."""
    return solve_cutlist_full(panel, parts).text


def _solve_from_cached_bom(
    panel_override: tuple[float, float] | None = None,
) -> CutlistOutput:
    """Read BOM dari cache file (last `!qc`), solve + viz."""
    from core.furniture_qc import load_last_bom

    cached = load_last_bom()
    if cached is None:
        return CutlistOutput(text=(
            "❌ Belum ada BOM cache. Jalanin `!qc <drawing.pdf>` dulu — kalau drawing-nya "
            "punya tabel BOM terbaca, Anisa bakal auto-extract & simpan.\n\n"
            "Atau pakai `!cutlist` manual dengan input BOM text."
        ))

    panel = panel_override or DEFAULT_PANEL
    parts: list[CutPart] = []
    skipped: list[str] = []
    for item in cached.get("bom", []):
        try:
            w = float(item["width"])
            h = float(item["height"])
            qty = int(item.get("qty", 1))
            name = str(item.get("name", "part"))
            if w <= 0 or h <= 0 or qty <= 0:
                skipped.append(name)
                continue
            part_min, part_max = min(w, h), max(w, h)
            panel_min, panel_max = min(panel[0], panel[1]), max(panel[0], panel[1])
            if part_min > panel_min or part_max > panel_max:
                skipped.append(f"{name} (terlalu besar)")
                continue
            parts.append(CutPart(name=name, width=w, height=h, qty=qty))
        except (KeyError, ValueError, TypeError):
            continue

    if not parts:
        return CutlistOutput(text=(
            f"❌ Cache BOM kosong / invalid (file: {cached.get('filename', '?')}). "
            "Jalanin `!qc` ulang."
        ))

    out = solve_cutlist_full(panel, parts)
    header = (
        f"📦 _BOM dari `{cached.get('filename', '?')}` "
        f"({len(parts)} part, skipped {len(skipped)})_\n\n"
    )
    out.text = header + out.text
    return out


def handle_cutlist_full(body: str) -> CutlistOutput:
    """End-to-end: text body → CutlistOutput (text + viz PNG).

    Special: `last [WxH]` → pakai BOM dari cache QC terakhir, override panel optional.
    """
    body = body.strip()
    if not body:
        return CutlistOutput(text=CUTLIST_HELP_TEXT)

    if body.lower().startswith("last"):
        rest = body[4:].strip()
        panel_override: tuple[float, float] | None = None
        if rest:
            bare = re.match(r"([\d.]+)\s*[x×]\s*([\d.]+)", rest, re.IGNORECASE)
            if bare:
                panel_override = (float(bare.group(1)), float(bare.group(2)))
        return _solve_from_cached_bom(panel_override)

    try:
        panel, parts = parse_cutlist_input(body)
        return solve_cutlist_full(panel, parts)
    except ValueError as e:
        return CutlistOutput(text=f"❌ {e}\n\n{CUTLIST_HELP_TEXT}")
    except Exception as e:
        logger.exception("[cutlist] solver gagal")
        return CutlistOutput(text=f"❌ Cutlist solver error: `{e}`")


def handle_cutlist_text(body: str) -> str:
    """Backward-compat: text-only return."""
    return handle_cutlist_full(body).text


async def handle_cutlist_wa(message_text: str) -> dict:
    """WA entry: strip prefix, return dict siap-balik (response + output_files PNG layout)."""
    parts = message_text.split(None, 1)
    body = parts[1] if len(parts) > 1 else ""
    out = handle_cutlist_full(body)

    output_files: list[str] = []
    if out.png_bytes:
        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            slug = os.urandom(4).hex()
            png_path = OUTPUT_DIR / f"cutlist_wa_{slug}_layout.png"
            png_path.write_bytes(out.png_bytes)
            output_files.append(str(png_path))
        except Exception as e:
            logger.warning(f"[cutlist-wa] save PNG gagal: {e}")

    return {
        "status": "ok",
        "response": out.text,
        "output_files": output_files,
        "voice_file": None,
        "voice_mode": None,
    }


async def handle_cutlist_command(message) -> None:
    """Discord entry: `!cutlist <body>`. Reply text + PNG attachment kalau ada viz."""
    parts = message.content.split(None, 1)
    body = parts[1] if len(parts) > 1 else ""
    out = handle_cutlist_full(body)

    text = out.text
    if len(text) > 1900:
        text = text[:1870] + "\n\n... _(terpotong)_"

    files = []
    if out.png_bytes:
        try:
            import discord
            files = [discord.File(BytesIO(out.png_bytes), filename="cutlist_layout.png")]
        except Exception as e:
            logger.warning(f"[cutlist-discord] discord.File gagal: {e}")

    if files:
        await message.reply(text, files=files)
    else:
        await message.reply(text)
