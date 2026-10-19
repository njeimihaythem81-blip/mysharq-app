"""Login, session verification, password changes. Fails closed."""
import time

from . import config, store
from .security import (FAILED_LOGINS, LIMITER, THROTTLE, dummy_verify, hash_password, make_token, password_policy,
                       verify_password, verify_token)
from .validators import clean_text

OP_TTL = 7 * 86400
MGR_TTL = 8 * 3600
GENERIC = "Invalid username or password."


def _secret():
    return str(config.get("SESSION_SECRET"))


def _issue(uid, role, version):
    return make_token(_secret(), uid, role, version, MGR_TTL if role == "manager" else OP_TTL)


def login(username, password, ip):
    """-> (ok, message, token, user). Progressive throttling, generic errors, dummy hash for unknown users."""
    u = clean_text(username, 40).lower()
    key = "%s|%s" % (u, ip)
    if not LIMITER.allow("login:" + ip, 30, 60):
        return False, "Too many attempts. Please wait a minute.", None, None
    w = THROTTLE.wait_seconds(key)
    if w > 0:
        return False, "Too many attempts. Try again in %d seconds." % w, None, None
    if u == "manager":
        m = store.manager()
        if m is None:
            ok = dummy_verify(password)
        else:
            ok = verify_password(password, m["hash"])
        if ok:
            THROTTLE.reset(key)
            return True, "ok", _issue("manager", "manager", m["token_version"]), {"id": "manager", "role": "manager", "display": "Store Manager"}
    else:
        usr = store.find_user(u)
        ok = verify_password(password, usr["hash"]) if usr else dummy_verify(password)
        if ok and usr and usr.get("active", True):
            THROTTLE.reset(key)
            return True, "ok", _issue(usr["username"], "operator", usr["token_version"]), \
                {"id": usr["username"], "role": "operator", "display": usr["display"], "must_change": usr.get("must_change", False)}
    THROTTLE.fail(key)
    FAILED_LOGINS.append((time.time(), u))
    return False, GENERIC, None, None


def session_user(token):
    """Verify signature, expiry, active flag and token_version against the current records."""
    d = verify_token(_secret(), token or "")
    if not d:
        return None
    if d["r"] == "manager":
        m = store.manager()
        if m and d["u"] == "manager" and m["token_version"] == d["v"]:
            return {"id": "manager", "role": "manager", "display": "Store Manager"}
        return None
    usr = store.find_user(d["u"])
    if usr and usr.get("active", True) and usr["token_version"] == d["v"]:
        return {"id": usr["username"], "role": "operator", "display": usr["display"], "must_change": usr.get("must_change", False)}
    return None


def check_password(user, pw):
    """Re-authentication for sensitive actions."""
    if user["role"] == "manager":
        return verify_password(pw, store.manager()["hash"])
    usr = store.find_user(user["id"])
    return bool(usr) and verify_password(pw, usr["hash"])


def check_staff_key(key, ip):
    """Secret staff link. Constant-time compare, throttled per IP. A hidden door, not a lock:
    the real lock is still the username/password."""
    import hmac
    if not key or not LIMITER.allow("staffkey:" + ip, 20, 600):
        return False
    return hmac.compare_digest(str(key), str(config.get("STAFF_KEY")))


def setup_manager(code, pw, confirm, ip):
    """First run only. Needs SETUP_CODE; allowed only when manager.json is a real 404."""
    import hmac
    if not LIMITER.allow("setup:" + ip, 10, 600):
        return False, "Too many attempts. Please wait."
    if not hmac.compare_digest(str(code or ""), str(config.get("SETUP_CODE"))):
        return False, "Invalid setup code."
    if pw != confirm:
        return False, "Passwords do not match."
    err = password_policy(pw, "manager", "manager")
    if err:
        return False, err
    if store.manager(fresh=True) is not None:
        return False, "Setup is already complete."
    from .ghstore import Conflict
    try:
        store.create_manager(hash_password(pw))
    except Conflict:
        return False, "Setup is already complete."
    return True, "ok"


def change_password(user, old, new):
    err = password_policy(new, user["id"], user["role"])
    if err:
        return False, err
    if not check_password(user, old):
        return False, "Current password is incorrect."
    h = hash_password(new)
    if user["role"] == "manager":
        store.update_manager(lambda d: d.update(hash=h, token_version=d["token_version"] + 1), "manager", "password")
    else:
        def f(us):
            for x in us:
                if x["username"] == user["id"]:
                    x.update(hash=h, token_version=x["token_version"] + 1, must_change=False)
        store.mutate_users(f, "op:" + user["id"], "password")
    return True, "ok"


def logout(user):
    if user["role"] == "manager":
        store.update_manager(lambda d: d.update(token_version=d["token_version"] + 1), "manager", "logout")
    else:
        store.mutate_users(lambda us: [x.update(token_version=x["token_version"] + 1) for x in us if x["username"] == user["id"]],
                           "op:" + user["id"], "logout")


# ------------- manager: operators -------------
def add_operator(username, display, password):
    u = clean_text(username, 30).lower()
    import re
    if not re.fullmatch(r"[a-z0-9_.-]{3,30}", u) or u == "manager":
        return False, "Username: 3-30 characters (a-z, 0-9, _ . -). 'manager' is reserved."
    d = clean_text(display, 40)
    if len(d) < 2:
        return False, "Display name required."
    err = password_policy(password, u, "operator")
    if err:
        return False, err
    if store.find_user(u):
        return False, "Username already exists."
    rec = {"username": u, "display": d, "hash": hash_password(password), "active": True, "token_version": 1, "must_change": True}
    store.mutate_users(lambda us: us.append(rec), "manager", "operator-add:" + u)
    return True, "ok"


def reset_operator(username, password):
    err = password_policy(password, username, "operator")
    if err:
        return False, err
    h = hash_password(password)
    store.mutate_users(lambda us: [x.update(hash=h, token_version=x["token_version"] + 1, must_change=True)
                                   for x in us if x["username"] == username], "manager", "operator-reset:" + username)
    return True, "ok"


def set_operator_active(username, active):
    store.mutate_users(lambda us: [x.update(active=active, token_version=x["token_version"] + 1)
                                   for x in us if x["username"] == username], "manager", "operator-%s:%s" % ("on" if active else "off", username))


def delete_operator(username):
    store.mutate_users(lambda us: us.__setitem__(slice(None), [x for x in us if x["username"] != username]),
                       "manager", "operator-delete:" + username)
