"""Customer view of a functional bundle: its items, a choice for each alternative (e.g. door), a quantity, and one button that
adds everything to the basket together."""
import streamlit as st

from core import bundles, orders
from core.validators import safe_html


def _ss():
    return st.session_state


def _opts(cat, opts):
    return {"%s  |  %s" % (bundles.part_label(cat, p), p["no"]): p["no"] for p in opts}


def picks_from_state(cat, b, pfx):
    """{choice name: item_no} from the radios the customer touched."""
    ss = _ss(); out = {}
    for name, opts in bundles.resolve(cat, b)[1].items():
        no = _opts(cat, opts).get(ss.get("%s_c_%s" % (pfx, name)))
        if no:
            out[name] = no
    return out


def picker(cat, b, pfx):
    """Shows the items and one radio per choice. -> (picks, names of choices not yet made)."""
    fixed, choices = bundles.resolve(cat, b)
    for p in fixed:
        d = cat["by_no"][p["no"]]
        st.markdown("%d &times; %s<br><span style='opacity:.75'>%s</span>" % (p["qty"], safe_html(d["description"]), safe_html(p["no"])), unsafe_allow_html=True)
    for name, opts in choices.items():
        st.radio(name, list(_opts(cat, opts)), index=None, key="%s_c_%s" % (pfx, name))
    picks = picks_from_state(cat, b, pfx)
    return picks, [n for n in choices if n not in picks]


def add_lines(lines):
    """Adds (item_no, qty) pairs to the basket. -> (added, skipped)."""
    ss = _ss(); added = skipped = 0
    for no, qty in lines:
        if no not in ss.basket and len(ss.basket) >= orders.MAX_LINES:
            skipped += 1; continue
        cur = ss.basket.get(no, {"qty": 0, "note": ""})
        cur["qty"] = min(9999, int(cur.get("qty") or 0) + int(qty)); ss.basket[no] = cur
        added += 1
    return added, skipped


def _add(cat, b, pfx):
    ss = _ss()
    lines, missing = bundles.expand(cat, b, picks_from_state(cat, b, pfx), ss.get(pfx + "_q") or 1)
    if missing:
        return
    added, skipped = add_lines(lines)
    ss.flash = "%s added to your basket (%d item(s))%s." % (b["name"], added, (", %d skipped" % skipped) if skipped else "")


def render(cat, b, pfx):
    ss = _ss()
    with st.container(border=True):
        st.markdown("**%s**" % safe_html(b["name"]), unsafe_allow_html=True)
        st.caption("Bundle: all these items are added together.")
        picks, missing = picker(cat, b, pfx)
        ss.setdefault(pfx + "_q", 1)
        c1, c2 = st.columns([1, 2])
        c1.number_input("Quantity", 1, 999, key=pfx + "_q", label_visibility="collapsed")
        c2.button("Add all to basket", key=pfx + "_add", on_click=_add, args=(cat, b, pfx), disabled=bool(missing), use_container_width=True)
        if missing:
            st.caption("Please choose: " + ", ".join(missing))
