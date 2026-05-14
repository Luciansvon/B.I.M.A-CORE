"""Standalone dashboard server (tanpa Discord bot).

Pakai ini kalau cuma mau test pixel dashboard tanpa nyalain seluruh BIMA core.
Chat fitur tetap fungsi karena LangGraph engine di-load lazy oleh /api/command.

Usage (dari root repo):
    source bima_env/bin/activate
    python dashboard/serve.py
"""
import os
import sys
from pathlib import Path

# Pastikan root repo ada di path supaya `from core...` jalan saat dipanggil
# dari folder ini.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from core.dashboard_server import _run  # noqa: E402

if __name__ == "__main__":
    print("[serve] dashboard at http://localhost:8000/dashboard/v3")
    _run("0.0.0.0", 8000)
