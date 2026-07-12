"""Unified embedding wrapper — local sentence-transformers atau cloud OpenRouter.

Switch via env `EMBEDDING_BACKEND=local|cloud` (default: local — zero behavior change).

Cloud backend pakai OpenAI-compatible /embeddings endpoint OpenRouter, dengan
diskcache supaya re-embed teks sama ga billing ulang.

Per-domain model selection:
    - "arsip" → general Indonesian docs/chat
        local:  sentence-transformers/all-MiniLM-L6-v2 (384 dim)
        cloud:  baai/bge-m3                            (1024 dim, multilingual ID kuat)
    - "code"  → source code embedding (repo_rag)
        local:  sentence-transformers/all-MiniLM-L6-v2 (384 dim)
        cloud:  mistralai/codestral-embed-2505         (1024 dim, code-tuned)

PENTING: kalau lo switch backend dari local ke cloud, dim berubah (384 → 1024).
LanceDB schema fixed dim, jadi WAJIB re-index (drop tabel + rebuild) setelah switch.
Vault source files tetep ada → re-index regenerate vector dgn model baru.

Migrasi:
    1. Set di .env: EMBEDDING_BACKEND=cloud
    2. Hapus folder vault_index/ + repo_index/ (atau jalanin script reindex)
    3. Restart bot — index auto-rebuild dgn model baru
    4. Test query
"""
import hashlib
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Union

import numpy as np

logger = logging.getLogger("bima_core.embedder")

BIMA_ROOT = Path(__file__).parent.parent
EMBED_CACHE_DIR = BIMA_ROOT / "outputs" / "embed_cache"
DEFAULT_CACHE_TTL_DAYS = 30

# Per-domain model + dim untuk LanceDB schema.
_DOMAIN_CONFIG: dict[str, dict] = {
    "arsip": {
        "local_model": "Qwen/Qwen3-Embedding-0.6B",  # multilingual; benchmark dedup ID: 38%->96% vs all-MiniLM
        "cloud_model": "baai/bge-m3",
        "local_dim": 1024,
        "cloud_dim": 1024,
    },
    "code": {
        "local_model": "all-MiniLM-L6-v2",  # sharing dgn arsip kalau backend=local
        "cloud_model": "mistralai/codestral-embed-2505",
        "local_dim": 384,
        "cloud_dim": 1024,
    },
}


class Embedder:
    """Drop-in replacement buat `SentenceTransformer` di Bima codebase.

    `encode(text)` return `np.ndarray` — kompatibel dgn existing
    `embedder.encode(...).tolist()` pattern.
    """

    def __init__(self, domain: str = "arsip"):
        self.domain = domain
        self.backend = os.environ.get("EMBEDDING_BACKEND", "local").lower()
        if self.backend not in ("local", "cloud"):
            logger.warning(f"[embedder] backend={self.backend} unknown, fallback ke local")
            self.backend = "local"

        cfg = _DOMAIN_CONFIG.get(domain, _DOMAIN_CONFIG["arsip"])
        self.model_name = cfg[f"{self.backend}_model"]
        self.dim = cfg[f"{self.backend}_dim"]

        self._local_model = None  # lazy init
        self._cache = None
        self._cache_ttl_sec = int(os.environ.get("EMBED_CACHE_TTL_DAYS", str(DEFAULT_CACHE_TTL_DAYS))) * 86400

        logger.info(
            f"[embedder] domain={domain} backend={self.backend} "
            f"model={self.model_name} dim={self.dim}"
        )

    # ---------- local backend ----------
    def _get_local(self):
        if self._local_model is None:
            from sentence_transformers import SentenceTransformer

            self._local_model = SentenceTransformer(self.model_name)
        return self._local_model

    # ---------- cloud backend ----------
    def _get_cache(self):
        if self._cache is not None:
            return self._cache
        try:
            import diskcache

            EMBED_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            self._cache = diskcache.Cache(str(EMBED_CACHE_DIR / self.domain))
        except Exception as e:
            logger.warning(f"[embedder] diskcache init fail, no cache: {e}")
            self._cache = {}
        return self._cache

    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(f"{self.model_name}|{text}".encode("utf-8")).hexdigest()

    def _encode_cloud_one(self, text: str) -> np.ndarray:
        cache = self._get_cache()
        key = self._cache_key(text)
        cached = cache.get(key) if hasattr(cache, "get") else None
        if cached is not None:
            return np.array(cached, dtype=np.float32)

        from openai import OpenAI
        import stamina

        client = OpenAI(
            api_key=os.environ.get("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
        )

        @stamina.retry(on=Exception, attempts=3, wait_initial=1, wait_max=10)
        def _call():
            return client.embeddings.create(model=self.model_name, input=text)

        resp = _call()
        vec = resp.data[0].embedding
        if hasattr(cache, "set"):
            try:
                cache.set(key, vec, expire=self._cache_ttl_sec)
            except Exception as e:
                logger.debug(f"[embedder] cache.set fail: {e}")
        else:
            cache[key] = vec
        return np.array(vec, dtype=np.float32)

    # ---------- public API ----------
    def encode(self, text: Union[str, list[str]]) -> np.ndarray:
        if isinstance(text, str):
            if self.backend == "cloud":
                return self._encode_cloud_one(text)
            return self._get_local().encode(text)

        # Batch list[str]
        if self.backend == "cloud":
            return np.stack([self._encode_cloud_one(t) for t in text])
        return self._get_local().encode(text)

    def encode_query(self, text: str) -> np.ndarray:
        """Embed sebuah query. Untuk arsip lokal (Qwen3) pakai retrieval prompt
        `query`; selain itu jalur `encode()` biasa (dokumen tetap tanpa prompt)."""
        if self.backend == "local" and self.domain == "arsip":
            return self._get_local().encode(text, prompt_name="query")
        return self.encode(text)


@lru_cache(maxsize=8)
def get_embedder(domain: str = "arsip") -> Embedder:
    """Singleton per-domain embedder. Cache ke-share di proses bot."""
    return Embedder(domain)
