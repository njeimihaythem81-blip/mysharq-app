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


def to_staff():
    st.session_state.view = "staff"


try:
    if st.session_state.view == "staff":
        staff.render(settings)
    else:
        customer.render(settings)
        from ui import common
        common.footer(settings)
        st.button("Staff", key="to_staff", on_click=to_staff)
except GhError:
    st.error("The service is temporarily unavailable. Please try again in a moment.")
except Exception as e:  # never show stack traces; log only the type and a reference id
    ref = uuid.uuid4().hex[:8]
    log.error("ref=%s error=%s", ref, type(e).__name__)
    st.error("Something went wrong. Reference: %s" % ref)
