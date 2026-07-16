"""DiagramGeneratorTool — render Mermaid diagram code (flowchart/sequence/state/dsb)
jadi file HTML mandiri dengan theme toggle + export, dipakai buat diagram yang
BUKAN dependency-import (itu tugas CodebaseVisualizerTool).
"""
from __future__ import annotations

import hashlib
import html
import logging
import time
from pathlib import Path
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from core.public_errors import public_failure

_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"
_OUTPUT_DIR.mkdir(exist_ok=True)
logger = logging.getLogger("bima_core.diagram")


class DiagramGeneratorInput(BaseModel):
    mermaid_code: str = Field(
        ...,
        description=(
            "Kode diagram dalam sintaks Mermaid.js (contoh: 'sequenceDiagram\\n"
            "Alice->>Bob: Hi'). Dukung flowchart, sequenceDiagram, stateDiagram, "
            "classDiagram, dll. Tulis sintaks-nya sendiri sesuai yang diminta user."
        ),
    )
    title: str = Field("Diagram", description="Judul diagram, ditampilkan di header HTML.")


class DiagramGeneratorTool(BaseTool):
    name: str = "Diagram Generator Tool"
    description: str = (
        "Render kode Mermaid (flowchart, sequence diagram, state/lifecycle diagram, dll) "
        "jadi file HTML mandiri dengan toggle dark/light dan tombol export PNG/SVG. "
        "Gunakan untuk diagram ALUR/PROSES/ARSITEKTUR NARATIF (bukan peta dependency-import "
        "kode — buat itu pakai Codebase Visualizer Tool). "
        "Input: mermaid_code (str, sintaks Mermaid.js valid), title (str, opsional). "
        "Output: SUCCESS|<filepath>|<message> atau FAILED|<error>."
    )
    args_schema: type[BaseModel] = DiagramGeneratorInput

    def _run(self, mermaid_code: str, title: str = "Diagram") -> str:
        if not mermaid_code or not mermaid_code.strip():
            return "FAILED|mermaid_code kosong."

        safe_title = html.escape(title)
        safe_code = html.escape(mermaid_code.strip())

        html_template = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>""" + safe_title + """</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.9.1/mermaid.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        :root { --bg: #0f111a; --fg: #e0e6ed; --panel: rgba(20, 24, 38, 0.85); --accent: #00f2fe; }
        body[data-theme="light"] { --bg: #f4f6fb; --fg: #1b1f2e; --panel: rgba(255,255,255,0.85); --accent: #0077b6; }
        body {
            margin: 0; padding: 0; min-height: 100vh; box-sizing: border-box;
            background: var(--bg); color: var(--fg); font-family: 'Outfit', sans-serif;
        }
        header {
            display: flex; align-items: center; justify-content: space-between;
            padding: 16px 24px; background: var(--panel); backdrop-filter: blur(12px);
            border-bottom: 1px solid rgba(255,255,255,0.08);
        }
        h1 {
            margin: 0; font-size: 18px; font-weight: 600;
            background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        button {
            background: #1f2438; color: var(--fg); border: 1px solid rgba(255,255,255,0.1);
            border-radius: 6px; padding: 8px 14px; margin-left: 8px; cursor: pointer;
            font-family: inherit; font-size: 13px;
        }
        button:hover { border-color: var(--accent); }
        #diagram-wrap { padding: 32px; display: flex; justify-content: center; }
        .mermaid { background: transparent; }
    </style>
</head>
<body data-theme="dark">
    <header>
        <h1>""" + safe_title + """</h1>
        <div>
            <button id="theme-btn" title="Toggle theme (T)">🌓 Theme</button>
            <button id="export-btn" title="Export PNG (E)">⬇ Export PNG</button>
        </div>
    </header>
    <div id="diagram-wrap">
        <pre class="mermaid">""" + safe_code + """</pre>
    </div>

    <script>
        function initMermaid(theme) {
            mermaid.initialize({ startOnLoad: true, theme: theme === 'light' ? 'default' : 'dark' });
        }
        initMermaid('dark');

        document.getElementById('theme-btn').addEventListener('click', function () {
            const body = document.body;
            const next = body.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
            body.setAttribute('data-theme', next);
            document.querySelectorAll('.mermaid').forEach(function (el) {
                delete el.dataset.processed;
            });
            initMermaid(next);
            mermaid.run();
        });

        document.getElementById('export-btn').addEventListener('click', function () {
            const svg = document.querySelector('.mermaid svg');
            if (!svg) return;
            const svgData = new XMLSerializer().serializeToString(svg);
            const canvas = document.createElement('canvas');
            const bbox = svg.getBBox();
            canvas.width = bbox.width * 2;
            canvas.height = bbox.height * 2;
            const ctx = canvas.getContext('2d');
            const img = new Image();
            const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
            const url = URL.createObjectURL(svgBlob);
            img.onload = function () {
                ctx.scale(2, 2);
                ctx.drawImage(img, 0, 0);
                URL.revokeObjectURL(url);
                const a = document.createElement('a');
                a.download = 'diagram.png';
                a.href = canvas.toDataURL('image/png');
                a.click();
            };
            img.src = url;
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 't' || e.key === 'T') document.getElementById('theme-btn').click();
            if (e.key === 'e' || e.key === 'E') document.getElementById('export-btn').click();
        });
    </script>
</body>
</html>
"""
        digest = hashlib.sha256(
            f"{title}\0{mermaid_code.strip()}".encode("utf-8")
        ).hexdigest()[:12]
        out_file = _OUTPUT_DIR / f"diagram_{digest}_{time.time_ns()}.html"
        try:
            out_file.write_text(html_template, encoding="utf-8")
        except Exception:
            logger.exception("Gagal menulis file HTML diagram")
            return public_failure("Gagal menulis file HTML diagram")

        return f"SUCCESS|{out_file}|Diagram '{title}' berhasil dibuat."
