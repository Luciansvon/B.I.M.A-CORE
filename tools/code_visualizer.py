"""CodebaseVisualizerTool — parse the python codebase structure and generate an interactive Cytoscape.js network map."""
from __future__ import annotations

import ast
import json
import logging
import os
import time
from pathlib import Path
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

logger = logging.getLogger("bima_core")

_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"
_OUTPUT_DIR.mkdir(exist_ok=True)

class CodebaseVisualizerInput(BaseModel):
    target_dir: str = Field(".", description="Directory path to analyze relative to workspace root. Default is '.'")

class CodebaseVisualizerTool(BaseTool):
    name: str = "Codebase Visualizer Tool"
    description: str = (
        "Memindai direktori codebase dan menganalisis ketergantungan import antar file python. "
        "Menghasilkan dashboard grafis interaktif (HTML + Cytoscape.js) di folder outputs/ "
        "yang menunjukkan arsitektur modul dan teams. Gunakan tool ini saat Bima ingin memetakan arsitektur "
        "atau melihat relasi modul BIMA_CORE."
        "Input: target_dir (str)."
        "Output: SUCCESS|<filepath>|<message> atau FAILED|<error>."
    )
    args_schema: type[BaseModel] = CodebaseVisualizerInput

    def _run(self, target_dir: str = ".") -> str:
        base_path = Path(__file__).resolve().parent.parent
        scan_dir = (base_path / target_dir).resolve()
        
        if not scan_dir.exists():
            return f"FAILED|Direktori {scan_dir} tidak ditemukan."

        logger.info(f"[CODE_VIS] Scanning directory: {scan_dir}")
        
        # Cari file python
        py_files = sorted(list(scan_dir.glob("**/*.py")))
        
        nodes = []
        edges = []
        edge_set = set()

        # Deteksi import ketergantungan
        for py_file in py_files:
            # Lewati file virtual environment
            if "bima_env" in py_file.parts or ".venv" in py_file.parts or "__pycache__" in py_file.parts:
                continue
                
            rel_path = py_file.relative_to(scan_dir).as_posix()
            
            # Hitung statistik sederhana
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                lines_count = len(content.splitlines())
                size_kb = py_file.stat().st_size / 1024
            except Exception:
                lines_count = 0
                size_kb = 0.0

            # Ekstrak imports menggunakan AST
            imports = []
            try:
                root = ast.parse(content, filename=str(py_file))
                for node in ast.walk(root):
                    if isinstance(node, ast.Import):
                        for name in node.names:
                            imports.append(name.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            imports.append(node.module)
            except SyntaxError:
                # Fallback ke regex parse jika syntax error
                pass

            # Kelompokkan node berdasarkan folder induk
            group = "root"
            if len(py_file.relative_to(scan_dir).parts) > 1:
                group = py_file.relative_to(scan_dir).parts[0]

            nodes.append({
                "data": {
                    "id": rel_path,
                    "label": py_file.name,
                    "group": group,
                    "size_kb": f"{size_kb:.1f} KB",
                    "lines": lines_count,
                    "full_path": str(py_file)
                }
            })

            # Tambahkan edges berdasarkan import lokal
            for imp in imports:
                # Deteksi jika import menunjuk ke modul lokal (core.xxx atau teams.xxx)
                imp_parts = imp.split(".")
                local_candidates = []
                if imp_parts[0] in ("core", "teams", "tools"):
                    # Buat kandidat rel path
                    local_candidates.append(f"{'/'.join(imp_parts)}.py")
                    local_candidates.append(f"{'/'.join(imp_parts)}/__init__.py")
                else:
                    # Coba deteksi relative imports / sibling imports
                    local_candidates.append(f"{group}/{imp_parts[0]}.py")
                
                for candidate in local_candidates:
                    cand_path = scan_dir / candidate
                    if cand_path.exists():
                        cand_rel = cand_path.relative_to(scan_dir).as_posix()
                        edge_key = (rel_path, cand_rel)
                        if edge_key not in edge_set and rel_path != cand_rel:
                            edge_set.add(edge_key)
                            edges.append({
                                "data": {
                                    "id": f"{rel_path}->{cand_rel}",
                                    "source": rel_path,
                                    "target": cand_rel
                                }
                            })
                            break

        # Generate HTML template dengan cytoscape.js
        html_template = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BIMA_CORE Codebase Map</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.29.2/cytoscape.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        body {
            margin: 0;
            padding: 0;
            width: 100vw;
            height: 100vh;
            background: #0f111a;
            color: #e0e6ed;
            font-family: 'Outfit', sans-serif;
            overflow: hidden;
            display: flex;
        }
        #sidebar {
            width: 320px;
            background: rgba(20, 24, 38, 0.85);
            backdrop-filter: blur(12px);
            border-right: 1px solid rgba(255, 255, 255, 0.08);
            padding: 20px;
            box-sizing: border-box;
            display: flex;
            flex-direction: column;
            gap: 20px;
            z-index: 10;
        }
        #cy {
            flex-grow: 1;
            height: 100%;
            z-index: 1;
        }
        h2 {
            margin: 0;
            font-weight: 600;
            font-size: 20px;
            background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .panel {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            padding: 12px;
            font-size: 14px;
        }
        .panel-title {
            font-weight: 600;
            margin-bottom: 8px;
            color: #00f2fe;
        }
        .stats-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 6px;
        }
        select, button {
            background: #1f2438;
            color: #e0e6ed;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 6px;
            padding: 8px 12px;
            width: 100%;
            cursor: pointer;
            font-family: inherit;
        }
        select:focus, button:hover {
            outline: none;
            border-color: #00f2fe;
            background: #252c48;
        }
        #node-details {
            display: none;
        }
    </style>
</head>
<body>
    <div id="sidebar">
        <h2>BIMA_CORE Map</h2>
        <div class="panel">
            <div class="panel-title">Statistik Projek</div>
            <div class="stats-row">
                <span>Total File:</span>
                <span style="font-weight: 600; color: #4facfe;">""" + str(len(nodes)) + """</span>
            </div>
            <div class="stats-row">
                <span>Total Hubungan:</span>
                <span style="font-weight: 600; color: #4facfe;">""" + str(len(edges)) + """</span>
            </div>
        </div>
        <div class="panel">
            <div class="panel-title">Layout Graf</div>
            <select id="layout-select">
                <option value="cose">CoSE (Physics)</option>
                <option value="circle">Lingkaran</option>
                <option value="grid">Grid</option>
                <option value="concentric">Konsentris</option>
            </select>
        </div>
        <div class="panel" id="node-details">
            <div class="panel-title">Detail File</div>
            <div class="stats-row">
                <span>Nama:</span>
                <span id="detail-name" style="font-weight: 600;">-</span>
            </div>
            <div class="stats-row">
                <span>Folder:</span>
                <span id="detail-group">-</span>
            </div>
            <div class="stats-row">
                <span>Ukuran:</span>
                <span id="detail-size">-</span>
            </div>
            <div class="stats-row">
                <span>Baris Kode:</span>
                <span id="detail-lines">-</span>
            </div>
        </div>
        <button id="reset-btn">Reset Tampilan</button>
    </div>
    <div id="cy"></div>

    <script>
        const elements = {
            nodes: """ + json.dumps(nodes) + """,
            edges: """ + json.dumps(edges) + """
        };

        const cy = cytoscape({
            container: document.getElementById('cy'),
            elements: elements,
            style: [
                {
                    selector: 'node',
                    style: {
                        'background-color': function(ele) {
                            const grp = ele.data('group');
                            if (grp === 'core') return '#00f2fe';
                            if (grp === 'teams') return '#ff007f';
                            if (grp === 'tools') return '#a1ff00';
                            return '#888888';
                        },
                        'label': 'data(label)',
                        'color': '#e0e6ed',
                        'font-family': 'Outfit',
                        'font-size': '11px',
                        'text-valign': 'bottom',
                        'text-margin-y': '6px',
                        'width': '16px',
                        'height': '16px',
                        'overlay-padding': '4px',
                        'overlay-color': '#00f2fe'
                    }
                },
                {
                    selector: 'edge',
                    style: {
                        'width': 1.5,
                        'line-color': '#333b5c',
                        'target-arrow-color': '#333b5c',
                        'target-arrow-shape': 'triangle',
                        'curve-style': 'bezier',
                        'arrow-scale': 0.8
                    }
                },
                {
                    selector: 'node:selected',
                    style: {
                        'border-width': '2px',
                        'border-color': '#ffffff',
                        'width': '22px',
                        'height': '22px'
                    }
                }
            ],
            layout: {
                name: 'cose',
                animate: false
            }
        });

        // Event listener saat node diklik
        cy.on('tap', 'node', function(evt){
            const node = evt.target;
            document.getElementById('node-details').style.display = 'block';
            document.getElementById('detail-name').innerText = node.data('label');
            document.getElementById('detail-group').innerText = node.data('group');
            document.getElementById('detail-size').innerText = node.data('size_kb');
            document.getElementById('detail-lines').innerText = node.data('lines');
        });

        cy.on('tap', function(evt){
            if (evt.target === cy) {
                document.getElementById('node-details').style.display = 'none';
            }
        });

        // Layout switcher
        document.getElementById('layout-select').addEventListener('change', function(e) {
            cy.layout({ name: e.target.value, animate: true }).run();
        });

        document.getElementById('reset-btn').addEventListener('click', function() {
            cy.fit();
            cy.layout({ name: document.getElementById('layout-select').value, animate: true }).run();
        });
    </script>
</body>
</html>
"""
        # Tulis ke file HTML
        ts = int(time.time())
        out_file = _OUTPUT_DIR / f"codebase_map_{ts}.html"
        try:
            out_file.write_text(html_template, encoding="utf-8")
        except Exception as e:
            return f"FAILED|Gagal menulis file HTML visualizer: {e}"

        logger.info(f"[CODE_VIS] Visualizer HTML saved: {out_file}")
        return f"SUCCESS|{out_file}|Codebase map generated successfully with {len(nodes)} modules and {len(edges)} connections."
