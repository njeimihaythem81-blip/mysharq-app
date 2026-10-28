import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import openpyxl

from core import catalog, listimport, store, training
from tests.test_core import REAL_TREE, fresh

T = REAL_TREE
S1 = T[0]["section"]
S2 = T[1]["section"]


def mk(no, desc, sec, qty=5):
    return {"item_no": no, "description": desc, "section": sec, "branch": "", "sub_branch": "", "qty": qty}


ITEMS = [mk("LC1D09M7", "Contactor 9A 220V", S1), mk("LC1D25M7", "Contactor 25A 220V", S1), mk("LC1D32M7", "Contactor 32A 220V", S1),
         mk("A9F74110", "Circuit breaker 10A 1P", S1), mk("A9F74216", "Circuit breaker 16A 2P", S1),
         mk("CBL001", "Cable 3x2.5 flexible", S2), mk("CBL002", "Cable 5x4 flexible", S2),
         mk("DP48", "Panel double row 48 modules", S2), mk("RELAY1", "Relay 24V", S2), mk("DISJ1", "Disjoncteur differentiel 40A", S1)]


def xl(sheets):
    wb = openpyxl.Workbook(); wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for r in rows:
            ws.append(r)
    b = io.BytesIO(); wb.save(b); return b.getvalue()


class TrainingTests(unittest.TestCase):
    def setUp(self):
        fresh()

    def pub(self, train=None, learned=None):
        return catalog.build_public(ITEMS, T, training.compile_training(train) if train else None, learned)

    def test_template_roundtrip(self):
        tpl = training.training_xlsx(None, T)
        tr, rep = training.parse_training_file(tpl, "t.xlsx", T)
        self.assertIsNone(rep["error"]); self.assertEqual(rep["groups"], 4); self.assertEqual(rep["scopes"], 2)
        out, rep2 = training.parse_training_file(training.training_xlsx(tr, T), "t.xlsx", T)
        self.assertEqual(out["groups"], tr["groups"]); self.assertEqual(len(out["scopes"]), 2)

    def test_parse_reports_bad_rows_not_whole_file(self):
        data = xl({"Synonyms": [["Arabic", "French", "English", "Other"], ["x", "", "", ""], ["كونتاكتور", "contacteur", "contactor", ""]],
                   "Scopes": [["Word", "Section", "Branch", "Sub-Branch"], ["cable", "NO SUCH SECTION", "", ""], ["cable", S2.lower(), "", ""], ["", S1, "", ""]]})
        tr, rep = training.parse_training_file(data, "a.xlsx", T)
        self.assertEqual((rep["groups"], rep["scopes"]), (1, 1)); self.assertEqual(len(rep["warnings"]), 3)
        self.assertEqual(tr["scopes"][0]["path"], [S2])

    def test_parse_rejects(self):
        self.assertIsNotNone(training.parse_training_file(b"x", "a.csv", T)[1]["error"])
        self.assertIsNotNone(training.parse_training_file(b"not a zip", "a.xlsx", T)[1]["error"])
        self.assertIsNotNone(training.parse_training_file(xl({"Other": [["a"]]}), "a.xlsx", T)[1]["error"])
        self.assertIsNotNone(training.parse_training_file(b"x" * (6 * 1024 * 1024), "a.xlsx", T)[1]["error"])

    def test_synonyms_french_arabic(self):
        tr = {"groups": [["كونتاكتور", "contacteur", "contactor"], ["قاطع تفاضلي", "disjoncteur differentiel", "rcd"]], "scopes": []}
        c = self.pub(tr)
        r = catalog.smart_search(c, "contacteur 25A")[0]; self.assertEqual(r[0]["item_no"], "LC1D25M7")
        r = catalog.smart_search(c, "différentiel")[0]; self.assertEqual(r[0]["item_no"], "DISJ1")       # accents folded
        r = catalog.smart_search(c, "قاطع تفاضلي")[0]; self.assertEqual(r[0]["item_no"], "DISJ1")         # phrase -> French words

    def test_scope_limits_search(self):
        tr = {"groups": [["كابل", "cable", "cable"]], "scopes": [{"word": "cable", "path": [S2]}]}
        c = self.pub(tr)
        res, mode, info = catalog.smart_search_ex(c, "كابل")
        self.assertEqual(info["scope"], (S2,)); self.assertEqual({r["item_no"] for r in res}, {i["item_no"] for i in ITEMS if i["section"] == S2})
        res, _, info = catalog.smart_search_ex(c, "cable 5x4")
        self.assertEqual(res[0]["item_no"], "CBL002"); self.assertTrue(all(r["section"] == S2 for r in res))
        res, _, info = catalog.smart_search_ex(c, "cable contactor")          # scope has no match for the other word -> falls back
        self.assertTrue(res)

    def test_no_training_same_as_before(self):
        c = self.pub()
        self.assertEqual(catalog.smart_search(c, "contactor 25")[0][0]["item_no"], "LC1D25M7")

    def test_learned_needs_manager_approval_always(self):
        L = {}
        for sid in ("s1", "s2", "s3", "s4"):                                  # many different customers choose the same thing
            training.learn_add(L, [("اللمبه الحمراء", "RELAY1")], sid)
        self.assertEqual(training.learn_active(L), {})                       # still nothing: only the manager can activate
        self.assertEqual(len(training.learn_pending(L)), 1); self.assertEqual(len(training.learn_pending(L)[0][2]["s"]), 4)
        k = list(L["q"])[0]
        training.learn_decide(L, k, "RELAY1", True)
        act = training.learn_active(L); self.assertEqual(len(act), 1)
        c = self.pub(None, act)
        res, mode, info = catalog.smart_search_ex(c, "اللمبه الحمراء"); self.assertEqual(res[0]["item_no"], "RELAY1"); self.assertTrue(info["learned"])
        training.learn_decide(L, k, "RELAY1", False); self.assertEqual(training.learn_active(L), {})
        for sid in ("a", "b", "c"):
            training.learn_add(L, [("اللمبه الحمراء", "RELAY1")], sid)
        self.assertEqual(training.learn_active(L), {}); self.assertEqual(training.learn_pending(L), [])   # rejected stays rejected
        training.learn_forget(L, k, "RELAY1"); self.assertEqual(L["q"], {})

    def test_approved_sheet_roundtrip(self):
        L = {}
        training.learn_add(L, [("لمبة بيان حمراء", "RELAY1"), ("tableau 48", "DP48")], "s1")
        for k, slot in L["q"].items():
            for no in slot:
                training.learn_decide(L, k, no, True)
        by_no = self.pub()["by_no"]
        rows = training.learn_approved_rows(L, by_no); self.assertEqual(len(rows), 2); self.assertEqual({r[1] for r in rows}, {"RELAY1", "DP48"})
        self.assertIn("لمبة بيان حمراء", [r[0] for r in rows])                  # the ORIGINAL wording is exported, not the normalised key
        data = training.training_xlsx({"groups": [], "scopes": []}, T, rows)
        tr, rep = training.parse_training_file(data, "x.xlsx", T, set(by_no))
        self.assertIsNone(rep["error"]); self.assertEqual(rep["approved"], 2)
        M = {}; self.assertEqual(training.learn_import_approved(M, tr["approved"]), 2)
        self.assertEqual(len(training.learn_active(M)), 2)
        bad = xl({"Approved": [["Wording", "Item No"], ["x y", "NOPE"], ["", "RELAY1"], ["ok word", "RELAY1"]]})
        tr, rep = training.parse_training_file(bad, "x.xlsx", T, set(by_no)); self.assertEqual(rep["approved"], 1); self.assertEqual(len(rep["warnings"]), 2)

    def test_learned_limits(self):
        L = {}
        for i in range(training.LEARN_MAX_QUERIES + 50):
            training.learn_add(L, [("word%d" % i, "X")], "s")
        self.assertLessEqual(len(L["q"]), training.LEARN_MAX_QUERIES)
        L = {}
        for i in range(20):
            training.learn_add(L, [("same", "I%d" % i)], "s")
        self.assertEqual(len(L["q"]["same"]), training.LEARN_MAX_ITEMS)

    def test_store_roundtrip_and_conflict(self):
        data, _, _ = fresh()
        training_ = {"groups": [["a1", "b1"]], "scopes": [], "approved": [["zzz", "LRD08"]]}
        store.save_training(training_, "manager"); self.assertEqual(store.training_data(), {"groups": [["a1", "b1"]], "scopes": []})
        self.assertEqual(store.record_choices([("hello world", "LRD08")], "sid1"), 1)
        self.assertEqual(len(store.learned()["q"]), 1); self.assertEqual(store.public()["learned"], {})          # pending: not used
        self.assertEqual(store.record_choices([], "sid1"), 0)
        k = list(store.learned()["q"])[0]
        store.decide_learned(k, "LRD08", True, "manager"); self.assertEqual(len(training.learn_active(store.learned())), 1)
        self.assertIn(k, store.public()["learned"])
        store.forget_learned(k, "LRD08", "manager"); self.assertEqual(store.learned()["q"], {})
        self.assertEqual(store.import_approved([("zzz", "LRD08")], "manager"), 1)
        self.assertEqual(len(store.public()["learned"]), 1)


class ListImportTests(unittest.TestCase):
    def setUp(self):
        fresh()
        self.tr = {"groups": [["كونتاكتور", "contacteur", "contactor"]], "scopes": []}
        self.cat = catalog.build_public(ITEMS, T, training.compile_training(self.tr))

    def test_parse_line(self):
        P = listimport.parse_line
        self.assertEqual(P("2 x contactor 25A"), ("contactor 25A", 2)); self.assertEqual(P("contactor 25A x3"), ("contactor 25A", 3))
        self.assertEqual(P("relay 24V : 5"), ("relay 24V", 5)); self.assertEqual(P("5 pcs fuse"), ("fuse", 5))
        self.assertEqual(P("٣ × كونتاكتور"), ("كونتاكتور", 3)); self.assertEqual(P("contactor 25A"), ("contactor 25A", 1))
        self.assertEqual(P("- relay 24V"), ("relay 24V", 1)); self.assertEqual(P("LC1D09M7")[1], 1)
        self.assertEqual(P("cable 3x2.5")[1], 1)                              # 3x2.5 is a size, not a quantity
        self.assertEqual(P("x5")[1], 1)

    def test_excel_with_header(self):
        d = xl({"S": [["Item No", "Description", "Qty"], ["LC1D09M7", "", 4], ["", "contacteur 32A", 2], ["", "", ""]]})
        lines, notes, err = listimport.extract_lines(d, "l.xlsx")
        self.assertIsNone(err); self.assertEqual([(l["text"], l["qty"]) for l in lines], [("LC1D09M7", 4), ("contacteur 32A", 2)])
        m = listimport.match_all(self.cat, lines)
        self.assertEqual(m[0]["cands"][0], "LC1D09M7"); self.assertEqual(m[0]["state"], "auto")
        self.assertEqual(m[1]["cands"][0], "LC1D32M7")

    def test_excel_without_header_and_arabic_header(self):
        d = xl({"S": [["contactor 25A", 3], ["relay 24V", 1]]})
        lines, _, err = listimport.extract_lines(d, "l.xlsx"); self.assertEqual([(l["text"], l["qty"]) for l in lines], [("contactor 25A", 3), ("relay 24V", 1)])
        d = xl({"S": [["رقم الصنف", "الكمية"], ["LC1D25M7", 6]]})
        lines, _, err = listimport.extract_lines(d, "l.xlsx"); self.assertEqual([(l["text"], l["qty"]) for l in lines], [("LC1D25M7", 6)])

    def test_text_csv(self):
        lines, _, e = listimport.extract_lines("2 x contactor 25A\n\n  \nrelay 24V : 5\n".encode(), "a.txt")
        self.assertEqual([(l["text"], l["qty"]) for l in lines], [("contactor 25A", 2), ("relay 24V", 5)])
        lines, _, e = listimport.extract_lines(b"code,qty\nLRD08,7\n", "a.csv"); self.assertEqual((lines[0]["text"], lines[0]["qty"]), ("LRD08", 7))

    def test_pdf_text_and_scanned(self):
        from reportlab.pdfgen import canvas
        b = io.BytesIO(); c = canvas.Canvas(b); c.drawString(72, 750, "2 x contactor 25A"); c.drawString(72, 730, "relay 24V : 5"); c.save()
        lines, _, err = listimport.extract_lines(b.getvalue(), "a.pdf")
        self.assertIsNone(err); self.assertEqual([(l["text"], l["qty"]) for l in lines], [("contactor 25A", 2), ("relay 24V", 5)])
        b = io.BytesIO(); c = canvas.Canvas(b); c.showPage(); c.save()
        self.assertIn("scanned", listimport.extract_lines(b.getvalue(), "a.pdf")[2])

    def test_rejects(self):
        self.assertIsNotNone(listimport.extract_lines(b"x", "a.docx")[2])
        self.assertIsNotNone(listimport.extract_lines(b"\x00\x01", "a.pdf")[2])
        self.assertIsNotNone(listimport.extract_lines(b"x" * (6 * 1024 * 1024), "a.txt")[2])
        self.assertIsNotNone(listimport.extract_lines(b"", "a.txt")[2])

    def test_line_cap(self):
        lines, notes, err = listimport.extract_lines("\n".join("item%d" % i for i in range(400)).encode(), "a.txt")
        self.assertEqual(len(lines), listimport.MAX_LINES); self.assertTrue(notes)

    def test_states(self):
        M = lambda t: listimport.match_line(self.cat, {"text": t, "qty": 1})
        self.assertEqual(M("A9F74110")["state"], "auto")                         # exact item number
        self.assertEqual(M("contactor")["state"], "suggest")                     # three equally good items: ambiguous -> suggestions
        self.assertEqual(len(M("contactor")["cands"]), 3)
        self.assertEqual(M("zzzzqq")["state"], "manual"); self.assertEqual(M("zzzzqq")["cands"], [])
        self.assertEqual(M("breaker 16A 2P")["cands"][0], "A9F74216")

    def test_learned_makes_auto(self):
        L = {}
        training.learn_add(L, [("اللي في الصورة", "RELAY1")], "a")
        k = list(L["q"])[0]; training.learn_decide(L, k, "RELAY1", True)
        cat = catalog.build_public(ITEMS, T, None, training.learn_active(L))
        m = listimport.match_line(cat, {"text": "اللي في الصورة", "qty": 1}); self.assertEqual((m["state"], m["cands"][0]), ("auto", "RELAY1"))


if __name__ == "__main__":
    unittest.main()
