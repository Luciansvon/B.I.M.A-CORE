"""Unit tests untuk core/bm25_index.py — BM25 keyword search + hybrid merge.

Jalankan: pytest tests/test_hybrid_rag.py -v
(atau: python -m pytest tests/test_hybrid_rag.py -v)

Tidak butuh API call — semua test offline pakai sample data.
"""
import pytest
from pathlib import Path


# ============================================================
# 1. BM25Index — Build, Search, Save/Load Roundtrip
# ============================================================

from core.bm25_index import BM25Index, build_from_corpus, hybrid_merge


class TestBM25IndexBasic:
    """Test BM25Index constructor dan search dasar."""

    def _make_index(self):
        """Helper: build index sederhana 3 dokumen."""
        doc_ids = ["doc1", "doc2", "doc3"]
        tokenized_docs = [
            ["harga", "saham", "bbca", "naik", "hari", "ini"],
            ["cuaca", "jakarta", "cerah", "hari", "ini"],
            ["saham", "bbri", "turun", "drastis", "saham", "merah"],
        ]
        return BM25Index(doc_ids, tokenized_docs)

    def test_search_returns_relevant_docs(self):
        idx = self._make_index()
        hits = idx.search("saham bbca")
        assert len(hits) > 0
        # doc1 punya "saham" + "bbca" → harus paling relevan
        assert hits[0][0] == "doc1"

    def test_search_scores_are_positive(self):
        idx = self._make_index()
        hits = idx.search("saham")
        for doc_id, score in hits:
            assert score > 0

    def test_search_top_k_limits_results(self):
        idx = self._make_index()
        hits = idx.search("saham", top_k=1)
        assert len(hits) <= 1

    def test_search_no_match_returns_empty(self):
        idx = self._make_index()
        hits = idx.search("blockchain cryptocurrency")
        assert hits == []

    def test_search_empty_query_returns_empty(self):
        idx = self._make_index()
        hits = idx.search("")
        assert hits == []

    def test_search_whitespace_query_returns_empty(self):
        idx = self._make_index()
        hits = idx.search("   ")
        assert hits == []

    def test_doc_ids_length_mismatch_raises(self):
        with pytest.raises(ValueError, match="panjangnya beda"):
            BM25Index(["doc1", "doc2"], [["harga"]])


class TestBM25IndexEmpty:
    """Edge case: empty corpus."""

    def test_empty_corpus_search_returns_empty(self):
        idx = BM25Index([], [])
        hits = idx.search("apa saja")
        assert hits == []

    def test_single_doc_corpus_idf_zero(self):
        """BM25Okapi IDF = 0 kalau term ada di semua doc. Dengan 1 doc, semua term IDF=0.
        Ini expected behavior dari rank_bm25 — bukan bug, tapi quirk."""
        idx = BM25Index(["only"], [["satu", "dokumen", "saja"]])
        hits = idx.search("dokumen")
        # BM25 single-doc: IDF=0 → semua score 0 → difilter `score > 0`
        assert hits == []

    def test_three_doc_corpus_finds_relevant(self):
        """BM25Okapi butuh 3+ docs agar IDF > 0 untuk term unik."""
        idx = BM25Index(
            ["relevant", "noise1", "noise2"],
            [
                ["satu", "dokumen", "saja"],
                ["lain", "cerita", "ini"],
                ["beda", "topik", "lagi"],
            ],
        )
        hits = idx.search("dokumen")
        assert len(hits) == 1
        assert hits[0][0] == "relevant"
        assert hits[0][1] > 0


class TestBM25IndexSaveLoad:
    """Test save/load roundtrip — index yang di-load harus ngasih hasil sama."""

    def test_save_load_roundtrip(self, tmp_path):
        doc_ids = ["a", "b", "c"]
        tokenized = [
            ["python", "asyncio", "coroutine"],
            ["javascript", "react", "component"],
            ["python", "flask", "api", "server"],
        ]
        original = BM25Index(doc_ids, tokenized)
        original_hits = original.search("python asyncio")

        save_path = tmp_path / "bm25_test.pkl"
        original.save(save_path)

        assert save_path.exists()

        loaded = BM25Index.load(save_path)
        loaded_hits = loaded.search("python asyncio")

        # Hasil harus identik
        assert len(loaded_hits) == len(original_hits)
        for (orig_id, orig_score), (load_id, load_score) in zip(original_hits, loaded_hits):
            assert orig_id == load_id
            assert orig_score == pytest.approx(load_score)

    def test_save_creates_parent_dirs(self, tmp_path):
        idx = BM25Index(["x"], [["test"]])
        deep_path = tmp_path / "sub" / "dir" / "index.pkl"
        idx.save(deep_path)
        assert deep_path.exists()

    def test_load_empty_index_roundtrip(self, tmp_path):
        idx = BM25Index([], [])
        save_path = tmp_path / "empty.pkl"
        idx.save(save_path)

        loaded = BM25Index.load(save_path)
        assert loaded.search("anything") == []


# ============================================================
# 2. build_from_corpus — Factory Function
# ============================================================

class TestBuildFromCorpus:
    def test_basic_build(self):
        items = [
            {"id": "note1", "content": "Harga saham BBCA naik 2% hari ini"},
            {"id": "note2", "content": "Cuaca Jakarta cerah pagi ini"},
            {"id": "note3", "content": "Review kode Python async handler"},
        ]
        idx = build_from_corpus(items)
        hits = idx.search("saham BBCA")
        assert len(hits) > 0
        assert hits[0][0] == "note1"

    def test_custom_field_names(self):
        items = [
            {"doc_id": "x1", "text": "motor listrik gesits harga murah"},
            {"doc_id": "x2", "text": "mobil listrik wuling bev sedan"},
            {"doc_id": "x3", "text": "sepeda pancal klasik retro"},
        ]
        idx = build_from_corpus(items, id_field="doc_id", text_field="text")
        hits = idx.search("motor gesits")
        assert len(hits) > 0
        assert hits[0][0] == "x1"

    def test_empty_corpus(self):
        idx = build_from_corpus([])
        assert idx.search("test") == []

    def test_case_insensitive_search(self):
        """BM25 tokenizer lowercase — 'BBCA' dan 'bbca' harus match identik.
        BM25Okapi butuh 3+ docs agar IDF > 0."""
        items = [
            {"id": "d1", "content": "Harga BBCA naik tajam"},
            {"id": "d2", "content": "Cuaca cerah hari ini"},
            {"id": "d3", "content": "Berita politik terkini"},
        ]
        idx = build_from_corpus(items)
        hits_lower = idx.search("bbca")
        hits_upper = idx.search("BBCA")
        # Keduanya harus return d1 dengan score identik
        assert len(hits_lower) == len(hits_upper) == 1
        assert hits_lower[0][0] == hits_upper[0][0] == "d1"
        assert hits_lower[0][1] == pytest.approx(hits_upper[0][1])


# ============================================================
# 3. hybrid_merge — Weighted Merge Vector + BM25
# ============================================================

class TestHybridMerge:
    def test_basic_merge(self):
        vector_hits = [("doc1", 0.9), ("doc2", 0.5), ("doc3", 0.3)]
        bm25_hits = [("doc2", 4.0), ("doc4", 3.0), ("doc1", 1.0)]

        merged = hybrid_merge(vector_hits, bm25_hits)
        ids = [doc_id for doc_id, _ in merged]

        # Semua doc harus ada di hasil
        assert set(ids) == {"doc1", "doc2", "doc3", "doc4"}

    def test_scores_sorted_descending(self):
        vector_hits = [("a", 1.0), ("b", 0.5)]
        bm25_hits = [("b", 2.0), ("c", 1.0)]

        merged = hybrid_merge(vector_hits, bm25_hits)
        scores = [score for _, score in merged]
        assert scores == sorted(scores, reverse=True)

    def test_top_k_limits(self):
        vector_hits = [(f"d{i}", float(i)) for i in range(10)]
        bm25_hits = [(f"d{i}", float(i)) for i in range(10)]

        merged = hybrid_merge(vector_hits, bm25_hits, top_k=3)
        assert len(merged) == 3

    def test_empty_vector_hits(self):
        """Hanya BM25 hits — harus tetap return hasil."""
        bm25_hits = [("doc1", 3.0), ("doc2", 1.0)]
        merged = hybrid_merge([], bm25_hits)
        assert len(merged) == 2
        # doc1 harus paling tinggi (BM25 score tertinggi)
        assert merged[0][0] == "doc1"

    def test_empty_bm25_hits(self):
        """Hanya vector hits — harus tetap return hasil."""
        vector_hits = [("doc1", 0.9), ("doc2", 0.3)]
        merged = hybrid_merge(vector_hits, [])
        assert len(merged) == 2
        assert merged[0][0] == "doc1"

    def test_both_empty(self):
        merged = hybrid_merge([], [])
        assert merged == []

    def test_weight_influence(self):
        """Kalau w_vector=1.0 dan w_bm25=0.0, hasil harus murni vector ranking."""
        vector_hits = [("a", 1.0), ("b", 0.5)]
        bm25_hits = [("b", 10.0), ("a", 0.1)]

        merged = hybrid_merge(vector_hits, bm25_hits, w_vector=1.0, w_bm25=0.0)
        assert merged[0][0] == "a"  # vector top-1 harus tetap top-1

    def test_disjoint_sets(self):
        """Vector dan BM25 gak ada overlap — semua doc tetap masuk."""
        vector_hits = [("v1", 1.0), ("v2", 0.5)]
        bm25_hits = [("b1", 3.0), ("b2", 1.0)]

        merged = hybrid_merge(vector_hits, bm25_hits)
        ids = {doc_id for doc_id, _ in merged}
        assert ids == {"v1", "v2", "b1", "b2"}

    def test_normalized_scores_bounded(self):
        """Merged scores harus <= w_vector + w_bm25 (max 1.0 default)."""
        vector_hits = [("x", 5.0)]
        bm25_hits = [("x", 10.0)]

        merged = hybrid_merge(vector_hits, bm25_hits, w_vector=0.6, w_bm25=0.4)
        assert len(merged) == 1
        _, score = merged[0]
        # Max possible = 0.6 * 1.0 + 0.4 * 1.0 = 1.0
        assert score == pytest.approx(1.0)

    def test_zero_scores_handled(self):
        """BM25 bisa return score 0 — gak boleh crash."""
        vector_hits = [("a", 0.0), ("b", 0.0)]
        bm25_hits = [("a", 0.0)]

        merged = hybrid_merge(vector_hits, bm25_hits)
        # Semua score 0 → semuanya di-filter atau scored 0
        for _, score in merged:
            assert score == pytest.approx(0.0)
