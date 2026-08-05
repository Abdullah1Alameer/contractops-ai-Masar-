"""Simple in-memory rate limiter for public endpoints (single-process demo)."""
from __future__ import annotations

import time
from collections import defaultdict

_buckets: dict[str, list[float]] = defaultdict(list)
WINDOW_SEC = 60
MAX_HITS = 30


def check_rate_limit(key: str) -> bool:
    """Return True if allowed, False if rate limited."""
    now = time.time()
    hits = _buckets[key]
    _buckets[key] = [t for t in hits if now - t < WINDOW_SEC]
    if len(_buckets[key]) >= MAX_HITS:
        return False
    _buckets[key].append(now)
    return True
