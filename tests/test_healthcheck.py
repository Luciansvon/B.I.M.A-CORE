"""Regression tests for the CLI healthcheck."""

import importlib


def test_healthcheck_uses_project_root(capsys):
    module = importlib.import_module("scripts.healthcheck")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert (module.BASE_DIR / "main.py").is_file()
    assert (module.BASE_DIR / "core").is_dir()
    assert (module.BASE_DIR / "teams").is_dir()


def test_existing_indexes_are_ready(tmp_path):
    module = importlib.import_module("scripts.healthcheck")

    for name in ("search_index", "repo_index", "vault_index"):
        (tmp_path / name).mkdir()

    status = module.index_status(tmp_path)
    assert status == {
        "search_index": True,
        "repo_index": True,
        "vault_index": True,
    }


def test_accessible_wsl_mounted_vault_is_healthy(monkeypatch):
    module = importlib.import_module("scripts.healthcheck")
    monkeypatch.setenv("OBSIDIAN_PATH", "/mnt/c/Users/example/OneDrive/Vault")
    monkeypatch.setattr(module.Path, "exists", lambda _path: True)
    report = module.CheckReport()

    module._check_vault(report)

    assert report.passed == 1
    assert report.warnings == 0
