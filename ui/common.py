"""Shared UI helpers."""
import os

import streamlit as st
import streamlit.components.v1 as components

from core import store
from core.cache import CACHE
from core.validators import safe_html, wa_digits, normalize_support

_COMP = components.declare_component(
    "browser_store", path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "components", "browser_store"))


def bstore(name, read=False, save=None, clear=False, key=None):
    """Best-effort localStorage bridge. Returns the stored string when read=True ('' if empty, None until ready)."""
    try:
        return _COMP(name=name, read=read, save=save, clear=clear, key=key or ("bs_" + name), default=None)
    except Exception:
        return ""


def client_ip():
    """Best-effort client IP from proxy headers (untrusted information)."""
    try:
        h = st.context.headers
        v = h.get("X-Forwarded-For") or h.get("X-Real-Ip") or ""
        return v.split(",")[0].strip()[:45] or "unknown"
    except Exception:
        return "unknown"


def logo_bytes():
    def load():
        import requests
        try:
            u = store.asset_url("logo.png")
            if not u:
                return None
            r = requests.get(u, timeout=5)
            return r.content if r.status_code == 200 else None
        except Exception:
            return None
    return CACHE.get("i:logobytes", 300, load)


def header(settings):
    try:
        lu = store.asset_url("logo.png")
    except Exception:
        lu = None
    img = '<img src="%s" alt="" style="max-height:60px;margin-right:10px">' % safe_html(lu) if lu else ""
    st.markdown('<div class="sq-head">%s<span class="sq-title">%s</span></div>' % (img, safe_html(settings.get("store_name", ""))),
                unsafe_allow_html=True)


def footer(settings):
    n = normalize_support(settings.get("support_number", ""))
    if n:
        st.markdown('<div class="sq-foot">Support: <a href="https://wa.me/%s" target="_blank" rel="noopener noreferrer">%s</a></div>'
                    % (wa_digits(n), safe_html(n)), unsafe_allow_html=True)


def friendly_error(msg="The service is temporarily unavailable. Please try again in a moment."):
    st.error(msg)
