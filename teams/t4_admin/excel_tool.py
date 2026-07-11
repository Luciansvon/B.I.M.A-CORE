import json
import logging
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from crewai.tools import BaseTool
from config import OUTPUT_DIR
from teams.t4_admin.styles import resolve_style, _hex_from_rgb

logger = logging.getLogger('bima_core')

_OFFICECLI_FALLBACK_PATH = os.path.expanduser("~/.local/bin/officecli")


def _officecli_bin() -> str | None:
    """Resolve path ke binary officecli. PATH proses bot (mis. lewat pm2) belum
    tentu include ~/.local/bin, jadi fallback ke lokasi install default resmi."""
    found = shutil.which("officecli")
    if found:
        return found
    if os.path.isfile(_OFFICECLI_FALLBACK_PATH) and os.access(_OFFICECLI_FALLBACK_PATH, os.X_OK):
        return _OFFICECLI_FALLBACK_PATH
    return None


def _col_letter(n: int) -> str:
    """1-indexed column number -> huruf kolom Excel (1=A, 27=AA, dst)."""
    letters = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _col_width(header: str, rows: list, col_idx: int) -> int:
    max_len = len(str(header))
    for row in rows:
        if col_idx < len(row):
            max_len = max(max_len, len(str(row[col_idx])))
    return max(14, min(max_len + 6, 50))


def _chart_command(parent: str, chart: dict) -> dict:
    chart_type = chart.get("type", "bar")
    datasets = chart.get("datasets", [])
    labels = chart.get("labels", [])
    data_spec = ";".join(
        f"{ds.get('label', f'Series {i + 1}')}:{','.join(str(v) for v in ds.get('data', []))}"
        for i, ds in enumerate(datasets)
    )
    props = {
        "chartType": chart_type,
        "data": data_spec,
        "categories": ",".join(str(l) for l in labels),
        "legend": "bottom",
        "width": "16cm",
        "height": "9cm",
    }
    if chart.get("title"):
        props["title"] = chart["title"]
    return {"command": "add", "parent": parent, "type": "chart", "props": props}


class ExcelGeneratorTool(BaseTool):
    name: str = "Excel Generator Tool"
    description: str = """Buat file Excel (.xlsx) dari data JSON. Dijalankan lewat OfficeCLI (native, bukan library Python).
    Input format JSON string:
    {
        "filename": "nama_file",
        "style": "formal" | "semi_formal" | "informal" | "akademik",
        "sheets": [
            {
                "name": "Sheet1",
                "headers": ["Kolom1", "Kolom2", "Kolom3"],
                "rows": [
                    ["data1", "data2", 100],
                    ["data4", "data5", "=SUM(C2:C2)"]
                ],
                "total_rows": [1],
                "charts": [
                    {"type": "bar", "title": "...", "labels": ["Q1","Q2"],
                     "datasets": [{"label": "Unit", "data": [10, 20]}]}
                ]
            }
        ],
        "references": [
            {"text": "Penulis (2026). Judul.", "url": "https://..."}
        ]
    }
    Cell value yang diawali '=' akan otomatis jadi formula Excel.
    Field 'total_rows' (opsional): index (0-based, relatif ke data rows) yang di-bold + border tebal buat baris total.
    Field 'charts' per sheet (opsional): chart Excel native (bukan gambar statis) — interaktif & bisa diedit di Excel.
    Field 'references' (opsional): auto-bikin sheet "Referensi" dengan kolom No|Sumber|URL (URL clickable).
    URL referensi WAJIB valid (Wikipedia/situs resmi/jurnal open-access). JANGAN dikarang.
    Field 'style' opsional — default 'formal'."""

    def _run(self, input_json: str) -> str:
        officecli = _officecli_bin()
        if not officecli:
            return ("FAILED|OfficeCLI belum terinstall/gak ketemu di PATH. "
                     "Jalankan: curl -fsSL https://raw.githubusercontent.com/iOfficeAI/OfficeCLI/main/install.sh | bash")

        try:
            data = json.loads(input_json)
        except json.JSONDecodeError as e:
            return f"FAILED|JSON tidak valid: {e}"

        style = resolve_style(data)
        header_hex = _hex_from_rgb(style["table_header_rgb"])
        alt_hex = _hex_from_rgb(style["table_alt_rgb"])

        sheets_data = data.get("sheets", [])
        doc_title = data.get("title") or data.get("filename", "Dokumen")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{data.get('filename', 'laporan')}_{timestamp}.xlsx"
        filepath = OUTPUT_DIR / filename

        commands = []

        # === SUMMARY SHEET — sheet pertama sebagai ringkasan ===
        commands.append({"command": "add", "parent": "/", "type": "sheet", "props": {"name": "Ringkasan"}})
        commands.append({"command": "remove", "path": "/Sheet1"})
        merge_cols = max(len(sheets_data), 1, 4)
        commands.append({
            "command": "add", "parent": "/Ringkasan", "type": "cell",
            "props": {"ref": "A1", "value": str(doc_title).upper(), "bold": "true",
                      "font.color": "FFFFFF", "fill": header_hex, "size": "16pt",
                      "alignment.horizontal": "center", "merge": f"A1:{_col_letter(merge_cols)}1"},
        })
        meta_rows = [
            ("Dokumen", str(doc_title)),
            ("Tanggal Dibuat", datetime.now().strftime("%d %B %Y, %H:%M")),
            ("Style", style["label"]),
            ("Jumlah Sheet Data", str(len(sheets_data))),
        ]
        for i, (k, v) in enumerate(meta_rows, start=3):
            commands.append({"command": "add", "parent": "/Ringkasan", "type": "cell",
                              "props": {"ref": f"A{i}", "value": k, "bold": "true"}})
            commands.append({"command": "add", "parent": "/Ringkasan", "type": "cell",
                              "props": {"ref": f"B{i}", "value": v}})
        commands.append({"command": "add", "parent": "/Ringkasan", "type": "column",
                          "props": {"name": "A", "width": "22"}})
        commands.append({"command": "add", "parent": "/Ringkasan", "type": "column",
                          "props": {"name": "B", "width": "42"}})

        for chart in data.get("charts", []) or []:
            commands.append(_chart_command("/Ringkasan", chart))

        # === DATA SHEETS ===
        for sheet_data in sheets_data:
            sheet_name = (sheet_data.get("name", "Sheet") or "Sheet")[:31]
            headers = sheet_data.get("headers", [])
            rows = sheet_data.get("rows", [])
            total_row_indices = set(sheet_data.get("total_rows", []))

            commands.append({"command": "add", "parent": "/", "type": "sheet", "props": {"name": sheet_name}})

            data_start_row = 1
            sheet_title = sheet_data.get("title", "")
            if sheet_title:
                commands.append({
                    "command": "add", "parent": f"/{sheet_name}", "type": "cell",
                    "props": {"ref": "A1", "value": sheet_title, "bold": "true",
                              "font.color": header_hex, "size": "13pt",
                              "merge": f"A1:{_col_letter(max(len(headers), 1))}1"},
                })
                data_start_row = 2

            hdr_row = data_start_row
            for col_idx, header in enumerate(headers, 1):
                ref = f"{_col_letter(col_idx)}{hdr_row}"
                commands.append({
                    "command": "add", "parent": f"/{sheet_name}", "type": "cell",
                    "props": {"ref": ref, "value": header, "bold": "true",
                              "font.color": "FFFFFF", "fill": header_hex,
                              "alignment.horizontal": "center", "alignment.vertical": "center",
                              "alignment.wrapText": "true", "border.all": "thin"},
                })

            for local_idx, row_data in enumerate(rows):
                row_idx = hdr_row + 1 + local_idx
                is_total = local_idx in total_row_indices
                for col_idx, value in enumerate(row_data, 1):
                    ref = f"{_col_letter(col_idx)}{row_idx}"
                    props = {"ref": ref}
                    is_formula = isinstance(value, str) and value.startswith("=")
                    if is_formula:
                        props["formula"] = value[1:]
                    else:
                        props["value"] = value

                    if is_total:
                        props["bold"] = "true"
                        props["border.top"] = "medium"
                        props["border.bottom"] = "double"
                        props["fill"] = alt_hex
                    else:
                        props["border.all"] = "thin"
                        if row_idx % 2 == 0:
                            props["fill"] = alt_hex

                    if isinstance(value, float) and not is_formula:
                        props["alignment.horizontal"] = "right"
                        props["numberformat"] = "#,##0.00" if value != int(value) else "#,##0"
                    elif isinstance(value, int) and not is_formula:
                        props["alignment.horizontal"] = "right"
                        props["numberformat"] = "#,##0"
                    elif is_formula:
                        props["alignment.horizontal"] = "right"
                    else:
                        props["alignment.horizontal"] = "left"
                        props["alignment.wrapText"] = "true"

                    commands.append({"command": "add", "parent": f"/{sheet_name}", "type": "cell", "props": props})

            for col_idx, header in enumerate(headers, 1):
                width = _col_width(header, rows, col_idx - 1)
                commands.append({"command": "add", "parent": f"/{sheet_name}", "type": "column",
                                  "props": {"name": _col_letter(col_idx), "width": str(width)}})

            if headers:
                freeze_ref = f"A{hdr_row + 1}"
                commands.append({"command": "set", "path": f"/{sheet_name}", "props": {"freeze": freeze_ref}})

            for chart in sheet_data.get("charts", []) or []:
                commands.append(_chart_command(f"/{sheet_name}", chart))

        # === Sheet Referensi (opsional) ===
        references = data.get("references", [])
        if references:
            commands.append({"command": "add", "parent": "/", "type": "sheet", "props": {"name": "Referensi"}})
            for col_idx, h in enumerate(["No", "Sumber", "URL"], 1):
                commands.append({
                    "command": "add", "parent": "/Referensi", "type": "cell",
                    "props": {"ref": f"{_col_letter(col_idx)}1", "value": h, "bold": "true",
                              "font.color": "FFFFFF", "fill": header_hex,
                              "alignment.horizontal": "center", "border.all": "thin"},
                })
            for idx, ref in enumerate(references, 1):
                if isinstance(ref, dict):
                    ref_text, ref_url = ref.get("text", ""), ref.get("url", "")
                else:
                    ref_text, ref_url = str(ref), ""
                row_idx = idx + 1
                fill = {"fill": alt_hex} if row_idx % 2 == 0 else {}
                commands.append({"command": "add", "parent": "/Referensi", "type": "cell",
                                  "props": {"ref": f"A{row_idx}", "value": idx,
                                            "alignment.horizontal": "center", "border.all": "thin", **fill}})
                commands.append({"command": "add", "parent": "/Referensi", "type": "cell",
                                  "props": {"ref": f"B{row_idx}", "value": ref_text,
                                            "alignment.wrapText": "true", "border.all": "thin", **fill}})
                url_props = {"ref": f"C{row_idx}", "value": ref_url,
                             "alignment.wrapText": "true", "border.all": "thin", **fill}
                if ref_url:
                    url_props["link"] = ref_url
                commands.append({"command": "add", "parent": "/Referensi", "type": "cell", "props": url_props})
            commands.append({"command": "add", "parent": "/Referensi", "type": "column",
                              "props": {"name": "A", "width": "6"}})
            commands.append({"command": "add", "parent": "/Referensi", "type": "column",
                              "props": {"name": "B", "width": "60"}})
            commands.append({"command": "add", "parent": "/Referensi", "type": "column",
                              "props": {"name": "C", "width": "50"}})
            commands.append({"command": "set", "path": "/Referensi", "props": {"freeze": "A2"}})

        batch_tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
        try:
            json.dump(commands, batch_tmp)
            batch_tmp.close()

            create_res = subprocess.run(
                [officecli, "create", str(filepath)],
                capture_output=True, text=True, timeout=30,
            )
            if create_res.returncode != 0:
                return f"FAILED|OfficeCLI gagal bikin file kosong: {create_res.stderr.strip() or create_res.stdout.strip()}"

            batch_res = subprocess.run(
                [officecli, "batch", str(filepath), "--input", batch_tmp.name, "--json"],
                capture_output=True, text=True, timeout=120,
            )
            try:
                batch_out = json.loads(batch_res.stdout)
            except json.JSONDecodeError:
                return f"FAILED|OfficeCLI batch output gak valid JSON: {batch_res.stdout[:500] or batch_res.stderr[:500]}"

            summary = batch_out.get("data", {}).get("summary", {})
            failed = summary.get("failed", 0)
            if failed:
                errors = [
                    f"{r.get('item', {}).get('parent') or r.get('item', {}).get('path')}: {r.get('error')}"
                    for r in batch_out.get("data", {}).get("results", []) if not r.get("success")
                ]
                return f"FAILED|{failed} operasi OfficeCLI gagal: " + "; ".join(errors[:5])

            return f"SUCCESS|{filepath}|Excel ({style['label']}) berhasil dibuat: {filename}"
        except subprocess.TimeoutExpired:
            return "FAILED|OfficeCLI timeout — dokumen terlalu besar atau proses macet."
        except Exception as e:
            logger.error(f"[ADMIN] ExcelGenerator (OfficeCLI) error: {e}", exc_info=True)
            return f"FAILED|{e}"
        finally:
            os.unlink(batch_tmp.name) if os.path.exists(batch_tmp.name) else None
            subprocess.run([officecli, "close", str(filepath)], capture_output=True, text=True, timeout=15)
