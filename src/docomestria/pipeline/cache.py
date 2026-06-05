"""Cache backends for `ExtractionResult` — disk (default) and memory (for tests).

The cache key is the SHA256 of (pdf bytes, schema repr, model identifier).
Use `Pipeline.cache_dir=None` to disable caching.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:  # pragma: no cover
    from .result import ExtractionResult


class CacheBackend(Protocol):
    """Minimum cache interface used by the pipeline."""

    def get(self, key: str) -> "ExtractionResult | None": ...

    def set(self, key: str, value: "ExtractionResult") -> None: ...


@dataclass
class MemoryCache:
    """Dict-backed cache, primarily for tests."""

    _store: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str) -> "ExtractionResult | None":
        return self._store.get(key)

    def set(self, key: str, value: "ExtractionResult") -> None:
        self._store[key] = value


@dataclass
class DiskCache:
    """Disk-backed cache using the `diskcache` library (lazy import)."""

    cache_dir: str
    ttl_seconds: int | None = None
    _cache: Any = field(default=None, init=False, repr=False)

    def _open(self) -> Any:
        if self._cache is not None:
            return self._cache
        try:
            import diskcache  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "DiskCache requires `diskcache`. Install with `pip install docomestria[pipeline]`."
            ) from exc
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
        self._cache = diskcache.Cache(self.cache_dir)
        return self._cache

    def get(self, key: str) -> "ExtractionResult | None":
        return self._open().get(key)

    def set(self, key: str, value: "ExtractionResult") -> None:
        cache = self._open()
        if self.ttl_seconds is None:
            cache.set(key, value)
        else:
            cache.set(key, value, expire=self.ttl_seconds)


def build_cache_key(pdf_path: str | Path, schema_repr: str, model_id: str) -> str:
    """SHA256 of pdf bytes + schema repr + model identifier."""
    digest = hashlib.sha256()
    pdf_bytes = Path(pdf_path).read_bytes()
    digest.update(pdf_bytes)
    digest.update(b"\x00")
    digest.update(schema_repr.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(model_id.encode("utf-8"))
    return digest.hexdigest()


__all__ = ["CacheBackend", "DiskCache", "MemoryCache", "build_cache_key"]
