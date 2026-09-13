# Saham Scheduler Misfire Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Memastikan tick paper trading tetap dieksekusi ketika event loop Anisa terlambat sampai dua menit, serta meninggalkan bukti log untuk tick yang selesai tanpa transaksi.

**Architecture:** Pertahankan `AsyncIOScheduler` dan alur paper trader yang ada. Tambahkan job defaults eksplisit pada scheduler saham (`misfire_grace_time=120`, `coalesce=True`, `max_instances=1`) agar job terlambat tidak langsung dibuang dan tidak menumpuk, lalu log hasil setiap tick tanpa mengubah keputusan BUY/SELL/HOLD.

**Tech Stack:** Python 3.12, APScheduler 3.11.3, asyncio, pytest, PM2.

---

### Task 1: Tambahkan regression test scheduler

**Files:**
- Create: `tests/test_saham_scheduler.py`
- Read: `core/saham_scheduler.py`

- [x] **Step 1: Tulis test konfigurasi toleransi**

```python
import logging

import pytest

from core import saham_scheduler as scheduler_module


def test_scheduler_keeps_late_jobs_for_two_minutes(monkeypatch):
    captured: dict[str, object] = {}

    class FakeScheduler:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def add_job(self, *args, **kwargs):
            return None

        def start(self):
            return None

    monkeypatch.setenv("SAHAM_CHANNEL_ID", "123")
    monkeypatch.setattr(scheduler_module, "AsyncIOScheduler", FakeScheduler)
    monkeypatch.setattr(scheduler_module, "_scheduler_started", False)

    scheduler_module.start_saham_scheduler(object())

    assert captured["job_defaults"] == {
        "misfire_grace_time": 120,
        "coalesce": True,
        "max_instances": 1,
    }
```

- [x] **Step 2: Tulis test bukti log tick HOLD**

```python
@pytest.mark.asyncio
async def test_paper_tick_logs_completion_without_trade(monkeypatch, caplog):
    async def fake_to_thread(func, *args):
        return []

    monkeypatch.setattr(scheduler_module.asyncio, "to_thread", fake_to_thread)
    caplog.set_level(logging.INFO, logger="bima_core")

    await scheduler_module._paper_trading_tick("idx")

    assert "[PAPER TRADER] idx: tick completed, no trade" in caplog.text
```

- [x] **Step 3: Jalankan test RED**

Run:

```bash
bima_env/bin/python -m pytest tests/test_saham_scheduler.py -q --no-header
```

Expected: dua test gagal karena `job_defaults` belum dikirim dan tick tanpa transaksi belum menulis log.

### Task 2: Terapkan fix minimal

**Files:**
- Modify: `core/saham_scheduler.py`
- Test: `tests/test_saham_scheduler.py`

- [x] **Step 1: Tambahkan job defaults eksplisit**

```python
SAHAM_JOB_DEFAULTS = {
    "misfire_grace_time": 120,
    "coalesce": True,
    "max_instances": 1,
}
```

Ubah pembuatan scheduler menjadi:

```python
scheduler = AsyncIOScheduler(
    timezone=WIB,
    job_defaults=SAHAM_JOB_DEFAULTS,
)
```

- [x] **Step 2: Log setiap tick yang selesai**

```python
if results:
    logger.info(f"[PAPER TRADER] {market}: {len(results)} trade(s) executed")
else:
    logger.info(f"[PAPER TRADER] {market}: tick completed, no trade")
```

- [x] **Step 3: Jalankan test GREEN**

Run:

```bash
bima_env/bin/python -m pytest tests/test_saham_scheduler.py -q --no-header
```

Expected: `2 passed`.

### Task 3: Verifikasi regresi dan runtime

**Files:**
- Verify: `core/saham_scheduler.py`
- Verify: `tests/test_saham_scheduler.py`

- [x] **Step 1: Jalankan focused saham suite**

Run:

```bash
bima_env/bin/python -m pytest tests/test_saham_scheduler.py tests/test_saham_paper_trader.py -q --no-header
bima_env/bin/python -m py_compile core/saham_scheduler.py
git diff --check -- core/saham_scheduler.py tests/test_saham_scheduler.py
```

Expected: seluruh test saham lulus, compile lulus, dan tidak ada whitespace error baru.

- [x] **Step 2: Restart runtime Python**

Run:

```bash
pm2 restart anisa-v3 --update-env
pm2 describe anisa-v3
```

Expected: `anisa-v3` kembali `online` dari `/home/bima_lucian/BIMA_CORE/main.py`.

- [x] **Step 3: Buktikan tick live berikutnya**

Run:

```bash
pm2 logs anisa-v3 --nostream --lines 200
```

Expected: tick berikutnya tidak memiliki warning `was missed` dan menulis salah satu:

```text
[PAPER TRADER] <market>: tick completed, no trade
[PAPER TRADER] <market>: <n> trade(s) executed
```

### Task 4: Catat solusi yang sudah terverifikasi

**Files:**
- Modify: `docs/ERROR_SOLUTIONS.md`

- [x] **Step 1: Perbarui ERR-R46 setelah bukti live tersedia**

Tambahkan fakta yang benar-benar terverifikasi:

```markdown
* **Mitigasi Terverifikasi (2026-07-20)**: Scheduler saham memakai `misfire_grace_time=120`, `coalesce=True`, dan `max_instances=1`, sehingga tick yang terlambat sampai dua menit tetap dijalankan tanpa menumpuk. Setiap tick paper trader juga menulis log saat selesai tanpa transaksi.
* **Verifikasi**: Focused test scheduler dan paper trader lulus, `anisa-v3` kembali online dari root repo, dan tick live berikutnya menulis log selesai tanpa warning `was missed`.
```

- [x] **Step 2: Pastikan dokumentasi tidak mengklaim akar stall yang belum diprofil**

Run:

```bash
sed -n '180,195p' docs/ERROR_SOLUTIONS.md
git diff --check -- docs/ERROR_SOLUTIONS.md
```

Expected: ERR-R46 membedakan event-loop stall yang masih perlu profiling dari mitigasi scheduler saham yang sudah terbukti.

Tidak membuat commit atau push.
