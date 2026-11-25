"""App-controlled file storage.

Files a learner imports are copied into Adle's own directory under generated
names. The original path is used once, to read the file, and is never stored
or reused; the original name is kept only as display text. This removes any
way for a file name to influence where something is written.
"""

from __future__ import annotations

import hashlib
import shutil
import time
from collections.abc import Collection
from pathlib import Path

_CHUNK = 1024 * 1024
#: Extensions that may be kept on stored files. Anything else is stored without one.
_SAFE_EXTENSIONS = frozenset({".pdf", ".docx", ".md", ".markdown", ".txt", ".text"})


def hash_file(path: Path) -> tuple[str, int]:
    """SHA-256 and size of a file, read in bounded chunks."""
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while block := handle.read(_CHUNK):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


#: How many times, and how far apart, an original held open is tried again as it is
#: deleted: five seconds in all.
_DELETE_TRIES = 25
_DELETE_PAUSE_SECONDS = 0.2


class AssetStore:
    """Stores files under a single root directory, addressed by generated names."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, stored_name: str) -> Path:
        """Resolve a stored name, refusing anything that is not a plain file name in the root."""
        if not stored_name or Path(stored_name).name != stored_name or stored_name in {".", ".."}:
            raise ValueError("Invalid stored file name.")
        return self.root / stored_name

    def import_file(self, source: Path, record_id: str, original_name: str) -> str:
        """Copy ``source`` into the store. Returns the stored name."""
        extension = Path(original_name).suffix.lower()
        stored_name = record_id + (extension if extension in _SAFE_EXTENSIONS else "")
        destination = self.path_for(stored_name)
        temporary = destination.with_name(destination.name + ".part")
        try:
            shutil.copyfile(source, temporary)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        return stored_name

    def delete(self, stored_name: str | None) -> None:
        """Delete a stored original, if there is one. On Windows a file held open cannot go:
        one held a moment (a page of it being drawn as its reading stops) is tried again for
        a few seconds; one held longer is left, and the next start deletes it with every
        original that no source refers to (``keep_only``)."""
        if not stored_name:
            return
        path = self.path_for(stored_name)
        for _ in range(_DELETE_TRIES):
            try:
                path.unlink(missing_ok=True)
            except PermissionError:
                time.sleep(_DELETE_PAUSE_SECONDS)
            else:
                return

    def keep_only(self, stored_names: Collection[str]) -> int:
        """Delete every stored file whose name is not in ``stored_names``.

        Returns how many were deleted. A file that cannot be deleted now is left for
        the next time; folders are never touched.
        """
        wanted = set(stored_names)
        removed = 0
        for entry in self.root.iterdir():
            if entry.name in wanted or not entry.is_file():
                continue
            try:
                entry.unlink()
            except OSError:
                continue
            removed += 1
        return removed
