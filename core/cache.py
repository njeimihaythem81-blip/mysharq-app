"""Tiny thread-safe TTL cache (process-wide, shared by all sessions)."""
import threading
import time


class TTLCache:
    def __init__(self):
        self._d = {}
        self._l = threading.RLock()

    def get(self, key, ttl, loader):
        now = time.time()
        with self._l:
            hit = self._d.get(key)
            if hit and now - hit[0] < ttl:
                return hit[1]
        val = loader()
        with self._l:
            self._d[key] = (time.time(), val)
        return val

    def invalidate(self, prefix=""):
        with self._l:
            for k in [k for k in self._d if str(k).startswith(prefix)]:
                del self._d[k]


CACHE = TTLCache()
