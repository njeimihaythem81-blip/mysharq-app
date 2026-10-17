"""Staff alerts. Channels (any combination, all free): ntfy push, e-mail (SMTP), Telegram (optional).
PLAIN TEXT only, never the customer's phone number, aggregated to avoid flooding."""
import smtplib
import threading
import time
from email.message import EmailMessage

import requests

from . import config
from .validators import clean_text

_lock = threading.Lock()
_last_sent = 0.0
_pending = []
_timer = None
MIN_GAP = 30


# ---------------------------------------------------------------- channels
def channels():
    out = []
    if _val("NTFY_TOPIC"):
        out.append("ntfy")
    if _val("EMAIL_USER") and _val("EMAIL_APP_PASSWORD") and _val("EMAIL_TO"):
        out.append("email")
    if _val("TELEGRAM_BOT_TOKEN") and config.chat_ids():
        out.append("telegram")
    return out


def _val(k):
    v = str(config.get(k, "") or "").strip()
    return "" if (not v or "REPLACE" in v) else v


def _ntfy(title, text):
    server = (_val("NTFY_SERVER") or "https://ntfy.sh").rstrip("/")
    headers = {"Title": title.encode("ascii", "ignore").decode() or "MY SHARQ", "Priority": "high", "Tags": "bell"}
    if _val("NTFY_TOKEN"):
        headers["Authorization"] = "Bearer " + _val("NTFY_TOKEN")
    if _val("APP_URL").startswith("https://"):
        headers["Click"] = _val("APP_URL")
    for attempt in range(3):
        try:
            r = requests.post("%s/%s" % (server, _val("NTFY_TOPIC")), data=text[:3500].encode("utf-8"), headers=headers, timeout=10)
            if r.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.5 * 2 ** attempt)
    return False


def _email(title, text):
    to = [a.strip() for a in _val("EMAIL_TO").split(",") if a.strip()]
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = title[:120], _val("EMAIL_USER"), ", ".join(to)
    msg.set_content(text[:3500])
    for attempt in range(2):
        try:
            with smtplib.SMTP_SSL(_val("EMAIL_SMTP") or "smtp.gmail.com", 465, timeout=15) as s:
                s.login(_val("EMAIL_USER"), _val("EMAIL_APP_PASSWORD"))
                s.send_message(msg)
            return True
        except Exception:
            time.sleep(1)
    return False


def _telegram(title, text):
    for cid in config.chat_ids():
        ok = False
        for attempt in range(3):
            try:
                r = requests.post("https://api.telegram.org/bot%s/sendMessage" % _val("TELEGRAM_BOT_TOKEN"),
                                  data={"chat_id": cid, "text": text[:3500], "disable_web_page_preview": "true"}, timeout=10)
                if r.status_code == 200:
                    ok = True
                    break
            except requests.RequestException:
                pass
            time.sleep(0.6 * 2 ** attempt)
        if not ok:
            return False
    return True


def _send(text, title="MY SHARQ RFQ"):
    """True if at least ONE configured channel delivered the message."""
    ch = channels()
    if not ch:
        return False
    ok = False
    if "ntfy" in ch:
        ok = _ntfy(title, text) or ok
    if "email" in ch:
        ok = _email(title, text) or ok
    if "telegram" in ch:
        ok = _telegram(title, text) or ok
    return ok


# ---------------------------------------------------------------- aggregation
def _flush():
    global _pending, _timer, _last_sent
    with _lock:
        batch, _pending, _timer = _pending, [], None
        _last_sent = time.time()
    if batch:
        lines = ["%d new orders waiting:" % len(batch)] + ["- %s (%s, %d lines)" % b for b in batch[:8]]
        _send("\n".join(lines) + "\n" + str(config.get("APP_URL", "") or ""), "%d new RFQs" % len(batch))


def notify_new_order(order_id, name, n_lines):
    """True if sent or queued, False if an immediate send failed (caller keeps notified=false)."""
    global _last_sent, _timer
    name = clean_text(name, 40)
    with _lock:
        now = time.time()
        if now - _last_sent >= MIN_GAP and not _pending:
            _last_sent = now
        else:
            _pending.append((order_id, name, n_lines))
            if _timer is None:
                _timer = threading.Timer(max(1.0, _last_sent + MIN_GAP - now), _flush)
                _timer.daemon = True
                _timer.start()
            return True
    return _send("New RFQ %s\nCustomer: %s\nLines: %d\n%s" % (order_id, name, n_lines, str(config.get("APP_URL", "") or "")),
                 "New RFQ " + order_id)


def send_test():
    return _send("Test message from MY SHARQ RFQ's. Alerts are working.", "Test")
