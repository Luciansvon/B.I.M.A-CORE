"""Benchmark kualitas + latency retrieval Vault Anisa.

Ukur p50/p95 latency hangat dan Recall@3 pada query sumber nyata, plus satu
true-negative (topik yang tidak ada di vault). Exit 1 kalau target penerimaan
tidak tercapai supaya bisa dipakai sebagai gerbang CI/verifikasi.

Target: p95 <= 3.0 detik, Recall@3 = 1.0, true-negative rate = 1.0.

Jalankan SETELAH index_vault(full_rebuild=True). Arahkan OBSIDIAN_PATH ke vault
sumber nyata bila config default tidak menunjuk ke sana, contoh:

    env OBSIDIAN_PATH=/path/ke/vault \
        bima_env/bin/python scripts/benchmark_vault_rag.py
"""
from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from teams.t3_arsip import search_vault  # noqa: E402

CASES: list[tuple[str, str | None]] = [
    ("apa preferensi musik Bima", "Preferensi_Musik_Bima.md"),
    ("jelaskan arsitektur BIMA Core", "BIMA_CORE_Arsitektur.md"),
    ("berapa harga robux di Itemku", "Harga_Robux_Itemku_-_9_Mei_2026.md"),
    ("kriteria laptop Bima", "Kriteria_Laptop_Bima_-_6_Mei_2026.md"),
    ("resep ramen tonkotsu keluarga Bima", None),
]

NOT_FOUND = "Tidak ada catatan relevan ditemukan di vault."
MEASUREMENTS = 3


def _files_in(output: str) -> list[str]:
    files: list[str] = []
    for line in output.splitlines():
        if line.startswith("File: "):
            fname = line[len("File: "):].split(" / ")[0].strip()
            files.append(fname)
    return files


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    idx = int(round((pct / 100.0) * (len(ordered) - 1)))
    return ordered[min(idx, len(ordered) - 1)]


def main() -> int:
    # Warmup global: muat embedder + reranker + cache BM25 sebelum pengukuran.
    search_vault("pemanasan retrieval", top_k=3)

    latencies: list[float] = []
    positives = hits = 0
    tn_total = tn_ok = 0

    for query, expected in CASES:
        result = ""
        for _ in range(MEASUREMENTS):
            start = time.perf_counter()
            result = search_vault(query, top_k=3)
            latencies.append(time.perf_counter() - start)

        if expected is None:
            tn_total += 1
            ok = result.strip() == NOT_FOUND
            tn_ok += 1 if ok else 0
            print(f"[{'TN-OK' if ok else 'TN-FAIL'}] {query!r} -> {result[:70]!r}")
        else:
            positives += 1
            top3 = _files_in(result)[:3]
            ok = expected in top3
            hits += 1 if ok else 0
            print(f"[{'HIT' if ok else 'MISS'}] {query!r} -> top3={top3}")

    p50 = statistics.median(latencies)
    p95 = _percentile(latencies, 95)
    recall3 = hits / positives if positives else 0.0
    tn_rate = tn_ok / tn_total if tn_total else 1.0

    print("\n=== HASIL ===")
    print(f"p50 latency  : {p50 * 1000:.0f} ms")
    print(f"p95 latency  : {p95 * 1000:.0f} ms")
    print(f"Recall@3     : {recall3:.2f} ({hits}/{positives})")
    print(f"TrueNeg rate : {tn_rate:.2f} ({tn_ok}/{tn_total})")

    passed = p95 <= 3.0 and recall3 >= 1.0 and tn_rate >= 1.0
    print("VERDICT      :", "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
