"""SlideGeneratorTool — compile Marp Markdown into PDF, PPTX, HTML, or PNG images."""
from __future__ import annotations

import logging
import os
import subprocess
import time
import hashlib
from pathlib import Path
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

logger = logging.getLogger("bima_core")

_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"
_OUTPUT_DIR.mkdir(exist_ok=True)

class SlideGeneratorInput(BaseModel):
    markdown_content: str = Field(..., description="Raw Marp Markdown content of the slides, including directives, theme/custom CSS, and layout.")
    output_format: str = Field("pdf", description="Format output: 'pdf', 'pptx', 'html', atau 'png'. Default is 'pdf'.")
    theme_style: str = Field("default", description="Gaya desain furnitur (Scandinavian, Industrial, Rustic, Minimalist Wood, Modern) untuk log audit.")
    bypass_preview: bool = Field(False, description="Set ke True untuk langsung membuat file tanpa melalui approval preview. Default adalah False.")

class SlideGeneratorTool(BaseTool):
    name: str = "Slide Generation Tool"
    description: str = (
        "Generate slide presentasi profesional dari kode Marp Markdown + Custom CSS. "
        "Format output yang didukung: 'pdf', 'pptx', 'html', atau 'png' (image per slide). "
        "Gunakan tool ini ketika Bima meminta presentasi, slide, atau proposal furnitur. "
        "Input: markdown_content (str) + output_format (str: 'pdf'|'pptx'|'html'|'png') + theme_style (str) + bypass_preview (bool). "
        "Output: SUCCESS|<filepath>|<message> atau FAILED|<error>."
    )
    args_schema: type[BaseModel] = SlideGeneratorInput

    def _run(self, markdown_content: str, output_format: str = "pdf", theme_style: str = "default", bypass_preview: bool = False) -> str:
        markdown_content = (markdown_content or "").strip()
        if not markdown_content:
            return "FAILED|Markdown content kosong"

        output_format = output_format.lower().strip()
        if output_format not in ("pdf", "pptx", "html", "png"):
            return f"FAILED|Format output '{output_format}' tidak didukung. Pilihan: pdf, pptx, html, png."

        # 1. Alur Preview Gate jika tidak di-bypass
        if not bypass_preview and output_format != "png":
            logger.info("[SLIDE_GEN] Memicu pembuatan preview PNG untuk persetujuan Bima...")
            preview_res = self._run(
                markdown_content=markdown_content,
                output_format="png",
                theme_style=theme_style,
                bypass_preview=True
            )
            if not preview_res.startswith("SUCCESS|"):
                return f"FAILED|Gagal membuat preview slide: {preview_res}"
            
            png_paths_str = preview_res.split("|")[1]
            png_paths = png_paths_str.split(",")
            
            from core.permission_gate import check_permission_sync
            approved = check_permission_sync(
                action_type="SLIDE_PREVIEW_APPROVAL",
                details=f"Draf presentasi tema '{theme_style}'. Total {len(png_paths)} slide.",
                attachment_paths=png_paths
            )
            
            # Bersihkan file preview gambar setelah diposting ke Discord
            for p in png_paths:
                try:
                    Path(p).unlink(missing_ok=True)
                except Exception:
                    pass
            
            if not approved:
                return "FAILED|Persetujuan draf preview slide ditolak oleh Bima."

        slug = hashlib.md5(markdown_content.encode("utf-8")).hexdigest()[:8]
        ts = int(time.time())
        
        # Simpan file markdown ke outputs/ untuk kelestarian & audit
        md_file = _OUTPUT_DIR / f"slide_{slug}_{ts}.md"
        try:
            md_file.write_text(markdown_content, encoding="utf-8")
        except Exception as e:
            return f"FAILED|Gagal menulis file markdown sementara: {e}"

        # Tentukan file output
        if output_format == "png":
            # Jika PNG, Marp akan generate folder/file bertingkat seperti slide_xyz.001.png
            out_file = _OUTPUT_DIR / f"slide_{slug}_{ts}.png"
        else:
            out_file = _OUTPUT_DIR / f"slide_{slug}_{ts}.{output_format}"

        # Compile menggunakan Marp CLI via npx
        # --allow-local-files wajib agar gambar lokal disematkan ke PDF
        cmd = ["npx", "-y", "@marp-team/marp-cli@latest", "--allow-local-files"]
        if output_format == "pdf":
            cmd.append("--pdf")
        elif output_format == "pptx":
            cmd.append("--pptx")
        elif output_format == "html":
            cmd.append("--html")
        elif output_format == "png":
            cmd.append("--images")
            cmd.append("png")

        cmd.extend([str(md_file), "-o", str(out_file)])

        # Cari playwright chromium di WSL untuk render Marp
        playwright_chrome = None
        cache_dir = Path("/home/bima_lucian/.cache/ms-playwright")
        if cache_dir.exists():
            chromes = sorted(list(cache_dir.glob("**/chrome")), reverse=True)
            # filter yang file executable
            chromes = [c for c in chromes if c.is_file() and os.access(c, os.X_OK)]
            if chromes:
                playwright_chrome = str(chromes[0])

        chrome_path = playwright_chrome or "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"
        
        env = {
            **os.environ,
            "CHROME_PATH": chrome_path,
            "CHROME_NO_SANDBOX": "1"
        }

        logger.info(f"[SLIDE_GEN] Mengompilasi marp slide: {' '.join(cmd)} menggunakan {chrome_path}")
        try:
            # Jalankan dengan timeout 60 detik
            res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)
            if res.returncode != 0:
                logger.error(f"[SLIDE_GEN] Marp CLI error (code={res.returncode}): {res.stderr}")
                return f"FAILED|Kompilasi Marp gagal: {res.stderr or res.stdout}"
        except subprocess.TimeoutExpired:
            logger.error("[SLIDE_GEN] Kompilasi Marp timeout")
            return "FAILED|Kompilasi Marp timeout setelah 60 detik"
        except Exception as e:
            logger.exception("[SLIDE_GEN] Gagal menjalankan Marp CLI")
            return f"FAILED|Gagal menjalankan Marp CLI: {e}"

        # Periksa file output hasil kompilasi
        if output_format == "png":
            # Cari file png yang ter-generate (slide_slug_ts.001.png, dll)
            parent = out_file.parent
            pattern = f"slide_{slug}_{ts}.*.png"
            generated_pngs = sorted([str(p) for p in parent.glob(pattern)])
            if not generated_pngs:
                # Coba fallback tanpa nomor jika hanya 1 halaman
                single_png = parent / f"slide_{slug}_{ts}.png"
                if single_png.exists():
                    generated_pngs = [str(single_png)]
            
            if not generated_pngs:
                return "FAILED|Marp sukses tapi tidak menemukan file gambar hasil ekspor."
            
            # Kembalikan list path gambar dipisahkan dengan koma
            paths_str = ",".join(generated_pngs)
            return f"SUCCESS|{paths_str}|Kompilasi slide ke gambar PNG berhasil. Dihasilkan {len(generated_pngs)} slide."
        else:
            if not out_file.exists():
                return f"FAILED|Marp CLI selesai tetapi file output tidak ditemukan di: {out_file}"
            
            size_kb = out_file.stat().st_size // 1024
            logger.info(f"[SLIDE_GEN] Saved slide: {out_file} ({size_kb} KB) style={theme_style}")
            return f"SUCCESS|{out_file}|Slide presentasi berhasil dibuat ({size_kb} KB, format={output_format})"

def extract_pdf_page_to_png(pdf_path: str, page_num: int = 1) -> str:
    """Utility helper untuk mengekstrak halaman PDF gambar kerja menjadi file PNG resolusi tinggi."""
    try:
        import fitz  # PyMuPDF
        p = Path(pdf_path)
        if not p.exists():
            return f"FAILED|File PDF tidak ditemukan: {pdf_path}"
        
        doc = fitz.open(p)
        if page_num < 1 or page_num > len(doc):
            return f"FAILED|Halaman {page_num} di luar jangkauan (total {len(doc)} halaman)"
            
        page = doc.load_page(page_num - 1)  # 0-indexed
        pix = page.get_pixmap(dpi=150)
        
        filename = f"extracted_{p.stem}_page{page_num}_{int(time.time())}.png"
        filepath = _OUTPUT_DIR / filename
        pix.save(str(filepath))
        doc.close()
        
        return f"SUCCESS|{filepath}|Berhasil mengekstrak halaman {page_num} menjadi PNG"
    except ImportError:
        return "FAILED|PyMuPDF (fitz) belum terinstall. Silakan pasang: pip install pymupdf"
    except Exception as e:
        return f"FAILED|Gagal mengekstrak PDF: {e}"
