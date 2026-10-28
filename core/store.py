"""Data layer on top of GitHub. Private DATA repo holds business/personal data; public IMAGES repo holds photos."""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

from . import catalog, config, training
from .cache import CACHE
from .ghstore import Conflict, GhError, NotFound, Repo
from .validators import item_key, new_order_id

SEED_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "seed")
DEFAULT_SETTINGS = {
    "store_name": "MY SHARQ RFQ's", "support_number": "", "working_hours_text": "", "export_reminder_days": 9,
    "timezone": "Africa/Tripoli", "overlay_opacity": 0.76, "global_orders_per_hour": 60,
    "whatsapp_reply_template": "Hello {customer_name}, this is {operator_name} (Sales Operator) from {store_name} "
                               "regarding your order {order_id}.",
    "leaderboard_reset_at": None, "customer_login_required": False,
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
    return CACHE.get("d:public", 60, lambda: catalog.build_public(
        items(), categories(), training.compile_training(training_data()), training.learn_active(learned())))


# ---- search training (v2.4): training.json = synonyms + scopes from the manager's Excel; learned.json = customer choices
def training_data():
    return CACHE.get("d:training", 60, lambda: _read(ctx().data, "training.json", {"groups": [], "scopes": []}))


def save_training(train, actor):
    train = {k: v for k, v in train.items() if k != "approved"}          # approved pairs live in learned.json
    ctx().data.commit_files({"training.json": _j(train)}, "%s|training|training" % actor)
    CACHE.invalidate("d:")


def learned():
    return CACHE.get("d:learned", 60, lambda: _read(ctx().data, "learned.json", {"q": {}}))


def _mutate_learned(fn, actor, action, tries=3):
    """Read-modify-write learned.json with the file's SHA; retried when two sessions write at the same moment."""
    for _ in range(tries):
        try:
            cur, sha = ctx().data.get_json("learned.json")
        except NotFound:
            cur, sha = {"q": {}}, None
        res = fn(cur)
        try:
            ctx().data.put_file("learned.json", _j(cur), "%s|%s|learned" % (actor, action), sha)
            CACHE.invalidate("d:")
            return res
        except Conflict:
            continue
    raise GhError("busy")


def record_choices(pairs, sid):
    """Customer choices (wording, item_no). Best effort: never breaks the customer's flow."""
    pairs = [(w, n) for w, n in pairs if w and n][:40]
    if not pairs:
        return 0
    return _mutate_learned(lambda cur: training.learn_add(cur, pairs, sid), "customer", "choices")


def decide_learned(key, no, approve, actor):
    return _mutate_learned(lambda cur: training.learn_decide(cur, key, no, approve), actor, "approve" if approve else "reject")


def import_approved(pairs, actor):
    """Approved wording -> item pairs from the training Excel become approved choices."""
    pairs = [(w, n) for w, n in pairs if w and n]
    if not pairs:
        return 0
    return _mutate_learned(lambda cur: training.learn_import_approved(cur, pairs), actor, "import-approved")


def forget_learned(key, no, actor):
    return _mutate_learned(lambda cur: training.learn_forget(cur, key, no), actor, "forget")


BACKUP_KEEP = 10
_BACKUP_SEQ = __import__("itertools").count(1)


def save_catalog(items_list, cats, actor, action, backup=False, imgmap=None):
    """Write items + categories (+ image map) in ONE commit. backup=True also stores the PREVIOUS state in
    backups/ (newest 10 kept) inside the same commit, so a bad import or delete can be undone."""
    ch = {"items.json": _j({"items": items_list}), "categories.json": _j({"categories": cats})}
    if imgmap is not None:
        ch["catimages.json"] = _j({"images": imgmap})
    if backup:
        prev = {"items": _read(ctx().data, "items.json", {"items": []})["items"],
                "categories": _read(ctx().data, "categories.json", {"categories": categories()})["categories"],
                "images": _read(ctx().data, "catimages.json", {"images": {}})["images"], "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        now = time.time()
        # timestamp (to the millisecond) + process-wide counter: names sort chronologically even within one millisecond
        name = "%s%03d-%04d_%s" % (time.strftime("%Y%m%d-%H%M%S", time.gmtime(now)), int(now * 1000) % 1000, next(_BACKUP_SEQ) % 10000,
                                   "".join(c for c in action if c.isalnum() or c in "-_")[:20])
        ch["backups/%s.json" % name] = _j(prev)
        old = sorted(f["name"] for f in ctx().data.list_dir("backups") if f["name"].endswith(".json"))
        for n in old[:max(0, len(old) + 1 - BACKUP_KEEP)]:
            ch["backups/" + n] = None
    ctx().data.commit_files(ch, "%s|%s|catalog" % (actor, action))
    CACHE.invalidate("d:")


def list_backups():
    return sorted((f["name"] for f in ctx().data.list_dir("backups") if f["name"].endswith(".json")), reverse=True)


def read_backup(name):
    if "/" in name or ".." in name:
        raise GhError("bad name")
    return json.loads(ctx().data.get_file("backups/" + name)[0].decode("utf-8"))


def restore_backup(name, actor):
    b = read_backup(name)
    save_catalog(b["items"], b["categories"], actor, "restore", backup=True, imgmap=b.get("images", {}))


# ---- category images (section / branch / sub-branch tiles)
def catimages():
    return CACHE.get("d:catimages", 60, lambda: _read(ctx().data, "catimages.json", {"images": {}})["images"])


def cat_image_url(path):
    tok = catimages().get(catalog.path_id(path))
    if tok and tok in images_index()["cats"]:
        return cdn("images/cat/%s.jpg" % tok)
    return None


def set_cat_images(mapping, actor):
    """mapping {path: jpeg bytes}. Files go to the PUBLIC images repo, the path->token map to the private repo."""
    import uuid
    imgmap = dict(catimages())
    files = {}
    for path, data in mapping.items():
        pid = catalog.path_id(path)
        tok = imgmap.get(pid) or uuid.uuid4().hex[:12]
        imgmap[pid] = tok
        files["images/cat/%s.jpg" % tok] = data
    ctx().images.commit_files(files, "%s|catimages|%d" % (actor, len(files)))
    ctx().data.commit_files({"catimages.json": _j({"images": imgmap})}, "%s|catimages|map" % actor)
    CACHE.invalidate("i:"); CACHE.invalidate("d:catimages")


def delete_cat_image_files(tokens, actor):
    """Remove category image files that no longer belong to any level."""
    if tokens:
        ctx().images.commit_files({"images/cat/%s.jpg" % t: None for t in tokens}, "%s|catimages-prune|%d" % (actor, len(tokens)))
        CACHE.invalidate("i:")


def remove_cat_image(path, actor):
    imgmap, gone = catalog.drop_image_keys(dict(catimages()), path)
    if gone:
        ctx().images.commit_files({"images/cat/%s.jpg" % t: None for t in gone}, "%s|catimages-remove|%d" % (actor, len(gone)))
    ctx().data.commit_files({"catimages.json": _j({"images": imgmap})}, "%s|catimages-remove|map" % actor)
    CACHE.invalidate("i:"); CACHE.invalidate("d:catimages")


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


# ---- customer accounts (v2.5): the manager creates a name + code for each customer
def customers():
    return CACHE.get("d:customers", 20, lambda: _read(ctx().data, "customers.json", {"customers": []})["customers"])


def mutate_customers(fn, actor, action):
    for _ in range(4):
        try:
            d, sha = ctx().data.get_json("customers.json")
        except NotFound:
            d, sha = {"customers": []}, None
        fn(d["customers"])
        try:
            ctx().data.put_file("customers.json", _j(d), "%s|%s|customers" % (actor, action), sha)
            CACHE.invalidate("d:customers")
            return
        except Conflict:
            time.sleep(0.3)
    raise GhError("Could not update, please retry")


def find_customer(cid):
    c = (cid or "").strip().lower()
    return next((x for x in customers() if x["id"] == c), None)


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
            return {"head": None, "thumbs": set(), "assets": set(), "cats": set()}
        thumbs = {p.split("/")[-1][:-4] for p, _ in paths if p.startswith("images/thumb/") and p.endswith(".jpg")}
        assets = {p.split("/")[-1] for p, _ in paths if p.startswith("assets/")}
        cats = {p.split("/")[-1][:-4] for p, _ in paths if p.startswith("images/cat/") and p.endswith(".jpg")}
        return {"head": head, "thumbs": thumbs, "assets": assets, "cats": cats}
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
