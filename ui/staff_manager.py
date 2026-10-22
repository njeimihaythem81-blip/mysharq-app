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
from . import common, livesearch, staff

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


# ------------------------------------------------------------------ items
def pick_path(prefix, cats, init=("", "", "")):
    """Section / Branch / Sub-branch pickers fed from the category tree (no typing mistakes)."""
    secs = [c["section"] for c in cats]
    sec = st.selectbox("Section", secs, index=secs.index(init[0]) if init[0] in secs else 0, key=prefix + "_s")
    sc = next(c for c in cats if c["section"] == sec)
    brs = [""] + [b["name"] for b in sc["branches"]]
    br = st.selectbox("Branch", brs, index=brs.index(init[1]) if init[1] in brs else 0, format_func=lambda x: x or "(none)", key=prefix + "_b")
    subs = [""]
    if br:
        subs += next(b for b in sc["branches"] if b["name"] == br)["sub_branches"]
    sb = st.selectbox("Sub-branch", subs, index=subs.index(init[2]) if init[2] in subs else 0, format_func=lambda x: x or "(none)", key=prefix + "_sb")
    return sec, br, sb


def screen_items(user, settings):
    st.header("Items")
    items = store.items(); pub = store.public()
    have = {i["key"] for i in pub["items"]} & store.images_index()["thumbs"]
    st.write("%d items · %d with photos · %d without" % (len(items), len(have), len(items) - len(have)))
    t_imp, t_add, t_edit, t_xl = st.tabs(["Import", "Add item", "Edit / delete", "Excel"])
    with t_imp:
        items_import(user, items)
    with t_add:
        cats = store.categories()
        sec, br, sb = pick_path("add", cats)
        with st.form("add_item", clear_on_submit=True):
            no = st.text_input("Item No", max_chars=80)
            desc = st.text_input("Description", max_chars=300)
            qty = st.number_input("Quantity (stock)", 0, 10_000_000, 0)
            if st.form_submit_button("Add item", use_container_width=True):
                new, err = catalog.item_add(items, no, desc, qty, sec, br, sb, cats)
                if err:
                    st.error(err)
                else:
                    store.save_catalog(new, cats, "manager", "item-add"); st.success("Added. Prepare a new Excel file to include it.")
    with t_edit:
        items_edit(user, items)
    with t_xl:
        st.write("Download the full current list: sheet **Items** (6 columns) and sheet **Categories** (the tree, in order).")
        st.caption("Edit this file, then upload it in Import with Merge. Always download the newest file before editing.")
        if st.button("Prepare Excel file", key="xl_prep", use_container_width=True):
            ss().items_xlsx = docs.items_xlsx(store.items(), store.categories(), store.catimages())
        if ss().get("items_xlsx"):
            st.download_button("Download items Excel", ss().items_xlsx, file_name="MySharq_Items.xlsx", mime=XLSX, use_container_width=True)
        try:
            with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", "MY_SHARQ_Items_Template.xlsx"), "rb") as f:
                st.download_button("Download the empty template", f.read(), file_name="MY_SHARQ_Items_Template.xlsx", mime=XLSX)
        except OSError:
            pass


def items_edit(user, items):
    from core.validators import item_key
    cats = store.categories()
    sel = livesearch.item_search(store.public()["payload"], key="ls_edit", placeholder="Type an item number")
    chosen = livesearch.new_selection("ls_edit", sel)
    if chosen:
        ss()["ei_q"] = chosen
    q = st.text_input("Or find an item by words", key="ei_q")
    if not q.strip():
        st.caption("Type part of the Item No or description."); return
    hits = catalog.search(store.public(), q)[:30]
    if not hits:
        st.info("No match."); return
    desc_of = {h["item_no"]: h["description"] for h in hits}
    pick = st.selectbox("Item", [h["item_no"] for h in hits], format_func=lambda n: "%s - %s" % (n, desc_of[n][:60]), key="ei_pick")
    it = catalog.find_item(items, pick)
    if not it:
        return
    k = item_key(it["item_no"])
    sec, br, sb = pick_path("ed_" + k, cats, (it["section"], it.get("branch", ""), it.get("sub_branch", "")))
    desc = st.text_input("Description", it["description"], max_chars=300, key="ed_d_" + k)
    qty = st.number_input("Quantity (stock)", 0, 10_000_000, int(it.get("qty", 0)), key="ed_q_" + k)
    if st.button("Save changes", key="ed_save_" + k, use_container_width=True):
        new, err = catalog.item_update(items, it["item_no"], desc, qty, sec, br, sb, cats)
        if err:
            st.error(err)
        else:
            store.save_catalog(new, cats, "manager", "item-edit"); st.success("Saved."); st.rerun()
    st.markdown("---")
    if reauth(user, "ed_ra_" + k) and st.button("Delete this item", key="del_item_" + k, use_container_width=True):
        new, err = catalog.item_delete(items, it["item_no"])
        if err:
            st.error(err)
        else:
            store.save_catalog(new, cats, "manager", "item-delete", backup=True); st.success("Deleted (a backup was saved)."); st.rerun()


def items_import(user, items):
    up = st.file_uploader("Upload items file (.xlsx or .csv)", type=["xlsx", "csv"], key="imp_file")
    if up is not None and st.button("Check file", key="imp_check"):
        data = up.getvalue()
        rows, err = catalog.parse_items_file(data, up.name)
        if err:
            st.error(err); ss().pop("imp", None)
        else:
            ss().imp = catalog.validate_import(rows, store.categories())
            ss().imp_cats = catalog.parse_categories_sheet(data, up.name)
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
    mode = st.radio("Mode", ["Merge (add new, update existing, keep the rest)", "Replace all (delete items not in the file)"], key="imp_mode")
    replace = mode.startswith("Replace")
    new_items, cats2, s = catalog.apply_import(items, rep, "replace" if replace else "merge", decisions, store.categories())
    cats3, from_sheet = catalog.merge_category_paths(cats2, ss().get("imp_cats", []))
    st.info(("If you save: add %(added)d · update %(updated)d · unchanged %(unchanged)d · skipped %(skipped)d · remove %(removed)d" % s)
            + " · new categories: %d" % (from_sheet + len(cats2) - len(store.categories())))
    st.caption("A backup of the current data is saved automatically before the import.")
    ok = True
    if replace:
        st.error("Replace all removes every item that is not in this file.")
        ok = reauth(user, "imp_ra")
    if ok and st.button("Save import", key="imp_save", use_container_width=True):
        store.save_catalog(new_items, cats3, "manager", "import", backup=True)
        ss().pop("imp", None); ss().pop("imp_cats", None)
        st.success("Saved. Added %(added)d · updated %(updated)d · unchanged %(unchanged)d · skipped %(skipped)d · removed %(removed)d" % s)


# ------------------------------------------------------------------ categories (+ images for every level)
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
    if br != "(none)":
        path = (sec, br)
        b = next(x for x in s["branches"] if x["name"] == br)
        sub = st.selectbox("Sub-branch", ["(none)"] + b["sub_branches"], key="ce_sb")
        if sub != "(none)":
            path = (sec, br, sub)
    st.caption("Selected: " + " > ".join(path))
    cur = None
    try:
        cur = store.cat_image_url(path)
    except Exception:
        pass
    if cur:
        st.image(cur, width=140)
    else:
        st.caption("No image yet for this level.")
    f = st.file_uploader("Image for this level (JPEG, PNG or WebP)", type=["jpg", "jpeg", "png", "webp"], key="ci_up_" + catalog.path_id(path))
    c1, c2 = st.columns(2)
    if f is not None and c1.button("Save image", key="ci_save", use_container_width=True):
        try:
            store.set_cat_images({path: imaging.process_cat_image(f.getvalue())}, "manager"); st.success("Saved. It appears within about a minute."); st.rerun()
        except imaging.ImageRejected as e:
            st.error(str(e))
    if cur and c2.button("Remove image", key="del_ci", use_container_width=True):
        store.remove_cat_image(path, "manager"); st.rerun()
    new = st.text_input("Name (for add or rename)", key="ce_name")
    c1, c2, c3, c4 = st.columns(4)
    try:
        if len(path) < 3 and c1.button("Add child", key="ce_add"):
            store.save_catalog(items, catalog.cat_add(cats, path, new), "manager", "category-add"); st.rerun()
        if c2.button("Rename", key="ce_ren"):
            cats2, items2 = catalog.cat_rename(cats, copy.deepcopy(items), path, new)
            store.save_catalog(items2, cats2, "manager", "category-rename", backup=True,
                               imgmap=catalog.remap_image_keys(dict(store.catimages()), path, clean_text(new, 80))); st.rerun()
        if c3.button("Up", key="ce_up"):
            store.save_catalog(items, catalog.cat_move(cats, path, -1), "manager", "category-move"); st.rerun()
        if c4.button("Down", key="ce_dn"):
            store.save_catalog(items, catalog.cat_move(cats, path, 1), "manager", "category-move"); st.rerun()
        st.markdown("---")
        ok = reauth(user, "ce_ra")
        if ok and st.button("Delete selected", key="del_cat"):
            cats2 = catalog.cat_delete(cats, items, path)
            store.save_catalog(items, cats2, "manager", "category-delete", backup=True)
            store.remove_cat_image(path, "manager"); st.rerun()
    except ValueError as e:
        st.error(str(e))
    category_images_zip(settings)


def category_images_zip(settings):
    st.markdown("---")
    st.subheader("Images for all levels (ZIP)")
    st.write("Name each image after its path, then put all images in one ZIP:  "
             "`SECTION.jpg`, `SECTION__BRANCH.jpg`, `SECTION__BRANCH__SUB.jpg` (two underscores between levels).")
    cats = store.categories()
    rows = catalog.image_names_table(cats, store.catimages())
    st.download_button("Download the list of image file names (Excel)", docs.simple_xlsx(
        ["Level", "Section", "Branch", "Sub-Branch", "File name", "Has image"], rows), file_name="MySharq_Image_Names.xlsx", mime=XLSX)
    z = st.file_uploader("ZIP of images", type=["zip"], key="ci_zip")
    if z is not None and st.button("Check ZIP", key="ci_zip_check"):
        entries, errs = catalog.read_zip_images(z.getvalue())
        matched, unmatched = catalog.match_zip_images(entries, cats)
        ss().ci_zip = {"matched": matched, "unmatched": unmatched, "errs": errs}
    r = ss().get("ci_zip")
    if r:
        st.write("Matched images: **%d**" % len(r["matched"]))
        if r["unmatched"]:
            st.warning("Not matched (name does not fit any level): " + ", ".join(r["unmatched"][:30]) + (" ..." if len(r["unmatched"]) > 30 else ""))
        for e in r["errs"][:10]:
            st.caption(e)
        if r["matched"] and st.button("Apply images", key="ci_zip_apply", use_container_width=True):
            ready, bad = {}, []
            for p, data in r["matched"].items():
                try:
                    ready[p] = imaging.process_cat_image(data)
                except imaging.ImageRejected:
                    bad.append(catalog.expected_filename(p))
            if ready:
                store.set_cat_images(ready, "manager")
            ss().pop("ci_zip", None)
            st.success("Applied %d image(s)." % len(ready) + ((" Rejected: " + ", ".join(bad)) if bad else ""))


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
    st.markdown("---")
    st.subheader("Automatic backups")
    st.caption("Saved automatically before every import, item delete, category rename or delete. The newest 10 are kept.")
    names = store.list_backups()
    if not names:
        st.info("No automatic backups yet."); return
    pick = st.selectbox("Backup", names, key="bk_pick")
    try:
        d = store.read_backup(pick)
        st.write("Contains %d items and %d sections (saved %s)." % (len(d.get("items", [])), len(d.get("categories", [])), d.get("time", "")))
    except GhError:
        st.error("Could not read this backup."); return
    st.warning("Restoring replaces the current items and categories with this backup. The current data is backed up first.")
    if ok and st.button("Restore this backup", key="del_restore", use_container_width=True):
        store.restore_backup(pick, "manager"); st.success("Restored."); st.rerun()
    elif not ok:
        st.caption("Enter your password above to enable restoring.")


SCREENS = {"All Orders": screen_all_orders, "Operators": screen_operators, "Items": screen_items, "Categories": screen_categories,
           "Settings": screen_settings, "Export": screen_export, "Backup": screen_backup, "Activity": screen_activity}
