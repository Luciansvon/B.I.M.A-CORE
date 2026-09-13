"""Safety stub for the retired live-repository Git backup."""

from typing import NoReturn


def run_git(*args: object, **kwargs: object) -> NoReturn:
    """Preserve import compatibility while blocking every Git mutation."""
    raise RuntimeError("Cloud backup Git runner is disabled")


def backup() -> bool:
    """Refuse unattended backup mutations in the active development repo."""
    print("Cloud backup dari repository kerja aktif: disabled.")
    print(
        "Gunakan repository backup terpisah dengan destination dan retention "
        "yang disetujui sebelum membuat automation baru."
    )
    return False


if __name__ == "__main__":
    raise SystemExit(1 if not backup() else 0)
