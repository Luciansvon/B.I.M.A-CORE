#!/usr/bin/env python3
"""BIMA Core deployment healthcheck."""

from __future__ import annotations

import importlib
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
NC = "\033[0m"


@dataclass
class CheckReport:
    """Mutable counters for one healthcheck execution."""

    passed: int = 0
    failed: int = 0
    warnings: int = 0

    def ok(self, message: str) -> None:
        self.passed += 1
        print(f"  {GREEN}✅ {message}{NC}")

    def fail(self, message: str) -> None:
        self.failed += 1
        print(f"  {RED}❌ {message}{NC}")

    def warn(self, message: str) -> None:
        self.warnings += 1
        print(f"  {YELLOW}⚠️  {message}{NC}")


def index_status(base_dir: Path) -> dict[str, bool]:
    """Return readiness for every persistent search index."""
    return {
        name: (base_dir / name).is_dir()
        for name in ("search_index", "repo_index", "vault_index")
    }


def _print_header() -> None:
    print(
        f"\n{CYAN}╔══════════════════════════════════════════╗\n"
        "║   B.I.M.A CORE — HEALTH CHECK            ║\n"
        f"╚══════════════════════════════════════════╝{NC}\n"
    )


def _check_python(report: CheckReport) -> None:
    print(f"{CYAN}[1] Python Version{NC}")
    version = sys.version_info
    if version.major == 3 and version.minor >= 10:
        report.ok(f"Python {version.major}.{version.minor}.{version.micro}")
    else:
        report.fail(f"Python {version.major}.{version.minor} — butuh minimal 3.10")


def _check_packages(report: CheckReport) -> None:
    print(f"\n{CYAN}[2] Critical Python Packages{NC}")
    packages = {
        "crewai": "CrewAI (agent framework)",
        "langgraph": "LangGraph (orchestration)",
        "langchain_core": "LangChain Core",
        "langchain_openai": "LangChain OpenAI",
        "fastapi": "FastAPI (dashboard server)",
        "uvicorn": "Uvicorn (ASGI server)",
        "discord": "Discord.py (bot)",
        "dotenv": "python-dotenv",
        "httpx": "HTTPX (async HTTP)",
        "scrapling": "Scrapling (web scraping + parsing)",
        "sentence_transformers": "Sentence Transformers (embeddings)",
        "lancedb": "LanceDB (vector store)",
        "fpdf": "FPDF2 (PDF generation)",
        "docx": "python-docx (Word generation)",
        "pptx": "python-pptx (PowerPoint)",
        "openpyxl": "OpenPyXL (Excel)",
        "pandas": "Pandas (data analysis)",
        "matplotlib": "Matplotlib (charts)",
    }
    for module, name in packages.items():
        try:
            importlib.import_module(module)
            report.ok(name)
        except ImportError:
            report.fail(f"{name} — pip install {module}")


def _check_environment(report: CheckReport) -> None:
    print(f"\n{CYAN}[3] Environment Variables{NC}")
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
    variables = {
        "OPENROUTER_API_KEY": ("OpenRouter API (LLM)", True),
        "DISCORD_TOKEN": ("Discord Bot Token", True),
        "SERPER_API_KEY": ("Serper (Google Search)", False),
        "GEMINI_API_KEY": ("Gemini API", False),
        "TAVILY_API_KEY": ("Tavily Search", False),
        "RAPIDAPI_KEY": ("RapidAPI", False),
        "LANGSMITH_API_KEY": ("LangSmith Tracing", False),
        "BOT_STATUS_CHANNEL_ID": ("Discord Status Channel", False),
        "OBSIDIAN_PATH": ("Obsidian Vault Path", False),
    }
    for variable, (description, required) in variables.items():
        value = os.environ.get(variable, "")
        if value:
            report.ok(f"{description}: configured")
        elif required:
            report.fail(f"{description}: {variable} NOT SET!")
        else:
            report.warn(f"{description}: {variable} not set (optional)")


def _check_vault(report: CheckReport) -> None:
    print(f"\n{CYAN}[4] Obsidian Vault Path{NC}")
    value = os.environ.get("OBSIDIAN_PATH", "")
    if value and Path(value).exists():
        report.ok(f"Vault accessible: {value}")
    elif value:
        report.warn(f"Vault path set tapi tidak ada: {value}")
    else:
        report.warn("OBSIDIAN_PATH tidak di-set, vault search tidak akan jalan")


def _check_structure(report: CheckReport) -> None:
    print(f"\n{CYAN}[5] Directory Structure{NC}")
    for name in ("outputs", "logs", "memory", "frontend", "core", "teams", "tools"):
        if (BASE_DIR / name).is_dir():
            report.ok(f"{name}/ exists")
        else:
            report.fail(f"{name}/ MISSING")


def _check_files(report: CheckReport) -> None:
    print(f"\n{CYAN}[6] Critical Files{NC}")
    files = {
        "main.py": BASE_DIR / "main.py",
        "config.py": BASE_DIR / "config.py",
        ".env": BASE_DIR / ".env",
        "ecosystem.config.js": BASE_DIR / "ecosystem.config.js",
        "dashboard": BASE_DIR / "dashboard",
        "memory.json": BASE_DIR / "memory" / "memory.json",
    }
    for name, path in files.items():
        if path.exists():
            report.ok(f"{name} exists")
        elif name == "memory.json":
            report.warn(f"{name} not found (will be created on first run)")
        else:
            report.fail(f"{name} MISSING")


def _check_indexes(report: CheckReport) -> None:
    print(f"\n{CYAN}[7] Search Index{NC}")
    for name, ready in index_status(BASE_DIR).items():
        if ready:
            file_count = sum(1 for path in (BASE_DIR / name).rglob("*") if path.is_file())
            report.ok(f"{name}/ ready ({file_count} files)")
        else:
            report.warn(f"{name}/ not found — rebuild index sebelum dipakai")


def _check_external_tools(report: CheckReport) -> None:
    print(f"\n{CYAN}[8] External Tools{NC}")
    tools = {
        "pm2": "PM2 (process manager)",
        "cloudflared": "Cloudflared (tunnel)",
        "node": "Node.js",
        "git": "Git",
    }
    for command, description in tools.items():
        if shutil.which(command):
            report.ok(f"{description} found")
        else:
            report.warn(f"{description} not found")


def _check_resources(report: CheckReport) -> None:
    print(f"\n{CYAN}[9] System Resources{NC}")
    try:
        import psutil
    except ImportError:
        report.warn("psutil not installed — skipping resource check")
        return

    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    ram_gb = memory.total / (1024**3)
    disk_free_gb = disk.free / (1024**3)
    if ram_gb >= 8:
        report.ok(f"RAM: {ram_gb:.1f} GB (recommended)")
    elif ram_gb >= 4:
        report.warn(f"RAM: {ram_gb:.1f} GB (minimum — use swap)")
    else:
        report.fail(f"RAM: {ram_gb:.1f} GB (insufficient — need 4GB+)")
    report.ok(f"CPU: {psutil.cpu_count()} cores")
    if disk_free_gb >= 40:
        report.ok(f"Disk free: {disk_free_gb:.1f} GB")
    elif disk_free_gb >= 20:
        report.warn(f"Disk free: {disk_free_gb:.1f} GB (getting low)")
    else:
        report.fail(f"Disk free: {disk_free_gb:.1f} GB (need more space)")


def main() -> int:
    """Run every healthcheck and return a meaningful process exit code."""
    report = CheckReport()
    _print_header()
    _check_python(report)
    _check_packages(report)
    _check_environment(report)
    _check_vault(report)
    _check_structure(report)
    _check_files(report)
    _check_indexes(report)
    _check_external_tools(report)
    _check_resources(report)

    print(f"\n{CYAN}{'=' * 50}{NC}")
    print(f"  {GREEN}✅ Passed: {report.passed}{NC}")
    if report.failed:
        print(f"  {RED}❌ Failed: {report.failed}{NC}")
    if report.warnings:
        print(f"  {YELLOW}⚠️  Warnings: {report.warnings}{NC}")
    print()
    if report.failed:
        print(f"  {RED}⛔ Ada {report.failed} issue yang harus diperbaiki sebelum deploy.{NC}")
    else:
        print(f"  {GREEN}🚀 BIMA CORE siap deploy.{NC}")
    print()
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
