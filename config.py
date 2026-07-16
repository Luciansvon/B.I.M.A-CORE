import os
from pathlib import Path
from dotenv import load_dotenv
from crewai import LLM

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
def get_llm(model_name: str) -> LLM:
    return LLM(
        model=model_name,
        api_key=_api_key,
        base_url="https://openrouter.ai/api/v1"
    )

# Model names (tanpa "openrouter/" prefix — buat OpenAI SDK langsung yg base_url-nya udah OpenRouter)
# Dipake furniture_qc.py via OpenAI SDK, dan crewai LLM via get_llm() di bawah.
VISUAL_MODEL_NAME = "google/gemini-3.5-flash"

try:
    # VISUAL LLM (Spesialis gambar/PDF)
    visual_llm = get_llm(f"openrouter/{VISUAL_MODEL_NAME}")
    
    # SPESIALIS MENENGAH (Tugas umum, harga terjangkau)
    arsip_llm = get_llm("openrouter/deepseek/deepseek-v4-flash")       
    admin_llm = get_llm("openrouter/deepseek/deepseek-v4-flash")       
    lifestyle_llm = get_llm("openrouter/deepseek/deepseek-v4-flash")   
    seniman_llm = get_llm("openrouter/deepseek/deepseek-v4-flash")     
    
    # SPESIALIS BERAT/LOGIKA (Minta model paling pintar)
    intel_llm = get_llm("openrouter/deepseek/deepseek-v4-flash")       # Riset web & ekstraksi data
    mekanik_llm = get_llm("openrouter/deepseek/deepseek-v4-pro")       # Coding & Debugging
    
    print("[CONFIG] ✅ Semua LLM berhasil diinisialisasi dengan mode HEMAT TOKEN!")
except Exception as e:
    print(f"[CONFIG] ❌ Gagal inisialisasi LLM: {e}")
    raise
