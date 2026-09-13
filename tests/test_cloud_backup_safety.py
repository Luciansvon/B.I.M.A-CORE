from tools import cloud_backup


def test_live_repo_backup_is_disabled_without_git_mutation(
    monkeypatch,
    capsys,
) -> None:
    def forbidden_git(*args: object, **kwargs: object) -> None:
        raise AssertionError("backup() tidak boleh menjalankan Git")

    monkeypatch.setattr(cloud_backup, "run_git", forbidden_git)

    assert cloud_backup.backup() is False
    output = capsys.readouterr().out.lower()
    assert "disabled" in output
    assert "repository backup terpisah" in output
