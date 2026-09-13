import logging
from pathlib import Path
from crewai.tools import BaseTool
from config import OUTPUT_DIR
from core.path_security import resolve_allowed_path
from core.public_errors import public_failure
from teams.t4_admin.styles import STYLES, DEFAULT_STYLE_NAME
from teams.t4_admin.chart_utils import render_chart

logger = logging.getLogger('bima_core')


# ============================================================
# Data Analysis Tool — sinkron warna dari STYLES via chart_utils.render_chart
# ============================================================
class DataAnalysisTool(BaseTool):
    name: str = "Data Analysis & Chart Tool"
    description: str = """Baca file CSV/Excel, analisis data dengan pandas, dan hasilkan grafik visual.
    Input format: 'path_file|jenis_chart|kolom_x|kolom_y|style'
    Contoh: 'outputs/data.csv|bar|Bulan|Penjualan|formal'
    Field 'style' opsional (default formal) — warna chart menyesuaikan style preset BIMA
    ("formal" | "semi_formal" | "informal" | "akademik").
    Jenis chart: bar, line, pie."""

    def _run(self, input_str: str) -> str:
        try:
            import pandas as pd

            if "|" not in input_str:
                return "FAILED|Format salah. Gunakan 'path_file|jenis_chart|kolom_x|kolom_y|style'"

            parts = input_str.split("|")
            filepath = parts[0].strip()
            chart_type = parts[1].strip().lower()

            style_name = parts[4].strip().lower() if len(parts) > 4 else DEFAULT_STYLE_NAME
            chart_style = STYLES.get(style_name, STYLES[DEFAULT_STYLE_NAME])

            raw_path = Path(filepath)
            candidate = raw_path
            if not raw_path.is_absolute():
                candidate = OUTPUT_DIR / raw_path.name
            try:
                p = resolve_allowed_path(
                    candidate,
                    (OUTPUT_DIR,),
                    base_dir=OUTPUT_DIR.parent,
                    allowed_suffixes={".csv", ".xlsx", ".xls"},
                )
            except ValueError:
                return "FAILED|Path tidak diizinkan"
            filepath = str(p)

            try:
                if p.suffix == '.csv':
                    df = pd.read_csv(filepath)
                elif p.suffix in ['.xlsx', '.xls']:
                    df = pd.read_excel(filepath)
                else:
                    return "FAILED|Format file harus CSV atau Excel."
            except Exception as read_err:
                logger.exception("[ADMIN] Gagal baca file data")
                return public_failure("Gagal baca file")

            if chart_type == 'pie':
                col_label = parts[2].strip()
                col_val = parts[3].strip() if len(parts) > 3 and parts[3].strip() else None
                if col_val:
                    chart_data = df.groupby(col_label)[col_val].sum()
                else:
                    chart_data = df[col_label].value_counts()
                chart_spec = {
                    "type": "pie",
                    "title": f"Proporsi {col_val or col_label}",
                    "labels": [str(x) for x in chart_data.index],
                    "datasets": [{"label": col_val or col_label, "data": chart_data.values.tolist()}],
                }
            else:
                x_col = parts[2].strip()
                y_col = parts[3].strip() if len(parts) > 3 and parts[3].strip() else None
                if not y_col:
                    return "FAILED|Kolom Y wajib diisi untuk chart bar/line."
                df_agg = df.groupby(x_col)[y_col].sum().reset_index()
                chart_spec = {
                    "type": chart_type,
                    "title": f"Total {y_col} per {x_col}",
                    "labels": [str(x) for x in df_agg[x_col]],
                    "datasets": [{"label": y_col, "data": df_agg[y_col].tolist()}],
                    "xlabel": x_col,
                    "ylabel": y_col,
                }

            chart_filepath = render_chart(chart_spec, chart_style)
            stats = df.describe().to_string()
            return f"SUCCESS|{chart_filepath}|\nStatistik:\n{stats}\n\nGrafik {chart_type} ({chart_style['label']}) disimpan di {chart_filepath}"

        except ImportError as e:
            logger.exception("[ADMIN] Library data analysis tidak tersedia")
            return public_failure("Library data analysis tidak tersedia")
        except Exception as e:
            logger.error(f"[ADMIN] DataAnalysis error: {e}", exc_info=True)
            return public_failure("Gagal analisis data")
