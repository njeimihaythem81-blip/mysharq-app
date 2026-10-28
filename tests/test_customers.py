import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import auth, orders, security, store
from core.security import LIMITER, THROTTLE
from tests.test_core import fresh


class CustomerTests(unittest.TestCase):
    def setUp(self):
        fresh()

    def test_create_login_and_one_time_code(self):
        ok, code = auth.add_customer("  Ahmed Trading  ")
        self.assertTrue(ok); self.assertRegex(code, r"^[A-Z2-9]{4}-[A-Z2-9]{4}$")
        raw = store.ctx().data.files["customers.json"].decode()
        self.assertNotIn(code, raw); self.assertNotIn(auth.norm_code(code), raw)          # only a hash is stored
        ok, msg, tok, u = auth.customer_login("ahmed trading", code.lower().replace("-", " "), "1.1.1.1")   # case / spaces / dash tolerant
        self.assertTrue(ok); self.assertEqual(u["display"], "Ahmed Trading")
        self.assertEqual(auth.customer_session(tok)["id"], "ahmed trading")
        self.assertFalse(auth.add_customer("AHMED trading")[0]); self.assertFalse(auth.add_customer("a")[0])

    def test_wrong_credentials_generic_and_throttled(self):
        auth.add_customer("Sara")
        ok, msg, *_ = auth.customer_login("Sara", "AAAA-BBBB", "2.2.2.2"); self.assertFalse(ok); self.assertEqual(msg, auth.CUST_GENERIC)
        ok, msg, *_ = auth.customer_login("nobody", "AAAA-BBBB", "2.2.2.2"); self.assertEqual(msg, auth.CUST_GENERIC)
        for _ in range(8):
            r = auth.customer_login("Sara", "AAAA-BBBB", "2.2.2.2")
        self.assertIn("Too many", r[1])

    def test_stop_reset_logout_invalidate_tokens(self):
        _, code = auth.add_customer("Omar")
        tok = auth.customer_login("Omar", code, "3.3.3.3")[2]
        auth.set_customer_active("omar", False); self.assertIsNone(auth.customer_session(tok))
        self.assertFalse(auth.customer_login("Omar", code, "3.3.3.4")[0])
        auth.set_customer_active("omar", True); tok = auth.customer_login("Omar", code, "3.3.3.5")[2]; self.assertTrue(auth.customer_session(tok))
        new = auth.reset_customer_code("omar"); self.assertIsNone(auth.customer_session(tok))
        self.assertFalse(auth.customer_login("Omar", code, "3.3.3.6")[0]); tok = auth.customer_login("Omar", new, "3.3.3.7")[2]
        auth.customer_logout("omar"); self.assertIsNone(auth.customer_session(tok))
        auth.delete_customer("omar"); self.assertIsNone(store.find_customer("omar"))

    def test_customer_token_cannot_be_a_staff_session(self):
        _, code = auth.add_customer("Layla")
        tok = auth.customer_login("Layla", code, "4.4.4.4")[2]
        self.assertIsNone(auth.session_user(tok))
        store.mutate_users(lambda us: us.append({"username": "layla", "display": "X", "hash": "x", "active": True, "token_version": 1}), "t", "t")
        self.assertIsNone(auth.session_user(tok))                                  # same name as an operator: still no staff access
        fake = security.make_token("wrong-secret" * 4, "layla", "customer", 1, 100); self.assertIsNone(auth.customer_session(fake))
        self.assertIsNone(auth.customer_session("")); self.assertIsNone(auth.customer_session(None))

    def test_order_records_account(self):
        _, code = auth.add_customer("Nour")
        o = orders.submit({"LC1D09M7": {"qty": 2, "note": ""}}, "Nour Co", "0912345678", "", "sid-x", "5.5.5.5", "", None, now=10**10, account="nour")
        self.assertTrue(o[0], o[1]); self.assertEqual(o[2]["account"], "nour")
        o = orders.submit({"LC1D09M7": {"qty": 1, "note": ""}}, "Walk In", "0922345678", "", "sid-y", "5.5.5.6", "", None, now=10**10 + 100)
        self.assertNotIn("account", o[2])

    def test_setting_defaults_off(self):
        self.assertFalse(store.settings()["customer_login_required"])


if __name__ == "__main__":
    unittest.main()
