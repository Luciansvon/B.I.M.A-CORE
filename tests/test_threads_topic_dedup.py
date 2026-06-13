"""Tests anti-repetisi topik fakta unik Threads (masalah 'hiu mulu').

Bug yang dicegah:
  - generate_random_interesting_fact_topic ngulang subjek yang sama karena LLM
    gak dikasih daftar topik lama, dan dedup database cuma cek judul persis
    (jadi "Fakta unik hiu" vs "Hiu nggak punya tulang" dua-duanya kesimpen).
"""
import json

import core.threads_scheduler as ts


def test_topics_related_detects_same_subject():
    # Subjek inti sama ("hiu") walau judulnya beda -> dianggap related/duplikat.
    assert ts._topics_related("Fakta unik hiu", "Kenapa hiu nggak punya tulang")
    assert ts._topics_related("Pemuaian Menara Eiffel",
                              "Tinggi Menara Eiffel berubah saat panas")


def test_topics_related_allows_different_subjects():
    assert not ts._topics_related("Asal-usul kursi bakso plastik",
                                  "Pemuaian Menara Eiffel")
    # Dua-duanya soal "ikan" tapi spesiesnya beda -> BUKAN duplikat.
    assert not ts._topics_related("Kemampuan memori visual ikan sumpit",
                                  "Ikan malaikat gua yang bisa berjalan")


def test_recent_topics_roundtrip(tmp_path, monkeypatch):
    path = tmp_path / "recent.json"
    monkeypatch.setattr(ts, "_recent_topics_path", lambda: str(path))

    ts._record_recent_topic("Fakta unik hiu")
    ts._record_recent_topic("Pemuaian Menara Eiffel")
    assert ts._load_recent_topics() == ["Fakta unik hiu", "Pemuaian Menara Eiffel"]

    # Re-record memindahkan entri ke paling baru, tanpa menambah duplikat.
    ts._record_recent_topic("Fakta unik hiu")
    assert ts._load_recent_topics() == ["Pemuaian Menara Eiffel", "Fakta unik hiu"]


def test_recent_topics_capped(tmp_path, monkeypatch):
    path = tmp_path / "recent.json"
    monkeypatch.setattr(ts, "_recent_topics_path", lambda: str(path))
    monkeypatch.setattr(ts, "RECENT_TOPICS_MAX", 5)

    for i in range(10):
        ts._record_recent_topic(f"topik nomor {i}")

    saved = ts._load_recent_topics()
    assert len(saved) == 5
    assert saved[-1] == "topik nomor 9"
    assert "topik nomor 0" not in saved


def test_save_scientific_fact_rejects_near_dup(tmp_path):
    facts_path = tmp_path / "scientific_facts.json"
    facts_path.write_text(
        json.dumps([{"topic": "Fakta unik hiu", "context": "hiu udah ada sebelum pohon"}],
                   ensure_ascii=False),
        encoding="utf-8",
    )

    # Subjek sama (hiu) walau judul beda -> ditolak, file tetap 1 entri.
    ts.save_scientific_fact("Kenapa hiu gak bisa berhenti berenang", "blah", str(facts_path))
    assert len(json.loads(facts_path.read_text(encoding="utf-8"))) == 1

    # Subjek beda -> diterima, jadi 2 entri.
    ts.save_scientific_fact("Asal-usul kursi bakso plastik", "blah", str(facts_path))
    assert len(json.loads(facts_path.read_text(encoding="utf-8"))) == 2
