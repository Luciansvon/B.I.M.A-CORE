#!/usr/bin/env python3
"""
BIMA CORE — VPS Health Check Script
Jalankan: python3 healthcheck.py
Verifikasi semua komponen siap sebelum start PM2.
"""

import os
import sys
import json
import shutil
from pathlib import Path

GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
NC = "\033[0m"

BASE_DIR = Path(__file__).parent
checks_passed = 0
checks_failed = 0
warnings = 0


def ok(msg):
    global checks_passed
    checks_passed += 1
    print(f"  {GREEN}✅ {msg}{NC}")

def fail(msg):
    global checks_failed
    checks_failed += 1
    print(f"  {RED}❌ {msg}{NC}")

def warn(msg):
    global warnings
    warnings += 1
    print(f"  {YELLOW}⚠️  {msg}{NC}")


print(f"\n{CYAN}╔══════════════════════════════════════════╗")
print(f"║   B.I.M.A CORE — HEALTH CHECK            ║")
print(f"╚══════════════════════════════════════════╝{NC}\n")


# ── 1. Python Version ──
print(f"{CYAN}[1] Python Version{NC}")
v = sys.version_info
if v.major == 3 and v.minor >= 10:
    ok(f"Python {v.major}.{v.minor}.{v.micro}")
else:
    fail(f"Python {v.major}.{v.minor} — butuh minimal 3.10")


# ── 2. Critical Imports ──
print(f"\n{CYAN}[2] Critical Python Packages{NC}")
critical_packages = [
    ("crewai", "CrewAI (agent framework)"),
    ("langgraph", "LangGraph (orchestration)"),
    ("langchain_core", "LangChain Core"),
    ("langchain_openai", "LangChain OpenAI"),
    ("fastapi", "FastAPI (dashboard server)"),
    ("uvicorn", "Uvicorn (ASGI server)"),
    ("discord", "Discord.py (bot)"),
    ("dotenv", "python-dotenv"),
    ("httpx", "HTTPX (async HTTP)"),
    ("scrapling", "Scrapling (web scraping + parsing)"),
    ("sentence_transformers", "Sentence Transformers (embeddings)"),
    ("lancedb", "LanceDB (vector store)"),
    ("fpdf", "FPDF2 (PDF generation)"),
    ("docx", "python-docx (Word generation)"),
    ("pptx", "python-pptx (PowerPoint)"),
    ("openpyxl", "OpenPyXL (Excel)"),
    ("pandas", "Pandas (data analysis)"),
    ("matplotlib", "Matplotlib (charts)"),
]

for module, name in critical_packages:
    try:
        __import__(module)
        ok(name)
    except ImportError:
        fail(f"{name} — pip install {module}")


# ── 3. Environment Variables ──
print(f"\n{CYAN}[3] Environment Variables{NC}")
from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

required_vars = {
    "OPENROUTER_API_KEY": "OpenRouter API (LLM)",
    "DISCORD_TOKEN": "Discord Bot Token",
}
optional_vars = {
    "SERPER_API_KEY": "Serper (Google Search)",
    "GEMINI_API_KEY": "Gemini API",
    "TAVILY_API_KEY": "Tavily Search",
    "RAPIDAPI_KEY": "RapidAPI",
    "LANGSMITH_API_KEY": "LangSmith Tracing",
    "BOT_STATUS_CHANNEL_ID": "Discord Status Channel",
    "OBSIDIAN_PATH": "Obsidian Vault Path",
}

for var, desc in required_vars.items():
    val = os.environ.get(var, "")
    if val:
        ok(f"{desc}: {val[:15]}...")
    else:
        fail(f"{desc}: {var} NOT SET!")

for var, desc in optional_vars.items():
    val = os.environ.get(var, "")
    if val:
        ok(f"{desc}: {val[:15]}...")
    else:
        warn(f"{desc}: {var} not set (optional)")


# ── 4. OBSIDIAN_PATH ──
print(f"\n{CYAN}[4] Obsidian Vault Path{NC}")
obs_path = os.environ.get("OBSIDIAN_PATH", "")
if "/mnt/c/" in obs_path or "/mnt/d/" in obs_path:
    warn(f"OBSIDIAN_PATH masih mengarah ke Windows: {obs_path}")
    warn(f"Ubah ke: OBSIDIAN_PATH={BASE_DIR / 'Bima_Vault'}")
elif obs_path and Path(obs_path).exists():
    ok(f"Vault accessible: {obs_path}")
elif obs_path:
    warn(f"Vault path set tapi tidak ada: {obs_path}")
else:
    warn("OBSIDIAN_PATH tidak di-set, vault search tidak akan jalan")


# ── 5. Directories ──
print(f"\n{CYAN}[5] Directory Structure{NC}")
dirs = {
    "outputs": BASE_DIR / "outputs",
    "logs": BASE_DIR / "logs",
    "memory": BASE_DIR / "memory",
    "frontend": BASE_DIR / "frontend",
    "core": BASE_DIR / "core",
    "teams": BASE_DIR / "teams",
    "tools": BASE_DIR / "tools",
}
for name, path in dirs.items():
    if path.exists():
        ok(f"{name}/ exists")
    else:
        fail(f"{name}/ MISSING")


# ── 6. Critical Files ──
print(f"\n{CYAN}[6] Critical Files{NC}")
files = {
    "main.py": BASE_DIR / "main.py",
    "config.py": BASE_DIR / "config.py",
    ".env": BASE_DIR / ".env",
    "ecosystem.config.js": BASE_DIR / "ecosystem.config.js",
    "dashboard.html": BASE_DIR / "frontend" / "dashboard.html",
    "memory.json": BASE_DIR / "memory" / "memory.json",
}
for name, path in files.items():
    if path.exists():
        size = path.stat().st_size
        ok(f"{name} ({size:,} bytes)")
    else:
        if name == "memory.json":
            warn(f"{name} not found (will be created on first run)")
        else:
            fail(f"{name} MISSING")


# ── 7. Search Index ──
print(f"\n{CYAN}[7] Search Index{NC}")
idx_dir = BASE_DIR / "search_index"
if idx_dir.exists():
    idx_files = list(idx_dir.iterdir())
    total_size = sum(f.stat().st_size for f in idx_files if f.is_file())
    ok(f"search_index/: {len(idx_files)} files, {total_size / 1024 / 1024:.1f} MB")
else:
    warn("search_index/ not found — semantic search won't work until rebuilt")

# Repo RAG index (kodok)
repo_idx = BASE_DIR / "repo_index"
if repo_idx.exists():
    repo_files = list(repo_idx.rglob("*"))
    repo_size = sum(f.stat().st_size for f in repo_files if f.is_file())
    ok(f"repo_index/ (kodok RAG): {len([f for f in repo_files if f.is_file()])} files, {repo_size / 1024 / 1024:.1f} MB")
else:
    warn("repo_index/ not found — kodok code-RAG belum di-build. Jalanin: python -m tools.repo_rag")


# ── 8. External Tools ──
print(f"\n{CYAN}[8] External Tools{NC}")
tools_check = {
    "pm2": "PM2 (process manager)",
    "cloudflared": "Cloudflared (tunnel)",
    "node": "Node.js",
    "git": "Git",
}
for cmd, desc in tools_check.items():
    if shutil.which(cmd):
        ok(f"{desc} found")
    else:
        warn(f"{desc} not found — install before deploying")


# ── 9. System Resources ──
print(f"\n{CYAN}[9] System Resources{NC}")
try:
    import psutil
    ram_gb = psutil.virtual_memory().total / (1024**3)
    cpu_count = psutil.cpu_count()
    disk = psutil.disk_usage("/")
    disk_free_gb = disk.free / (1024**3)

    if ram_gb >= 8:
        ok(f"RAM: {ram_gb:.1f} GB (recommended)")
    elif ram_gb >= 4:
        warn(f"RAM: {ram_gb:.1f} GB (minimum — use swap)")
    else:
        fail(f"RAM: {ram_gb:.1f} GB (insufficient — need 4GB+)")

    ok(f"CPU: {cpu_count} cores")

    if disk_free_gb >= 40:
        ok(f"Disk free: {disk_free_gb:.1f} GB")
    elif disk_free_gb >= 20:
        warn(f"Disk free: {disk_free_gb:.1f} GB (getting low)")
    else:
        fail(f"Disk free: {disk_free_gb:.1f} GB (need more space)")
except ImportError:
    warn("psutil not installed — skipping resource check (pip install psutil)")


# ── Summary ──
print(f"\n{CYAN}{'='*50}{NC}")
total = checks_passed + checks_failed
print(f"  {GREEN}✅ Passed: {checks_passed}{NC}")
if checks_failed > 0:
    print(f"  {RED}❌ Failed: {checks_failed}{NC}")
if warnings > 0:
    print(f"  {YELLOW}⚠️  Warnings: {warnings}{NC}")

print()
if checks_failed == 0:
    print(f"  {GREEN}🚀 BIMA CORE siap deploy! Jalankan:{NC}")
    print(f"  {CYAN}   pm2 start ecosystem.config.js{NC}")
    print(f"  {CYAN}   pm2 startup && pm2 save{NC}")
else:
    print(f"  {RED}⛔ Ada {checks_failed} issue yang harus diperbaiki sebelum deploy.{NC}")
print()
