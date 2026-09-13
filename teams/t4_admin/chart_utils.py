from datetime import datetime
from config import OUTPUT_DIR


def _palette(style: dict) -> list:
    primary_rgb = tuple(c / 255 for c in style["accent_rgb"])
    header_rgb = tuple(c / 255 for c in style["table_header_rgb"])
    return [
        primary_rgb,
        header_rgb,
        (0.40, 0.55, 0.85),
        (0.85, 0.55, 0.40),
        (0.55, 0.85, 0.55),
        (0.85, 0.45, 0.55),
    ]


def render_chart(chart: dict, style: dict) -> str:
    """Render chart spec ke PNG, simpan ke OUTPUT_DIR, return path lokal.
    Format chart sama seperti Chart.js: type, title, labels, datasets[{label, data}].
    Type yang didukung: bar, line, pie."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    chart_type = chart.get("type", "bar")
    title = chart.get("title", "")
    labels = chart.get("labels", [])
    datasets = chart.get("datasets", [])
    if not datasets:
        raise ValueError("Chart datasets kosong")
    if chart_type not in {"bar", "line", "pie"}:
        raise ValueError(f"Tipe chart tidak didukung: {chart_type}")

    title_rgb = tuple(c / 255 for c in style["title_rgb"])
    palette = _palette(style)

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)

    try:
        if chart_type == "bar":
            n_ds = len(datasets)
            x = list(range(len(labels)))
            width = 0.8 / max(n_ds, 1)
            for i, ds in enumerate(datasets):
                offsets = [xi + width * i for xi in x]
                ax.bar(offsets, ds["data"], width=width * 0.9,
                       label=ds.get("label", f"Series {i + 1}"),
                       color=palette[i % len(palette)])
            ax.set_xticks([xi + width * (n_ds - 1) / 2 for xi in x])
            ax.set_xticklabels(labels, rotation=30, ha='right', fontsize=9)
        elif chart_type == "line":
            for i, ds in enumerate(datasets):
                ax.plot(labels, ds["data"], marker='o', linewidth=2,
                        label=ds.get("label", f"Series {i + 1}"),
                        color=palette[i % len(palette)])
            ax.tick_params(axis='x', rotation=30)
            ax.grid(True, alpha=0.3)
        else:
            ax.pie(datasets[0]["data"], labels=labels, autopct='%1.1f%%',
                   startangle=140, colors=palette[:len(labels)])
            ax.axis('equal')

        if title:
            ax.set_title(title, fontsize=13, color=title_rgb, fontweight='bold', pad=12)
        if chart.get("xlabel"):
            ax.set_xlabel(chart["xlabel"], fontsize=10)
        if chart.get("ylabel"):
            ax.set_ylabel(chart["ylabel"], fontsize=10)
        if chart_type != "pie" and len(datasets) > 1:
            ax.legend(loc='best', fontsize=9, framealpha=0.9)

        plt.tight_layout()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        path = OUTPUT_DIR / f"chart_{chart_type}_{timestamp}.png"
        plt.savefig(path, dpi=300, bbox_inches='tight', facecolor='white')
        return str(path)
    finally:
        plt.close(fig)
