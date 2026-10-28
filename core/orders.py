"""Order submission: server-side validation, rate limits, line rebuilding from the catalogue."""
import json
import time
from datetime import datetime, timezone

from . import notify, store
from .security import LIMITER
from .validators import clean_text, new_order_id, normalize_phone, parse_int, valid_name

MAX_LINES = 150
MAX_PAYLOAD = 100 * 1024


def parse_basket(raw):
    """Untrusted JSON (e.g. from localStorage) -> {item_no: {'qty': int, 'note': str}} (shape only)."""
    if not raw or len(raw) > 100_000:
        return {}
    try:
        d = json.loads(raw)
    except ValueError:
        return {}
    out = {}
    if isinstance(d, dict):
        for k, v in list(d.items())[:MAX_LINES]:
            if isinstance(v, dict):
                out[str(k)[:80]] = {"qty": v.get("qty"), "note": v.get("note", "")}
    return out


def build_lines(basket, pub):
    """Rebuild lines from the SERVER catalogue; unknown items and bad quantities are dropped."""
    lines = []
    for item_no, e in basket.items():
        it = pub["by_no"].get(item_no)
        qty = parse_int(e.get("qty"), 1, 9999)
        if not it or qty is None:
            continue
        lines.append({"item_no": it["item_no"], "description": it["description"], "section": it["section"],
                      "branch": it["branch"], "sub_branch": it["sub_branch"], "qty": qty,
                      "note": clean_text(e.get("note", ""), 120)})
        if len(lines) >= MAX_LINES:
            break
    return lines


def submit(basket, name, phone, project, session_id, ip, honeypot, form_started, now=None, account=None):
    """-> (ok, message, order|None). Generic messages only."""
    now = now if now is not None else time.time()
    if honeypot or (form_started and now - form_started < 3):
        return False, "Please try again.", None
    nm, ph = valid_name(name), normalize_phone(phone)
    if not nm:
        return False, "Please enter your name (2 to 60 characters).", None
    if not ph:
        return False, "Invalid number. Enter a Libyan mobile number, for example 0912345678.", None
    pub = store.public()
    lines = build_lines(basket, pub)
    if not lines:
        return False, "Your basket is empty.", None
    s = store.settings()
    if LIMITER.count("s:" + session_id, 30, now) >= 1:
        return False, "Please wait a moment before sending another request.", None
    if LIMITER.count("ip:" + ip, 3600, now) >= 5 or LIMITER.count("ph:" + ph, 3600, now) >= 5:
        return False, "Too many requests. Please try again later.", None
    if LIMITER.count("global", 3600, now) >= int(s.get("global_orders_per_hour", 60)):
        return False, "Service busy, please try again later.", None
    order = {"order_id": new_order_id(), "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "customer": {"name": nm, "phone": ph}, "project_name": clean_text(project, 80), "lines": lines,
             "opened_by": None, "opened_by_display": None, "opened_at": None, "notified": False}
    if account:
        order["account"] = clean_text(account, 40)
    if len(json.dumps(order)) > MAX_PAYLOAD:
        return False, "The order is too large.", None
    try:
        store.create_order(order)
    except Exception:
        return False, "We could not save your request. Your basket is kept, please try again.", None
    for k in ("s:" + session_id, "ip:" + ip, "ph:" + ph, "global"):
        LIMITER.hit(k, now)
    ok = False
    try:
        ok = notify.notify_new_order(order["order_id"], nm, len(lines))
        if ok:
            store.mark_notified(order["order_id"])
            order["notified"] = True
    except Exception:
        pass
    return True, "ok", order


def resend_unnotified():
    n = 0
    for o in store.list_orders():
        if not o.get("notified"):
            if notify.notify_new_order(o["order_id"], o["customer"]["name"], len(o["lines"])):
                store.mark_notified(o["order_id"]); n += 1
    return n


def whatsapp_link(order, operator_name, settings):
    from urllib.parse import quote
    from .validators import wa_digits
    t = settings.get("whatsapp_reply_template", store.DEFAULT_SETTINGS["whatsapp_reply_template"])
    msg = t.format_map(_Safe(customer_name=order["customer"]["name"], operator_name=operator_name,
                            store_name=settings.get("store_name", ""), order_id=order["order_id"]))
    return "https://wa.me/%s?text=%s" % (wa_digits(order["customer"]["phone"]), quote(msg))


class _Safe(dict):
    def __missing__(self, k):
        return "{" + k + "}"
