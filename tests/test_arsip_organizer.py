import hashlib
import json
from pathlib import Path

import pytest

from teams import t3_arsip


@pytest.fixture
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(t3_arsip, "OBSIDIAN_PATH", str(tmp_path))
    monkeypatch.setattr(t3_arsip, "index_vault", lambda: None)
    return tmp_path


def save(**payload: object) -> str:
    return t3_arsip.VaultSaveTool()._run(json.dumps(payload, ensure_ascii=False))


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "", "content": "isi"},
        {"title": "judul", "content": "  "},
        {"title": 7, "content": "isi"},
        {"title": "judul", "content": ["isi"]},
    ],
)
def test_empty_or_non_string_title_content_rejected(
    vault: Path, payload: dict[str, object]
) -> None:
    assert t3_arsip.VaultSaveTool()._run(json.dumps(payload)).startswith("FAILED|")
    assert list(vault.rglob("*.md")) == []


def test_invalid_category_falls_back_to_safe_inbox_with_metadata(vault: Path) -> None:
    content = "  Kayu   jati\nkuat  "
    result = save(
        title="Kursi / Jati",
        content=content,
        category="../../escape",
        tags=["Kayu Jati", "", "KAYU JATI", "Furniture"],
        source='Browser: "contoh"',
    )

    note = vault / "Inbox" / "kursi-jati.md"
    digest = hashlib.sha256("Kayu jati kuat".encode()).hexdigest()
    assert result.startswith("SUCCESS|")
    assert note.exists()
    assert note.resolve().is_relative_to(vault.resolve())
    text = note.read_text(encoding="utf-8")
    assert 'category: "Inbox"' in text
    assert 'tags: ["kayu-jati", "furniture"]' in text
    assert 'source: "Browser: \\"contoh\\""' in text
    assert f'content_hash: "{digest}"' in text
    assert f"<!-- anisa:content-hash:{digest} -->" in text
    assert "# Kursi / Jati" in text


@pytest.mark.parametrize("category", [["Riset"], {"name": "Riset"}, 7, None])
def test_non_string_category_saves_safely_to_inbox(
    vault: Path, category: object
) -> None:
    result = save(title="Kategori Aman", content="isi kategori", category=category)

    assert result.startswith("SUCCESS|")
    assert (vault / "Inbox" / "kategori-aman.md").exists()


def test_category_string_is_normalized_with_strip_and_title(vault: Path) -> None:
    result = save(title="Kategori Riset", content="isi riset", category="  riset ")

    assert result.startswith("SUCCESS|")
    assert (vault / "Riset" / "kategori-riset.md").exists()


def test_same_content_different_title_and_category_is_skipped_globally(vault: Path) -> None:
    assert save(title="Catatan Satu", content="isi   sama", category="Riset").startswith(
        "SUCCESS|"
    )

    result = save(title="Catatan Lain", content="isi sama", category="Personal")

    assert result.startswith("SKIPPED|")
    assert len(list(vault.rglob("*.md"))) == 1


def test_same_title_different_content_updates_existing_note(
    vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert save(title="Kursi Rotan", content="versi lama", category="Riset").startswith(
        "SUCCESS|"
    )
    note = vault / "Riset" / "kursi-rotan.md"
    backups: list[Path] = []

    def fake_backup(path: Path) -> Path:
        backups.append(path)
        return path.with_suffix(".backup")

    monkeypatch.setattr(t3_arsip, "backup_file", fake_backup)
    result = save(title="Kursi Rotan", content="versi baru", category="Personal")

    assert result.startswith("SUCCESS|")
    assert backups == [note]
    assert len(list(vault.rglob("*.md"))) == 1
    text = note.read_text(encoding="utf-8")
    assert "versi lama" in text
    assert "## Update " in text
    assert "versi baru" in text


def test_tags_ignore_empty_are_unique_and_limited_to_eight(vault: Path) -> None:
    tags = ["", "Satu", "SATU", "Dua", "Tiga", "Empat", "Lima", "Enam", "Tujuh", "Delapan", "Sembilan"]

    save(title="Tag Test", content="isi tag unik", tags=tags)

    text = (vault / "Inbox" / "tag-test.md").read_text(encoding="utf-8")
    assert 'tags: ["satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan"]' in text


def test_atomic_write_replace_failure_keeps_old_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    note = tmp_path / "note.md"
    note.write_text("old", encoding="utf-8")

    def fail_replace(_source: Path, _target: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(t3_arsip.os, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        t3_arsip._atomic_write(note, "new")

    assert note.read_text(encoding="utf-8") == "old"
    assert not note.with_suffix(".md.tmp").exists()


@pytest.mark.parametrize("raw", ["not json", "[]", '"text"', "null"])
def test_invalid_json_or_non_dict_returns_failed(vault: Path, raw: str) -> None:
    assert t3_arsip.VaultSaveTool()._run(raw).startswith("FAILED|")
    assert list(vault.rglob("*.md")) == []


def test_reindex_failure_is_nonfatal_after_successful_save(
    vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_index() -> None:
        raise RuntimeError("index unavailable")

    monkeypatch.setattr(t3_arsip, "index_vault", fail_index)
    result = save(title="Tetap Tersimpan", content="isi aman")

    assert result.startswith("SUCCESS|")
    assert (vault / "Inbox" / "tetap-tersimpan.md").exists()


def test_backup_failure_blocks_update_and_retains_old_note(
    vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    save(title="Tidak Boleh Hilang", content="isi lama", category="Proyek")
    note = vault / "Proyek" / "tidak-boleh-hilang.md"
    before = note.read_text(encoding="utf-8")
    monkeypatch.setattr(t3_arsip, "backup_file", lambda _path: None)

    result = save(title="Tidak Boleh Hilang", content="isi baru", category="Inbox")

    assert result.startswith("FAILED|")
    assert note.read_text(encoding="utf-8") == before
    assert len(list(vault.rglob("*.md"))) == 1


def test_update_adds_hash_fields_to_existing_frontmatter_without_moving(
    vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    note = vault / "Personal" / "catatan-lama.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        '---\ntitle: "Catatan Lama"\ncategory: "Personal"\n---\n\nisi awal\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(t3_arsip, "backup_file", lambda path: path.with_suffix(".bak"))

    result = save(title="Catatan Lama", content="isi pembaruan", category="Riset")

    assert result.startswith("SUCCESS|")
    assert not (vault / "Riset" / "catatan-lama.md").exists()
    text = note.read_text(encoding="utf-8")
    assert "updated: " in text.split("---", 2)[1]
    assert "content_hash: " in text.split("---", 2)[1]
