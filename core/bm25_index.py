"""BM25 keyword search untuk hybrid RAG.

Pasangkan dgn vector search di LanceDB:
    - vector top-N (recall semantic)
    - BM25 top-M  (recall keyword — nyabet nama function, ticker, jargon teknis)
    - merge → rerank cross-encoder existing → top-K final.

Pemakaian:
    from core.bm25_index import build_from_corpus, BM25Index

    items = [{"id": "doc1", "content": "..."} , ...]
    idx = build_from_corpus(items)
    hits = idx.search("MCPClientManager startup", top_k=20)
    # hits = [("doc1", 4.32), ("doc5", 2.11), ...]

Helper untuk hybrid merge ada di `hybrid_merge()`.
"""
import logging
import pickle
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

logger = logging.getLogger("bima_core.bm25")

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    """Tokenize sederhana: lowercase + word split.

    Indonesian stemmer (mis. Sastrawi) bisa ditambah belakangan — untuk
    keyword retrieval scoring BM25, lowercase + word split udah cukup
    karena scoring berbasis term frequency.
    """
    return _WORD_RE.findall(text.lower())


class BM25Index:
    """Wrapper BM25Okapi dgn doc_id ↔ score mapping + persist."""

    def __init__(self, doc_ids: list[str], tokenized_docs: list[list[str]]):
        if len(doc_ids) != len(tokenized_docs):
            raise ValueError("doc_ids dan tokenized_docs panjangnya beda")
        self.doc_ids = doc_ids
        self.bm25 = BM25Okapi(tokenized_docs) if tokenized_docs else None

    def search(self, query: str, top_k: int = 20) -> list[tuple[str, float]]:
        if self.bm25 is None or not self.doc_ids:
            return []
        tokens = _tokenize(query)
        if not tokens:
            return []
        scores = self.bm25.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
        return [(self.doc_ids[i], float(score)) for i, score in ranked if score > 0]

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            pickle.dump({"doc_ids": self.doc_ids, "bm25": self.bm25}, f)
        logger.info(f"[bm25] saved index → {path} ({len(self.doc_ids)} docs)")

    @classmethod
    def load(cls, path: Path) -> "BM25Index":
        path = Path(path)
        with path.open("rb") as f:
            data = pickle.load(f)
        obj = cls.__new__(cls)
        obj.doc_ids = data["doc_ids"]
        obj.bm25 = data["bm25"]
        return obj


def build_from_corpus(items: list[dict], id_field: str = "id", text_field: str = "content") -> BM25Index:
    """Build dari list of dict (mis. row LanceDB).

    items: [{"id": "...", "content": "..."}, ...]
    """
    doc_ids = [item[id_field] for item in items]
    tokenized = [_tokenize(item[text_field]) for item in items]
    return BM25Index(doc_ids, tokenized)


def hybrid_merge(
    vector_hits: list[tuple[str, float]],
    bm25_hits: list[tuple[str, float]],
    *,
    w_vector: float = 0.6,
    w_bm25: float = 0.4,
    top_k: int = 20,
) -> list[tuple[str, float]]:
    """Weighted merge vector + BM25 hits (RRF-lite, normalized).

    Normalize per-list jadi 0-1, weighted sum, sort desc, return top_k.
    """
    def _normalize(hits: list[tuple[str, float]]) -> dict[str, float]:
        if not hits:
            return {}
        max_s = max(s for _, s in hits)
        if max_s <= 0:
            return {doc_id: 0.0 for doc_id, _ in hits}
        return {doc_id: s / max_s for doc_id, s in hits}

    v_norm = _normalize(vector_hits)
    b_norm = _normalize(bm25_hits)
    all_ids = set(v_norm) | set(b_norm)
    merged = {
        doc_id: w_vector * v_norm.get(doc_id, 0.0) + w_bm25 * b_norm.get(doc_id, 0.0)
        for doc_id in all_ids
    }
    return sorted(merged.items(), key=lambda x: x[1], reverse=True)[:top_k]
