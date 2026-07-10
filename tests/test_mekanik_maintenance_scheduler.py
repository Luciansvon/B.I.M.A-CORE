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
