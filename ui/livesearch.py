"""Live (type-ahead) item-number search: a small JavaScript component. Filtering happens in the browser on every key
press; Python only hears about the chosen item."""
import os

import streamlit as st
import streamlit.components.v1 as components

_COMP = components.declare_component(
    "item_search", path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "components", "item_search"))


def item_search(rows, key, placeholder="Item number", show_status=True):
    """rows: [[item_no, description, available(0/1)], ...] sorted by item number. Returns {'item_no', 'n'} or None.
    The last choice persists across reruns; item_no is None when the box was edited after a choice."""
    return _COMP(rows=rows, placeholder=placeholder, show_status=show_status, key=key, default=None)


def new_selection(key, sel):
    """The chosen item_no only the FIRST time it is seen (choices persist across reruns), else None."""
    if not sel or not sel.get("item_no"):
        return None
    if st.session_state.get("ls_seen_" + key) == sel.get("n"):
        return None
    st.session_state["ls_seen_" + key] = sel.get("n")
    return sel["item_no"]
