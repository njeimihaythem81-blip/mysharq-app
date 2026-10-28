"""Exercises ui/listview.py logic with a stand-in for Streamlit (skipped when the real Streamlit is installed)."""
import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import streamlit  # noqa
    HAVE_ST = True
except ImportError:
    HAVE_ST = False


class SS(dict):
    __getattr__ = lambda self, k: self.get(k)
    __setattr__ = dict.__setitem__


class F:
    def __init__(self, name, data):
        self.name, self._d = name, data

    def getvalue(self):
        return self._d


def get_st():
    """One shared stand-in for streamlit (UI modules keep a reference to the first one they import)."""
    if "streamlit" in sys.modules and getattr(sys.modules["streamlit"], "_is_stub", False):
        return sys.modules["streamlit"]
    st = MagicMock(); st._is_stub = True; st.session_state = SS()
    sys.modules["streamlit"] = st; sys.modules["streamlit.components"] = st.components; sys.modules["streamlit.components.v1"] = st.components.v1
    return st


def quiet(st):
    st.session_state.clear()
    for n in ("button", "form_submit_button", "download_button", "link_button"):
        getattr(st, n).reset_mock(); getattr(st, n).return_value = False
    st.text_input.return_value = ""; st.file_uploader.return_value = None; st.toggle.return_value = False
    st.columns.side_effect = lambda n, *a, **k: [st] * (n if isinstance(n, int) else len(n))
    return st


@unittest.skipIf(HAVE_ST, "real streamlit present")
class ScreensStub(unittest.TestCase):
    def test_gate(self):
        st = quiet(get_st())
        from core import auth, store
        from tests.test_core import fresh
        from ui import common, gate
        fresh()
        ss = st.session_state
        self.assertTrue(gate.passed({"customer_login_required": False}))                      # off: open to everyone
        S = {"customer_login_required": True}
        common.bstore = lambda *a, **k: None
        self.assertFalse(gate.passed(S))                                                       # waiting for the browser
        common.bstore = lambda *a, **k: ""
        self.assertFalse(gate.passed(S)); self.assertFalse(ss.get("cust"))                     # empty browser: login form
        _, code = auth.add_customer("Zaid")
        tok = auth.customer_login("Zaid", code, "9.9.9.9")[2]
        common.bstore = lambda *a, **k: tok                                                    # remembered on this device
        self.assertTrue(gate.passed(S)); self.assertEqual(ss.cust["display"], "Zaid")
        ss.clear(); common.bstore = lambda *a, **k: "garbage"
        self.assertFalse(gate.passed(S))
        ss.clear(); ss.staff_ok = True; self.assertTrue(gate.passed(S))                       # staff pass
        ss.clear(); ss.cust_token = tok; ss.cust = {"id": "zaid", "display": "Zaid"}
        gate._sign_out(); self.assertIsNone(auth.customer_session(tok)); self.assertTrue(ss.cust_clear)
        common.bstore = lambda *a, **k: ""
        ss.pop("cust_token", None); self.assertFalse(gate.passed(S))

    def test_manager_screens_run(self):
        st = quiet(get_st())
        from core import auth, catalog, store, training
        from tests.test_core import fresh
        from tests.test_training import ITEMS, T
        from ui import staff_manager as sm
        fresh()
        user = {"role": "manager", "id": "manager", "display": "M"}
        auth.add_customer("Rami"); store.record_choices([("hello", "LRD08")], "s1")
        sm.screen_customers(user, store.settings())
        sm.screen_training(user, store.settings())
        st.text_input.return_value = "contactor"; sm.screen_training(user, store.settings())
        st.button.side_effect = lambda label, *a, **k: label == "Approve"
        sm.screen_training(user, store.settings()); st.button.side_effect = None
        self.assertEqual(len(training.learn_active(store.learned())), 1)
        st.text_input.return_value = ""
        st.button.side_effect = lambda label, *a, **k: label == "Turn it ON"
        sm.screen_customers(user, store.settings()); st.button.side_effect = None
        self.assertTrue(store.settings()["customer_login_required"])


@unittest.skipIf(HAVE_ST, "real streamlit present")
class BundleStub(unittest.TestCase):
    def setUp(self):
        from core import catalog, training
        from tests.test_bundles import ITEMS, T, template_train
        from tests.test_core import fresh
        fresh()
        tr, _ = template_train({i["item_no"] for i in ITEMS})
        self.cat = catalog.build_public(ITEMS, T, training.compile_training(tr))
        self.st = quiet(get_st())

    def test_bundle_card_adds_everything_with_the_chosen_door(self):
        from ui import bundleview
        ss = self.st.session_state; ss.sid = "s"; ss.basket = {}
        b = self.cat["train"]["bundles"][0]
        bundleview.render(self.cat, b, "sb0")                                   # renders without a choice made
        self.assertEqual(bundleview.picks_from_state(self.cat, b, "sb0"), {})
        bundleview._add(self.cat, b, "sb0"); self.assertEqual(ss.basket, {})    # no door chosen: nothing is added
        ss["sb0_c_Door"] = "White door  |  PO40SUP48-72"; ss["sb0_q"] = 2
        bundleview._add(self.cat, b, "sb0")
        self.assertEqual({k: v["qty"] for k, v in ss.basket.items()}, {"S48M200": 2, "40ENL48-72": 2, "PO40SUP48-72": 2})
        self.assertIn("added", ss.flash)

    def test_bundle_row_in_imported_list(self):
        from ui import listview
        ss = self.st.session_state; ss.sid = "s"; ss.basket = {}
        listview._read(self.cat, F("a.txt", "2 x لوحة زوجية 48\ncontactor 25\n".encode()))
        rows = ss.imp["rows"]; self.assertEqual(rows[0]["state"], "bundle"); self.assertEqual(rows[0]["qty"], 2)
        listview._row(self.cat, rows[0])
        self.assertFalse(listview._ready(self.cat, rows[0]))
        ss["ib0_c_Door"] = "Transparent door  |  PT40SUP48-72"; ss["imp_q_0"] = 2
        self.assertTrue(listview._ready(self.cat, rows[0]))
        listview._add_all(self.cat)
        # the second line "contactor 25" was matched to the AC contactor automatically (the DC one is hidden by the default rule)
        self.assertEqual({k: v["qty"] for k, v in ss.basket.items()}, {"S48M200": 2, "40ENL48-72": 2, "PT40SUP48-72": 2, "LC1D25M7": 1})

    def test_not_a_bundle(self):
        from ui import listview
        ss = self.st.session_state; ss.sid = "s"; ss.basket = {}
        listview._read(self.cat, F("a.txt", "لوحة زوجية 48\n".encode()))
        r = ss.imp["rows"][0]; listview._not_bundle(r); self.assertIn(r["state"], ("suggest", "manual")); self.assertIsNone(r["bundle"])


@unittest.skipIf(HAVE_ST, "real streamlit present")
class ListViewStub(unittest.TestCase):
    def test_flow(self):
        st = quiet(get_st())
        from core import catalog, store
        from tests.test_core import fresh
        from tests.test_training import ITEMS, T
        from ui import listview
        fresh()
        cat = catalog.build_public(ITEMS, T)
        ss = st.session_state; ss.sid = "sid-1"; ss.basket = {}; ss.view = "import"
        listview._read(cat, F("a.txt", b"LC1D09M7 x2\ncontactor\nzzzzqq\n"))
        rows = ss.imp["rows"]
        self.assertEqual([r["state"] for r in rows], ["auto", "suggest", "manual"])
        self.assertEqual(listview._chosen(rows[0]), ("LC1D09M7", "auto")); self.assertEqual(listview._chosen(rows[1]), (None, None))
        ss["imp_c_1"] = "%s  |  %s" % (rows[1]["cands"][1], "x")
        self.assertEqual(listview._chosen(rows[1]), (rows[1]["cands"][1], "pick"))
        rows[2]["chosen"], rows[2]["src"] = "A9F74110", "typed"
        ss["imp_q_0"] = 2; ss["imp_q_1"] = 3
        listview._add_all(cat)
        self.assertEqual(ss.basket["LC1D09M7"]["qty"], 2); self.assertEqual(ss.basket[rows[1]["cands"][1]]["qty"], 3)
        self.assertEqual(ss.basket["A9F74110"]["qty"], 1); self.assertEqual(ss.view, "browse"); self.assertIsNone(ss.imp)
        self.assertIn("added", ss.flash)
        self.assertEqual(len(store.learned()["q"]), 2)                       # only the two choices the customer made were remembered
        ss.imp_edit = None


if __name__ == "__main__":
    unittest.main()
