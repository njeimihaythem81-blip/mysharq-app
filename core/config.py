"""Configuration and secrets. Secrets come ONLY from st.secrets (or a test dict)."""
_provider = None  # tests inject a plain dict here

REQUIRED = ["GITHUB_TOKEN_DATA", "GITHUB_TOKEN_IMAGES", "GITHUB_OWNER",
            "IMAGES_REPO", "DATA_REPO", "SESSION_SECRET", "SETUP_CODE", "STAFF_KEY"]
_PLACEHOLDERS = ("REPLACE", "your-github", "xxxx", "changeme", "<")


class ConfigError(Exception):
    """Raised when secrets are missing or still look like placeholders."""


def set_provider(d):
    global _provider
    _provider = d


def get(name, default=None):
    if _provider is not None:
        return _provider.get(name, default)
    import streamlit as st
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def validate():
    """Refuse to run with missing or placeholder secrets."""
    bad = []
    for k in REQUIRED:
        v = str(get(k, "") or "")
        if not v or any(m.lower() in v.lower() for m in _PLACEHOLDERS):
            bad.append(k)
    if len(str(get("SESSION_SECRET", "") or "")) < 32 and "SESSION_SECRET" not in bad:
        bad.append("SESSION_SECRET (needs 32+ characters)")
    if len(str(get("STAFF_KEY", "") or "")) < 20 and "STAFF_KEY" not in bad:
        bad.append("STAFF_KEY (needs 20+ characters)")
    if bad:
        raise ConfigError("Missing or placeholder secrets: " + ", ".join(bad))


def branch():
    return str(get("BRANCH", "main") or "main")


def chat_ids():
    raw = str(get("TELEGRAM_CHAT_IDS", "") or "")
    return [c.strip() for c in raw.split(",") if c.strip()]
