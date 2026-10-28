import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import openpyxl

from core import bundles, catalog, listimport, training
from tests.test_core import REAL_TREE, fresh
from tests.test_training import xl

T = REAL_TREE
S1, S2 = T[0]["section"], T[1]["section"]


def mk(no, desc, sec=S2):
    return {"item_no": no, "description": desc, "section": sec, "branch": "", "sub_branch": "", "qty": 5}


# the four items visible in the customer's stock-system screenshot, plus contactors with AC and DC coils
ITEMS = [mk("S48M200", "METAL LIDS KIT SURFACE 48MOD 200MM"), mk("40ENL48-72", "DISTRIBUTION WITHOUT DOOR (48-72 MOD.)"),
         mk("PT40SUP48-72", "TRANSPARENT DOOR FOR CABINET 48-72 MOD."), mk("PO40SUP48-72", "WHITE DOOR FOR CABINET 48-72 MOD."),
         mk("40ENL72-96", "DISTRIBUTION WITHOUT DOOR (72-96 MOD.)"), mk("PT40SUP72-96", "TRANSPARENT DOOR FOR CABINET 72-96 MOD."),
         mk("PO40SUP72-96", "WHITE DOOR FOR CABINET 72-96 MOD."),
         mk("LC1D09M7", "Contactor 9A 220VAC", S1), mk("LC1D09BD", "Contactor 9A 24VDC", S1), mk("LC1D25BD", "Contactor 25A 24VDC", S1),
         mk("LC1D25M7", "Contactor 25A 220VAC", S1), mk("DCONLY", "Contactor DC 40A", S1)]


def template_train(item_nos=None):
    tpl = training.training_xlsx(None, T)
    tr, rep = training.parse_training_file(tpl, "t.xlsx", T, item_nos)
    return tr, rep


class BundleTests(unittest.TestCase):
    def setUp(self):
        fresh()
        self.tr, self.rep = template_train({i["item_no"] for i in ITEMS})
        self.cat = catalog.build_public(ITEMS, T, training.compile_training(self.tr))

    def test_template_has_five_panels_and_default_rule(self):
        tr, rep = template_train()
        self.assertEqual(rep["bundles"], 5); self.assertEqual(rep["defaults"], 1)
        names = [b["name"] for b in tr["bundles"]]
        self.assertIn("لوحة زوجية 48-72", names); self.assertIn("لوحة سداسية 144-192", names)
        b = tr["bundles"][0]
        self.assertEqual([p["no"] for p in b["parts"]], ["S48M200", "40ENL48-72", "PT40SUP48-72", "PO40SUP48-72"])
        self.assertEqual([p["choice"] for p in b["parts"]], ["", "", "Door", "Door"])
        self.assertEqual(tr["bundles"][4]["parts"][1]["no"], "PT40SUP144-192")

    def test_missing_codes_are_reported_not_fatal(self):
        self.assertEqual(self.rep["bundles"], 2)                                   # only 48-72 and 72-96 exist in this catalogue
        self.assertTrue(any("is not in the catalogue" in w for w in self.rep["warnings"]))

    def test_roundtrip_export(self):
        out = training.training_xlsx(self.tr, T)
        tr2, rep2 = training.parse_training_file(out, "x.xlsx", T)
        self.assertEqual(tr2["bundles"], self.tr["bundles"]); self.assertEqual(tr2["defaults"], self.tr["defaults"])

    def test_find_by_name_alias_and_numbers(self):
        f = lambda q: [b["name"] for _, b in bundles.find(self.cat, q)]
        self.assertEqual(f("لوحة زوجية 48")[0], "لوحة زوجية 48-72")
        self.assertEqual(f("2 row panel"), ["لوحة زوجية 48-72"]); self.assertEqual(f("double row panel 48-72")[0], "لوحة زوجية 48-72")
        self.assertIn("لوحة ثلاثية 72-96", f("لوحة 72")); self.assertIn("لوحة زوجية 48-72", f("لوحة 72"))
        self.assertEqual(f("لوحة زوجية 96"), []); self.assertEqual(f("كونتاكتور"), []); self.assertEqual(f("48"), [])
        self.assertEqual(f("لوحة زوجية"), ["لوحة زوجية 48-72"])                        # no number typed: the 2-row bundle by name
        self.assertEqual(f("tableau 3 rangées")[0], "لوحة ثلاثية 72-96")                 # French, accents ignored

    def test_choice_and_expand(self):
        b = self.cat["train"]["bundles"][0]
        fixed, choices = bundles.resolve(self.cat, b)
        self.assertEqual([p["no"] for p in fixed], ["S48M200", "40ENL48-72"]); self.assertEqual(list(choices), ["Door"])
        lines, missing = bundles.expand(self.cat, b, {}, 2); self.assertEqual(missing, ["Door"])
        lines, missing = bundles.expand(self.cat, b, {"Door": "PT40SUP48-72"}, 3)
        self.assertEqual(missing, []); self.assertEqual(dict(lines), {"S48M200": 3, "40ENL48-72": 3, "PT40SUP48-72": 3})
        lines, _ = bundles.expand(self.cat, b, {"Door": "BOGUS"}, 1); self.assertEqual(len(lines), 2)       # unknown pick is ignored

    def test_bundle_validation_messages(self):
        data = xl({"Bundles": [list(training.BUNDLE_HEADERS),
                               ["Kit A", "kit alpha", "S48M200", 2, "", ""], ["", "", "40ENL48-72", "x", "", ""], ["", "", "NOPE", 1, "", ""],
                               ["", "", "PT40SUP48-72", 1, "Door", "Clear"],
                               ["Empty", "", "NOPE2", 1, "", ""], ["", "", "S48M200", 1, "", ""]]})
        tr, rep = training.parse_training_file(data, "b.xlsx", T, {i["item_no"] for i in ITEMS})
        self.assertEqual([b["name"] for b in tr["bundles"]], ["Kit A", "Empty"])
        self.assertEqual([p["no"] for p in tr["bundles"][0]["parts"]], ["S48M200", "PT40SUP48-72"]); self.assertEqual(tr["bundles"][0]["parts"][1]["choice"], "")
        msgs = " ".join(rep["warnings"]); self.assertIn("quantity", msgs); self.assertIn("only one option", msgs); self.assertIn("NOPE", msgs)

    def test_line_becomes_bundle_row(self):
        lines = [{"text": "لوحة زوجية 48", "alt": "", "qty": 2}, {"text": "40ENL48-72", "alt": "", "qty": 1}, {"text": "كونتاكتور", "alt": "", "qty": 1}]
        rows = listimport.match_all(self.cat, lines)
        self.assertEqual(rows[0]["state"], "bundle"); self.assertEqual(self.cat["train"]["bundles"][rows[0]["bundle"]]["name"], "لوحة زوجية 48-72")
        self.assertEqual(rows[1]["state"], "auto"); self.assertIsNone(rows[1]["bundle"])      # an exact item number is never a bundle


class DefaultsTests(unittest.TestCase):
    def setUp(self):
        fresh()
        tr, _ = template_train({i["item_no"] for i in ITEMS})
        tr["groups"] = [["كونتاكتور", "contacteur", "contactor"], ["تيار مستمر", "courant continu", "dc"]]
        self.cat = catalog.build_public(ITEMS, T, training.compile_training(tr))

    def nos(self, q):
        res, mode, info = catalog.smart_search_ex(self.cat, q)
        return {r["item_no"] for r in res}, info

    def test_ac_by_default(self):
        nos, info = self.nos("contactor 25")
        self.assertEqual(nos & {"LC1D25M7", "LC1D25BD"}, {"LC1D25M7"}); self.assertEqual(info["default"], ["dc"])

    def test_dc_when_written(self):
        for q in ("contactor 25 dc", "contactor 25 24VDC", "contactor 25 courant continu", "contactor 25 تيار مستمر"):
            nos, info = self.nos(q); self.assertIn("LC1D25BD", nos, q); self.assertIsNone(info["default"], q)

    def test_arabic_and_french_trigger_the_rule(self):
        for q in ("كونتاكتور 25", "contacteur 25"):
            nos, info = self.nos(q); self.assertNotIn("LC1D25BD", nos, q); self.assertIn("LC1D25M7", nos, q)

    def test_never_hides_everything_and_other_words_unaffected(self):
        nos, info = self.nos("contactor 40")
        self.assertIn("DCONLY", nos); self.assertIsNone(info["default"])               # only a DC item matches: shown, not hidden
        nos, _ = self.nos("LC1D25BD"); self.assertIn("LC1D25BD", nos)                  # exact item number: rule not triggered
        nos, _ = self.nos("white door"); self.assertIn("PO40SUP48-72", nos)

    def test_word_match(self):
        w = catalog.word_match
        self.assertTrue(w("dc", "dc")); self.assertTrue(w("24vdc", "dc")); self.assertFalse(w("adc", "dc")); self.assertFalse(w("dcs", "dc"))


if __name__ == "__main__":
    unittest.main()
