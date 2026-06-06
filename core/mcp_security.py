"""MCP Security Audit — Scan config_mcp.json to identify potential security vulnerabilities."""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger("bima_core")

# Whitelist perintah yang diperbolehkan dieksekusi oleh MCP
COMMAND_WHITELIST = {"npx", "uvx", "node", "python3", "python"}

# Blacklist argument/keyword berbahaya
DANGEROUS_KEYWORDS = {"rm ", "del ", "curl", "wget", "sh ", "bash ", ">", "|", "sudo", "eval", "exec"}

def audit_mcp_config(config_path: str | Path) -> dict:
    """Memindai file config_mcp.json dan mengembalikan hasil audit keamanan."""
    p = Path(config_path)
    if not p.exists():
        return {"status": "error", "message": f"File config tidak ditemukan di {p}", "issues": []}

    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return {"status": "error", "message": f"Gagal membaca/parse JSON: {e}", "issues": []}

    servers = data.get("servers", [])
    issues = []
    
    for srv in servers:
        name = srv.get("name", "Unnamed")
        enabled = srv.get("enabled", True)
        if not enabled:
            continue

        command = srv.get("command", "")
        args = srv.get("args", [])
        env = srv.get("env", {})

        # Rule 1: Periksa command whitelist
        if command and command not in COMMAND_WHITELIST:
            issues.append({
                "server": name,
                "severity": "HIGH",
                "issue": f"Perintah '{command}' tidak terdaftar di whitelist keamanan.",
                "remediation": f"Gunakan wrapper resmi seperti 'uvx' atau 'npx'."
            })

        # Rule 2: Deteksi keyword berbahaya di argumen
        for arg in args:
            arg_str = str(arg).lower()
            # Cek traversal
            if "../" in arg_str or "..\\" in arg_str:
                issues.append({
                    "server": name,
                    "severity": "CRITICAL",
                    "issue": f"Terdeteksi percobaan path traversal ('../') pada argumen: '{arg}'",
                    "remediation": "Batasi cakupan folder ke subdirektori lokal atau output saja."
                })
            
            # Cek command injection keywords
            for kw in DANGEROUS_KEYWORDS:
                if kw in arg_str:
                    issues.append({
                        "server": name,
                        "severity": "CRITICAL",
                        "issue": f"Terdeteksi keyword berbahaya '{kw}' di dalam argumen: '{arg}'",
                        "remediation": "Hindari piping shell (|), redirect (>), atau command execution dinamis."
                    })

        # Rule 3: Audit environment variables (kebocoran token sensitif)
        for key, val in env.items():
            val_str = str(val)
            if "key" in key.lower() or "token" in key.lower() or "secret" in key.lower():
                # Pastikan disematkan lewat variabel lingkungan, bukan hardcode string plaintext
                if not val_str.startswith("${") and not val_str.startswith("$"):
                    issues.append({
                        "server": name,
                        "severity": "WARNING",
                        "issue": f"Variabel sensitif '{key}' bernilai plaintext hardcoded.",
                        "remediation": "Gunakan ekspansi env, misalnya: '${MY_SECRET_TOKEN}'."
                    })

    status = "warning" if issues else "secure"
    critical_issues = [iss for iss in issues if iss["severity"] in ("HIGH", "CRITICAL")]
    if critical_issues:
        status = "unsafe"

    return {
        "status": status,
        "total_issues": len(issues),
        "issues": issues
    }

def verify_and_alert_mcp(config_path: str | Path) -> bool:
    """Menjalankan audit dan mencetak log / mematikan server jika mendeteksi ancaman CRITICAL."""
    result = audit_mcp_config(config_path)
    if result["status"] == "error":
        logger.error(f"[SECURITY] Gagal mengaudit MCP: {result['message']}")
        return True # toleransi jika file corrupt/hilang, tetapi beri peringatan
        
    issues = result["issues"]
    if issues:
        logger.warning(f"[SECURITY] Hasil scan MCP config menemukan {len(issues)} potensi bahaya:")
        for iss in issues:
            log_msg = f"  - [{iss['severity']}] Server '{iss['server']}': {iss['issue']} -> Solusi: {iss['remediation']}"
            if iss["severity"] in ("HIGH", "CRITICAL"):
                logger.error(log_msg)
            else:
                logger.warning(log_msg)
                
    if result["status"] == "unsafe":
        logger.error("[SECURITY] Eksekusi BIMA dihentikan karena config MCP tidak aman!")
        return False
        
    logger.info("[SECURITY] Scan MCP config berhasil. Status: AMAN.")
    return True
