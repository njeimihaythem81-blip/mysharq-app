"""Functional bundles (v2.6): one name that stands for several items, e.g. a modular panel = enclosure + door + lids kit.
A bundle may have choices (the customer picks one of several doors); everything else is added together, times a quantity."""
from . import catalog


def find(cat, query, limit=3):
    """Bundles whose name or alias is written in `query` -> [(index, bundle)] best first.
    All the words of an alias must be present (synonyms count); if the query has numbers, one must appear in the alias."""
    bl = (cat.get("train") or {}).get("bundles") or []
    if not bl:
        return []
    q = [t for t in catalog._tokens(catalog.clean_text(query, 120)) if len(t) > 1 or t.isdigit()]
    if not q:
        return []
    syn = cat["train"].get("syn", {})
    qx = set(q)
    for t in q:
        qx.update(syn.get(t, ()))
    qnames = {t for t in q if not t.isdigit()}
    qnums = {t for t in q if t.isdigit()}
    if not qnames:
        return []
    out = []
    for i, b in enumerate(bl):
        best = None
        for al in b["aliases"]:
            names, nums = {t for t in al if not t.isdigit()}, {t for t in al if t.isdigit()}
            if not names or not names <= qx:
                continue
            if len(names & qx) < 0.6 * len(qnames):
                continue                                       # most of what was typed must be about this bundle ('double row ... 96' is not the 3-row panel)
            if qnums and not (nums & qnums):
                continue
            sc = len(names) * 10 + len(nums & qnums) * 5 - len(nums - qnums) * 0.1
            if best is None or sc > best:
                best = sc
        if best is not None and any(resolve(cat, b)):
            out.append((best, i, b))
    out.sort(key=lambda x: (-x[0], x[2]["name"]))
    return [(i, b) for _, i, b in out[:limit]]


def resolve(cat, b):
    """-> (fixed parts, {choice name: [parts]}) keeping only parts whose item exists. A choice left with one option becomes fixed."""
    by_no = cat["by_no"]
    fixed, choices = [], {}
    for p in b["parts"]:
        if p["no"] not in by_no:
            continue
        (choices.setdefault(p["choice"], []) if p["choice"] else fixed).append(p)
    for name in [n for n, v in choices.items() if len(v) < 2]:
        fixed.extend(choices.pop(name))
    return fixed, choices


def part_label(cat, p):
    d = cat["by_no"].get(p["no"])
    return p.get("label") or (d["description"] if d else p["no"])


def expand(cat, b, picks, mult=1):
    """-> ([(item_no, qty)], [choice names still not picked]). picks = {choice name: item_no}."""
    fixed, choices = resolve(cat, b)
    mult = max(1, min(9999, int(mult or 1)))
    lines, missing = [], []
    for p in fixed:
        lines.append((p["no"], min(9999, p["qty"] * mult)))
    for name, opts in choices.items():
        chosen = next((o for o in opts if o["no"] == picks.get(name)), None)
        if chosen is None:
            missing.append(name)
        else:
            lines.append((chosen["no"], min(9999, chosen["qty"] * mult)))
    return lines, missing
