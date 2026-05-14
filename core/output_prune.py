"""Auto-prune file output berdasar pattern. Sisakan N terbaru by mtime."""

import logging
from pathlib import Path
from typing import Union

logger = logging.getLogger('bima_core')


def prune_outputs(directory: Union[Path, str], pattern: str, keep: int = 10) -> int:
    """Hapus file matching `pattern` di `directory`, sisakan `keep` terbaru.
    Return jumlah file yang dihapus."""
    d = Path(directory)
    if not d.exists():
        return 0

    files = sorted(
        (f for f in d.glob(pattern) if f.is_file()),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    if len(files) <= keep:
        return 0

    deleted = 0
    for f in files[keep:]:
        try:
            f.unlink()
            deleted += 1
        except OSError as e:
            logger.warning(f"[PRUNE] gagal hapus {f.name}: {e}")

    if deleted:
        logger.info(f"[PRUNE] {pattern} di {d.name}: hapus {deleted}, sisa {keep}")
    return deleted
