"""Pure routing helpers for Discord attachments."""

from collections.abc import Iterable
from pathlib import Path


DISCORD_IMAGE_EXTS = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
)


def has_supported_image_attachment(filenames: Iterable[str]) -> bool:
    """Return True when at least one supported Discord image is attached."""
    return any(
        Path(filename).suffix.lower() in DISCORD_IMAGE_EXTS
        for filename in filenames
    )


def image_only_prompt(current_prompt: str) -> str:
    """Supply an explicit Vision intent while preserving an existing caption."""
    return current_prompt or "analisis gambar ini"
