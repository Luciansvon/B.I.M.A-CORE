# Anisa Operational Status and Healthcheck Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Membuat snapshot status operasional Anisa yang selalu segar, memperbaiki false error healthcheck, menambah regression test, dan menutup vulnerability WhatsApp yang terverifikasi.

**Architecture:** Proses sidecar PM2 mengumpulkan status murah dari PM2, psutil, endpoint lokal, indeks, Git, dan log lalu menulis satu JSON secara atomic setiap 30 detik. Healthcheck dipecah menjadi fungsi import-safe agar root path serta hasil pemeriksaan dapat diuji tanpa menjalankan seluruh script saat import.

**Tech Stack:** Python 3.12, pytest, psutil, urllib standard library, PM2, Node.js/npm.

---

## Struktur File

- Create `core/operational_status.py`: pengumpulan, sanitasi, penentuan overall, atomic JSON write, dan freshness check.
- Create `scripts/status_collector.py`: loop CLI sidecar 30 detik.
- Create `tests/test_operational_status.py`: regression test collector.
- Modify `scripts/healthcheck.py`: project root benar dan import-safe.
- Create `tests/test_healthcheck.py`: regression test healthcheck.
- Modify `ecosystem.config.js`: definisi proses `anisa-status`.
- Modify `.gitignore`: abaikan snapshot runtime yang selalu berubah.
- Modify `.env`: pindahkan hanya `OBSIDIAN_PATH` ke vault lokal WSL.
- Modify `whatsapp/package-lock.json`: patch dependency hasil `npm audit fix` tanpa force.
- Modify `error_solutions.md`: catat akar masalah, solusi, dan verifikasi.

### Task 1: Perbaiki Healthcheck dengan Regression Test

**Files:**
- Modify: `scripts/healthcheck.py`
- Create: `tests/test_healthcheck.py`

- [ ] **Step 1: Tulis test root project dan import-safety**

```python
import importlib


def test_healthcheck_uses_project_root(capsys):
    module = importlib.import_module("scripts.healthcheck")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert (module.BASE_DIR / "main.py").is_file()
    assert (module.BASE_DIR / "core").is_dir()
    assert (module.BASE_DIR / "teams").is_dir()


def test_existing_indexes_are_ready():
    module = importlib.import_module("scripts.healthcheck")
    status = module.index_status(module.BASE_DIR)
    assert status == {
        "search_index": True,
        "repo_index": True,
        "vault_index": True,
    }
```

- [ ] **Step 2: Jalankan test dan pastikan RED**

Run: `source bima_env/bin/activate && pytest tests/test_healthcheck.py -q`

Expected: FAIL karena import mencetak healthcheck, `BASE_DIR` menunjuk `scripts/`, dan `index_status` belum ada.

- [ ] **Step 3: Refactor minimal healthcheck**

Gunakan bentuk berikut tanpa mengubah daftar pemeriksaan yang sudah ada:

```python
BASE_DIR = Path(__file__).resolve().parent.parent


def index_status(base_dir: Path) -> dict[str, bool]:
    return {
        name: (base_dir / name).is_dir()
        for name in ("search_index", "repo_index", "vault_index")
    }


def main() -> int:
    # seluruh eksekusi pemeriksaan lama dipindahkan ke sini
    return 1 if checks_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Jalankan test dan healthcheck nyata**

Run: `source bima_env/bin/activate && pytest tests/test_healthcheck.py -q`

Expected: `2 passed`.

Run: `source bima_env/bin/activate && python scripts/healthcheck.py`

Expected: folder root dan indeks tidak lagi dilaporkan `MISSING`; exit code mencerminkan jumlah critical failure.

### Task 2: Bangun Operational Snapshot dengan TDD

**Files:**
- Create: `core/operational_status.py`
- Create: `tests/test_operational_status.py`
- Modify: `.gitignore`

- [ ] **Step 1: Tulis test kontrak inti**

```python
import json
from datetime import datetime, timedelta, timezone

from core.operational_status import (
    determine_overall,
    is_snapshot_fresh,
    sanitize_error,
    write_snapshot_atomic,
)


def test_overall_priority():
    assert determine_overall(["healthy", "degraded"]) == "degraded"
    assert determine_overall(["degraded", "down"]) == "down"


def test_snapshot_stale_after_90_seconds():
    now = datetime.now(timezone.utc)
    fresh = {"updated_at": (now - timedelta(seconds=89)).isoformat()}
    stale = {"updated_at": (now - timedelta(seconds=91)).isoformat()}
    assert is_snapshot_fresh(fresh, now=now)
    assert not is_snapshot_fresh(stale, now=now)


def test_error_is_sanitized():
    text = "Authorization: Bearer secret-token OPENROUTER_API_KEY=secret"
    result = sanitize_error(text)
    assert "secret-token" not in result
    assert "OPENROUTER_API_KEY=secret" not in result


def test_atomic_write_creates_valid_json(tmp_path):
    target = tmp_path / "anisa_status.json"
    write_snapshot_atomic(target, {"schema_version": 1})
    assert json.loads(target.read_text(encoding="utf-8"))["schema_version"] == 1
    assert not list(tmp_path.glob("*.tmp"))
```

- [ ] **Step 2: Jalankan test dan pastikan RED**

Run: `source bima_env/bin/activate && pytest tests/test_operational_status.py -q`

Expected: collection FAIL karena modul belum tersedia.

- [ ] **Step 3: Implementasikan fungsi murni minimal**

```python
STATUS_PRIORITY = {"healthy": 0, "degraded": 1, "down": 2}


def determine_overall(states: list[str]) -> str:
    return max(states, key=STATUS_PRIORITY.__getitem__, default="healthy")


def is_snapshot_fresh(snapshot: dict, *, now: datetime | None = None) -> bool:
    current = now or datetime.now(timezone.utc)
    updated = datetime.fromisoformat(snapshot["updated_at"])
    return current - updated <= timedelta(seconds=90)


def write_snapshot_atomic(target: Path, snapshot: dict) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    temporary.replace(target)
```

Tambahkan `sanitize_error()` dengan pola key/token yang eksplisit dan batas panjang 500 karakter.

- [ ] **Step 4: Jalankan test GREEN**

Run: `source bima_env/bin/activate && pytest tests/test_operational_status.py -q`

Expected: `4 passed`.

- [ ] **Step 5: Tambah test pengumpulan snapshot**

Test memakai dependency injection untuk runner PM2, HTTP probe, metrics, Git, dan log reader; tidak menjalankan subprocess/network nyata.

```python
def test_collect_snapshot_keeps_partial_results_when_probe_fails(tmp_path):
    snapshot = collect_snapshot(
        project_root=tmp_path,
        pm2_reader=lambda: {"anisa-v3": {"status": "online"}},
        metrics_reader=lambda: {"cpu_percent": 10.0, "ram_percent": 20.0, "disk_percent": 30.0},
        health_reader=lambda: (_ for _ in ()).throw(TimeoutError()),
        git_reader=lambda: {"commit": "abc1234", "dirty": False},
        error_reader=lambda: None,
    )
    assert snapshot["health"]["backend"] == "unreachable"
    assert snapshot["overall"] == "down"
    assert snapshot["services"]["anisa-v3"]["status"] == "online"
```

- [ ] **Step 6: Jalankan RED, implementasikan collector, lalu GREEN**

Run sebelum implementasi: `source bima_env/bin/activate && pytest tests/test_operational_status.py -q`

Expected: FAIL karena `collect_snapshot` belum ada.

Implementasi membaca `pm2 jlist`, `core.system_metrics.snapshot()`, `http://127.0.0.1:8000/api/metrics` dengan timeout 2 detik, tiga direktori indeks, `git rev-parse --short HEAD`, `git status --porcelain`, dan baris error terbaru. Setiap sumber dibungkus pada boundary masing-masing agar hasil parsial tetap tersedia.

Run sesudah implementasi: `source bima_env/bin/activate && pytest tests/test_operational_status.py -q`

Expected: seluruh test PASS.

- [ ] **Step 7: Abaikan artefak runtime**

Tambahkan ke `.gitignore`:

```gitignore
runtime/anisa_status.json
runtime/*.tmp
```

### Task 3: Jalankan Collector sebagai Sidecar PM2

**Files:**
- Create: `scripts/status_collector.py`
- Modify: `ecosystem.config.js`

- [ ] **Step 1: Tulis CLI loop tipis**

```python
def run(interval_seconds: int = 30) -> None:
    target = PROJECT_ROOT / "runtime" / "anisa_status.json"
    while True:
        snapshot = collect_snapshot(project_root=PROJECT_ROOT)
        write_snapshot_atomic(target, snapshot)
        time.sleep(interval_seconds)


if __name__ == "__main__":
    run()
```

- [ ] **Step 2: Tambahkan definisi PM2**

```javascript
{
  name: "anisa-status",
  script: "scripts/status_collector.py",
  interpreter: "/home/bima_lucian/BIMA_CORE/bima_env/bin/python3",
  cwd: "/home/bima_lucian/BIMA_CORE",
  autorestart: true,
  restart_delay: 5000,
  error_file: "./logs/status-error.log",
  out_file: "./logs/status-output.log",
  merge_logs: true,
}
```

- [ ] **Step 3: Verifikasi syntax dan one-shot snapshot**

Run: `source bima_env/bin/activate && python -m py_compile core/operational_status.py scripts/status_collector.py scripts/healthcheck.py`

Expected: exit 0.

Run: `source bima_env/bin/activate && python -c "from pathlib import Path; from core.operational_status import collect_snapshot, write_snapshot_atomic; p=Path('runtime/anisa_status.json'); write_snapshot_atomic(p, collect_snapshot(project_root=Path.cwd())); print(p)"`

Expected: path snapshot tercetak dan JSON valid.

- [ ] **Step 4: Aktifkan hanya sidecar baru**

Run: `pm2 start ecosystem.config.js --only anisa-status && pm2 save`

Expected: `pm2 describe anisa-status` menunjukkan `online`; proses existing tidak direstart.

### Task 4: Perbarui Konfigurasi Vault dan Dependency WhatsApp

**Files:**
- Modify: `.env`
- Modify: `whatsapp/package-lock.json`

- [ ] **Step 1: Ubah hanya jalur vault**

```dotenv
OBSIDIAN_PATH=/home/bima_lucian/BIMA_CORE/Bima_Vault
```

- [ ] **Step 2: Terapkan patch audit dependency tanpa force**

Run: `cd whatsapp && npm audit fix`

Expected lockfile changes only: `form-data 4.0.6`, `js-yaml 4.3.0`, `ws 8.21.0`, dan `hasown 2.0.4`; tidak ada major package update.

- [ ] **Step 3: Verifikasi dependency dan bridge**

Run: `cd whatsapp && npm audit --audit-level=moderate`

Expected: `found 0 vulnerabilities`.

Run: `node --check whatsapp/index.js`

Expected: exit 0.

Run: `cd whatsapp && npm ls form-data js-yaml ws --all`

Expected: resolved version tidak berada di vulnerable ranges.

- [ ] **Step 4: Restart service yang terdampak**

Run: `pm2 restart anisa-v3 --update-env && pm2 restart bima-whatsapp && pm2 save`

Expected: kedua service kembali `online`; sidecar mencatat status terbaru.

### Task 5: Dokumentasi Error dan Verifikasi Akhir

**Files:**
- Modify: `error_solutions.md`

- [ ] **Step 1: Tambah log faktual**

Tambahkan log baru yang mencatat:

```markdown
## Log 27: Healthcheck Memakai Folder scripts sebagai Root
* **Masalah**: `BASE_DIR` menunjuk `scripts/`, menghasilkan 12 false critical failures dan false warning indeks.
* **Root Cause**: Root dihitung satu level terlalu dangkal dan script mengeksekusi pemeriksaan saat import.
* **Solusi**: Pakai project root dua level, fungsi `main()`, helper yang bisa diuji, dan regression test.
* **Verifikasi**: Cantumkan hasil pytest serta healthcheck aktual.

## Log 28: Agent Tidak Memiliki Snapshot Operasional Ringkas
* **Masalah**: Agent harus menjalankan banyak command atau scan untuk mengetahui kondisi Anisa.
* **Root Cause**: Status hanya tersedia on-demand dan tidak disimpan sebagai kontrak tunggal.
* **Solusi**: Sidecar `anisa-status` menulis snapshot atomic setiap 30 detik; stale setelah 90 detik.
* **Verifikasi**: Cantumkan status PM2, umur snapshot, dan validasi JSON.

## Log 29: Dependency WhatsApp Berada di Vulnerable Range
* **Masalah**: `npm audit` menemukan form-data, js-yaml, dan ws.
* **Root Cause**: Lockfile menahan versi patch lama.
* **Solusi**: Patch lockfile tanpa force ke versi aman hasil npm audit.
* **Verifikasi**: Cantumkan hasil npm audit, node syntax, dan status PM2.
```

- [ ] **Step 2: Jalankan suite fokus**

Run: `source bima_env/bin/activate && pytest tests/test_healthcheck.py tests/test_operational_status.py -q`

Expected: seluruh test PASS.

- [ ] **Step 3: Jalankan suite penuh**

Run: `source bima_env/bin/activate && pytest -q`

Expected: exit 0. Jika ada failure unrelated, berhenti dan laporkan; jangan auto-patch.

- [ ] **Step 4: Verifikasi runtime segar**

Run: `pm2 describe anisa-status`

Expected: status `online`.

Run: `source bima_env/bin/activate && python -c "import json; from pathlib import Path; from core.operational_status import is_snapshot_fresh; data=json.loads(Path('runtime/anisa_status.json').read_text()); assert is_snapshot_fresh(data); print(data['overall'])"`

Expected: exit 0 dan mencetak `healthy` atau status masalah faktual yang dapat ditelusuri dari snapshot.

- [ ] **Step 5: Periksa diff dan batas scope**

Run: `git diff --check`

Expected: tidak ada whitespace error.

Run: `git status --short`

Expected: perubahan QC milik Bima tetap tidak disentuh; hanya file scope plan yang bertambah/berubah.
