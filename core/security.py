"""Passwords (scrypt, stdlib), signed session tokens, rate limiting, login throttling."""
import base64
import hashlib
import hmac
import json
import os
import threading
import time
from collections import defaultdict, deque

_N, _R, _P = 2 ** 15, 8, 1
_COMMON = None


def _b64(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


# ---------------- passwords ----------------
def hash_password(pw):
    salt = os.urandom(16)
    h = hashlib.scrypt(pw.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, maxmem=128 * 1024 * 1024, dklen=32)
    return "scrypt$%d$%d$%d$%s$%s" % (_N, _R, _P, _b64(salt), _b64(h))


def verify_password(pw, stored):
    try:
        algo, n, r, p, salt, h = stored.split("$")
        if algo != "scrypt":
            return False
        calc = hashlib.scrypt(pw.encode("utf-8"), salt=_unb64(salt), n=int(n), r=int(r), p=int(p),
                              maxmem=128 * 1024 * 1024, dklen=32)
        return hmac.compare_digest(calc, _unb64(h))
    except Exception:
        return False


_DUMMY = None


def dummy_verify(pw):
    """Run a hash for unknown usernames so timing does not reveal valid usernames."""
    global _DUMMY
    if _DUMMY is None:
        _DUMMY = hash_password("dummy-password-for-timing")
    verify_password(pw, _DUMMY)
    return False


def _common():
    global _COMMON
    if _COMMON is None:
        p = os.path.join(os.path.dirname(__file__), "common_passwords.txt")
        with open(p, encoding="utf-8") as f:
            _COMMON = {l.strip().lower() for l in f if l.strip()}
    return _COMMON


def password_policy(pw, username, role):
    """Return an error message, or None when the password is acceptable."""
    minlen = 12 if role == "manager" else 8
    if len(pw) < minlen:
        return "Password must be at least %d characters." % minlen
    low = pw.lower()
    if low in _common() or low == (username or "").lower():
        return "This password is too common or equals the username."
    if len(set(pw)) < 4:
        return "Password is too repetitive."
    return None


# ---------------- session tokens ----------------
def make_token(secret, user_id, role, token_version, ttl_seconds, now=None):
    now = int(now if now is not None else time.time())
    payload = _b64(json.dumps({"u": user_id, "r": role, "v": token_version, "iat": now,
                               "exp": now + int(ttl_seconds)}, separators=(",", ":")).encode())
    sig = _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
    return payload + "." + sig


def verify_token(secret, token, now=None):
    try:
        payload, sig = token.split(".")
        good = _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            return None
        d = json.loads(_unb64(payload))
        if int(d["exp"]) < int(now if now is not None else time.time()):
            return None
        return d
    except Exception:
        return None


# ---------------- rate limiting ----------------
class RateLimiter:
    """Sliding-window limiter, in process memory shared by all sessions (resets on app restart)."""

    def __init__(self):
        self._h = defaultdict(deque)
        self._l = threading.Lock()

    def count(self, key, window, now=None):
        now = now if now is not None else time.time()
        with self._l:
            q = self._h[key]
            while q and q[0] <= now - window:
                q.popleft()
            return len(q)

    def hit(self, key, now=None):
        now = now if now is not None else time.time()
        with self._l:
            self._h[key].append(now)

    def allow(self, key, limit, window, now=None):
        """Record a hit and return True if still within the limit."""
        if self.count(key, window, now) >= limit:
            return False
        self.hit(key, now)
        return True


LIMITER = RateLimiter()


class Throttle:
    """Progressive login throttling: no permanent lock-out. After 5 failures the wait doubles 10s..900s."""

    def __init__(self):
        self._f = {}
        self._l = threading.Lock()

    def wait_seconds(self, key, now=None):
        now = now if now is not None else time.time()
        with self._l:
            n, last = self._f.get(key, (0, 0))
        if n < 5:
            return 0
        delay = min(10 * 2 ** (n - 5), 900)
        return max(0, int(last + delay - now + 0.999))

    def fail(self, key, now=None):
        now = now if now is not None else time.time()
        with self._l:
            n, _ = self._f.get(key, (0, 0))
            self._f[key] = (n + 1, now)

    def reset(self, key):
        with self._l:
            self._f.pop(key, None)


THROTTLE = Throttle()
FAILED_LOGINS = deque(maxlen=20)  # (time, username) for the Activity screen, memory only
