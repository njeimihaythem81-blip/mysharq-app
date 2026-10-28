"""Training for the intelligent search (v2.4), 100% free and local to the app.

Training Excel file, two sheets:
  Synonyms : one row = one group of words that mean the same thing. Columns Arabic | French | English | Other.
             A cell may hold several terms separated by comma / semicolon / Arabic comma / new line. Phrases are allowed.
  Bundles  : functional groups (v2.6). Name | Aliases | Item No | Qty | Choice | Option label. One row per component; the name
             is written on the first row only. Rows sharing the same Choice text are alternatives (e.g. door: transparent / white).
  Defaults : When | Unless | Leave out. e.g. When "contactor", unless "dc" is written, leave out items containing "dc" (AC by default).
  Scopes   : Word | Section | Branch | Sub-Branch. When the word (or any synonym of it) is typed, the search is limited
             to that category. Branch and Sub-Branch may stay empty.

Customer choices (what a customer picked for a wording the app could not match) are kept as small counters.
They NEVER take effect on their own: only a choice the manager approved is used by the search, and approved choices are
written into the training Excel (sheet "Approved") so the file stays the complete master copy.
"""
import hashlib
import io
import re
import time
import zipfile

from . import catalog
from .validators import cat_norm, clean_text

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 3000
MAX_TERM = 40
MAX_TERMS_PER_ROW = 24
SPLIT = re.compile(r"[,;\u060C\u061B|\n]+")
SYN_HEADERS = ("Arabic", "French", "English", "Other")
SCOPE_HEADERS = ("Word", "Section", "Branch", "Sub-Branch")

MAX_BUNDLES = 300
MAX_PARTS = 30
MAX_DEFAULTS = 200
BUNDLE_HEADERS = ("Name", "Aliases", "Item No", "Qty", "Choice", "Option label")
DEFAULT_HEADERS = ("When", "Unless", "Leave out")

LEARN_MAX_QUERIES = 3000
LEARN_MAX_ITEMS = 8


# ------------------------------------------------------------------ reading the Excel file
def _cell(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def _terms(cell):
    out = []
    for t in SPLIT.split(_cell(cell)):
        t = clean_text(t, MAX_TERM)
        if t and t not in out:
            out.append(t)
    return out


def _sheet_rows(wb, name):
    key = {n.strip().lower(): n for n in wb.sheetnames}.get(name.lower())
    if key is None:
        return None
    out = []
    for i, r in enumerate(wb[key].iter_rows(values_only=True), 1):
        out.append((i, list(r)))
        if i > MAX_ROWS + 1:
            break
    return out


def parse_training_file(data, filename, categories, item_nos=None):
    """-> (train, report). train = {'groups': [[term, ...]], 'scopes': [{'word', 'path'}]} or None on a fatal error.
    report = {'error': str|None, 'warnings': [str], 'groups': n, 'scopes': n}. Bad rows are skipped, never the whole file."""
    rep = {"error": None, "warnings": [], "groups": 0, "scopes": 0, "approved": 0}
    if len(data) > MAX_BYTES:
        rep["error"] = "File is larger than 5 MB."; return None, rep
    if not (filename or "").lower().endswith(".xlsx"):
        rep["error"] = "Only .xlsx files are accepted."; return None, rep
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        if any("vbaproject" in n.lower() for n in z.namelist()):
            rep["error"] = "Macro-enabled files are not accepted."; return None, rep
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        syn_rows, scope_rows, appr_rows = _sheet_rows(wb, "Synonyms"), _sheet_rows(wb, "Scopes"), _sheet_rows(wb, "Approved")
        bun_rows, def_rows = _sheet_rows(wb, "Bundles"), _sheet_rows(wb, "Defaults")
    except Exception:
        rep["error"] = "The file could not be read. Make sure it is a valid .xlsx file."; return None, rep
    if all(x is None for x in (syn_rows, scope_rows, appr_rows, bun_rows, def_rows)):
        rep["error"] = "No sheet named Synonyms, Scopes, Bundles, Defaults or Approved was found. Download the template and fill it in."; return None, rep
    groups, scopes, seen_scope = [], [], set()
    for i, r in (syn_rows or [])[1:]:
        cells = [_cell(c) for c in r[:4]]
        if not any(cells):
            continue
        terms = []
        for c in r[:4]:
            for t in _terms(c):
                if t not in terms:
                    terms.append(t)
        if len(terms) < 2:
            rep["warnings"].append("Synonyms row %d skipped: it needs at least two terms." % i); continue
        if len(terms) > MAX_TERMS_PER_ROW:
            rep["warnings"].append("Synonyms row %d: only the first %d terms were kept." % (i, MAX_TERMS_PER_ROW)); terms = terms[:MAX_TERMS_PER_ROW]
        if len(groups) >= MAX_ROWS:
            rep["warnings"].append("Synonyms: more than %d rows, the rest were ignored." % MAX_ROWS); break
        groups.append(terms)
    lookup = catalog._lookup(categories)
    for i, r in (scope_rows or [])[1:]:
        cells = [_cell(c) for c in (list(r) + [None] * 4)[:4]]
        if not any(cells):
            continue
        word, sec, br, sub = (clean_text(c, 80) for c in cells)
        if not word or not sec:
            rep["warnings"].append("Scopes row %d skipped: Word and Section are required." % i); continue
        if sub and not br:
            rep["warnings"].append("Scopes row %d skipped: Sub-Branch given without Branch." % i); continue
        canon = lookup.get((cat_norm(sec), cat_norm(br), cat_norm(sub)))
        if canon is None:
            rep["warnings"].append("Scopes row %d skipped: '%s' is not in the category tree." % (i, " > ".join(x for x in (sec, br, sub) if x))); continue
        path = [x for x in canon if x]
        k = (cat_norm(word), tuple(path))
        if k in seen_scope:
            continue
        seen_scope.add(k)
        scopes.append({"word": word, "path": path})
    approved, seen_a = [], set()
    for i, r in (appr_rows or [])[1:]:
        cells = [_cell(c) for c in (list(r) + [None] * 2)[:2]]
        if not any(cells):
            continue
        wording, no = clean_text(cells[0], 120), clean_text(cells[1], 60)
        if not wording or not no:
            rep["warnings"].append("Approved row %d skipped: wording and item number are required." % i); continue
        if item_nos is not None and no not in item_nos:
            rep["warnings"].append("Approved row %d skipped: item %s is not in the catalogue." % (i, no)); continue
        k = (catalog.learn_key(wording), no)
        if not k[0] or k in seen_a:
            continue
        seen_a.add(k); approved.append([wording, no])
        if len(approved) >= LEARN_MAX_QUERIES:
            rep["warnings"].append("Approved: more than %d rows, the rest were ignored." % LEARN_MAX_QUERIES); break
    bundles = _parse_bundles(bun_rows or [], item_nos, rep)
    defaults = _parse_defaults(def_rows or [], rep)
    rep["groups"], rep["scopes"], rep["approved"] = len(groups), len(scopes), len(approved)
    rep["bundles"], rep["defaults"] = len(bundles), len(defaults)
    if not (groups or scopes or approved or bundles or defaults):
        rep["error"] = "The file has no usable rows."; return None, rep
    return {"groups": groups, "scopes": scopes, "approved": approved, "bundles": bundles, "defaults": defaults}, rep


def _qty(v):
    t = _cell(v)
    if not t:
        return 1
    try:
        n = int(float(t))
    except ValueError:
        return None
    return n if 1 <= n <= 999 else None


def _parse_bundles(rows, item_nos, rep):
    out, idx, cur = [], {}, None
    for i, r in rows[1:]:
        cells = (list(r) + [None] * 6)[:6]
        if not any(_cell(c) for c in cells):
            continue
        name = clean_text(_cell(cells[0]), 60)
        if name:
            k = cat_norm(name)
            if k not in idx:
                if len(out) >= MAX_BUNDLES:
                    rep["warnings"].append("Bundles: more than %d bundles, the rest were ignored." % MAX_BUNDLES); break
                idx[k] = {"name": name, "aliases": [], "parts": []}; out.append(idx[k])
            cur = idx[k]
        if cur is None:
            rep["warnings"].append("Bundles row %d skipped: it has no bundle name." % i); continue
        for a in _terms(cells[1]):
            if a not in cur["aliases"]:
                cur["aliases"].append(a)
        no = clean_text(_cell(cells[2]), 60)
        if not no:
            continue
        q = _qty(cells[3])
        if q is None:
            rep["warnings"].append("Bundles row %d skipped: quantity must be a whole number 1-999." % i); continue
        if item_nos is not None and no not in item_nos:
            rep["warnings"].append("Bundles row %d skipped: item %s is not in the catalogue." % (i, no)); continue
        if len(cur["parts"]) >= MAX_PARTS:
            rep["warnings"].append("Bundle '%s': only the first %d items were kept." % (cur["name"], MAX_PARTS)); continue
        cur["parts"].append({"no": no, "qty": q, "choice": clean_text(_cell(cells[4]), 40), "label": clean_text(_cell(cells[5]), 60)})
    final = []
    for b in out:
        if not b["parts"]:
            rep["warnings"].append("Bundle '%s' skipped: it has no valid items." % b["name"]); continue
        counts, warned = {}, set()
        for p in b["parts"]:
            if p["choice"]:
                counts[p["choice"]] = counts.get(p["choice"], 0) + 1
        for p in b["parts"]:
            if p["choice"] and counts[p["choice"]] < 2:
                if p["choice"] not in warned:
                    rep["warnings"].append("Bundle '%s': choice '%s' has only one option, so it is treated as a normal item." % (b["name"], p["choice"])); warned.add(p["choice"])
                p["choice"] = ""
        final.append(b)
    return final


def _parse_defaults(rows, rep):
    out = []
    for i, r in rows[1:]:
        cells = (list(r) + [None] * 3)[:3]
        if not any(_cell(c) for c in cells):
            continue
        when, unless, leave = _terms(cells[0]), _terms(cells[1]), _terms(cells[2])
        if not (when and unless and leave):
            rep["warnings"].append("Defaults row %d skipped: When, Unless and Leave out are all required." % i); continue
        if len(out) >= MAX_DEFAULTS:
            rep["warnings"].append("Defaults: more than %d rows, the rest were ignored." % MAX_DEFAULTS); break
        out.append({"when": when, "unless": unless, "exclude": leave})
    return out


# ------------------------------------------------------------------ compiling for the search
def _toks(term):
    return [t for t in catalog._tokens(term) if len(t) > 1 or t.isdigit()]


def compile_training(train):
    """train (stored form) -> structure used by catalog.smart_search_ex.
    syn: single word -> words of the other terms in its group. phrases: (word sequence, words to add) for multi-word terms.
    scopes: (word sequence, category path); the word itself and every synonym of it limit the search."""
    syn, phrases, scopes, seen = {}, [], [], set()
    train = train or {}
    group_of = {}                                  # term tokens -> list of groups (indexes)
    groups = train.get("groups", [])
    for gi, terms in enumerate(groups):
        tk = [tuple(_toks(t)) for t in terms]
        tk = [t for t in tk if t]
        for me in tk:
            others = [w for o in tk if o != me for w in o if w not in me]
            if not others:
                continue
            others = list(dict.fromkeys(others))
            if len(me) == 1:
                syn.setdefault(me[0], [])
                syn[me[0]].extend(w for w in others if w not in syn[me[0]])
            else:
                phrases.append((me, others))
            group_of.setdefault(me, []).append(gi)
    for sc in train.get("scopes", []):
        words = {tuple(_toks(sc["word"]))}
        for gi in group_of.get(tuple(_toks(sc["word"])), []):
            for t in groups[gi]:
                words.add(tuple(_toks(t)))
        for w in words:
            if w and (w, tuple(sc["path"])) not in seen:
                seen.add((w, tuple(sc["path"])))
                scopes.append((w, tuple(sc["path"])))
    scopes.sort(key=lambda s: -len(s[0]))          # the longest scope phrase wins
    defaults = []
    for d in train.get("defaults", []):
        whens, unless = set(), set()
        for t in d["when"]:
            whens.add(tuple(_toks(t)))
            for gi in group_of.get(tuple(_toks(t)), []):
                whens.update(tuple(_toks(x)) for x in groups[gi])
        for t in d["unless"]:
            unless.update(_toks(t))
            for gi in group_of.get(tuple(_toks(t)), []):
                for x in groups[gi]:
                    unless.update(_toks(x))
        excl = {w for t in d["exclude"] for w in _toks(t)}
        whens = [w for w in whens if w]
        if whens and unless and excl:
            defaults.append((whens, unless, excl))
    bundles = []
    for b in train.get("bundles", []):
        al = []
        for t in [b["name"]] + list(b.get("aliases", [])):
            ts = frozenset(_toks(t))
            if ts and ts not in al:
                al.append(ts)
        bundles.append({"name": b["name"], "aliases": al, "parts": b["parts"]})
    return {"syn": syn, "phrases": phrases, "scopes": scopes, "defaults": defaults, "bundles": bundles}


# ------------------------------------------------------------------ template / export
PANEL_RANGES = [(2, "48-72", "زوجية"), (3, "72-96", "ثلاثية"), (4, "96-120", "رباعية"), (5, "120-168", "خماسية"), (6, "144-192", "سداسية")]


def _example_bundles():
    """Modular distribution panels by number of rows. The codes follow the pattern of the 48-72 panel; the upload report lists any that are not in the catalogue."""
    out = []
    for rows, rng, ar in PANEL_RANGES:
        aliases = ["لوحة %s" % ar, "لوحة %s %s" % (ar, rng), "لوحة %d صفوف" % rows, "لوحة %s" % rng,
                   "%d row panel" % rows, "%d raw panel" % rows, "%d row %s" % (rows, rng), "tableau %d rangees" % rows]
        if rows in (2, 3):
            en = "double" if rows == 2 else "triple"
            aliases += ["%s row panel" % en, "%s row panel %s" % (en, rng), "tableau %s rangee" % en]
        parts = []
        if rows == 2:
            parts.append({"no": "S48M200", "qty": 1, "choice": "", "label": ""})
        parts += [{"no": "40ENL" + rng, "qty": 1, "choice": "", "label": ""},
                  {"no": "PT40SUP" + rng, "qty": 1, "choice": "Door", "label": "Transparent door"},
                  {"no": "PO40SUP" + rng, "qty": 1, "choice": "Door", "label": "White door"}]
        out.append(("لوحة %s %s" % (ar, rng), aliases, parts))
    return out
def training_xlsx(train=None, categories=None, approved=None):
    """Template when train is None (with examples), else an export of the current training."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook()
    ws = wb.active; ws.title = "Synonyms"
    ws.append(list(SYN_HEADERS))
    if train is None:
        ex = [["كونتاكتور, كونتكتور", "contacteur", "contactor", ""],
              ["قاطع حماية, بريكر", "disjoncteur", "circuit breaker, mcb", ""],
              ["مصهر, فيوز", "fusible", "fuse", ""],
              ["لوحة زوجية", "tableau double rangee", "double row panel", "لوحه مزدوجة"]]
        for r in ex:
            ws.append(r)
    else:
        for terms in train.get("groups", []):
            ws.append([", ".join(terms), "", "", ""])
    ws2 = wb.create_sheet("Scopes")
    ws2.append(list(SCOPE_HEADERS))
    if train is None:
        first = (categories or [{"section": "SECTION NAME", "branches": []}])[0]
        ws2.append(["كابل", first["section"], "", ""])
        ws2.append(["cable", first["section"], "", ""])
    else:
        for sc in train.get("scopes", []):
            p = list(sc["path"]) + ["", ""]
            ws2.append([sc["word"], p[0], p[1], p[2]])
    wsb = wb.create_sheet("Bundles"); wsb.append(list(BUNDLE_HEADERS))
    for name, aliases, parts in (_example_bundles() if train is None else
                                 [(b["name"], b.get("aliases", []), b["parts"]) for b in train.get("bundles", [])]):
        for k, p in enumerate(parts):
            wsb.append([name if k == 0 else "", ", ".join(aliases) if k == 0 else "", p["no"], p["qty"], p.get("choice", ""), p.get("label", "")])
    wsd = wb.create_sheet("Defaults"); wsd.append(list(DEFAULT_HEADERS))
    for d in ([{"when": ["contactor"], "unless": ["dc"], "exclude": ["dc"]}] if train is None else train.get("defaults", [])):
        wsd.append([", ".join(d["when"]), ", ".join(d["unless"]), ", ".join(d["exclude"])])
    ws4 = wb.create_sheet("Approved")
    ws4.append(["Wording", "Item No", "Description (information only)"])
    for row in (approved or []):
        ws4.append(list(row))
    ws3 = wb.create_sheet("Read me")
    for line in ("Synonyms: one row = one group of words that mean the same. Put Arabic, French, English terms in their columns.",
                 "A cell may hold several terms separated by commas. Phrases of 2-3 words are allowed (e.g. double row panel).",
                 "Scopes: when the Word is typed (or any synonym of it), the search is limited to that Section / Branch / Sub-Branch.",
                 "Branch and Sub-Branch may be empty. Names must match the category tree exactly (case does not matter).",
                 "Bundles: one row per component. Write the bundle name and its aliases on the first row only. Rows with the same Choice text are alternatives; the customer picks one (e.g. door: transparent / white).",
                 "Defaults: When the word is typed and the Unless word is NOT typed, items containing the Leave out word are hidden (e.g. contactor without dc -> AC only). If that would hide everything, nothing is hidden.",
                 "Approved: wording -> item number pairs that customers chose and the manager approved. Rows you add here are treated as approved.",
                 "Upload this file from Training in the manager menu. Rows with problems are skipped and reported."):
        ws3.append([line])
    fill = PatternFill("solid", fgColor="D9D9D9")
    for w in (ws, ws2, ws4, wsb, wsd):
        for c in w[1]:
            c.font = Font(bold=True); c.fill = fill
        for col in "ABCD":
            w.column_dimensions[col].width = 34
        for row in w.iter_rows():
            for c in row:
                c.alignment = Alignment(wrap_text=True, vertical="top")
    ws3.column_dimensions["A"].width = 120
    for col, wd in (("A", 40), ("B", 20), ("C", 60)):
        ws4.column_dimensions[col].width = wd
    for col, wd in (("A", 30), ("B", 60), ("C", 22), ("D", 8), ("E", 14), ("F", 24)):
        wsb.column_dimensions[col].width = wd
    for col in "ABC":
        wsd.column_dimensions[col].width = 34
    bio = io.BytesIO(); wb.save(bio)
    return bio.getvalue()


# ------------------------------------------------------------------ learned customer choices
def sid_hash(sid):
    return hashlib.sha256(("sharq-learn|" + str(sid)).encode()).hexdigest()[:10]


def learn_add(learned, pairs, sid, now=None):
    """learned: {'q': {wording: {item_no: {'n', 's': [session hashes], 'ok', 'no', 't'}}}}. pairs: [(wording, item_no)].
    Pure function (returns the number of pairs recorded). A session counts once per pair."""
    now = int(now if now is not None else time.time())
    q = learned.setdefault("q", {})
    h, done = sid_hash(sid), 0
    for wording, no in pairs:
        key = catalog.learn_key(wording)
        if not key or not no or len(key) > 120:
            continue
        if key not in q and len(q) >= LEARN_MAX_QUERIES:
            continue
        slot = q.setdefault(key, {})
        if no not in slot and len(slot) >= LEARN_MAX_ITEMS:
            continue
        e = slot.setdefault(no, {"n": 0, "s": [], "ok": False, "no": False, "t": now, "w": clean_text(wording, 120)})
        if e.get("no"):
            continue
        if h not in e["s"] and len(e["s"]) < 6:
            e["s"].append(h)
        e["n"] = e.get("n", 0) + 1; e["t"] = now; done += 1
    return done


def learn_active(learned):
    """-> {wording: {item_no: weight}} of the choices the search may use: ONLY those the manager approved."""
    out = {}
    for key, slot in (learned.get("q") or {}).items():
        for no, e in slot.items():
            if e.get("ok") and not e.get("no"):
                out.setdefault(key, {})[no] = min(5, int(e.get("n", 1)) or 1)
    return out


def learn_pending(learned):
    """Choices waiting for the manager: [(wording key, item_no, entry)], most chosen first, then newest."""
    rows = []
    for key, slot in (learned.get("q") or {}).items():
        for no, e in slot.items():
            if not e.get("no") and not e.get("ok"):
                rows.append((key, no, e))
    rows.sort(key=lambda r: (-len(r[2].get("s", ())), -r[2].get("n", 0), -r[2].get("t", 0)))
    return rows


def learn_approved_rows(learned, by_no=None, with_key=False):
    """Approved choices as rows for the Excel 'Approved' sheet: [wording, item_no, description] (+ the internal key when with_key)."""
    out = []
    for key, slot in sorted((learned.get("q") or {}).items()):
        for no, e in sorted(slot.items()):
            if e.get("ok") and not e.get("no"):
                d = (by_no or {}).get(no)
                out.append([e.get("w") or key, no, d["description"] if d else ""] + ([key] if with_key else []))
    return out


def learn_import_approved(learned, pairs, now=None):
    """Rows from the training Excel 'Approved' sheet become approved choices. Returns how many were added or re-approved."""
    now = int(now if now is not None else time.time())
    q, n = learned.setdefault("q", {}), 0
    for wording, no in pairs:
        key = catalog.learn_key(wording)
        if not key or not no or len(key) > 120:
            continue
        if key not in q and len(q) >= LEARN_MAX_QUERIES:
            continue
        slot = q.setdefault(key, {})
        if no not in slot and len(slot) >= LEARN_MAX_ITEMS:
            continue
        e = slot.setdefault(no, {"n": 1, "s": [], "ok": True, "no": False, "t": now, "w": clean_text(wording, 120)})
        if not e.get("ok") or e.get("no"):
            e["ok"], e["no"] = True, False; n += 1
        elif e.get("t") == now:
            n += 1
    return n


def learn_decide(learned, key, no, approve):
    e = ((learned.get("q") or {}).get(key) or {}).get(no)
    if not e:
        return False
    if approve:
        e["ok"], e["no"] = True, False
    else:
        e["no"], e["ok"] = True, False
    return True


def learn_forget(learned, key, no):
    slot = (learned.get("q") or {}).get(key)
    if slot and no in slot:
        del slot[no]
        if not slot:
            del learned["q"][key]
        return True
    return False
