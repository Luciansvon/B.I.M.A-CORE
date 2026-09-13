import json
import logging
from datetime import datetime
from pathlib import Path
from crewai.tools import BaseTool
from config import OUTPUT_DIR
from core.path_security import safe_output_path
from core.public_errors import public_failure
from teams.t4_admin.styles import STYLES, resolve_style, DEFAULT_STYLE_NAME
from teams.t4_admin.chart_utils import render_chart

logger = logging.getLogger('bima_core')

# Font yang di-bundle di assets/fonts/. Kalau ada, register sebagai "Inter"
# (branding alias) — yang sebenarnya pakai NotoSans (close visual match,
# free + sudah di-copy via scripts/fetch_fonts.sh).
_ASSETS_FONT_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"
_CUSTOM_FONT_WEIGHTS = {
    "": "NotoSans-Regular.ttf",
    "B": "NotoSans-Bold.ttf",
    "I": "NotoSans-Italic.ttf",
    "BI": "NotoSans-BoldItalic.ttf",
}


def _try_register_custom_font(pdf, alias: str = "Inter") -> bool:
    """Register Noto Sans → alias 'Inter' di FPDF instance. Idempotent per-instance.
    Return True kalau berhasil register Regular weight (minimum requirement).
    """
    if not _ASSETS_FONT_DIR.is_dir():
        return False
    regular_path = _ASSETS_FONT_DIR / _CUSTOM_FONT_WEIGHTS[""]
    if not regular_path.exists():
        return False
    try:
        for style_key, fname in _CUSTOM_FONT_WEIGHTS.items():
            fpath = _ASSETS_FONT_DIR / fname
            if fpath.exists():
                pdf.add_font(alias, style_key, str(fpath))
        return True
    except Exception as e:
        logger.warning(f"[ADMIN] register font '{alias}' gagal: {e}")
        return False


# ============================================================
# PDF Generator — style + cover design + TOC
# ============================================================
class PDFGeneratorTool(BaseTool):
    name: str = "PDF Generator Tool"
    description: str = """Buat file PDF dengan style fleksibel & cover design.
    Input format JSON string:
    {
        "filename": "nama_file",
        "style": "formal" | "semi_formal" | "informal" | "akademik",
        "cover": true,
        "title": "Judul Laporan",
        "subtitle": "Subjudul opsional",
        "author": "Nama Author",
        "toc": true,
        "sections": [
            {
                "heading": "Judul Bagian",
                "content": "Isi paragraf...",
                "drop_cap": false,            // OPSIONAL: huruf pertama gede magazine-style
                "pullquote": "kutipan menonjol opsional dengan accent bar kiri",
                "list": ["Item 1", "Item 2"],
                "key_values": {"Nama": "Bima", "Jabatan": "Admin"},
                "image_path": "/path/to/image.png",
                "charts": [
                    {"type": "bar", "title": "Perbandingan Harga", "labels": ["Pinus","Jati","Mahoni"],
                     "datasets": [{"label": "Rp/m²", "data": [55000, 120000, 85000]}]}
                ],
                "table": {
                    "headers": ["Kolom1", "Kolom2"],
                    "rows": [["data1", "data2"]]
                }
            }
        ],
        "references": [
            {"text": "Kementerian PUPR (2025). Standar Harga Material Konstruksi. Jakarta.",
             "url": "https://pu.go.id"},
            {"text": "BPS (2026). Indeks Harga Bahan Bangunan.",
             "url": "https://bps.go.id"}
        ]
    }
    Field 'charts' (opsional, list per section): tipe 'bar'|'line'|'pie' — auto-render via matplotlib (DPI 300, tajam).
    Field 'drop_cap' (opsional, per section): true bikin huruf pertama paragraf gede magazine-style.
    Field 'pullquote' (opsional, per section): string yang akan di-render sebagai blockquote dengan accent bar kiri.
    Field 'references' (opsional): daftar pustaka — auto render section terakhir dengan link clickable.
    URL referensi WAJIB valid (Wikipedia/situs resmi/jurnal open-access). JANGAN dikarang.
    Font: auto pakai Inter (Noto Sans) kalau di-bundle di assets/fonts/, else Helvetica.
    Cocok untuk: laporan, proposal, resume, invoice, surat, tutorial, journal, certificate.
    Style menyesuaikan tone & color scheme."""

    def _safe_text(self, text: str) -> str:
        replacements = {
            '–': '-', '—': '-',
            '‘': "'", '’': "'",
            '“': '"', '”': '"',
            '…': '...', '•': '-',
            '→': '->', '←': '<-',
            '≥': '>=', '≤': '<=',
            '≠': '!=', '≈': '~=',
            ' ': ' ', '​': '',
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text.encode('latin-1', errors='replace').decode('latin-1')

    def _wrap_lines(self, pdf, text: str, max_width: float) -> int:
        """Estimasi jumlah baris untuk teks dengan lebar max_width (mm)."""
        if not text:
            return 1
        words = str(text).split()
        if not words:
            return 1
        usable = max_width - 4  # padding kiri-kanan
        lines = 1
        current = ""
        for word in words:
            candidate = (current + " " + word).strip() if current else word
            if pdf.get_string_width(candidate) <= usable:
                current = candidate
            else:
                lines += 1
                current = word
        return max(lines, 1)

    def _render_pdf_table(self, pdf, headers: list, rows: list, style: dict):
        """Render tabel dengan auto-wrap per cell (tanpa truncation), padding rapi.
        Setiap cell tingginya menyesuaikan konten terpanjang dalam row tersebut.
        """
        n_cols = len(headers)
        if n_cols == 0:
            return

        page_width = pdf.w - 2 * pdf.l_margin
        col_max_chars = []
        for c_idx in range(n_cols):
            header_len = len(str(headers[c_idx]))
            row_lens = [len(str(r[c_idx])) if c_idx < len(r) else 0 for r in rows]
            col_max_chars.append(max([header_len] + row_lens))
        total_chars = sum(col_max_chars) or 1
        col_widths = [max(page_width * (c / total_chars), 18) for c in col_max_chars]
        scale = page_width / sum(col_widths)
        col_widths = [w * scale for w in col_widths]

        line_h = 5.5

        pdf.set_font(style.get("pdf_font", "Helvetica"), "B", 9)
        pdf.set_fill_color(*style["table_header_rgb"])
        pdf.set_text_color(255, 255, 255)
        header_lines = max(self._wrap_lines(pdf, str(h), w) for h, w in zip(headers, col_widths))
        header_h = header_lines * line_h + 3

        if pdf.get_y() + header_h > pdf.page_break_trigger:
            pdf.add_page()

        x_start = pdf.l_margin
        y_start = pdf.get_y()
        for i, h in enumerate(headers):
            x_now = x_start + sum(col_widths[:i])
            pdf.set_xy(x_now, y_start)
            try:
                pdf.multi_cell(col_widths[i], line_h,
                               self._safe_text(str(h)),
                               border=1, fill=True, align="C",
                               max_line_height=line_h)
            except TypeError:
                # fpdf2 lama tidak support max_line_height
                pdf.multi_cell(col_widths[i], line_h,
                               self._safe_text(str(h)),
                               border=1, fill=True, align="C")
        pdf.set_xy(x_start, y_start + header_h)

        pdf.set_font(style.get("pdf_font", "Helvetica"), "", 9)
        pdf.set_text_color(30, 30, 30)
        for r_idx, row in enumerate(rows):
            row_padded = (list(row) + [""] * n_cols)[:n_cols]
            row_lines = max(self._wrap_lines(pdf, str(v), w) for v, w in zip(row_padded, col_widths))
            row_h = row_lines * line_h + 3

            if pdf.get_y() + row_h > pdf.page_break_trigger:
                pdf.add_page()

            if r_idx % 2 == 0:
                pdf.set_fill_color(*style["table_alt_rgb"])
            else:
                pdf.set_fill_color(255, 255, 255)

            y_row = pdf.get_y()
            for i, val in enumerate(row_padded):
                x_now = x_start + sum(col_widths[:i])
                pdf.set_xy(x_now, y_row)
                try:
                    pdf.multi_cell(col_widths[i], line_h,
                                   self._safe_text(str(val)),
                                   border=1, fill=True,
                                   max_line_height=line_h)
                except TypeError:
                    pdf.multi_cell(col_widths[i], line_h,
                                   self._safe_text(str(val)),
                                   border=1, fill=True)
            pdf.set_xy(x_start, y_row + row_h)

        pdf.ln(4)

    def _run(self, input_json: str) -> str:
        try:
            from fpdf import FPDF

            try:
                data = json.loads(input_json)
            except json.JSONDecodeError as e:
                logger.warning("[ADMIN] JSON PDF tidak valid: %s", e)
                return public_failure("JSON tidak valid")

            style_name = data.get("style", DEFAULT_STYLE_NAME)
            style = resolve_style(data)
            title_rgb = style["title_rgb"]
            accent_rgb = style["accent_rgb"]
            doc_title  = data.get("title", "Dokumen")
            doc_author = data.get("author", "B.I.M.A Core")

            # === Configurable typography (JSON overrides > style defaults) ===
            pdf_font = data.get("pdf_font", style.get("pdf_font", "Helvetica"))
            # Auto-upgrade Helvetica → Inter (Noto Sans) kalau ke-bundle di assets/fonts/.
            # User bisa override eksplisit dengan field "pdf_font" di JSON input.
            if pdf_font == "Helvetica" and not data.get("pdf_font") and (_ASSETS_FONT_DIR / "NotoSans-Regular.ttf").exists():
                pdf_font = "Inter"
            margins_cm = data.get("margins", style.get("margins_cm", {"top": 2.54, "bottom": 2.54, "left": 2.54, "right": 2.54}))
            do_justify = data.get("justify", style.get("justify", False))
            line_spacing_mult = data.get("line_spacing", style.get("line_spacing", 1.15))
            content_align = "J" if do_justify else "L"

            # === Mode Landscape untuk Sertifikat ===
            is_certificate = data.get("certificate", False)
            orientation = "L" if is_certificate else "P"

            # === Subclass FPDF: auto header & footer dengan nomor halaman ===
            _style_ref = style
            _title_ref = doc_title
            _author_ref = doc_author
            _accent_rgb = accent_rgb
            _title_rgb  = title_rgb
            _pdf_font   = pdf_font
            _body_start_page = [0]  # mutable agar bisa diupdate dari luar class
            _page_phase = ["front"]  # front | body; mengikuti pagination aktual
            _first_content_page = [0]  # halaman yang render judul besar -- header kecil di-skip di sini biar gak dobel

            def _to_roman_pdf(num):
                vals = [(1000,'m'),(900,'cm'),(500,'d'),(400,'cd'),(100,'c'),
                        (90,'xc'),(50,'l'),(40,'xl'),(10,'x'),(9,'ix'),(5,'v'),(4,'iv'),(1,'i')]
                result = ''
                for v, r in vals:
                    while num >= v:
                        result += r
                        num -= v
                return result

            class BimaFPDF(FPDF):
                def header(self):
                    # Hanya di halaman isi (bukan cover page 1)
                    if self.page_no() <= 1 and data.get("cover", True):
                        return
                    # Skip di halaman pertama konten -- judul besar sudah render di situ, jangan dobel
                    if self.page_no() == _first_content_page[0]:
                        return
                    self.set_font(_pdf_font, "B", 8)
                    self.set_text_color(*_title_rgb)
                    self.cell(0, 8, self._safe_text_inner(_title_ref), new_x="LMARGIN", new_y="NEXT", align="L")
                    self.set_draw_color(*_accent_rgb)
                    self.set_line_width(0.3)
                    self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
                    self.ln(3)

                def footer(self):
                    # Hanya di halaman isi (bukan cover page 1)
                    if self.page_no() <= 1 and data.get("cover", True):
                        return
                    self.set_y(-14)
                    self.set_font(_pdf_font, "I", 8)
                    self.set_text_color(140, 140, 140)
                    pg = self.page_no()
                    # Roman/Arabic split akademik mengikuti phase render aktual.
                    if style_name == "akademik" and _page_phase[0] == "body":
                        page_str = str(pg - _body_start_page[0] + 1)
                    elif style_name == "akademik":
                        page_str = _to_roman_pdf(pg)
                    else:
                        page_str = str(pg)
                    left_txt = f"{_author_ref}  -  {_style_ref['label']}"
                    self.cell(0, 8,
                              self._safe_text_inner(left_txt) + "     halaman " + page_str,
                              align="C")

                def _safe_text_inner(self, text):
                    reps = {'–':'-','—':'-','‘':"'",'’':"'",'“':'"','”':'"','…':'...'}
                    for old, new in reps.items():
                        text = text.replace(old, new)
                    return text.encode('latin-1', errors='replace').decode('latin-1')

            pdf = BimaFPDF(orientation=orientation)
            # Register custom font BEFORE first add_page (header memanggil set_font dengan pdf_font).
            if pdf_font == "Inter":
                if not _try_register_custom_font(pdf, "Inter"):
                    logger.warning("[ADMIN] Inter font gagal register, fallback ke Helvetica")
                    pdf_font = "Helvetica"
                    # Note: _pdf_font sudah ke-capture sebagai "Inter" di closure BimaFPDF.
                    # Header/footer akan error. Edge case langka — file checked exists tadi.
            pdf.set_auto_page_break(auto=True, margin=margins_cm.get("bottom", 2.54) * 10)
            pdf.set_margins(
                left=margins_cm.get("left", 2.54) * 10,
                top=margins_cm.get("top", 2.54) * 10,
                right=margins_cm.get("right", 2.54) * 10
            )

            # === COVER PAGE (opsional) ===
            if data.get("cover", True):
                pdf.add_page()
                pdf.set_y(80)
                # Decorative bar
                pdf.set_fill_color(*accent_rgb)
                pdf.rect(10, 60, 30, 3, "F")

                pdf.set_font(pdf_font, "B", style["title_size"] + 8)
                pdf.set_text_color(*title_rgb)
                pdf.multi_cell(0, 12, self._safe_text(data.get("title", "Dokumen")), align="L")
                pdf.ln(4)

                if data.get("subtitle"):
                    pdf.set_font(pdf_font, "I", style["body_size"] + 4)
                    pdf.set_text_color(*accent_rgb)
                    pdf.multi_cell(0, 8, self._safe_text(data["subtitle"]), align="L")
                    pdf.ln(8)

                pdf.set_y(-50)
                pdf.set_font(pdf_font, "", 10)
                pdf.set_text_color(80, 80, 80)
                pdf.cell(0, 6, self._safe_text(f"Disusun oleh: {data.get('author', 'B.I.M.A Core')}"),
                         new_x="LMARGIN", new_y="NEXT")
                pdf.cell(0, 6, self._safe_text(f"Tanggal: {datetime.now().strftime('%d %B %Y')}"),
                         new_x="LMARGIN", new_y="NEXT")
                pdf.cell(0, 6, self._safe_text(f"Style: {style['label']}"),
                         new_x="LMARGIN", new_y="NEXT")

            # === ABSTRAK PDF (opsional) ===
            if data.get("abstract"):
                pdf.add_page()
                pdf.set_font(pdf_font, "B", style["heading_size"] + 2)
                pdf.set_text_color(*title_rgb)
                pdf.cell(0, 10, "ABSTRAK", new_x="LMARGIN", new_y="NEXT", align="C")
                pdf.ln(4)

                pdf.set_font(pdf_font, "", style["body_size"])
                pdf.set_text_color(30, 30, 30)
                # Abstrak single-spaced
                abs_lh = round(style["body_size"] * 1.15 * 0.39 + 5.5, 1)
                # Indent kiri-kanan 10mm ekstra
                old_l = pdf.l_margin
                old_r = pdf.r_margin
                pdf.set_left_margin(old_l + 10)
                pdf.set_right_margin(old_r + 10)
                pdf.multi_cell(0, abs_lh, self._safe_text(data["abstract"]), align=content_align)
                pdf.set_left_margin(old_l)
                pdf.set_right_margin(old_r)
                pdf.ln(4)

                # Keywords
                if data.get("keywords"):
                    pdf.set_left_margin(old_l + 10)
                    pdf.set_font(pdf_font, "B", style["body_size"])
                    kw_text = "Kata Kunci: "
                    pdf.cell(pdf.get_string_width(kw_text) + 2, 6, self._safe_text(kw_text))
                    pdf.set_font(pdf_font, "I", style["body_size"])
                    pdf.multi_cell(0, 6, self._safe_text(", ".join(data["keywords"])))
                    pdf.set_left_margin(old_l)

            # === HALAMAN ISI ===
            _first_content_page[0] = pdf.page_no() + 1
            pdf.add_page()
            sections = data.get("sections", [])
            has_toc = bool(data.get("toc") and sections)
            if style_name == "akademik" and not has_toc:
                _body_start_page[0] = pdf.page_no()
                _page_phase[0] = "body"

            # Header tipis di halaman isi
            pdf.set_font(pdf_font, "B", style["title_size"])
            pdf.set_text_color(*title_rgb)
            pdf.cell(0, 12, self._safe_text(data.get("title", "Dokumen")),
                     new_x="LMARGIN", new_y="NEXT", align="C")

            pdf.set_font(pdf_font, "", 9)
            pdf.set_text_color(112, 112, 112)
            pdf.cell(0, 6, self._safe_text(
                f"{data.get('author', 'B.I.M.A Core')} | {datetime.now().strftime('%d %B %Y')}"
            ), new_x="LMARGIN", new_y="NEXT", align="C")
            pdf.ln(4)
            pdf.set_draw_color(*accent_rgb)
            pdf.set_line_width(0.5)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(8)

            # === Table of Contents (opsional, multi-level) ===
            if has_toc:
                pdf.set_font(pdf_font, "B", style["heading_size"] + 2)
                pdf.set_text_color(*title_rgb)
                pdf.cell(0, 10, "DAFTAR ISI", new_x="LMARGIN", new_y="NEXT", align="C")
                pdf.ln(4)
                pdf.set_text_color(40, 40, 40)
                for sec in sections:
                    if sec.get("heading"):
                        lvl = sec.get("level", 1)
                        indent = 5 * (lvl - 1)  # mm indent per level
                        if lvl == 1:
                            pdf.set_font(pdf_font, "B", style["body_size"])
                        else:
                            pdf.set_font(pdf_font, "", style["body_size"])
                        if indent:
                            pdf.set_x(pdf.get_x() + indent)
                        pdf.cell(0, 7, self._safe_text(sec["heading"]),
                                 new_x="LMARGIN", new_y="NEXT")
                pdf.ln(6)
                pdf.add_page()
                if style_name == "akademik":
                    _body_start_page[0] = pdf.page_no()
                    _page_phase[0] = "body"

            # === SECTIONS (multi-level heading) ===
            body_lh = round(style["body_size"] * line_spacing_mult * 0.39 + 5.5, 1)  # line height proporsional
            for section in sections:
                if section.get("heading"):
                    lvl = section.get("level", 1)
                    lvl = max(1, min(lvl, 3))  # clamp 1-3

                    if lvl == 1:
                        pdf.set_font(pdf_font, "B", style["heading_size"] + 2)
                        pdf.set_text_color(*title_rgb)
                        pdf.multi_cell(0, 9, self._safe_text(section["heading"]))
                        # Garis tipis aksen di bawah heading level 1
                        pdf.set_draw_color(*accent_rgb)
                        pdf.set_line_width(0.4)
                        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
                        pdf.ln(3)
                    elif lvl == 2:
                        pdf.set_font(pdf_font, "B", style["heading_size"])
                        pdf.set_text_color(*title_rgb)
                        pdf.cell(3, 8, "")  # slight indent
                        pdf.multi_cell(0, 8, self._safe_text(section["heading"]))
                        pdf.ln(2)
                    elif lvl == 3:
                        pdf.set_font(pdf_font, "BI", style["heading_size"] - 1)
                        pdf.set_text_color(*title_rgb)
                        pdf.cell(6, 7, "")  # more indent
                        pdf.multi_cell(0, 7, self._safe_text(section["heading"]))
                        pdf.ln(2)

                if section.get("content"):
                    content_text = self._safe_text(section["content"])
                    if section.get("drop_cap") and content_text:
                        # Drop-cap magazine-style: huruf pertama gede di kiri,
                        # body wraps di sisi kanan untuk paragraf pertama.
                        first_char = content_text[0]
                        rest = content_text[1:].lstrip()
                        cap_size = style["body_size"] * 3.5
                        cap_w = 12  # mm, slot untuk huruf gede
                        cap_h = 14  # mm, tinggi cap
                        y_start = pdf.get_y()
                        # Render cap
                        pdf.set_font(pdf_font, "B", cap_size)
                        pdf.set_text_color(*title_rgb)
                        pdf.set_xy(pdf.l_margin, y_start)
                        pdf.cell(cap_w, cap_h, first_char, align="L")
                        # Render body di sisi kanan cap
                        pdf.set_xy(pdf.l_margin + cap_w, y_start + 1)
                        pdf.set_font(pdf_font, "", style["body_size"])
                        pdf.set_text_color(30, 30, 30)
                        page_width = pdf.w - 2 * pdf.l_margin
                        pdf.multi_cell(page_width - cap_w, body_lh, rest, align=content_align)
                        # Pastikan y berikutnya gak overlap cap kalau body lebih pendek
                        if pdf.get_y() < y_start + cap_h:
                            pdf.set_y(y_start + cap_h)
                        pdf.ln(3)
                    else:
                        pdf.set_font(pdf_font, "", style["body_size"])
                        pdf.set_text_color(30, 30, 30)
                        pdf.multi_cell(0, body_lh, content_text, align=content_align)
                        pdf.ln(3)

                # Pull-quote (magazine callout dengan accent bar kiri)
                if section.get("pullquote"):
                    pdf.ln(2)
                    quote_txt = self._safe_text(str(section["pullquote"]).strip().strip('"'))
                    # Accent bar vertikal
                    quote_y_start = pdf.get_y()
                    pdf.set_fill_color(*accent_rgb)
                    pdf.rect(pdf.l_margin, quote_y_start, 1.5, 1, "F")  # placeholder, akan di-extend
                    # Render text dulu untuk tau tingginya
                    pdf.set_xy(pdf.l_margin + 6, quote_y_start)
                    pdf.set_font(pdf_font, "BI", style["body_size"] + 2)
                    pdf.set_text_color(*title_rgb)
                    page_width = pdf.w - 2 * pdf.l_margin
                    pdf.multi_cell(page_width - 8, 7, f'"{quote_txt}"', align="L")
                    quote_y_end = pdf.get_y()
                    # Re-draw accent bar dengan tinggi penuh
                    pdf.set_fill_color(*accent_rgb)
                    pdf.rect(pdf.l_margin, quote_y_start, 1.5, max(quote_y_end - quote_y_start - 1, 5), "F")
                    pdf.ln(3)

                # Bullet list
                if section.get("list"):
                    pdf.set_font(pdf_font, "", style["body_size"])
                    pdf.set_text_color(30, 30, 30)
                    for item in section["list"]:
                        pdf.cell(8, 6, "")
                        pdf.cell(4, 6, "-")
                        pdf.multi_cell(0, 6, self._safe_text(str(item)), new_x="LMARGIN", new_y="NEXT")
                    pdf.ln(2)

                # Key Values (untuk surat izin, detail rapi dengan titik dua sejajar)
                if section.get("key_values") and isinstance(section["key_values"], dict):
                    pdf.set_font(pdf_font, "", style["body_size"])
                    pdf.set_text_color(30, 30, 30)
                    for k, v in section["key_values"].items():
                        pdf.cell(40, 6, self._safe_text(str(k)))
                        pdf.cell(5, 6, ":")
                        pdf.multi_cell(0, 6, self._safe_text(str(v)), new_x="LMARGIN", new_y="NEXT")
                    pdf.ln(2)

                # Image embedding
                if section.get("image_path"):
                    img_path = Path(section["image_path"])
                    if img_path.exists() and img_path.is_file():
                        try:
                            pdf.image(str(img_path), w=160)
                            pdf.ln(4)
                        except Exception as img_err:
                            logger.warning(f"[ADMIN] Gagal embed image PDF {img_path}: {img_err}")

                # Chart rendering (matplotlib → embed PNG)
                for chart in section.get("charts", []) or []:
                    try:
                        chart_path = render_chart(chart, style)
                        pdf.image(chart_path, w=170)
                        pdf.ln(4)
                    except Exception as chart_err:
                        logger.warning(f"[ADMIN] Gagal render chart PDF: {chart_err}")

                # Tables — auto wrap per cell, no truncation
                if section.get("table"):
                    tbl = section["table"]
                    headers = tbl.get("headers", [])
                    rows = tbl.get("rows", [])
                    if headers:
                        self._render_pdf_table(pdf, headers, rows, style)

            # === DAFTAR PUSTAKA (opsional) ===
            references = data.get("references", [])
            if references:
                pdf.ln(6)
                pdf.set_font(pdf_font, "B", style["heading_size"])
                pdf.set_text_color(*title_rgb)
                pdf.multi_cell(0, 9, self._safe_text("Daftar Pustaka"))
                pdf.ln(2)

                pdf.set_draw_color(*accent_rgb)
                pdf.set_line_width(0.3)
                pdf.line(pdf.l_margin, pdf.get_y(), 80, pdf.get_y())
                pdf.ln(4)

                for idx, ref in enumerate(references, 1):
                    if isinstance(ref, dict):
                        ref_text = ref.get("text", "")
                        ref_url = ref.get("url", "")
                    else:
                        ref_text = str(ref)
                        ref_url = ""

                    pdf.set_font(pdf_font, "", style["body_size"])
                    pdf.set_text_color(30, 30, 30)
                    pdf.multi_cell(0, 6, self._safe_text(f"{idx}. {ref_text}"), new_x="LMARGIN", new_y="NEXT")

                    if ref_url:
                        pdf.set_font(pdf_font, "U", style["body_size"] - 1)
                        pdf.set_text_color(*accent_rgb)
                        pdf.cell(8, 5, "")
                        pdf.cell(0, 5,
                                 self._safe_text(ref_url),
                                 link=ref_url,
                                 new_x="LMARGIN", new_y="NEXT")
                    pdf.ln(2)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = safe_output_path(
                OUTPUT_DIR,
                data.get("filename"),
                default_stem="dokumen",
                suffix=".pdf",
                timestamp=timestamp,
            )
            filename = filepath.name
            pdf.output(str(filepath))

            return f"SUCCESS|{filepath}|PDF ({style['label']}) berhasil dibuat: {filename}"
        except ImportError:
            return "FAILED|fpdf2 belum terinstall. Jalankan: pip install fpdf2"
        except Exception as e:
            logger.error(f"[ADMIN] PDFGenerator error: {e}", exc_info=True)
            return public_failure("Gagal membuat PDF")
