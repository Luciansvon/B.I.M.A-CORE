from pathlib import Path
from types import SimpleNamespace
import sys

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


def test_arsip_cloud_backend_can_override_other_domains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EMBEDDING_BACKEND", "local")
    monkeypatch.setenv("EMBEDDING_BACKEND_ARSIP", "cloud")
    monkeypatch.setenv("EMBEDDING_MODEL_ARSIP", "qwen/qwen3-embedding-8b")
    monkeypatch.setenv("EMBEDDING_DIM_ARSIP", "1024")

    embedder = Embedder("arsip")

    assert embedder.backend == "cloud"
    assert embedder.model_name == "qwen/qwen3-embedding-8b"
    assert embedder.dim == 1024


def test_cloud_query_sends_dimension_and_query_input_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []

    class FakeEmbeddings:
        def create(self, **kwargs: object) -> object:
            calls.append(dict(kwargs))
            return SimpleNamespace(
                data=[SimpleNamespace(embedding=[0.1] * 1024)]
            )

    class FakeOpenAI:
        def __init__(self, **kwargs: object) -> None:
            self.embeddings = FakeEmbeddings()

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    embedder = Embedder("arsip")
    embedder.backend = "cloud"
    embedder.model_name = "qwen/qwen3-embedding-8b"
    embedder.dim = 1024
    embedder._cache = {}

    vector = embedder.encode_query("preferensi musik")

    assert vector.shape == (1024,)
    assert calls == [
        {
            "model": "qwen/qwen3-embedding-8b",
            "input": "preferensi musik",
            "dimensions": 1024,
            "extra_body": {"input_type": "query"},
        }
    ]


def test_cloud_document_batch_uses_one_api_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []

    class FakeEmbeddings:
        def create(self, **kwargs: object) -> object:
            calls.append(dict(kwargs))
            inputs = kwargs["input"]
            return SimpleNamespace(
                data=[
                    SimpleNamespace(embedding=[float(index)] * 1024)
                    for index, _ in enumerate(inputs)
                ]
            )

    class FakeOpenAI:
        def __init__(self, **kwargs: object) -> None:
            self.embeddings = FakeEmbeddings()

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    embedder = Embedder("arsip")
    embedder.backend = "cloud"
    embedder.model_name = "qwen/qwen3-embedding-8b"
    embedder.dim = 1024
    embedder._cache = {}

    vectors = embedder.encode(["dokumen satu", "dokumen dua"])

    assert vectors.shape == (2, 1024)
    assert vectors[1, 0] == 1.0
    assert calls == [
        {
            "model": "qwen/qwen3-embedding-8b",
            "input": ["dokumen satu", "dokumen dua"],
            "dimensions": 1024,
            "extra_body": {"input_type": "document"},
        }
    ]


def test_pending_vault_docs_are_embedded_in_one_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    class FakeEmbedder:
        def encode(self, texts: list[str]) -> list[list[float]]:
            calls.append(texts)
            return [[float(index), 1.0] for index, _ in enumerate(texts)]

    monkeypatch.setattr(t3_arsip, "embedder", FakeEmbedder())
    pending = [
        {"filename": "a.md", "embedding_text": "dokumen a"},
        {"filename": "b.md", "embedding_text": "dokumen b"},
    ]

    docs = t3_arsip._embed_pending_docs(pending)

    assert calls == [["dokumen a", "dokumen b"]]
    assert docs == [
        {"filename": "a.md", "vector": [0.0, 1.0]},
        {"filename": "b.md", "vector": [1.0, 1.0]},
    ]


def test_disabled_reranker_does_not_construct_local_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constructed: list[tuple] = []

    class FakeCrossEncoder:
        def __init__(self, *args: object, **kwargs: object) -> None:
            constructed.append((args, kwargs))

    monkeypatch.setenv("RERANKER_ENABLED", "false")
    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False)),
    )
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(CrossEncoder=FakeCrossEncoder),
    )
    monkeypatch.setattr(t3_arsip, "_reranker", None)

    assert t3_arsip._get_reranker() is None
    assert constructed == []


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
