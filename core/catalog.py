"""Catalogue logic: public view (NO quantities), search, Excel import, category editing."""
import csv
import difflib
import io
import re
import zipfile

from .validators import cat_norm, clean_text, item_key, search_norm

MAX_IMPORT_BYTES = 10 * 1024 * 1024
MAX_IMPORT_ROWS = 20000
HEADERS = {"section": "section", "branch": "branch", "subbranch": "sub_branch", "itemno": "item_no",
           "description": "description", "quantity": "qty"}


def availability(qty):
    """Customer-facing status. The number itself must never leave the server."""
    return "Available" if isinstance(qty, int) and qty > 0 else "Waiting"


# ---------------------------------------------------------------- public view
def build_public(items, categories):
    pub, level, counts, by_no, index = [], {}, {}, {}, []
    for it in items:
        d = {"item_no": it["item_no"], "description": it["description"], "section": it["section"],
             "branch": it.get("branch", ""), "sub_branch": it.get("sub_branch", ""),
             "status": availability(it.get("qty", 0)), "key": item_key(it["item_no"])}
        pub.append(d)
        by_no[d["item_no"]] = d
        path = tuple(p for p in (d["section"], d["branch"], d["sub_branch"]) if p)
        level.setdefault(path, []).append(d)
        for i in range(1, len(path) + 1):
            counts[path[:i]] = counts.get(path[:i], 0) + 1
        index.append((search_norm(d["item_no"]), d["description"].lower(), d))
    tree = []
    for c in categories:
        if counts.get((c["section"],), 0) == 0:
            continue
        brs = []
        for b in c.get("branches", []):
            if counts.get((c["section"], b["name"]), 0) == 0:
                continue
            subs = [s for s in b.get("sub_branches", []) if counts.get((c["section"], b["name"], s), 0) > 0]
            brs.append({"name": b["name"], "subs": subs})
        tree.append({"name": c["section"], "branches": brs})
    return {"items": pub, "level": level, "counts": counts, "by_no": by_no, "index": index, "tree": tree}


def children(cat, path):
    """Visible child category names under path (tuple)."""
    if not path:
        return [s["name"] for s in cat["tree"]]
    for s in cat["tree"]:
        if s["name"] == path[0]:
            if len(path) == 1:
                return [b["name"] for b in s["branches"]]
            for b in s["branches"]:
                if b["name"] == path[1] and len(path) == 2:
                    return list(b["subs"])
    return []


def search(cat, query, limit=500):
    qn = search_norm(query)
    words = [w for w in re.split(r"\s+", query.lower().strip()) if w]
    exact, prefix, contains, desc = [], [], [], []
    for nno, dl, it in cat["index"]:
        if qn and nno == qn:
            exact.append(it)
        elif qn and nno.startswith(qn):
            prefix.append(it)
        elif qn and qn in nno:
            contains.append(it)
        elif words and all(w in dl for w in words):
            desc.append(it)
    return (exact + prefix + contains + desc)[:limit]


# ---------------------------------------------------------------- categories
def norm_categories(cats):
    out = []
    for i, c in enumerate(cats, 1):
        out.append({"order": i, "section": c["section"],
                    "branches": [{"name": b["name"], "sub_branches": list(b.get("sub_branches", []))} for b in c.get("branches", [])]})
    return out


def triples(categories):
    """Canonical (section, branch, sub) strings available in the tree."""
    out = []
    for c in categories:
        out.append((c["section"], "", ""))
        for b in c["branches"]:
            out.append((c["section"], b["name"], ""))
            for s in b["sub_branches"]:
                out.append((c["section"], b["name"], s))
    return out


def _lookup(categories):
    m = {}
    for t in triples(categories):
        m[tuple(cat_norm(x) for x in t)] = t
    return m


def items_using(items, level, name_path):
    """Items referencing a category (name_path = tuple of 1-3 names)."""
    n = len(name_path)
    return [i for i in items if tuple(i.get(k, "") for k in ("section", "branch", "sub_branch"))[:n] == tuple(name_path)]


def cat_add(cats, path, name):
    name = clean_text(name, 80)
    if not name:
        raise ValueError("Name required")
    if len(path) == 0:
        if any(cat_norm(c["section"]) == cat_norm(name) for c in cats):
            raise ValueError("Section already exists")
        cats.append({"order": len(cats) + 1, "section": name, "branches": []})
    else:
        sec = next(c for c in cats if c["section"] == path[0])
        if len(path) == 1:
            if any(cat_norm(b["name"]) == cat_norm(name) for b in sec["branches"]):
                raise ValueError("Branch already exists")
            sec["branches"].append({"name": name, "sub_branches": []})
        else:
            br = next(b for b in sec["branches"] if b["name"] == path[1])
            if any(cat_norm(s) == cat_norm(name) for s in br["sub_branches"]):
                raise ValueError("Sub-branch already exists")
            br["sub_branches"].append(name)
    return norm_categories(cats)


def cat_rename(cats, items, path, new):
    """Rename and update the items that reference it. Returns (cats, items)."""
    new = clean_text(new, 80)
    if not new:
        raise ValueError("Name required")
    key = ("section", "branch", "sub_branch")[len(path) - 1]
    for it in items:
        if tuple(it.get(k, "") for k in ("section", "branch", "sub_branch"))[:len(path)] == tuple(path):
            it[key] = new
    sec = next(c for c in cats if c["section"] == path[0])
    if len(path) == 1:
        sec["section"] = new
    else:
        br = next(b for b in sec["branches"] if b["name"] == path[1])
        if len(path) == 2:
            br["name"] = new
        else:
            br["sub_branches"] = [new if s == path[2] else s for s in br["sub_branches"]]
    return norm_categories(cats), items


def cat_delete(cats, items, path):
    if items_using(items, None, path):
        raise ValueError("This category still has items. Move or delete them first.")
    sec = next(c for c in cats if c["section"] == path[0])
    if len(path) == 1:
        cats = [c for c in cats if c is not sec]
    elif len(path) == 2:
        sec["branches"] = [b for b in sec["branches"] if b["name"] != path[1]]
    else:
        br = next(b for b in sec["branches"] if b["name"] == path[1])
        br["sub_branches"] = [s for s in br["sub_branches"] if s != path[2]]
    return norm_categories(cats)


def cat_move(cats, path, delta):
    def mv(lst, pred):
        i = next(i for i, x in enumerate(lst) if pred(x))
        j = i + delta
        if 0 <= j < len(lst):
            lst[i], lst[j] = lst[j], lst[i]
    if len(path) == 1:
        mv(cats, lambda c: c["section"] == path[0])
    else:
        sec = next(c for c in cats if c["section"] == path[0])
        if len(path) == 2:
            mv(sec["branches"], lambda b: b["name"] == path[1])
        else:
            br = next(b for b in sec["branches"] if b["name"] == path[1])
            mv(br["sub_branches"], lambda s: s == path[2])
    return norm_categories(cats)


# ---------------------------------------------------------------- import
def _hdr(h):
    return HEADERS.get(re.sub(r"[^a-z]", "", str(h or "").lower()))


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def parse_items_file(data, filename):
    """-> (rows, fatal_error). Rows keep their spreadsheet row number. Values only, never formulas."""
    if len(data) > MAX_IMPORT_BYTES:
        return [], "File is larger than 10 MB."
    name = (filename or "").lower()
    raw = []
    try:
        if name.endswith(".xlsx"):
            z = zipfile.ZipFile(io.BytesIO(data))
            if any("vbaproject" in n.lower() for n in z.namelist()):
                return [], "Macro-enabled files are not accepted."
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            ws = wb["Items"] if "Items" in wb.sheetnames else wb.worksheets[0]
            for i, r in enumerate(ws.iter_rows(values_only=True), 1):
                raw.append((i, list(r)))
                if i > MAX_IMPORT_ROWS + 1:
                    return [], "More than 20,000 rows."
        elif name.endswith(".csv"):
            txt = data.decode("utf-8-sig", errors="replace")
            for i, r in enumerate(csv.reader(io.StringIO(txt)), 1):
                raw.append((i, r))
                if i > MAX_IMPORT_ROWS + 1:
                    return [], "More than 20,000 rows."
        else:
            return [], "Only .xlsx or .csv files are accepted."
    except Exception:
        return [], "The file could not be read. Make sure it is a valid .xlsx or .csv file."
    if not raw:
        return [], "The file is empty."
    cols = {}
    for idx, h in enumerate(raw[0][1]):
        k = _hdr(h)
        if k and k not in cols:
            cols[k] = idx
    missing = [k for k in ("section", "branch", "sub_branch", "item_no", "description", "qty") if k not in cols]
    if missing:
        return [], "Missing columns: " + ", ".join(missing) + ". Expected: Section, Branch, Sub-Branch, Item No, Description, Quantity."
    rows = []
    for i, r in raw[1:]:
        if not any(_cell(c) for c in r):
            continue
        g = lambda k: _cell(r[cols[k]]) if cols[k] < len(r) else ""
        rows.append({"row": i, "section": g("section"), "branch": g("branch"), "sub_branch": g("sub_branch"),
                     "item_no": g("item_no"), "description": g("description"), "qty_raw": g("qty")})
    return rows, None


def validate_import(rows, categories):
    look = _lookup(categories)
    names = [" > ".join(x for x in t if x) for t in triples(categories)]
    rep = {"ok": [], "empty_no": [], "empty_desc": [], "dups": [], "bad_qty": [], "unknown": {}, "suggest": {}}
    seen = set()
    for r in rows:
        no = clean_text(r["item_no"], 80)
        if not no:
            rep["empty_no"].append(r["row"]); continue
        if not clean_text(r["description"], 300):
            rep["empty_desc"].append(r["row"]); continue
        if no.upper() in seen:
            rep["dups"].append((r["row"], no)); continue
        seen.add(no.upper())
        q = r["qty_raw"]
        if q == "":
            qty = 0
        else:
            try:
                f = float(q)
                qty = int(f) if f.is_integer() and f >= 0 else None
            except ValueError:
                qty = None
            if qty is None:
                rep["bad_qty"].append((r["row"], q)); qty = 0
        s, b, sb = (clean_text(r[k], 80) for k in ("section", "branch", "sub_branch"))
        rec = dict(r, item_no=no, description=clean_text(r["description"], 300), qty=qty, section=s, branch=b, sub_branch=sb)
        key = (cat_norm(s), cat_norm(b), cat_norm(sb))
        if (sb and not b) or key not in look:
            raw_t = (s, b, sb)
            rep["unknown"].setdefault(raw_t, []).append(r["row"])
            rec["_unknown"] = raw_t
            if raw_t not in rep["suggest"]:
                label = " > ".join(x for x in raw_t if x)
                close = difflib.get_close_matches(label, names, n=3, cutoff=0.6)
                rep["suggest"][raw_t] = [triples(categories)[names.index(c)] for c in close]
        else:
            rec["section"], rec["branch"], rec["sub_branch"] = look[key]
        rep["ok"].append(rec)
    return rep


def apply_import(existing, report, mode, decisions, categories):
    """decisions: {raw_triple: 'create' | 'skip' | ('map', canonical_triple)}.
    Returns (items, categories, summary). Nothing is lost silently: skipped rows are counted."""
    cats = norm_categories(categories)
    by_no = {i["item_no"].upper(): i for i in existing}
    imported, summary = [], {"added": 0, "updated": 0, "unchanged": 0, "skipped": 0, "removed": 0}
    for rec in report["ok"]:
        t = rec.get("_unknown")
        if t:
            dec = decisions.get(t, "skip")
            if dec == "skip" or t[0] == "" or (t[2] and not t[1]):
                summary["skipped"] += 1; continue
            if isinstance(dec, tuple) and dec[0] == "map":
                rec["section"], rec["branch"], rec["sub_branch"] = dec[1]
            else:
                look = _lookup(cats)
                for lvl, name in enumerate(t):
                    if not name:
                        continue
                    path = tuple(x for x in t[:lvl] if x)
                    if tuple(cat_norm(x) for x in (list(t[:lvl + 1]) + [""] * (2 - lvl))) not in look:
                        cats = cat_add(cats, path, name)
                        look = _lookup(cats)
                canon = look[tuple(cat_norm(x) for x in t)]
                rec["section"], rec["branch"], rec["sub_branch"] = canon
        item = {"item_no": rec["item_no"], "description": rec["description"], "section": rec["section"],
                "branch": rec["branch"], "sub_branch": rec["sub_branch"], "qty": rec["qty"]}
        old = by_no.get(item["item_no"].upper())
        if old is None:
            summary["added"] += 1
        elif all(old.get(k) == item[k] for k in item):
            summary["unchanged"] += 1
        else:
            summary["updated"] += 1
        imported.append(item)
    if mode == "replace":
        new_items = imported
        summary["removed"] = len([k for k in by_no if k not in {i["item_no"].upper() for i in imported}])
    else:
        merged = dict(by_no)
        for it in imported:
            merged[it["item_no"].upper()] = it
        new_items = list(merged.values())
    return new_items, norm_categories(cats), summary
