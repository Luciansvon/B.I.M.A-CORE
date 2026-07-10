import tomllib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _project(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _dependency_names(project: dict) -> set[str]:
    return {
        item.split("[", 1)[0].split("=", 1)[0].split("<", 1)[0].lower()
        for item in project["project"]["dependencies"]
    }


def test_core_project_excludes_conflicting_browser_and_f5_packages() -> None:
    core = _project(PROJECT_ROOT / "pyproject.toml")
    legacy_requirements = (PROJECT_ROOT / "requirements.txt").read_text(
        encoding="utf-8"
    ).lower()

    assert core["project"]["requires-python"] == ">=3.12,<3.13"
    assert "browser-use" not in _dependency_names(core)
    assert "f5-tts" not in _dependency_names(core)
    assert "browser-use" not in legacy_requirements
    assert "f5-tts" not in legacy_requirements


def test_browser_and_voice_are_independent_uv_projects() -> None:
    browser = _project(PROJECT_ROOT / "services" / "browser" / "pyproject.toml")
    voice = _project(PROJECT_ROOT / "services" / "voice" / "pyproject.toml")

    assert browser["project"]["dependencies"] == ["browser-use==0.13.3"]
    assert "f5-tts==1.1.21" in voice["project"]["dependencies"]
    assert "torch" in voice["tool"]["uv"]["sources"]


def test_each_runtime_has_its_own_lockfile() -> None:
    assert (PROJECT_ROOT / "uv.lock").is_file()
    assert (PROJECT_ROOT / "services" / "browser" / "uv.lock").is_file()
    assert (PROJECT_ROOT / "services" / "voice" / "uv.lock").is_file()


def test_ci_installs_only_locked_ci_group() -> None:
    core = _project(PROJECT_ROOT / "pyproject.toml")
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert "ci" in core["dependency-groups"]
    assert "uv sync --locked --only-group ci" in workflow
    assert "pip install -r" not in workflow
