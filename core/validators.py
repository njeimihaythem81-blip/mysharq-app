"""Input validation, normalisation and output-encoding helpers (security critical)."""
import html
import re
import secrets
import unicodedata
from datetime import datetime, timezone

_AR = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_PHONE_RE = re.compile(r"^(?:\+?218|00218|0)?(9[1-4]\d{7})$")
_ORDER_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0 O 1 I


def to_western_digits(s):
    return str(s).translate(_AR)


def normalize_phone(raw):
    """Libyan MOBILE numbers only (91/92/93/94). Format check only. Returns +218XXXXXXXXX or None."""
    if raw is None:
        return None
    s = to_western_digits(raw)
    s = re.sub(r"[\s\-\.\(\)\u00a0\u200f\u200e]", "", s)
    m = _PHONE_RE.match(s)
    return "+218" + m.group(1) if m else None


def normalize_support(raw):
    """Support number shown in the footer: Libyan mobile OR any international number (+CC...). Format check only."""
    n = normalize_phone(raw)
    if n:
        return n
    s = re.sub(r"[\s\-\.\(\)\u00a0]", "", to_western_digits(raw or ""))
    if s.startswith("00"):
        s = "+" + s[2:]
    return s if re.fullmatch(r"\+[1-9]\d{7,14}", s) else None


def display_phone(norm):
    d = norm.replace("+218", "")
    return "+218 %s %s %s" % (d[:2], d[2:5], d[5:])


def wa_digits(norm):
    return norm.replace("+", "")


def clean_text(s, maxlen):
    """Strip control / zero-width / bidi-override chars, collapse spaces, truncate."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFC", str(s))
    s = "".join(ch for ch in s if unicodedata.category(ch) not in ("Cc", "Cf", "Cs", "Co") or ch in "\n")
    s = re.sub(r"\s+", " ", s).strip()
    return s[:maxlen]


def valid_name(s):
    c = clean_text(s, 60)
    return c if len(c) >= 2 else None


def item_key(item_no):
    """Reversible, filesystem/URL-safe key. Allowed: A-Z 0-9 . - ; everything else -> _XX_ (hex of UTF-8)."""
    out = []
    for i, ch in enumerate(str(item_no).strip().upper()):
        if (ch.isascii() and ch.isalnum()) or ch == "-" or (ch == "." and i > 0):
            out.append(ch)
        else:
            out.append("".join("_%02X_" % b for b in ch.encode("utf-8")))
    return "".join(out)


def decode_key(key):
    def rep(m):
        return m.group(0)
    raw = bytearray()
    i = 0
    while i < len(key):
        if key[i] == "_" and i + 3 < len(key) + 0 and key[i + 3] == "_":
            raw += bytes([int(key[i + 1:i + 3], 16)])
            i += 4
        else:
            raw += key[i].encode("utf-8")
            i += 1
    return raw.decode("utf-8")


def search_norm(s):
    return re.sub(r"[^0-9A-Z]", "", str(s).upper())


def cat_norm(s):
    return re.sub(r"\s+", " ", str(s or "").strip()).upper()


def neutralize_formula(v):
    """Spreadsheet formula injection defence for any user-controlled string."""
    if isinstance(v, str) and v and (v[0] in "=+-@\t\r" or v.lstrip()[:1] in ("=",)):
        return "'" + v
    return v


_MD_SPECIAL = set("*_[]`$~#\\|{}!")


def safe_html(s):
    """Escape for use inside st.markdown(unsafe_allow_html=True): HTML + Markdown special characters.
    One pass per character, so entities are never double-escaped."""
    out = []
    for c in str(s):
        out.append("&#%d;" % ord(c) if c in _MD_SPECIAL else html.escape(c, quote=True))
    return "".join(out)


def new_order_id(now=None):
    now = now or datetime.now(timezone.utc)
    return "MS-%s-%s" % (now.strftime("%y%m%d"), "".join(secrets.choice(_ORDER_ALPHABET) for _ in range(4)))


def parse_int(v, lo, hi, default=None):
    try:
        n = int(str(v).strip())
    except Exception:
        return default
    return n if lo <= n <= hi else default
