"""Store Manager screens. Every function receives a user already verified by staff.guard(user, 'manager')."""
import copy
import io
import json
import os
import time
import zipfile
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import streamlit as st

from core import auth, catalog, docs, imaging, orders, store, notify
from core.ghstore import GhError
from core.security import FAILED_LOGINS
from core.validators import clean_text, normalize_support, safe_html
from . import common, staff

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def ss():
    return st.session_state


def reauth(user, key):
    """Password re-entry for sensitive actions. Returns True only if the password is right."""
    pw = st.text_input("Confirm with your password", type="password", key=key)
    if not pw:
        return False
    if auth.check_password(user, pw):
        return True
    st.error("Wrong password."); return False


def banners(settings):
    try:
        allo = store.list_orders()
    except GhError:
        return
    if any(not o.get("notified") for o in allo):
        st.error("Some orders were not announced to staff alerts.")
        if st.button("Resend notifications", key="resend"):
            st.success("Sent %d." % orders.resend_unnotified())
    pend = None
    try:
        pend = store.get_pending()
    except GhError:
        pass
    pids = set(pend["order_ids"]) if pend else set()
    limit = int(settings.get("export_reminder_days", 9)) * 86400
    now = datetime.now(timezone.utc)
    old = [o for o in allo if o["order_id"] not in pids and
           (now - datetime.fromisoformat(o["created_at"].replace("Z", "+00:00"))).total_seconds() > limit]
    if old:
        st.warning("%d order(s) are older than %s days and not exported yet." % (len(old), settings.get("export_reminder_days", 9)))


# ------------------------------------------------------------------ orders
def screen_all_orders(user, settings):
    if ss().get("flash"):
        st.warning(ss().pop("flash"))
    if ss().get("open_id"):
        staff.order_detail(user, settings); return
    st.header("All Orders")
    flt = st.radio("Show", ["All", "New", "Opened"], horizontal=True, key="ao_f")
    q = st.text_input("Search order number, name or phone", key="ao_q").strip().lower()
    lst = sorted(store.list_orders(), key=lambda o: o["created_at"], reverse=True)
    if flt == "New":
        lst = [o for o in lst if not o.get("opened_by")]
    elif flt == "Opened":
        lst = [o for o in lst if o.get("opened_by")]
    if q:
        lst = [o for o in lst if q in o["order_id"].lower() or q in o["customer"]["name"].lower() or q in o["customer"]["phone"]]
    st.caption("%d order(s)" % len(lst))
    staff.order_rows(lst, user, "all", show_state=True)


# ------------------------------------------------------------------ operators
def screen_operators(user, settings):
    st.header("Manage Operators")
    with st.form("add_op"):
        c1, c2 = st.columns(2)
        un = c1.text_input("Username"); dn = c2.text_input("Display name")
        pw = st.text_input("Temporary password", type="password")
        if st.form_submit_button("Add Operator"):
            ok, msg = auth.add_operator(un, dn, pw)
            st.success("Operator added. They must change the password at first login.") if ok else st.error(msg)
    for u in store.users():
        with st.expander("%s (%s)%s" % (u["display"], u["username"], "" if u.get("active", True) else " - inactive")):
            ok = reauth(user, "ra_" + u["username"])
            npw = st.text_input("New temporary password", type="password", key="np_" + u["username"])
            c1, c2, c3 = st.columns(3)
            if c1.button("Reset password", key="rs_" + u["username"]):
                if ok:
                    good, msg = auth.reset_operator(u["username"], npw); st.success("Reset.") if good else st.error(msg)
                else:
                    st.error("Enter your password first.")
            if c2.button("Deactivate" if u.get("active", True) else "Activate", key="act_" + u["username"]):
                auth.set_operator_active(u["username"], not u.get("active", True)); st.rerun()
            if c3.button("Delete", key="del_op_" + u["username"]):
                if ok:
                    auth.delete_operator(u["username"]); st.rerun()
                else:
                    st.error("Enter your password first.")


# ------------------------------------------------------------------ items import
def screen_items(user, settings):
    st.header("Items")
    items = store.items(); pub = store.public()
    have = {i["key"] for i in pub["items"]} & store.images_index()["thumbs"]
    st.write("%d items · %d with photos · %d without" % (len(items), len(have), len(items) - len(have)))
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", "MY_SHARQ_Items_Template.xlsx"), "rb") as f:
            st.download_button("Download the Excel template", f.read(), file_name="MY_SHARQ_Items_Template.xlsx", mime=XLSX)
    except OSError:
        pass
    up = st.file_uploader("Upload items file (.xlsx or .csv)", type=["xlsx", "csv"], key="imp_file")
    if up is not None and st.button("Check file", key="imp_check"):
        rows, err = catalog.parse_items_file(up.getvalue(), up.name)
        if err:
            st.error(err); ss().pop("imp", None)
        else:
            ss().imp = catalog.validate_import(rows, store.categories())
    rep = ss().get("imp")
    if not rep:
        return
    st.subheader("Report (nothing is saved yet)")
    st.write("Ready rows: %d" % len(rep["ok"]))
    for lbl, v in (("Empty Item No (rows)", rep["empty_no"]), ("Empty description (rows)", rep["empty_desc"]),
                   ("Duplicate Item No (row, item)", rep["dups"]), ("Invalid quantity treated as 0 (row, value)", rep["bad_qty"])):
        if v:
            st.warning("%s: %s%s" % (lbl, v[:20], " ..." if len(v) > 20 else ""))
    decisions = {}
    for t, rws in rep["unknown"].items():
        name = " > ".join(x for x in t if x) or "(empty)"
        opts = ["Create new category", "Skip these rows"] + ["Map to: " + " > ".join(x for x in s if x) for s in rep["suggest"].get(t, [])]
        ch = st.selectbox("Unknown category: %s (%d rows)" % (name, len(rws)), opts, key="unk_" + name)
        decisions[t] = "create" if ch == opts[0] else "skip" if ch == opts[1] else ("map", rep["suggest"][t][opts.index(ch) - 2])
    mode = st.radio("Mode", ["Merge (add new, update existing)", "Replace all (delete items not in the file)"], key="imp_mode")
    ok = True
    if mode.startswith("Replace"):
        st.error("Replace all removes every item that is not in this file.")
        ok = reauth(user, "imp_ra")
    if ok and st.button("Save import", key="imp_save"):
        new_items, cats, s = catalog.apply_import(items, rep, "replace" if mode.startswith("Replace") else "merge", decisions, store.categories())
        store.save_catalog(new_items, cats, "manager", "import")
        ss().pop("imp", None)
        st.success("Added %(added)d · updated %(updated)d · unchanged %(unchanged)d · skipped %(skipped)d · removed %(removed)d" % s)


# ------------------------------------------------------------------ categories
def screen_categories(user, settings):
    st.header("Categories")
    cats = copy.deepcopy(store.categories()); items = store.items()
    with st.form("new_sec"):
        n = st.text_input("New section")
        if st.form_submit_button("Add section"):
            try:
                store.save_catalog(items, catalog.cat_add(cats, (), n), "manager", "category-add"); st.rerun()
            except ValueError as e:
                st.error(str(e))
    sec = st.selectbox("Section", [c["section"] for c in cats], key="ce_s")
    s = next(c for c in cats if c["section"] == sec)
    br = st.selectbox("Branch", ["(none)"] + [b["name"] for b in s["branches"]], key="ce_b")
    path = (sec,)
    sub = "(none)"
    if br != "(none)":
        path = (sec, br)
        b = next(x for x in s["branches"] if x["name"] == br)
        sub = st.selectbox("Sub-branch", ["(none)"] + b["sub_branches"], key="ce_sb")
        if sub != "(none)":
            path = (sec, br, sub)
    st.caption("Selected: " + " > ".join(path))
    new = st.text_input("Name (for add or rename)", key="ce_name")
    c1, c2, c3, c4 = st.columns(4)
    try:
        if len(path) < 3 and c1.button("Add child", key="ce_add"):
            store.save_catalog(items, catalog.cat_add(cats, path, new), "manager", "category-add"); st.rerun()
        if c2.button("Rename", key="ce_ren"):
            cats2, items2 = catalog.cat_rename(cats, copy.deepcopy(items), path, new)
            store.save_catalog(items2, cats2, "manager", "category-rename"); st.rerun()
        if c3.button("Up", key="ce_up"):
            store.save_catalog(items, catalog.cat_move(cats, path, -1), "manager", "category-move"); st.rerun()
        if c4.button("Down", key="ce_dn"):
            store.save_catalog(items, catalog.cat_move(cats, path, 1), "manager", "category-move"); st.rerun()
        st.markdown("---")
        ok = reauth(user, "ce_ra")
        if ok and st.button("Delete selected", key="del_cat"):
            store.save_catalog(items, catalog.cat_delete(cats, items, path), "manager", "category-delete"); st.rerun()
    except ValueError as e:
        st.error(str(e))


# ------------------------------------------------------------------ settings
def screen_settings(user, settings):
    st.header("Settings")
    with st.form("settings"):
        name = st.text_input("Store name", settings["store_name"], max_chars=60)
        sup = st.text_input("Support number (WhatsApp, with country code)", settings["support_number"], placeholder="+21622123456 or 0912345678")
        hours = st.text_input("Working hours text", settings["working_hours_text"], max_chars=120)
        days = st.number_input("Export reminder (days)", 1, 60, int(settings["export_reminder_days"]))
        tz = st.text_input("Timezone", settings["timezone"])
        op = st.slider("Background overlay opacity", 0.0, 1.0, float(settings["overlay_opacity"]), 0.01)
        cap = st.number_input("Maximum orders per hour (all customers)", 5, 1000, int(settings["global_orders_per_hour"]))
        tpl = st.text_area("WhatsApp reply template", settings["whatsapp_reply_template"], height=110,
                           help="Placeholders: {customer_name} {operator_name} {store_name} {order_id}")
        pw = st.text_input("Your password (needed when changing the support number)", type="password")
        go = st.form_submit_button("Save settings", use_container_width=True)
    if go:
        new_sup = ""
        if sup.strip():
            new_sup = normalize_support(sup) or ""
            if not new_sup:
                st.error("Invalid support number."); return
        try:
            ZoneInfo(tz)
        except Exception:
            st.error("Unknown timezone."); return
        if new_sup != settings["support_number"] and not auth.check_password(user, pw):
            st.error("Password required to change the support number."); return
        d = dict(settings, store_name=clean_text(name, 60) or settings["store_name"], support_number=new_sup,
                 working_hours_text=clean_text(hours, 120), export_reminder_days=int(days), timezone=tz,
                 overlay_opacity=float(op), global_orders_per_hour=int(cap), whatsapp_reply_template=tpl[:500])
        store.save_settings(d, "manager"); st.success("Saved."); st.rerun()
    st.subheader("Images")
    for lbl, fn, kind in (("Logo (png/jpg)", "logo.png", "logo"), ("Phone background", "bg-mobile.jpg", "mobile"), ("Desktop background", "bg-desktop.jpg", "desktop")):
        f = st.file_uploader(lbl, type=["png", "jpg", "jpeg", "webp"], key="up_" + kind)
        if f is not None and st.button("Save " + lbl, key="sv_" + kind):
            try:
                data = imaging.process_logo(f.getvalue()) if kind == "logo" else imaging.process_background(f.getvalue(), kind)
                store.put_asset(fn, data, "manager"); st.success("Saved. It appears within about a minute.")
            except imaging.ImageRejected as e:
                st.error(str(e))
    st.caption("Alert channels configured: " + (", ".join(notify.channels()) or "none (add NTFY_TOPIC or EMAIL_* secrets)"))
    if st.button("Send test alert", key="tg_test"):
        st.success("Sent.") if notify.send_test() else st.error("No alert was delivered. Check the alert secrets.")


# ------------------------------------------------------------------ export / purge / backup / activity
def screen_export(user, settings):
    st.header("Export and delete orders")
    allo = sorted(store.list_orders(), key=lambda o: o["created_at"])
    tz = settings["timezone"]
    if not allo:
        st.info("There are no orders.")
    else:
        st.write("All orders are pre-selected. Untick any order you want to keep.")
        rows = [{"Export": True, "Order": o["order_id"], "Date": docs.local_time(o["created_at"], tz), "Customer": o["customer"]["name"],
                 "Lines": len(o["lines"]), "State": ("opened by " + (o.get("opened_by_display") or "")) if o.get("opened_by") else "new"} for o in allo]
        ed = st.data_editor(rows, disabled=["Order", "Date", "Customer", "Lines", "State"], hide_index=True, key="exp_tbl", use_container_width=True)
        chosen = [r["Order"] for r in ed if r["Export"]] if not hasattr(ed, "to_dict") else [r["Order"] for r in ed.to_dict("records") if r["Export"]]
        if chosen and st.button("Generate export file", key="exp_go", use_container_width=True):
            now = datetime.now(ZoneInfo(tz)); batch = now.strftime("%Y%m%d-%H%M")
            fname = "MySharq_Orders_%s_%s.xlsx" % (batch, batch[-4:])
            store.set_pending({"batch": batch, "time": now.isoformat(), "order_ids": chosen, "file": fname}, "manager")
            st.success("Export ready. Download it, check it, then delete below.")
    pend = store.get_pending()
    if pend:
        by = {o["order_id"]: o for o in allo}
        sel = [by[i] for i in pend["order_ids"] if i in by]
        st.subheader("Pending export: %s (%d orders)" % (pend["batch"], len(pend["order_ids"])))
        st.download_button("Download export file", docs.export_xlsx(sel, tz), file_name=pend["file"], mime=XLSX, use_container_width=True)
        st.warning("Save the exported file to your phone or Google Drive before deleting. Deletion is final.")
        ok = reauth(user, "purge_ra")
        if ok and st.button("Delete exported orders", key="del_purge", use_container_width=True):
            n = store.purge_pending("manager"); st.success("Deleted %d orders." % n); st.rerun()
    else:
        st.button("Delete exported orders", key="del_purge_off", disabled=True)
        st.caption("Generate an export first. Nothing can be deleted without an export.")


def screen_activity(user, settings):
    st.header("Activity")
    st.caption("Latest changes (who did what). No customer data is shown.")
    try:
        for c in store.activity(40):
            st.text("%s  %s" % (c["date"][:16].replace("T", " "), c["message"].split("\n")[0][:90]))
    except GhError:
        st.error("Could not load the activity log.")
    st.subheader("Latest failed logins (this session of the server)")
    for t, u in reversed(list(FAILED_LOGINS)):
        st.text("%s  %s" % (time.strftime("%H:%M:%S", time.localtime(t)), u[:30]))


def screen_backup(user, settings):
    st.header("Backup")
    st.write("Downloads items, categories, settings and the Operator list. Password hashes and secrets are NOT included.")
    ok = reauth(user, "bk_ra")
    if ok:
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("items.json", json.dumps({"items": store.items()}, ensure_ascii=False, indent=1))
            z.writestr("categories.json", json.dumps({"categories": store.categories()}, ensure_ascii=False, indent=1))
            z.writestr("settings.json", json.dumps(settings, ensure_ascii=False, indent=1))
            z.writestr("operators.json", json.dumps([{k: u[k] for k in ("username", "display", "active")} for u in store.users()], indent=1))
        st.download_button("Download backup (ZIP)", b.getvalue(), file_name="mysharq_backup.zip", mime="application/zip")


SCREENS = {"All Orders": screen_all_orders, "Operators": screen_operators, "Items": screen_items, "Categories": screen_categories,
           "Settings": screen_settings, "Export": screen_export, "Backup": screen_backup, "Activity": screen_activity}
