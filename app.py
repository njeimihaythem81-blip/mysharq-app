"""MY SHARQ RFQ's - entry point (Streamlit)."""
import logging
import uuid

import streamlit as st

from core import config, store
from core.ghstore import GhError

DEFAULT_NAME = store.DEFAULT_SETTINGS["store_name"]
log = logging.getLogger("mysharq")

settings, cfg_error = dict(store.DEFAULT_SETTINGS), None
try:
    config.validate()
    settings = store.settings()
except config.ConfigError as e:
    cfg_error = str(e)
except GhError:
    pass
except Exception:
    pass

st.set_page_config(page_title=settings.get("store_name", DEFAULT_NAME), page_icon="⚡", layout="centered",
                   initial_sidebar_state="collapsed")

from ui import customer, staff, theme  # noqa: E402  (after set_page_config)

theme.inject(settings)

if cfg_error:
    st.title(DEFAULT_NAME)
    st.error("The store is not configured yet.")
    st.caption(cfg_error + ". Add them in Streamlit > Settings > Secrets.")
    st.stop()

st.session_state.setdefault("view", "browse")

# Secret staff link: https://<app>/?k=<STAFF_KEY>. No button exists for customers. Wrong keys are ignored silently.
_k = st.query_params.get("k")
if _k:
    from core import auth
    from ui import common as _common
    if auth.check_staff_key(_k, _common.client_ip()):
        st.session_state.staff_ok = True
        st.session_state.view = "staff"
    try:
        st.query_params.clear()   # remove the key from the address bar
    except Exception:
        pass
if st.session_state.view == "staff" and not st.session_state.get("staff_ok"):
    st.session_state.view = "browse"


try:
    if st.session_state.view == "staff":
        staff.render(settings)
    else:
        customer.render(settings)
        from ui import common
        common.footer(settings)
except GhError:
    st.error("The service is temporarily unavailable. Please try again in a moment.")
except Exception as e:  # never show stack traces; log only the type and a reference id
    ref = uuid.uuid4().hex[:8]
    log.error("ref=%s error=%s", ref, type(e).__name__)
    st.error("Something went wrong. Reference: %s" % ref)
