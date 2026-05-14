import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

# Menggunakan OpenRouter API (sesuai config.py Anda yang lama)
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

def get_langchain_llm(model_name: str = "deepseek/deepseek-v4-flash") -> ChatOpenAI:
    # LangChain ChatOpenAI kirim model_name apa adanya ke OpenRouter,
    # JANGAN pakai prefix "openrouter/" (itu khusus CrewAI/LiteLLM).
    if model_name.startswith("openrouter/"):
        model_name = model_name.split("/", 1)[1]
    return ChatOpenAI(
        model=model_name,
        openai_api_key=OPENROUTER_API_KEY,
        openai_api_base="https://openrouter.ai/api/v1",
        max_retries=2
    )

# Kita inisialisasi LLM utama untuk percobaan ini
default_llm = get_langchain_llm()
