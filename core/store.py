"""Data layer on top of GitHub. Private DATA repo holds business/personal data; public IMAGES repo holds photos."""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

from . import catalog, config
from .cache import CACHE
from .ghstore import Conflict, GhError, NotFound, Repo
from .validators import item_key, new_order_id

SEED_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "seed")
DEFAULT_SETTINGS = {
    "store_name": "MY SHARQ RFQ's", "support_number": "", "working_hours_text": "", "export_reminder_days": 9,
    "timezone": "Africa/Tripoli", "overlay_opacity": 0.76, "global_orders_per_hour": 60,
    "whatsapp_reply_template": "Hello {customer_name}, this is {operator_name} (Sales Operator) from {store_name} "
                               "regarding your order {order_id}.",
    "leaderboard_reset_at": None,
}


class Ctx:
    def __init__(self, data, images):
        self.data, self.images = data, images


_ctx = None


def ctx():
    global _ctx
    if _ctx is None:
        config.validate()
        o, b = config.get("GITHUB_OWNER"), config.branch()
        _ctx = Ctx(Repo(o, config.get("DATA_REPO"), config.get("GITHUB_TOKEN_DATA"), b),
                   Repo(o, config.get("IMAGES_REPO"), config.get("GITHUB_TOKEN_IMAGES"), b))
    return _ctx


def set_ctx(c):
    global _ctx
    _ctx = c
    CACHE.invalidate("")


def _j(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1).encode("utf-8")


def _read(repo, path, default):
    try:
        return repo.get_json(path)[0]
    except NotFound:
        return default


# ---------------------------------------------------------------- settings / categories / items
def settings():
    def load():
        d = dict(DEFAULT_SETTINGS)
        d.update(_read(ctx().data, "settings.json", {}))
        return d
    return CACHE.get("d:settings", 60, load)


def save_settings(new, actor):
    d = dict(DEFAULT_SETTINGS); d.update(new)
    ctx().data.commit_files({"settings.json": _j(d)}, "%s|settings|settings" % actor)
    CACHE.invalidate("d:")


def categories():
    def load():
        try:
            return ctx().data.get_json("categories.json")[0]["categories"]
        except NotFound:
            with open(os.path.join(SEED_DIR, "categories.json"), encoding="utf-8") as f:
                return json.load(f)["categories"]
    return CACHE.get("d:categories", 60, load)


def items():
    """FULL items including quantities. STAFF ONLY."""
    return CACHE.get("d:items", 60, lambda: _read(ctx().data, "items.json", {"items": []})["items"])


def public():
    """Customer view of the catalogue: availability only, quantities are removed."""
    return CACHE.get("d:public", 60, lambda: catalog.build_public(items(), categories()))


def save_catalog(items_list, cats, actor, action):
    ctx().data.commit_files({"items.json": _j({"items": items_list}), "categories.json": _j({"categories": cats})},
                            "%s|%s|catalog" % (actor, action))
    CACHE.invalidate("d:")


# ---------------------------------------------------------------- manager / users
def manager(fresh=False):
    """None ONLY for a real 404. Any other error propagates (fail closed, prevents first-run takeover).
    Cached 20 s for session checks; the first-run guard always reads fresh."""
    def load():
        try:
            return ctx().data.get_json("manager.json")[0]
        except NotFound:
            return None
    if fresh:
        CACHE.invalidate("d:manager")
    return CACHE.get("d:manager", 20, load)


def create_manager(pw_hash):
    """Create-only. Also seeds categories.json so the tree lives in the data repo."""
    ctx().data.put_file("manager.json", _j({"hash": pw_hash, "token_version": 1}), "setup|manager|created")
    try:
        ctx().data.get_file("categories.json")
    except NotFound:
        with open(os.path.join(SEED_DIR, "categories.json"), "rb") as f:
            ctx().data.put_file("categories.json", f.read(), "setup|categories|seed")
    CACHE.invalidate("d:")


def update_manager(fn, actor, action):
    for _ in range(4):
        d, sha = ctx().data.get_json("manager.json")
        fn(d)
        try:
            ctx().data.put_file("manager.json", _j(d), "%s|%s|manager" % (actor, action), sha)
            CACHE.invalidate("d:manager")
            return d
        except Conflict:
            time.sleep(0.3)
    raise GhError("Could not update, please retry")


def users():
    return CACHE.get("d:users", 30, lambda: _read(ctx().data, "users.json", {"users": []})["users"])


def mutate_users(fn, actor, action):
    for _ in range(4):
        try:
            d, sha = ctx().data.get_json("users.json")
        except NotFound:
            d, sha = {"users": []}, None
        fn(d["users"])
        try:
            ctx().data.put_file("users.json", _j(d), "%s|%s|users" % (actor, action), sha)
            CACHE.invalidate("d:users")
            return
        except Conflict:
            time.sleep(0.3)
    raise GhError("Could not update, please retry")


def find_user(username):
    u = (username or "").strip().lower()
    return next((x for x in users() if x["username"] == u), None)


# ---------------------------------------------------------------- orders
_ORDER_CACHE = {}


def _order_files():
    return CACHE.get("d:orderfiles", 15, lambda: ctx().data.list_dir("orders"))


def list_orders():
    files = [f for f in _order_files() if f["name"].endswith(".json")]

    def load(f):
        k = (f["path"], f["sha"])
        if k not in _ORDER_CACHE:
            try:
                _ORDER_CACHE[k] = json.loads(ctx().data.get_file(f["path"])[0].decode("utf-8"))
            except (NotFound, ValueError):
                return None
        return _ORDER_CACHE[k]
    with ThreadPoolExecutor(6) as ex:
        out = [o for o in ex.map(load, files) if o]
    live = {(f["path"], f["sha"]) for f in files}
    for k in [k for k in _ORDER_CACHE if k not in live]:
        _ORDER_CACHE.pop(k, None)
    return sorted(out, key=lambda o: o["created_at"])


def get_order(order_id):
    try:
        return json.loads(ctx().data.get_file("orders/%s.json" % order_id)[0].decode("utf-8"))
    except NotFound:
        return None


def create_order(order):
    """Create-only write; regenerates the id on collision."""
    for _ in range(4):
        try:
            ctx().data.put_file("orders/%s.json" % order["order_id"], _j(order), "customer|order|%s" % order["order_id"])
            CACHE.invalidate("d:orderfiles")
            return order
        except Conflict:
            order["order_id"] = new_order_id()
    raise GhError("Could not save the order")


def claim_order(order_id, actor_id, display, actor_label):
    """Atomic claim with the file SHA. -> (won, order). The loser gets the winner's name in order['opened_by_display']."""
    path = "orders/%s.json" % order_id
    for _ in range(3):
        try:
            data, sha = ctx().data.get_file(path)
        except NotFound:
            return False, None
        o = json.loads(data.decode("utf-8"))
        if o.get("opened_by"):
            return False, o
        o.update(opened_by=actor_id, opened_by_display=display,
                 opened_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        try:
            ctx().data.put_file(path, _j(o), "%s|claim|%s" % (actor_label, order_id), sha)
            CACHE.invalidate("d:orderfiles")
            return True, o
        except Conflict:
            continue
    return False, get_order(order_id)


def mark_notified(order_id):
    path = "orders/%s.json" % order_id
    try:
        data, sha = ctx().data.get_file(path)
        o = json.loads(data.decode("utf-8"))
        o["notified"] = True
        ctx().data.put_file(path, _j(o), "system|notified|%s" % order_id, sha)
        CACHE.invalidate("d:orderfiles")
    except (NotFound, Conflict):
        pass


# ---------------------------------------------------------------- export / purge
def get_pending():
    return _read(ctx().data, "exports/pending.json", None)


def set_pending(batch, actor):
    log = _read(ctx().data, "exports/log.json", {"exports": []})
    log["exports"].append({"batch": batch["batch"], "time": batch["time"], "count": len(batch["order_ids"]),
                           "file": batch["file"]})
    ctx().data.commit_files({"exports/pending.json": _j(batch), "exports/log.json": _j(log)},
                            "%s|export|%s" % (actor, batch["batch"]))


def purge_pending(actor):
    """Delete exactly the orders in the pending batch, in ONE commit, then clear the batch."""
    p = get_pending()
    if not p:
        raise GhError("No pending export")
    existing = {f["name"] for f in ctx().data.list_dir("orders")}
    ch = {"orders/%s.json" % i: None for i in p["order_ids"] if "%s.json" % i in existing}
    ch["exports/pending.json"] = None
    ctx().data.commit_files(ch, "%s|purge|%s" % (actor, p["batch"]))
    CACHE.invalidate("d:")
    return len(ch) - 1


# ---------------------------------------------------------------- images, photos, points
def images_index(fresh=False):
    def load():
        try:
            head, paths = ctx().images.tree_paths("")
        except (NotFound, Conflict):
            return {"head": None, "thumbs": set(), "assets": set()}
        thumbs = {p.split("/")[-1][:-4] for p, _ in paths if p.startswith("images/thumb/") and p.endswith(".jpg")}
        assets = {p.split("/")[-1] for p, _ in paths if p.startswith("assets/")}
        return {"head": head, "thumbs": thumbs, "assets": assets}
    if fresh:
        CACHE.invalidate("i:")
    return CACHE.get("i:index", 60, load)


def cdn(path):
    idx = images_index()
    ref = idx["head"] or config.branch()
    return "https://cdn.jsdelivr.net/gh/%s/%s@%s/%s" % (config.get("GITHUB_OWNER"), config.get("IMAGES_REPO"), ref, path)


def thumb_url(key):
    return cdn("images/thumb/%s.jpg" % key) if key in images_index()["thumbs"] else None


def asset_url(name):
    return cdn("assets/" + name) if name in images_index()["assets"] else None


def photolog():
    def load():
        try:
            _, paths = ctx().data.tree_paths("photolog/")
        except (NotFound, Conflict):
            return []
        out = []
        for p, _ in paths:
            n = p.split("/")[-1]
            if n.endswith(".json") and n.count("@@") == 2:
                k, a, e = n[:-5].split("@@")
                if e.isdigit():
                    out.append((k, a, int(e)))
        return out
    return CACHE.get("d:photolog", 30, load)


def save_photo(item_no, thumb, full, actor):
    """Commit both sizes in one commit. Returns True if this upload earns a point (item had no photo before)."""
    key = item_key(item_no)
    had = key in images_index(fresh=True)["thumbs"]
    ctx().images.commit_files({"images/thumb/%s.jpg" % key: thumb, "images/full/%s.jpg" % key: full},
                              "%s|photo|%s" % (actor, key))
    CACHE.invalidate("i:")
    awarded = False
    if not had and not any(k == key for k, _, _ in photolog()):
        ctx().data.put_file("photolog/%s@@%s@@%d.json" % (key, actor, int(time.time())), b"{}", "%s|point|%s" % (actor, key))
        CACHE.invalidate("d:photolog")
        awarded = True
    return awarded


def points(reset_at=None):
    """{username: points}. Earliest log entry per item counts; entries before reset_at are ignored."""
    first = {}
    for k, a, e in photolog():
        if k not in first or e < first[k][1]:
            first[k] = (a, e)
    tally = {}
    for a, e in first.values():
        if reset_at is None or e >= reset_at:
            tally[a] = tally.get(a, 0) + 1
    return tally


def put_asset(name, data, actor):
    ctx().images.commit_files({"assets/" + name: data}, "%s|asset|%s" % (actor, name))
    CACHE.invalidate("i:")


def activity(n=30):
    return ctx().data.commits(n)
