"""Unified embedding wrapper — local sentence-transformers atau cloud OpenRouter.

Switch via env `EMBEDDING_BACKEND=local|cloud` (default: local — zero behavior change).

Cloud backend pakai OpenAI-compatible /embeddings endpoint OpenRouter, dengan
diskcache supaya re-embed teks sama ga billing ulang.

Per-domain model selection:
    - "arsip" → general Indonesian docs/chat
        local:  Qwen/Qwen3-Embedding-0.6B              (1024 dim)
        cloud:  model OpenRouter yang dikonfigurasi    (1024 dim)
    - "code"  → source code embedding (repo_rag)
        local:  sentence-transformers/all-MiniLM-L6-v2 (384 dim)
        cloud:  mistralai/codestral-embed-2505         (1024 dim, code-tuned)

PENTING: kalau lo switch backend dari local ke cloud, dim berubah (384 → 1024).
LanceDB schema fixed dim, jadi WAJIB re-index (drop tabel + rebuild) setelah switch.
Vault source files tetep ada → re-index regenerate vector dgn model baru.

Migrasi:
    1. Set EMBEDDING_BACKEND_ARSIP, EMBEDDING_MODEL_ARSIP, dan dimensinya.
    2. Jalankan full rebuild index terkait.
    3. Restart bot dan test query.
"""
import hashlib
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Union
from dotenv import load_dotenv

load_dotenv()

import numpy as np

logger = logging.getLogger("bima_core.embedder")

BIMA_ROOT = Path(__file__).parent.parent
EMBED_CACHE_DIR = BIMA_ROOT / "outputs" / "embed_cache"
DEFAULT_CACHE_TTL_DAYS = 30

# Per-domain model + dim untuk LanceDB schema.
_DOMAIN_CONFIG: dict[str, dict] = {
    "arsip": {
        "local_model": "Qwen/Qwen3-Embedding-0.6B",  # multilingual; benchmark dedup ID: 38%->96% vs all-MiniLM
        "cloud_model": "openrouter/qwen/qwen3-embedding-8b",
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
        domain_key = domain.upper()
        self.backend = os.environ.get(
            f"EMBEDDING_BACKEND_{domain_key}",
            os.environ.get("EMBEDDING_BACKEND", "local"),
        ).lower()
        if self.backend not in ("local", "cloud"):
            logger.warning(f"[embedder] backend={self.backend} unknown, fallback ke local")
            self.backend = "local"

        cfg = _DOMAIN_CONFIG.get(domain, _DOMAIN_CONFIG["arsip"])
        self.model_name = os.environ.get(
            f"EMBEDDING_MODEL_{domain_key}",
            cfg[f"{self.backend}_model"],
        )
        self.dim = int(
            os.environ.get(
                f"EMBEDDING_DIM_{domain_key}",
                str(cfg[f"{self.backend}_dim"]),
            )
        )

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

    def _cache_key(self, text: str, input_type: str) -> str:
        payload = f"{self.model_name}|{self.dim}|{input_type}|{text}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _get_client(self):
        from openai import OpenAI

        api_key = (
            os.environ.get("NINEROUTER_API_KEY")
            or os.environ.get("ROUTER_API_KEY")
            or os.environ.get("OPENROUTER_API_KEY")
        )
        base_url = (
            os.environ.get("NINEROUTER_BASE_URL")
            or os.environ.get("ROUTER_BASE_URL")
            or os.environ.get("OPENROUTER_BASE_URL")
            or "http://127.0.0.1:20128/v1"
        )
        return OpenAI(api_key=api_key, base_url=base_url)

    def _encode_cloud_one(
        self,
        text: str,
        input_type: str = "document",
    ) -> np.ndarray:
        cache = self._get_cache()
        key = self._cache_key(text, input_type)
        cached = cache.get(key) if hasattr(cache, "get") else None
        if cached is not None:
            return np.array(cached, dtype=np.float32)

        import stamina

        client = self._get_client()

        @stamina.retry(on=Exception, attempts=3, wait_initial=1, wait_max=10)
        def _call():
            return client.embeddings.create(
                model=self.model_name,
                input=text,
                dimensions=self.dim,
                extra_body={"input_type": input_type},
            )

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

    def _encode_cloud_batch(
        self,
        texts: list[str],
        input_type: str = "document",
    ) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dim), dtype=np.float32)

        cache = self._get_cache()
        vectors: list[list[float] | None] = [None] * len(texts)
        missing: list[tuple[int, str, str]] = []
        for index, text in enumerate(texts):
            key = self._cache_key(text, input_type)
            cached = cache.get(key) if hasattr(cache, "get") else None
            if cached is None:
                missing.append((index, text, key))
            else:
                vectors[index] = cached

        if missing:
            import stamina

            client = self._get_client()
            batch_size = max(1, int(os.environ.get("EMBED_BATCH_SIZE", "64")))

            for start in range(0, len(missing), batch_size):
                batch = missing[start:start + batch_size]

                @stamina.retry(on=Exception, attempts=3, wait_initial=1, wait_max=10)
                def _call():
                    return client.embeddings.create(
                        model=self.model_name,
                        input=[text for _, text, _ in batch],
                        dimensions=self.dim,
                        extra_body={"input_type": input_type},
                    )

                response = _call()
                for (index, _, key), item in zip(batch, response.data):
                    vector = item.embedding
                    vectors[index] = vector
                    if hasattr(cache, "set"):
                        try:
                            cache.set(key, vector, expire=self._cache_ttl_sec)
                        except Exception as e:
                            logger.debug(f"[embedder] cache.set fail: {e}")
                    else:
                        cache[key] = vector

        return np.asarray(vectors, dtype=np.float32)

    # ---------- public API ----------
    def encode(self, text: Union[str, list[str]]) -> np.ndarray:
        if isinstance(text, str):
            if self.backend == "cloud":
                return self._encode_cloud_one(text, "document")
            return self._get_local().encode(text)

        # Batch list[str]
        if self.backend == "cloud":
            return self._encode_cloud_batch(text, "document")
        return self._get_local().encode(text)

    def encode_query(self, text: str) -> np.ndarray:
        """Embed sebuah query. Untuk arsip lokal (Qwen3) pakai retrieval prompt
        `query`; selain itu jalur `encode()` biasa (dokumen tetap tanpa prompt)."""
        if self.backend == "local" and self.domain == "arsip":
            return self._get_local().encode(text, prompt_name="query")
        if self.backend == "cloud":
            return self._encode_cloud_one(text, "query")
        return self.encode(text)


@lru_cache(maxsize=8)
def get_embedder(domain: str = "arsip") -> Embedder:
    """Singleton per-domain embedder. Cache ke-share di proses bot."""
    return Embedder(domain)
