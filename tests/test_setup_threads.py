from pathlib import Path

import pytest

from scripts import setup_threads, test_post_image


def test_threads_scripts_use_project_root_env() -> None:
    expected = Path(__file__).resolve().parent.parent / ".env"

    assert setup_threads.ENV_PATH == expected
    assert test_post_image.ENV_PATH == expected


@pytest.mark.parametrize("payload", [{}, {"access_token": None}, {"access_token": "  "}])
def test_require_access_token_rejects_missing_token(payload: dict) -> None:
    with pytest.raises(ValueError, match="access_token"):
        setup_threads.require_access_token(payload)


def test_require_access_token_returns_stripped_token() -> None:
    assert setup_threads.require_access_token({"access_token": " token-123 "}) == (
        "token-123"
    )


def test_save_env_never_writes_none(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"

    with pytest.raises(ValueError):
        setup_threads.save_env(
            {"THREADS_ACCESS_TOKEN": None},
            env_path=env_path,
        )

    assert not env_path.exists()


def test_load_and_save_env_accept_explicit_path(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"

    setup_threads.save_env({"THREADS_APP_ID": "123"}, env_path=env_path)

    assert setup_threads.load_env(env_path=env_path) == {"THREADS_APP_ID": "123"}
