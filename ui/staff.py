"""Staff area: login, first-run setup, Operator screens (shared with Store Manager)."""
import time
from datetime import datetime, timezone

import streamlit as st

from core import auth, catalog, docs, imaging, orders, store
from core.ghstore import GhError
from core.validators import display_phone, item_key, safe_html, search_norm
from . import common, livesearch

OP_MENU = ["Orders", "My Orders", "Photos", "Leaderboard", "Account"]
MGR_MENU = ["All Orders", "Operators", "Items", "Categories", "Training", "Customers", "Settings", "Export", "Backup", "Photos", "Leaderboard", "Activity", "Account"]


def ss():
    return st.session_state


def label(user):
    return "manager" if user["role"] == "manager" else "op:" + user["id"]


def guard(user, role=None):
    """Central server-side role check used by EVERY staff screen. Fails closed."""
    if not user:
        st.stop()
    if role and user["role"] != role:
        st.error("Not allowed."); st.stop()
    return user


def fresh_user():
    """Re-verify the session token on every run (signature, expiry, active flag, token_version)."""
    tok = ss().get("token")
    u = auth.session_user(tok) if tok else None
    if not u:
        ss().pop("token", None); ss().pop("user", None)
        return None
    ss().user = u
    return u


# ------------------------------------------------------------------ login / setup
def login_screen(settings):
    ip = common.client_ip()
    try:
        m = store.manager(fresh=True)
    except GhError:
        st.error("The service is temporarily unavailable. Please try again in a moment."); return
    if m is None:
        st.subheader("First-time setup")
        st.write("Create the Store Manager password. You need the setup code from your Secrets.")
        with st.form("setup"):
            code = st.text_input("Setup code", type="password")
            pw = st.text_input("New password (12+ characters)", type="password")
            cf = st.text_input("Confirm password", type="password")
            go = st.form_submit_button("Create Store Manager")
        if go:
            ok, msg = auth.setup_manager(code, pw, cf, ip)
            st.success("Done. You can now sign in as 'manager'.") if ok else st.error(msg)
        return
    st.subheader("Staff login")
    with st.form("login"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        go = st.form_submit_button("Sign in", use_container_width=True)
    if go:
        ok, msg, tok, user = auth.login(u, p, ip)
        if ok:
            ss().token = tok; ss().user = user; ss().save_token = tok
            st.rerun()
        else:
            st.error(msg)


def force_change(user):
    st.warning("Please choose a new password before continuing.")
    with st.form("force_pw"):
        old = st.text_input("Temporary password", type="password")
        new = st.text_input("New password", type="password")
        go = st.form_submit_button("Change password")
    if go:
        ok, msg = auth.change_password(user, old, new)
        if ok:
            st.success("Password changed. Please sign in again."); ss().pop("token", None); ss().pop("user", None); ss().clear_token = True
        else:
            st.error(msg)


# ------------------------------------------------------------------ orders
def waiting(o):
    try:
        d = datetime.fromisoformat(o["created_at"].replace("Z", "+00:00"))
        m = int((datetime.now(timezone.utc) - d).total_seconds() // 60)
        return "%dm" % m if m < 120 else "%dh" % (m // 60) if m < 2880 else "%dd" % (m // 1440)
    except Exception:
        return ""


def open_order(oid):
    u = fresh_user()
    if not u:
        return
    o = store.get_order(oid)
    if not o:
        ss().flash = "Order not found."; return
    if o.get("opened_by"):
        if u["role"] == "manager" or o["opened_by"] == u["id"]:
            ss().open_id = oid
        else:
            ss().flash = "Already opened by %s." % o.get("opened_by_display", "another operator")
        return
    won, o2 = store.claim_order(oid, u["id"], u["display"], label(u))
    if won or (o2 and o2.get("opened_by") == u["id"]):
        ss().open_id = oid
    else:
        ss().flash = "Already opened by %s." % ((o2 or {}).get("opened_by_display") or "another operator")


def close_order():
    ss().open_id = None


def order_rows(lst, user, key, show_state=False):
    if not lst:
        st.info("Nothing here."); return
    for o in lst:
        st.markdown("**%s** · %s · %d lines · %s%s" % (o["order_id"], safe_html(o["customer"]["name"]), len(o["lines"]), waiting(o),
                    (" · " + ("opened by %s" % safe_html(o.get("opened_by_display") or "")) if o.get("opened_by") else " · NEW") if show_state else ""),
                    unsafe_allow_html=True)
        st.button("Open", key="open_%s_%s" % (key, o["order_id"]), on_click=open_order, args=(o["order_id"],))


def order_detail(user, settings):
    o = store.get_order(ss().open_id)
    if not o:
        st.error("Order not found."); ss().open_id = None; return
    if user["role"] != "manager" and o.get("opened_by") != user["id"]:
        st.error("Not allowed."); ss().open_id = None; return
    st.button("Back to list", key="close_order", on_click=close_order)
    st.subheader(o["order_id"])
    st.markdown("**Customer:** %s<br>**Phone:** %s<br>%s" % (safe_html(o["customer"]["name"]), display_phone(o["customer"]["phone"]),
                ("**Project:** " + safe_html(o["project_name"])) if o.get("project_name") else "") +
                ("<br>**Account:** " + safe_html(o["account"]) if o.get("account") else ""), unsafe_allow_html=True)
    op_name = o.get("opened_by_display") or user["display"]
    st.link_button("Reply on WhatsApp", orders.whatsapp_link(o, op_name, settings), use_container_width=True)
    for l in o["lines"]:
        u = None
        try:
            u = store.thumb_url(item_key(l["item_no"]))
        except Exception:
            pass
        img = '<img src="%s" loading="lazy" alt="">' % safe_html(u) if u else '<div class="ph">No photo</div>'
        note = "<br><i>Note: %s</i>" % safe_html(l["note"]) if l.get("note") else ""
        st.markdown('<div class="it">%s<div><b>%s</b> × %d<br>%s%s</div></div>' % (img, safe_html(l["item_no"]), l["qty"], safe_html(l["description"]), note),
                    unsafe_allow_html=True)
    st.download_button("Download Excel", docs.order_xlsx(o), file_name="RFQ_%s.xlsx" % o["order_id"],
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    k = "pdf_" + o["order_id"]
    if st.button("Prepare PDF", key="prep_" + o["order_id"], use_container_width=True):
        urls = {l["item_no"]: store.thumb_url(item_key(l["item_no"])) for l in o["lines"]}
        ss()[k] = docs.order_pdf(o, settings, common.logo_bytes(), docs.fetch_thumbs({a: b for a, b in urls.items() if b}))
    if ss().get(k):
        st.download_button("Download PDF", ss()[k], file_name="RFQ_%s.pdf" % o["order_id"], mime="application/pdf", use_container_width=True)


def screen_orders(user, settings):
    if ss().get("flash"):
        st.warning(ss().pop("flash"))
    if ss().get("open_id"):
        order_detail(user, settings); return
    allo = store.list_orders()
    st.header("Orders")
    order_rows(sorted([o for o in allo if not o.get("opened_by")], key=lambda o: o["created_at"]), user, "new")


def screen_my_orders(user, settings):
    if ss().get("open_id"):
        order_detail(user, settings); return
    st.header("My Orders")
    mine = [o for o in store.list_orders() if o.get("opened_by") == user["id"]]
    order_rows(sorted(mine, key=lambda o: o["created_at"], reverse=True), user, "mine")


# ------------------------------------------------------------------ photos / leaderboard / account
def pick(item_no):
    ss().photo_item = item_no


def screen_photos(user, settings):
    st.header("Photos")
    pub = store.public()
    keys = {i["key"] for i in pub["items"]}
    have = keys & store.images_index()["thumbs"]
    st.progress(len(have) / max(1, len(keys)), text="%d of %d items have photos" % (len(have), len(keys)))
    sel = ss().get("photo_item")
    if sel and sel in pub["by_no"]:
        it = pub["by_no"][sel]
        st.subheader(it["item_no"]); st.write(it["description"])
        cam = st.camera_input("Take a photo", key="cam_" + it["key"])
        up = st.file_uploader("Or choose a photo", type=["jpg", "jpeg", "png", "webp"], key="up_" + it["key"])
        f = cam or up
        if f is not None:
            st.image(f, width=220)
            if st.button("Save photo", key="save_photo", use_container_width=True):
                try:
                    t, full = imaging.process_photo(f.getvalue())
                    earned = store.save_photo(it["item_no"], t, full, label(user))
                    st.success("Saved. +1 point!" if earned else "Photo replaced.")
                    ss().photo_item = None
                    st.rerun()
                except imaging.ImageRejected as e:
                    st.error(str(e))
                except GhError:
                    st.error("Could not save the photo right now. Please try again.")
        st.button("Back to list", key="photo_back", on_click=pick, args=(None,))
        return
    sel = livesearch.item_search(pub["payload"], key="ls_photos", placeholder="Type an item number")
    chosen = livesearch.new_selection("ls_photos", sel)
    if chosen and chosen in pub["by_no"]:
        ss().photo_item = chosen
        st.rerun()
    q = st.text_input("Or search by words", placeholder="Search by description", key="photo_q")
    only = st.checkbox("Only items without a photo", value=True, key="photo_only")
    pool = catalog.smart_search(pub, q)[0] if q.strip() else pub["items"]
    if only:
        pool = [i for i in pool if i["key"] not in have]
    page = ss().setdefault("photo_page", 0)
    pages = max(1, (len(pool) + 14) // 15); page = min(page, pages - 1)
    for it in pool[page * 15:(page + 1) * 15]:
        c1, c2 = st.columns([3, 1])
        c1.markdown("**%s**<br>%s" % (safe_html(it["item_no"]), safe_html(it["description"])), unsafe_allow_html=True)
        c2.button("Select", key="sel_" + it["key"], on_click=pick, args=(it["item_no"],))
    if pages > 1:
        a, b = st.columns(2)
        if a.button("Previous", disabled=page == 0, key="pp"): ss().photo_page = page - 1; st.rerun()
        if b.button("Next", disabled=page >= pages - 1, key="pn"): ss().photo_page = page + 1; st.rerun()


def screen_leaderboard(user, settings):
    st.header("Operator Leaderboard" if user["role"] == "manager" else "My points")
    pts = store.points(settings.get("leaderboard_reset_at"))
    names = {u["username"]: u["display"] for u in store.users()}
    if user["role"] != "manager":
        p = pts.get(user["id"], 0)
        st.metric("Points", p); st.metric("Stars", p // 100)
        st.caption("%d more point(s) to your next star." % (100 - p % 100)); return
    rows = sorted(pts.items(), key=lambda x: -x[1])
    for i, (u, p) in enumerate(rows, 1):
        st.write("%d. %s: %d points, %d star(s)" % (i, names.get(u, u), p, p // 100))
    if not rows:
        st.info("No points yet.")
    if rows:
        st.download_button("Export leaderboard", docs.simple_xlsx(["Operator", "Points", "Stars"], [(names.get(u, u), p, p // 100) for u, p in rows]),
                           file_name="leaderboard.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if st.checkbox("I understand: reset the leaderboard", key="lb_ok") and st.button("Reset leaderboard", key="del_lb"):
        s = dict(settings); s["leaderboard_reset_at"] = int(time.time()); store.save_settings(s, "manager"); st.rerun()


def screen_account(user, settings):
    st.header("Account")
    st.write("Signed in as **%s** (%s)" % (safe_html(user["display"]), "Store Manager" if user["role"] == "manager" else "Operator"))
    with st.form("chpw"):
        old = st.text_input("Current password", type="password")
        new = st.text_input("New password", type="password")
        go = st.form_submit_button("Change password")
    if go:
        ok, msg = auth.change_password(user, old, new)
        if ok:
            st.success("Password changed. Please sign in again."); ss().pop("token", None); ss().pop("user", None); ss().clear_token = True
        else:
            st.error(msg)


def logout():
    u = ss().get("user")
    try:
        if u:
            auth.logout(u)
    except Exception:
        pass
    ss().pop("token", None); ss().pop("user", None); ss().clear_token = True; ss().open_id = None


# ------------------------------------------------------------------ entry
def render(settings):
    from . import staff_manager
    st.button("Back to the store", key="to_store", on_click=lambda: ss().update(view="browse"))
    # browser-stored session (best effort)
    if "token" not in ss():
        v = common.bstore("session", read=True, key="ss_read")
        if v:
            if auth.session_user(v):
                ss().token = v
    if ss().pop("clear_token", False):
        common.bstore("session", clear=True, key="ss_clear")
    user = fresh_user()
    if not user:
        st.header("Staff")
        login_screen(settings); common.footer(settings); return
    if ss().pop("save_token", None):
        common.bstore("session", save=ss().token, key="ss_save")
    if user.get("must_change"):
        force_change(user); return
    st.caption("%s · %s" % (user["display"], "Store Manager" if user["role"] == "manager" else "Operator"))
    if user["role"] == "manager":
        staff_manager.banners(settings)
    menu = MGR_MENU if user["role"] == "manager" else OP_MENU
    choice = st.radio("Menu", menu, horizontal=True, key="menu", label_visibility="collapsed")
    if choice != ss().get("last_menu"):
        ss().last_menu = choice; ss().open_id = None
    try:
        if user["role"] == "manager" and choice in staff_manager.SCREENS:
            staff_manager.SCREENS[choice](guard(user, "manager"), settings)
        elif choice in ("Orders",):
            screen_orders(guard(user), settings)
        elif choice == "My Orders":
            screen_my_orders(guard(user), settings)
        elif choice == "Photos":
            screen_photos(guard(user), settings)
        elif choice == "Leaderboard":
            screen_leaderboard(guard(user), settings)
        elif choice == "Account":
            screen_account(guard(user), settings)
    except GhError as e:
        st.error("Storage error: %s" % e)
    st.button("Sign out", key="signout", on_click=logout)
    common.footer(settings)
