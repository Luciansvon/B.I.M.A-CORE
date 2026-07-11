from pathlib import Path
from teams.t4_admin import styles as admin_styles
from teams.t4_admin import STYLES, resolve_style, detect_style, detect_format


def test_styles_has_expected_four_presets():
    assert set(STYLES.keys()) == {"formal", "semi_formal", "informal", "akademik"}
    for name, cfg in STYLES.items():
        assert isinstance(cfg["title_rgb"], tuple) and len(cfg["title_rgb"]) == 3
        assert "tone" in cfg and "label" in cfg


def test_resolve_style_known_and_unknown():
    assert resolve_style({"style": "informal"})["label"] == "INFORMAL"
    # nama gak dikenal -> fallback ke default, bukan KeyError
    assert resolve_style({"style": "gak-ada-gini"})["label"] == STYLES[admin_styles.DEFAULT_STYLE_NAME]["label"]
    # field 'style' absen -> default
    assert resolve_style({})["label"] == STYLES[admin_styles.DEFAULT_STYLE_NAME]["label"]


def test_detect_style_keywords():
    assert detect_style("tolong bikinin skripsi bab 1") == "akademik"
    assert detect_style("bikinin tutorial cara install python") == "semi_formal"
    assert detect_style("bikinin caption blog santai") == "informal"
    assert detect_style("bikinin surat kontrak kerja resmi") == "formal"
    assert detect_style("random text tanpa kata kunci apapun") == admin_styles.DEFAULT_STYLE_NAME


def test_detect_format_keywords():
    assert detect_format("bikin rekap excel") == "excel"
    assert detect_format("bikin dokumen word") == "word"
    assert detect_format("bikin laporan") == "pdf"  # default


def test_styles_loader_falls_back_on_missing_file(monkeypatch, tmp_path):
    monkeypatch.setattr(admin_styles, "_STYLES_PATH", tmp_path / "does_not_exist.json")
    result = admin_styles._load_styles()
    assert result == admin_styles._FALLBACK_STYLES


def test_styles_loader_falls_back_on_corrupt_json(monkeypatch, tmp_path):
    bad_file = tmp_path / "corrupt.json"
    bad_file.write_text("{ ini bukan json valid", encoding="utf-8")
    monkeypatch.setattr(admin_styles, "_STYLES_PATH", bad_file)
    result = admin_styles._load_styles()
    assert result == admin_styles._FALLBACK_STYLES


def test_document_styles_json_exists_beside_module():
    json_path = Path(admin_styles.__file__).parent / "document_styles.json"
    assert json_path.exists()
