from pathlib import Path

import pytest

from core.embedder import Embedder
from teams import t3_arsip


def test_contextual_embedding_text() -> None:
    text = t3_arsip._document_embedding_text("Preferensi.md", "Musik", "Suka jazz")
    assert text == "Document: Preferensi.md\nSection: Musik\nContent: Suka jazz"


@pytest.mark.parametrize(
    "scores, expected",
    [
        ([-4.0, -5.0], False),  # jelas tidak relevan
        ([0.3, -5.0], True),    # sigmoid(0.3)=0.574 >= 0.52 -> lolos
        ([0.0, -5.0], False),   # sigmoid(0.0)=0.500 < 0.52 -> ditolak (batas true-negative)
        ([], False),
    ],
)
def test_relevance_gate(scores: list[float], expected: bool) -> None:
    assert t3_arsip._passes_relevance_gate(scores) is expected


def test_neighbor_ids_stay_in_same_file() -> None:
    assert t3_arsip._neighbor_chunk_ids(0) == [0, 1]
    assert t3_arsip._neighbor_chunk_ids(3) == [2, 3, 4]


def test_local_arsip_query_uses_qwen_query_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    embedder = Embedder("arsip")
    calls: list[dict] = []

    class FakeModel:
        def encode(self, text: str, **kwargs: object) -> list[float]:
            calls.append({"text": text, **kwargs})
            return [0.0, 1.0]

    monkeypatch.setattr(embedder, "_get_local", lambda: FakeModel())
    embedder.backend = "local"

    embedder.encode_query("preferensi musik")

    assert calls == [{"text": "preferensi musik", "prompt_name": "query"}]


def test_cloud_query_falls_back_to_plain_encode(monkeypatch: pytest.MonkeyPatch) -> None:
    embedder = Embedder("arsip")
    embedder.backend = "cloud"
    seen: list[str] = []
    monkeypatch.setattr(embedder, "encode", lambda text: seen.append(text) or [0.1])

    embedder.encode_query("halo")

    assert seen == ["halo"]


def test_bm25_cache_loads_once_and_invalidates(monkeypatch: pytest.MonkeyPatch) -> None:
    t3_arsip._set_bm25_index(None)
    calls = {"n": 0}
    first = object()

    class FakeBM25:
        @staticmethod
        def load(path: object) -> object:
            calls["n"] += 1
            return first

    monkeypatch.setattr("core.bm25_index.BM25Index", FakeBM25)
    real_exists = Path.exists
    monkeypatch.setattr(
        Path,
        "exists",
        lambda self: True if self.name == "bm25.pkl" else real_exists(self),
    )

    try:
        assert t3_arsip._get_bm25_index() is first
        assert t3_arsip._get_bm25_index() is first
        assert calls["n"] == 1

        second = object()
        t3_arsip._set_bm25_index(second)
        assert t3_arsip._get_bm25_index() is second
    finally:
        t3_arsip._set_bm25_index(None)
