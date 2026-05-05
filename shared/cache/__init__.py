"""
Cache abstraction.

Public API:
- `ICache`       — protocol every adapter must satisfy
- `InMemoryCache` — process-local LRU+TTL implementation

Importers should depend on `ICache`, not on the concrete class. The
composition root chooses the adapter (e.g. swap to Redis later
without touching call sites).
"""

from shared.cache.memory_adapter import InMemoryCache
from shared.cache.ports import ICache

__all__ = ["ICache", "InMemoryCache"]
