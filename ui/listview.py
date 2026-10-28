"""Customer screen: upload a list (Excel / CSV / text / text PDF), review what the app understood, add the confirmed items to the basket.
Heavy work happens only here, only when the customer presses Read. Nothing is stored except the customer's own choices (counters)."""
import streamlit as st

from core import bundles, listimport, orders, store
from core.security import LIMITER
from core.validators import safe_html
from . import bundleview, livesearch


def _ss():
    return st.session_state


def _reset():
    ss = _ss()
    for k in [k for k in ss if str(k).startswith(("imp_q_", "imp_c_", "ls_imp_"))]:
        ss.pop(k, None)
    ss.imp = None; ss.imp_edit = None
    ss.imp_up = ss.get("imp_up", 0) + 1                      # a new uploader widget forgets the old file


def close():
    _reset(); _ss().view = "browse"


def _desc(cat, no):
    d = cat["by_no"].get(no)
    return d["description"] if d else ""


def _read(cat, f):
    ss = _ss()
    if not LIMITER.allow("imp:" + ss.sid, 8, 600):
        st.error("Please wait a few minutes before reading another list."); return
    with st.spinner("Reading your list..."):
        lines, notes, err = listimport.extract_lines(f.getvalue(), f.name)
        if err:
            st.error(err); return
        rows = listimport.match_all(cat, lines)
    for r in rows:
        r["chosen"], r["src"] = (r["cands"][0], "auto") if r["state"] == "auto" else (None, None)
    ss.imp = {"rows": rows, "notes": notes}; ss.imp_edit = None
    st.rerun()


def _chosen(r):
    ss = _ss()
    if r["state"] == "suggest" and r["src"] != "typed":
        v = ss.get("imp_c_%d" % r["id"])
        if v and v != "Skip this line":
            return v.split("  |  ")[0], "pick"
        return (None, None) if not v else (None, "skip")
    return r["chosen"], r["src"]


def _not_bundle(r):
    r["state"] = "suggest" if r["cands"] and r["conf"] >= listimport.SUGGEST else "manual"; r["bundle"] = None


def _bundle_lines(cat, r):
    b = cat["train"]["bundles"][r["bundle"]]
    return bundles.expand(cat, b, bundleview.picks_from_state(cat, b, "ib%d" % r["id"]), _ss().get("imp_q_%d" % r["id"]) or r["qty"])


def _ready(cat, r):
    if r["state"] == "bundle":
        return not _bundle_lines(cat, r)[1]
    return _chosen(r)[0] is not None


def _row(cat, r):
    ss = _ss(); k = r["id"]
    st.markdown("<div style='margin-top:.7rem'><b>%s</b></div>" % safe_html(r["text"]), unsafe_allow_html=True)
    if ss.get("imp_edit") == k:
        sel = livesearch.item_search(cat["payload"], key="ls_imp_%d" % k, placeholder="Type the item number")
        if sel and sel.get("item_no"):
            r["chosen"], r["src"] = sel["item_no"], "typed"; ss.imp_edit = None; st.rerun()
        st.button("Cancel", key="imp_cx_%d" % k, on_click=lambda: ss.__setitem__("imp_edit", None))
        return
    if r["state"] == "bundle":
        b = cat["train"]["bundles"][r["bundle"]]
        with st.container(border=True):
            st.markdown("Bundle: **%s**" % safe_html(b["name"]), unsafe_allow_html=True)
            _, miss = bundleview.picker(cat, b, "ib%d" % k)
            if miss:
                st.caption("Please choose: " + ", ".join(miss))
        c1, c2 = st.columns([1, 2])
        ss.setdefault("imp_q_%d" % k, r["qty"])
        c1.number_input("Quantity", 1, 999, key="imp_q_%d" % k, label_visibility="collapsed")
        c2.button("Not a bundle", key="imp_nb_%d" % k, use_container_width=True, on_click=_not_bundle, args=(r,))
        return
    no, src = _chosen(r)
    if r["state"] == "suggest" and r["src"] != "typed":
        opts = ["%s  |  %s" % (n, _desc(cat, n)) for n in r["cands"][:2]] + ["Skip this line"]
        st.radio("Did you mean", opts, index=None, key="imp_c_%d" % k, label_visibility="collapsed")
    elif no:
        st.markdown("&#10003; %s<br><span style='opacity:.8'>%s</span>" % (safe_html(no), safe_html(_desc(cat, no))), unsafe_allow_html=True)
    else:
        st.caption("Not recognised. Type the item number.")
    c1, c2 = st.columns([1, 2])
    ss.setdefault("imp_q_%d" % k, r["qty"])
    c1.number_input("Quantity", 1, 9999, key="imp_q_%d" % k, label_visibility="collapsed")
    c2.button("Type item number" if (r["state"] != "auto" and not no) else "Change", key="imp_ed_%d" % k, use_container_width=True,
              on_click=lambda: ss.__setitem__("imp_edit", k))


def _add_all(cat):
    ss = _ss(); added = skipped = 0; learn = []
    for r in ss.imp["rows"]:
        if r["state"] == "bundle":
            lines, missing = _bundle_lines(cat, r)
            if missing:
                skipped += 1; continue
            a, sk = bundleview.add_lines(lines); added += 1 if a else 0; skipped += 1 if sk and not a else 0
            continue
        no, src = _chosen(r)
        if not no:
            skipped += 1; continue
        if no not in ss.basket and len(ss.basket) >= orders.MAX_LINES:
            skipped += 1; continue
        qty = max(1, min(9999, int(ss.get("imp_q_%d" % r["id"]) or 1)))
        cur = ss.basket.get(no, {"qty": 0, "note": ""})
        cur["qty"] = min(9999, int(cur.get("qty") or 0) + qty); ss.basket[no] = cur
        added += 1
        if src in ("pick", "typed") and r.get("wording"):
            learn.append((r["wording"], no))
    if learn and LIMITER.allow("learn:" + ss.sid, 6, 3600):
        try:
            store.record_choices(learn, ss.sid)
        except Exception:
            pass                                             # learning is a bonus; never block the customer
    ss.flash = "%d item(s) added to your basket%s." % (added, (", %d skipped" % skipped) if skipped else "")
    close()


def render(cat):
    ss = _ss()
    st.button("Back", key="imp_back", on_click=close)
    st.header("Upload your list")
    if not ss.get("imp"):
        st.caption("Excel, CSV, text or a text-based PDF. One item per line, for example: 2 x contactor 25A")
        f = st.file_uploader("List file", type=["xlsx", "csv", "txt", "pdf"], key="imp_file_%d" % ss.get("imp_up", 0), label_visibility="collapsed")
        if f is not None and st.button("Read my list", key="imp_read", use_container_width=True):
            _read(cat, f)
        return
    rows = ss.imp["rows"]
    for n in ss.imp["notes"]:
        st.info(n)
    ready = sum(1 for r in rows if _ready(cat, r))
    st.write("%d line(s) read, %d ready. Check the others below." % (len(rows), ready))
    st.button("Add %d item(s) to basket" % ready, key="imp_add_top", on_click=_add_all, args=(cat,), type="primary",
              use_container_width=True, disabled=ready == 0)
    for r in sorted(rows, key=lambda r: ({"manual": 0, "suggest": 1, "bundle": 1, "auto": 2}[r["state"]], r["id"])):   # fixed order: rows do not jump when chosen
        _row(cat, r)
        st.markdown("<hr style='margin:.4rem 0'>", unsafe_allow_html=True)
    st.button("Start over", key="imp_over", on_click=_reset)
