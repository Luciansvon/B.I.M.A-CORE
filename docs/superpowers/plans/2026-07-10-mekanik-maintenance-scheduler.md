# Mekanik Maintenance Scheduler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe Team Mekanik maintenance report schedule for Anisa, three nights per week, without auto-restart or destructive actions.

**Architecture:** Reuse the existing Discord startup scheduler pattern and add a focused `core.mekanik_maintenance_scheduler` module. The module builds a deterministic text report from system metrics, PM2 status, GPU VRAM, recent local logs, and MCP config audit, then sends it to `BOT_STATUS_CHANNEL_ID` on Monday/Wednesday/Friday at 21:30 WIB.

**Tech Stack:** Python 3.10+, APScheduler `AsyncIOScheduler`, `CronTrigger`, Discord client, `psutil`, existing `core.system_metrics`, existing `core.mcp_security`.

---

### Task 1: Test Report Builder

**Files:**
- Create: `tests/test_mekanik_maintenance_scheduler.py`

- [ ] **Step 1: Write the failing test**

```python
from core import mekanik_maintenance_scheduler as mt


def test_build_report_includes_schedule_identity_and_no_autofix(monkeypatch):
    monkeypatch.setattr(mt, "snapshot", lambda: {
        "cpu_percent": 12.0,
        "ram_used_mb": 2048.0,
        "ram_total_mb": 8192.0,
        "ram_percent": 25.0,
        "disk_used_gb": 20.0,
        "disk_total_gb": 100.0,
        "disk_percent": 20.0,
        "load_avg_1m": 0.5,
        "proc_count": 120,
    })
    monkeypatch.setattr(mt, "_get_gpu_vram_usage", lambda: (1000.0, 8000.0, 12.5))
    monkeypatch.setattr(mt, "_get_pm2_status", lambda: [
        {"name": "anisa-v3", "status": "online", "restart_count": 1, "mem": 256.0, "cpu": 2.0},
        {"name": "bima-whatsapp", "status": "online", "restart_count": 0, "mem": 128.0, "cpu": 1.0},
    ])
    monkeypatch.setattr(mt, "_scan_recent_log_errors", lambda: [])
    monkeypatch.setattr(mt, "_audit_mcp", lambda: {"status": "secure", "message": "ok", "issues": []})

    report = mt.build_mekanik_maintenance_report()

    assert "Team Mekanik MT Check" in report
    assert "Mode: report only" in report
    assert "anisa-v3" in report
    assert "MCP: secure" in report
    assert "Tidak ada auto-restart" in report
```

- [ ] **Step 2: Run test to verify RED**

Run: `wsl.exe -d Ubuntu -- bash -lc "cd /home/bima_lucian/BIMA_CORE && source bima_env/bin/activate && pytest tests/test_mekanik_maintenance_scheduler.py -q"`

Expected: FAIL because `core.mekanik_maintenance_scheduler` does not exist yet.

### Task 2: Implement Scheduler Module

**Files:**
- Create: `core/mekanik_maintenance_scheduler.py`

- [ ] **Step 1: Add minimal implementation**

Create:
- `build_mekanik_maintenance_report() -> str`
- `_get_gpu_vram_usage() -> tuple[float, float, float] | None`
- `_get_pm2_status() -> list[dict]`
- `_scan_recent_log_errors() -> list[str]`
- `_audit_mcp() -> dict`
- `_send_mekanik_maintenance_report(client) -> None`
- `start_mekanik_maintenance_scheduler(client)`

Rules:
- Default schedule: `mon,wed,fri` at `21:30` WIB.
- Env overrides: `ENABLE_MEKANIK_MT`, `MEKANIK_MT_DAYS`, `MEKANIK_MT_HOUR`, `MEKANIK_MT_MINUTE`.
- No auto-restart, no write/delete, no commit/push.
- Send only to `BOT_STATUS_CHANNEL_ID`.

- [ ] **Step 2: Run test to verify GREEN**

Run: `wsl.exe -d Ubuntu -- bash -lc "cd /home/bima_lucian/BIMA_CORE && source bima_env/bin/activate && pytest tests/test_mekanik_maintenance_scheduler.py -q"`

Expected: PASS.

### Task 3: Wire Scheduler on Discord Startup

**Files:**
- Modify: `core/discord_bot.py`

- [ ] **Step 1: Start scheduler after observability scheduler**

Add guarded startup block:

```python
try:
    from core.mekanik_maintenance_scheduler import start_mekanik_maintenance_scheduler
    start_mekanik_maintenance_scheduler(client)
except Exception as e:
    logger.error(f'Gagal start Mekanik maintenance scheduler: {e}', exc_info=True)
```

- [ ] **Step 2: Run syntax check**

Run: `wsl.exe -d Ubuntu -- bash -lc "cd /home/bima_lucian/BIMA_CORE && source bima_env/bin/activate && python3 -m py_compile core/discord_bot.py core/mekanik_maintenance_scheduler.py"`

Expected: exit code 0.

### Task 4: Document Env Example

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Add optional config**

```env
# === TEAM MEKANIK MAINTENANCE ===
ENABLE_MEKANIK_MT=true
MEKANIK_MT_DAYS=mon,wed,fri
MEKANIK_MT_HOUR=21
MEKANIK_MT_MINUTE=30
```

### Task 5: Error Log

**Files:**
- Modify: `error_solutions.md`

- [ ] **Step 1: Record feature decision**

Add a short log entry:
- Problem: Anisa had interval observability alerts but no named Team Mekanik maintenance schedule.
- Solution: Add report-only scheduler three nights per week.
- Verification commands run.

### Task 6: Final Verification

- [ ] **Step 1: Run focused tests**

Run: `wsl.exe -d Ubuntu -- bash -lc "cd /home/bima_lucian/BIMA_CORE && source bima_env/bin/activate && pytest tests/test_mekanik_maintenance_scheduler.py tests/test_mcp_security.py tests/test_permission_gate.py -q"`

- [ ] **Step 2: Inspect diff**

Run: `git diff -- core/mekanik_maintenance_scheduler.py core/discord_bot.py .env.example tests/test_mekanik_maintenance_scheduler.py error_solutions.md`

- [ ] **Step 3: Do not commit unless Bima asks**

Reason: repo rules require explicit user intent for git operations.
