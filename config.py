import os
from pathlib import Path
from dotenv import load_dotenv
from crewai import LLM
from core.model_router import (
    VISUAL_MODEL,
    crewai_model_id,
    model_profile,
)

load_dotenv()

# Direktori utama
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)
OBSIDIAN_PATH = os.environ.get("OBSIDIAN_PATH", str(BASE_DIR / "vault"))

# MCP client config — dipake core.mcp_client_manager.init_manager()
MCP_CLIENTS_CONFIG = BASE_DIR / "config_mcp.json"

# Validasi environment
_api_key = os.environ.get("OPENROUTER_API_KEY")
if not _api_key:
    print("[CONFIG] ⚠️  OPENROUTER_API_KEY tidak ditemukan di .env!")
else:
    print(f"[CONFIG] ✅ API Key terdeteksi ({len(_api_key)} chars)")

# Inisialisasi LLM secara terpusat
def get_llm(
    model_name: str,
    *,
    fallbacks: tuple[str, ...] = (),
    reasoning_effort: str | None = None,
) -> LLM:
    kwargs: dict[str, object] = {}
    if fallbacks:
        router_model = model_name.removeprefix("openrouter/")
        kwargs["extra_body"] = {"models": [router_model, *fallbacks]}
    if reasoning_effort:
        kwargs["reasoning_effort"] = reasoning_effort
    return LLM(
        model=model_name,
        api_key=_api_key,
        base_url="https://openrouter.ai/api/v1",
        **kwargs,
    )


def get_team_llm(team: str, profile: str = "standard") -> LLM:
    selected = model_profile(team, profile)
    return get_llm(
        crewai_model_id(selected.model),
        fallbacks=selected.fallbacks,
        reasoning_effort=selected.reasoning_effort,
    )

# Model names (tanpa "openrouter/" prefix — buat OpenAI SDK langsung yg base_url-nya udah OpenRouter)
# Dipake furniture_qc.py via OpenAI SDK, dan crewai LLM via get_llm() di bawah.
VISUAL_MODEL_NAME = VISUAL_MODEL

try:
    # 1. MANAGER & ROUTING LLM (Paling sering dipanggil, harus termurah)
    manager_llm = get_team_llm("manager")

    # 2. VISUAL LLM (Spesialis gambar/PDF)
    visual_llm = get_team_llm("visual")
    
    # 3. SPESIALIS MENENGAH (Tugas umum, harga terjangkau)
    arsip_llm = get_team_llm("arsip")
    arsip_heavy_llm = get_team_llm("arsip", "heavy")
    admin_llm = get_team_llm("admin")
    admin_heavy_llm = get_team_llm("admin", "heavy")
    lifestyle_llm = get_team_llm("lifestyle")
    seniman_llm = get_team_llm("seniman")
    
    # 4. SPESIALIS BERAT/LOGIKA (Minta model paling pintar)
    intel_llm = get_team_llm("intel")
    mekanik_llm = get_team_llm("mekanik")
    mekanik_heavy_llm = get_team_llm("mekanik", "heavy")
    saham_llm = get_team_llm("saham")
    kodok_llm = get_team_llm("kodok")
    kodok_heavy_llm = get_team_llm("kodok", "heavy")
    
    print("[CONFIG] ✅ Semua LLM berhasil diinisialisasi dengan mode HEMAT TOKEN!")
except Exception as e:
    print(f"[CONFIG] ❌ Gagal inisialisasi LLM: {e}")
    raise
