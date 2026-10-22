"""Anonymous customer experience: selection guide, basket, send RFQ."""
import time

import streamlit as st

from core import catalog, docs, orders, store
from core.validators import item_key, parse_int, safe_html
from . import common, livesearch

PAGE = 24


def _ss():
    return st.session_state


def init():
    import uuid
    ss = _ss()
    ss.setdefault("basket", {}); ss.setdefault("path", ()); ss.setdefault("page", 0)
    ss.setdefault("view", "browse"); ss.setdefault("sid", uuid.uuid4().hex); ss.setdefault("lastq", "")


# ------------------------------------------------------------------ callbacks
def go(path):
    ss = _ss(); ss.path = tuple(path); ss.page = 0; ss.view = "browse"; ss.q = ""


def set_page(p):
    _ss().page = max(0, p)


def add(item_no, qkey):
    ss = _ss(); qty = parse_int(ss.get(qkey), 1, 9999, 1)
    if item_no not in ss.basket and len(ss.basket) >= orders.MAX_LINES:
        st.toast("Basket is full (150 lines max)."); return
    cur = ss.basket.get(item_no, {"qty": 0, "note": ""})
    cur["qty"] = min(9999, int(cur.get("qty") or 0) + qty)
    ss.basket[item_no] = cur
    st.toast("Added to basket")


def open_basket():
    ss = _ss(); ss.view = "basket"; ss.form_started = ss.get("form_started") or time.time()


def set_qty(item_no, k):
    v = parse_int(_ss().get("bq_" + k), 1, 9999)
    if v and item_no in _ss().basket:
        _ss().basket[item_no]["qty"] = v


def set_note(item_no, k):
    from core.validators import clean_text
    if item_no in _ss().basket:
        _ss().basket[item_no]["note"] = clean_text(_ss().get("bn_" + k, ""), 120)


def remove(item_no, k):
    ss = _ss(); ss.basket.pop(item_no, None)
    for p in ("bq_", "bn_"):
        ss.pop(p + k, None)


# ------------------------------------------------------------------ pieces
def card(it, pfx=""):
    k = it["key"]
    try:
        url = store.thumb_url(k)
    except Exception:
        url = None
    img = '<img src="%s" loading="lazy" alt="">' % safe_html(url) if url else '<div class="ph">No photo</div>'
    badge = '<span class="badge ok">Available</span>' if it["status"] == "Available" else '<span class="badge wait">Waiting</span>'
    st.markdown('<div class="it">%s<div><b>%s</b><br>%s<br>%s</div></div>' % (img, safe_html(it["item_no"]), safe_html(it["description"]), badge),
                unsafe_allow_html=True)
    c1, c2 = st.columns([1, 2])
    c1.number_input("Quantity", 1, 9999, 1, key=pfx + "q_" + k, label_visibility="collapsed")
    c2.button("Add to basket", key=pfx + "add_" + k, on_click=add, args=(it["item_no"], pfx + "q_" + k), use_container_width=True)


def tile(path, label):
    """Image + name; the name button is the click target and (via CSS) the whole tile is clickable."""
    try:
        url = store.cat_image_url(path)
    except Exception:
        url = None
    k = item_key("__".join(path))
    img = '<img src="%s" loading="lazy" alt="">' % safe_html(url) if url else '<div class="tph">%s</div>' % safe_html(label[:2].upper())
    with st.container(key="tile_" + k):
        st.markdown('<div class="timg">%s</div>' % img, unsafe_allow_html=True)
        st.button(label, key="tbtn_" + k, on_click=go, args=(path,), use_container_width=True)


def item_list(lst):
    ss = _ss(); total = len(lst); pages = max(1, (total + PAGE - 1) // PAGE)
    ss.page = min(ss.page, pages - 1)
    for it in lst[ss.page * PAGE:(ss.page + 1) * PAGE]:
        card(it)
    if pages > 1:
        a, b, c = st.columns([1, 1, 1])
        a.button("Previous", key="pg_prev", disabled=ss.page == 0, on_click=set_page, args=(ss.page - 1,), use_container_width=True)
        b.markdown("<div style='text-align:center;padding-top:.6rem'>%d / %d</div>" % (ss.page + 1, pages), unsafe_allow_html=True)
        c.button("Next", key="pg_next", disabled=ss.page >= pages - 1, on_click=set_page, args=(ss.page + 1,), use_container_width=True)


def browse(cat):
    ss = _ss()
    sel = livesearch.item_search(cat["payload"], key="ls_customer", placeholder="Type an item number")
    picked = cat["by_no"].get(sel["item_no"]) if sel and sel.get("item_no") else None
    if picked:
        card(picked, "sel_")           # own widget keys: the same item may also appear in the list below
    q = st.text_input("Search", key="q", placeholder="Search by item number or description", label_visibility="collapsed")
    if ss.lastq != q:
        ss.lastq = q; ss.page = 0
    if q.strip():
        res = catalog.search(cat, q)
        st.caption("%d result(s)" % len(res))
        if not res:
            st.info("No items found. Try a shorter part of the item number.")
        item_list(res)
        return
    path = ss.path
    if path:
        c1, c2 = st.columns(2)
        c1.button("Back", key="nav_back", on_click=go, args=(path[:-1],), use_container_width=True)
        c2.button("Home", key="nav_home", on_click=go, args=((),), use_container_width=True)
        st.markdown('<div class="crumb">Home › %s</div>' % " › ".join(safe_html(p) for p in path), unsafe_allow_html=True)
        st.subheader(path[-1])
    else:
        st.subheader("Sections")
    names = catalog.children(cat, path)
    if not cat["items"]:
        st.info("The catalogue is being prepared. Please check back soon.")
    if names:
        with st.container(key="tilegrid"):
            for n in names:
                tile(path + (n,), n)
    if path:
        lst = cat["level"].get(path, [])
        if lst:
            st.markdown("---")
            item_list(lst)


def basket_view(cat, settings):
    ss = _ss()
    st.button("Continue browsing", key="back_browse", on_click=go, args=(ss.path,))
    st.header("Your basket")
    lines = orders.build_lines(ss.basket, cat)
    keep = {l["item_no"] for l in lines}
    for n in [n for n in ss.basket if n not in keep]:
        ss.basket.pop(n, None)
    if not lines:
        st.info("Your basket is empty."); return
    for l in lines:
        k = item_key(l["item_no"])
        ss["bq_" + k] = ss.basket[l["item_no"]]["qty"]
        ss["bn_" + k] = ss.basket[l["item_no"]].get("note", "")
        st.markdown("<b>%s</b><br>%s" % (safe_html(l["item_no"]), safe_html(l["description"])), unsafe_allow_html=True)
        c1, c2 = st.columns([1, 2])
        c1.number_input("Quantity", 1, 9999, key="bq_" + k, on_change=set_qty, args=(l["item_no"], k))
        c2.text_input("Note (optional)", max_chars=120, key="bn_" + k, on_change=set_note, args=(l["item_no"], k))
        st.button("Remove", key="del_" + k, on_click=remove, args=(l["item_no"], k))
        st.markdown("<hr style='margin:.4rem 0'>", unsafe_allow_html=True)
    st.subheader("Send your request")
    with st.form("send_rfq"):
        project = st.text_input("Project name (optional)", max_chars=80)
        name = st.text_input("Your name", max_chars=60)
        phone = st.text_input("Mobile number", max_chars=24, placeholder="0912345678")
        with st.container(key="hp_wrap"):
            hp = st.text_input("Website", key="hp_field")
        st.caption("Your name and phone number are used only to reply to your request. We never publish them.")
        sent = st.form_submit_button("Send RFQ", use_container_width=True)
    if sent:
        ok, msg, order = orders.submit(ss.basket, name, phone, project, ss.sid, common.client_ip(), hp, ss.get("form_started"))
        if not ok:
            st.error(msg); return
        with st.spinner("Preparing your documents..."):
            urls = {}
            for l in order["lines"]:
                u = store.thumb_url(item_key(l["item_no"]))
                if u:
                    urls[l["item_no"]] = u
            try:
                pdf = docs.order_pdf(order, settings, common.logo_bytes(), docs.fetch_thumbs(urls))
            except Exception:
                pdf = None
            xl = docs.order_xlsx(order)
        ss.done = {"id": order["order_id"], "pdf": pdf, "xlsx": xl}
        ss.basket = {}; ss.pop("form_started", None); ss.view = "done"
        st.rerun()


def done_view(settings):
    ss = _ss(); d = ss.get("done")
    if not d:
        ss.view = "browse"; st.rerun()
    st.success("Your request %s was received." % d["id"])
    st.write("We will reply with your price offer on WhatsApp.")
    if settings.get("working_hours_text"):
        st.write("Working hours: " + settings["working_hours_text"])
    if d.get("pdf"):
        st.download_button("Download PDF copy", d["pdf"], file_name="RFQ_%s.pdf" % d["id"], mime="application/pdf", use_container_width=True)
    st.download_button("Download Excel copy", d["xlsx"], file_name="RFQ_%s.xlsx" % d["id"],
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    st.button("Start a new request", key="new_req", on_click=go, args=((),), use_container_width=True)


def restore_basket(cat):
    """Best effort: untrusted localStorage content, re-validated against the catalogue."""
    ss = _ss()
    if ss.get("basket_restored"):
        common.bstore("basket", save=__import__("json").dumps(ss.basket), key="bs")
        return
    val = common.bstore("basket", read=True, key="bs")
    if val is None:
        return
    ss.basket_restored = True
    if val and not ss.basket:
        raw = orders.parse_basket(val)
        lines = orders.build_lines(raw, cat)
        ss.basket = {l["item_no"]: {"qty": l["qty"], "note": l["note"]} for l in lines}
        if ss.basket:
            st.rerun()


def render(settings):
    init()
    try:
        cat = store.public()
    except Exception:
        common.header(settings); common.friendly_error(); return
    common.header(settings)
    ss = _ss()
    if ss.view == "basket":
        basket_view(cat, settings)
    elif ss.view == "done":
        done_view(settings)
    else:
        browse(cat)
    n = len(ss.basket)
    if ss.view == "browse" and n:
        with st.container(key="basketbar"):
            st.button("View basket (%d items)" % n, key="open_basket", on_click=open_basket, use_container_width=True)
    restore_basket(cat)
