"""SHA256 content-based caching for extraction results.

Only re-extracts files that have actually changed. Cache is stored
in codemap-out/cache/ as JSON files keyed by content hash.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any


def _file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of file contents + relative path for cache key."""
    try:
        content = file_path.read_bytes()
    except OSError:
        return ""
    h = hashlib.sha256()
    h.update(content)
    return h.hexdigest()


def _cache_path(file_hash: str, cache_dir: Path) -> Path:
    """Return the cache file path for a given hash."""
    return cache_dir / f"{file_hash}.json"


def load_cached(file_path: Path, cache_dir: Path) -> dict[str, Any] | None:
    """Load cached extraction result for a file if it exists and is current.

    Returns:
        Cached dict with 'nodes' and 'edges', or None if not cached.
    """
    fhash = _file_hash(file_path)
    if not fhash:
        return None

    cp = _cache_path(fhash, cache_dir)
    if not cp.is_file():
        return None

    try:
        data = json.loads(cp.read_text(encoding="utf-8"))
        return data
    except (json.JSONDecodeError, OSError):
        return None


def save_cached(file_path: Path, result: dict[str, Any], cache_dir: Path) -> None:
    """Save extraction result to cache.

    Uses atomic write (temp file + rename) for Windows safety.
    """
    fhash = _file_hash(file_path)
    if not fhash:
        return

    cache_dir.mkdir(parents=True, exist_ok=True)
    cp = _cache_path(fhash, cache_dir)

    content = json.dumps(result, indent=2, default=str)

    # Atomic write
    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(cache_dir), suffix=".tmp")
        try:
            with open(fd, "w", encoding="utf-8") as f:
                f.write(content)
            # On Windows, rename fails if target exists
            if cp.exists():
                cp.unlink()
            Path(tmp_path).rename(cp)
        except OSError:
            # Fallback: direct write
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:
                pass
            cp.write_text(content, encoding="utf-8")
    except OSError:
        cp.write_text(content, encoding="utf-8")


def check_cache(
    files: list[str],
    root: Path,
    cache_dir: Path,
) -> tuple[list[str], list[str]]:
    """Split files into cached and uncached.

    Returns:
        (cached_files, uncached_files) — both as relative paths.
    """
    cached: list[str] = []
    uncached: list[str] = []

    for rel_path in files:
        fp = root / rel_path
        if load_cached(fp, cache_dir) is not None:
            cached.append(rel_path)
        else:
            uncached.append(rel_path)

    return cached, uncached


def clear_cache(cache_dir: Path) -> int:
    """Delete all cached files. Returns count of files deleted."""
    if not cache_dir.is_dir():
        return 0
    count = 0
    for f in cache_dir.glob("*.json"):
        f.unlink()
        count += 1
    return count
