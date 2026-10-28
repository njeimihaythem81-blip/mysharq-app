"""Customer access gate (v2.5). When the manager switches 'Require customer login' on, only customers with a name + code
created by the manager can see the store. Staff using the secret staff link pass automatically."""
import streamlit as st

from core import auth
from core.ghstore import GhError
from . import common


def _ss():
    return st.session_state


def _login(settings):
    common.header(settings)
    st.subheader("Sign in")
    st.caption("Enter the name and the code you received from the store.")
    with st.form("cust_login"):
        n = st.text_input("Name", max_chars=40)
        c = st.text_input("Code", type="password", max_chars=20)
        go = st.form_submit_button("Sign in", use_container_width=True)
    if go:
        try:
            ok, msg, tok, user = auth.customer_login(n, c, common.client_ip())
        except GhError:
            st.error("The service is temporarily unavailable. Please try again in a moment."); return
        if ok:
            _ss().cust_token = tok; _ss().cust_save = tok
            st.rerun()
        else:
            st.error(msg)
    common.footer(settings)


def passed(settings):
    """True when the customer may see the store. Also sets session 'cust' (id, display) for signed-in customers."""
    ss = _ss()
    if ss.pop("cust_clear", False):
        common.bstore("cust_session", clear=True, key="cs_clear")
    if not settings.get("customer_login_required") or ss.get("staff_ok"):
        return True
    tok = ss.get("cust_token")
    if not tok:
        v = common.bstore("cust_session", read=True, key="cs_read")
        if v is None:
            st.caption("Loading..."); return False
        if v and auth.customer_session(v):
            ss.cust_token = tok = v
    user = auth.customer_session(tok) if tok else None
    if not user:
        ss.pop("cust_token", None); ss.pop("cust", None)
        _login(settings); return False
    ss.cust = user
    if ss.pop("cust_save", None):
        common.bstore("cust_session", save=ss.cust_token, key="cs_save")
    return True


def sign_out_button():
    ss = _ss()
    if ss.get("cust") and ss.get("cust_token"):
        st.button("Sign out", key="cust_out", on_click=_sign_out)


def _sign_out():
    ss = _ss(); u = ss.get("cust")
    try:
        if u:
            auth.customer_logout(u["id"])           # invalidates the stored token on every device
    except Exception:
        pass
    ss.pop("cust_token", None); ss.pop("cust", None); ss.basket = {}
    ss.cust_clear = True
