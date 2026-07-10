"""Unit tests untuk core/qc_visual_diff.py — pixel-diff revisi gambar kerja.

Jalankan: pytest tests/test_qc_visual_diff.py -v
Semua offline: synthetic image via PIL, nol API call.
"""
import base64
from io import BytesIO

import numpy as np
from PIL import Image, ImageDraw

from core.qc_visual_diff import (
    PageDiff,
    _COLOR_ADDED,
    _COLOR_REMOVED,
    build_hint_text,
    diff_from_b64,
)

W, H = 800, 600
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)


def _draw_base_pattern(draw: ImageDraw.ImageDraw, ox: int = 0, oy: int = 0) -> None:
    """Pola dasar gambar kerja sintetis — banyak sudut biar ORB dapet fitur.

    Area (400..500, 300..400) sengaja dikosongin buat test add/remove rect.
    """
    # Border frame + kop kanan-bawah
    draw.rectangle([10 + ox, 10 + oy, 780 + ox, 580 + oy], outline=BLACK, width=3)
    draw.rectangle([560 + ox, 480 + oy, 780 + ox, 580 + oy], outline=BLACK, width=2)
    # Grid "tampak depan" kiri-atas
    for i in range(4):
        draw.rectangle(
            [40 + i * 70 + ox, 40 + oy, 90 + i * 70 + ox, 120 + oy],
            outline=BLACK, width=2,
        )
    # Garis dimensi diagonal + horizontal
    draw.line([40 + ox, 200 + oy, 350 + ox, 260 + oy], fill=BLACK, width=2)
    draw.line([40 + ox, 400 + oy, 300 + ox, 400 + oy], fill=BLACK, width=2)
    # Lingkaran (simbol hardware) — posisi asimetris
    draw.ellipse([600 + ox, 60 + oy, 660 + ox, 120 + oy], outline=BLACK, width=3)
    draw.ellipse([650 + ox, 200 + oy, 690 + ox, 240 + oy], outline=BLACK, width=3)
    # Blok "teks" (rect kecil-kecil, mirip baris label)
    for j in range(5):
        draw.rectangle(
            [60 + ox, 440 + j * 22 + oy, 60 + 90 - j * 12 + ox, 452 + j * 22 + oy],
            fill=BLACK,
        )
    # Marker unik pojok (anti-ambigu matching)
    draw.polygon(
        [(720 + ox, 30 + oy), (760 + ox, 30 + oy), (740 + ox, 70 + oy)], fill=BLACK
    )


def _page_png(extra_rect: bool = False, offset: tuple[int, int] = (0, 0)) -> bytes:
    img = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)
    _draw_base_pattern(draw, *offset)
    if extra_rect:
        draw.rectangle([400, 300, 500, 400], fill=BLACK)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _b64(png: bytes) -> str:
    return base64.b64encode(png).decode()


def _anaglyph_has_color(png: bytes, color: tuple[int, int, int]) -> bool:
    img = np.array(Image.open(BytesIO(png)).convert("RGB"))
    return bool(np.any(np.all(img == np.array(color, dtype=np.uint8), axis=-1)))


class TestIdenticalPages:
    def test_low_change_and_no_regions(self):
        page = _page_png()
        (d,) = diff_from_b64([_b64(page)], [_b64(page)])
        assert d.aligned is True
        assert d.changed_ratio < 0.002
        assert d.regions == ()
        assert d.anaglyph_png is not None


class TestAddedAndRemoved:
    def test_added_rect_detected_as_region(self):
        a = _page_png(extra_rect=False)
        b = _page_png(extra_rect=True)
        (d,) = diff_from_b64([_b64(a)], [_b64(b)])
        assert d.aligned is True
        assert d.changed_ratio > 0.005
        # Rect baru di normalized (0.5, 0.5, 0.625, ~0.667) — minimal 1 region intersect
        exp = (400 / W, 300 / H, 500 / W, 400 / H)
        assert any(
            r[0] < exp[2] and r[2] > exp[0] and r[1] < exp[3] and r[3] > exp[1]
            for r in d.regions
        ), f"regions {d.regions} gak ada yang overlap {exp}"

    def test_added_rect_shows_green_in_anaglyph(self):
        a = _page_png(extra_rect=False)
        b = _page_png(extra_rect=True)
        (d,) = diff_from_b64([_b64(a)], [_b64(b)])
        assert d.anaglyph_png is not None
        assert _anaglyph_has_color(d.anaglyph_png, _COLOR_ADDED)

    def test_removed_rect_shows_magenta_in_anaglyph(self):
        a = _page_png(extra_rect=True)
        b = _page_png(extra_rect=False)
        (d,) = diff_from_b64([_b64(a)], [_b64(b)])
        assert d.anaglyph_png is not None
        assert _anaglyph_has_color(d.anaglyph_png, _COLOR_REMOVED)


class TestAlignment:
    def test_shifted_page_gets_aligned(self):
        """Konten sama tapi geser cetak (12,8)px → alignment harus meng-cancel shift."""
        a = _page_png()
        b = _page_png(offset=(12, 8))
        (d,) = diff_from_b64([_b64(a)], [_b64(b)])
        assert d.aligned is True
        # Tanpa alignment, shift 12px bakal bikin changed_ratio gede (semua garis dobel)
        assert d.changed_ratio < 0.01

    def test_blank_page_fails_graceful(self):
        a = _page_png()
        blank = Image.new("RGB", (W, H), WHITE)
        buf = BytesIO()
        blank.save(buf, format="PNG")
        (d,) = diff_from_b64([_b64(a)], [_b64(buf.getvalue())])
        assert d.aligned is False
        assert d.anaglyph_png is None
        assert d.regions == ()

    def test_invalid_bytes_fail_graceful(self):
        (d,) = diff_from_b64([_b64(b"bukan png")], [_b64(_page_png())])
        assert d.aligned is False


class TestPairing:
    def test_pairs_capped_at_min_page_count(self):
        page = _b64(_page_png())
        diffs = diff_from_b64([page, page], [page])
        assert len(diffs) == 1
        assert diffs[0].page == 1


class TestHintText:
    def test_empty_when_all_unaligned(self):
        diffs = (
            PageDiff(page=1, aligned=False, changed_ratio=-1.0, regions=(), anaglyph_png=None),
        )
        assert build_hint_text(diffs, 1, 1) == ""

    def test_contains_regions_and_warning(self):
        diffs = (
            PageDiff(
                page=1, aligned=True, changed_ratio=0.0234,
                regions=((0.12, 0.3, 0.25, 0.41),), anaglyph_png=b"x",
            ),
            PageDiff(page=2, aligned=False, changed_ratio=-1.0, regions=(), anaglyph_png=None),
        )
        text = build_hint_text(diffs, 3, 2)
        assert "PIXEL-DIFF" in text
        assert "2.34%" in text
        assert "[0.12, 0.3, 0.25, 0.41]" in text
        assert "Halaman 2: alignment gagal" in text
        assert "REV_A=3" in text  # page count mismatch note
        assert "JANGAN mengarang" in text

    def test_identical_page_reported_as_no_change(self):
        diffs = (
            PageDiff(page=1, aligned=True, changed_ratio=0.0, regions=(), anaglyph_png=b"x"),
        )
        text = build_hint_text(diffs, 1, 1)
        assert "identik" in text
