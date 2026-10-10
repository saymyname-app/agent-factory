#!/usr/bin/env python3
"""bin/test-cases-compare (CI01, Spec af-q9urgr §1 and Testing Decisions 3
and 4): the same cases with the same verifications are accepted; a case that
is gone, a case renamed, a verification removed — in the case or in a helper
it uses — are refused, the case named.

The command is called through its entry function in this process, same
arguments, same observations (exit status, stdout, stderr); one pass and one
refusal are launched as a real process, which proves the command line itself.
"""
import importlib.machinery
import importlib.util
import io
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "test-cases-compare"

_loader = importlib.machinery.SourceFileLoader("test_cases_compare", str(TOOL))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
tool = importlib.util.module_from_spec(_spec)
_loader.exec_module(tool)

# A test file as the command reads one: two cases, one of them through a helper.
BEFORE = """
    import unittest


    def page(address):
        assert address
        return "ok"


    class ShopTest(unittest.TestCase):
        def paid(self, order):
            self.assertTrue(order)
            self.assertEqual("paid", order["state"])
            return order

        def test_an_order_is_paid(self):
            order = self.paid({"state": "paid"})
            self.assertIn("state", order)

        def test_the_page_answers(self):
            self.assertEqual("ok", page("http://localhost"))
"""


class TestCasesCompareTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="test-cases-compare-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def source(self, name, text):
        path = self.tmp / name
        path.write_text(textwrap.dedent(text))
        return path

    def compare(self, before, *after):
        """The entry function, as the command line calls it: (status, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        args = ["--before", str(self.source("before-test.py", before))]
        for number, text in enumerate(after):
            args += ["--after", str(self.source(f"after-{number}-test.py", text))]
        status = tool.main(args, stdout=out, stderr=err)
        return status, out.getvalue(), err.getvalue()

    def refused(self, after, *mentions):
        status, out, err = self.compare(BEFORE, after)
        self.assertEqual((1, ""), (status, out), err)
        for mention in mentions:
            self.assertIn(mention, err)
        return err

    # --- accepted ---------------------------------------------------------------

    def test_the_same_cases_with_the_same_verifications_are_accepted(self):
        status, out, err = self.compare(BEFORE, BEFORE)

        self.assertEqual((0, ""), (status, err))
        self.assertIn("2 cas, 5 vérifications avant, 5 après sur les mêmes cas : identiques", out)

    def test_a_decor_built_another_way_is_accepted_when_cases_and_verifications_stay(self):
        after = BEFORE.replace('order = self.paid({"state": "paid"})',
                               'order = self.stage("paid", lambda: self.paid({"state": "paid"}))')

        status, out, err = self.compare(BEFORE, after)

        self.assertEqual((0, ""), (status, err))
        self.assertIn("identiques", out)

    def test_a_file_cut_in_two_is_accepted_when_the_two_halves_hold_every_case(self):
        first = BEFORE[:BEFORE.index("        def test_the_page_answers")]
        second = BEFORE[:BEFORE.index("        def test_an_order_is_paid")] + BEFORE[BEFORE.index("        def test_the_page_answers"):]

        status, out, err = self.compare(BEFORE, first, second)

        self.assertEqual((0, ""), (status, err))
        self.assertIn("2 cas, 5 vérifications avant, 5 après", out)

    def test_a_new_case_and_an_added_verification_are_accepted_and_named(self):
        after = BEFORE.replace('self.assertIn("state", order)', 'self.assertIn("state", order)\n            self.assertTrue(order)')
        after += "\n        def test_a_refund_is_shown(self):\n            self.fail('pas encore')\n"

        status, out, err = self.compare(BEFORE, after)

        self.assertEqual((0, ""), (status, err))
        self.assertIn("aucun cas ni vérification en moins", out)
        self.assertIn("vérifications en plus : ShopTest.test_an_order_is_paid en avait 3, en a 4", out)
        self.assertIn("cas nouveau : ShopTest.test_a_refund_is_shown (1 vérifications)", out)

    def test_a_case_inherited_from_a_class_of_the_file_counts_for_the_class_that_inherits_it(self):
        before = BEFORE + "\n\n    class OtherShopTest(ShopTest):\n        pass\n"
        after = before.replace("class OtherShopTest(ShopTest):", "class OtherShopTest(unittest.TestCase):")

        status, _out, err = self.compare(before, after)

        self.assertEqual(1, status)
        self.assertIn("cas disparu : OtherShopTest.test_an_order_is_paid (3 vérifications)", err)
        self.assertIn("cas disparu : OtherShopTest.test_the_page_answers (2 vérifications)", err)

    # --- refused, the case named ----------------------------------------------------

    def test_a_case_that_is_gone_is_refused(self):
        after = BEFORE[:BEFORE.index("        def test_the_page_answers")]

        self.refused(after, "cas disparu : ShopTest.test_the_page_answers (2 vérifications)")

    def test_a_renamed_case_is_refused(self):
        after = BEFORE.replace("test_the_page_answers", "test_the_page_is_there")

        err = self.refused(after, "cas renommé : ShopTest.test_the_page_answers est devenu ShopTest.test_the_page_is_there")
        self.assertNotIn("cas disparu", err)

    def test_a_verification_removed_from_a_case_is_refused(self):
        after = BEFORE.replace('self.assertIn("state", order)', "pass")

        self.refused(after, "vérifications en moins : ShopTest.test_an_order_is_paid en avait 3, en a 2")

    def test_a_verification_removed_from_a_helper_is_refused_for_the_case_that_uses_it(self):
        after = BEFORE.replace('            self.assertEqual("paid", order["state"])\n', "")

        err = self.refused(after, "vérifications en moins : ShopTest.test_an_order_is_paid en avait 3, en a 2")
        self.assertNotIn("test_the_page_answers", err)

    def test_a_verification_removed_from_a_function_of_the_module_is_refused(self):
        after = BEFORE.replace("        assert address\n", "")

        self.refused(after, "vérifications en moins : ShopTest.test_the_page_answers en avait 2, en a 1")

    def test_a_case_held_by_the_two_halves_of_a_cut_file_is_refused(self):
        status, _out, err = self.compare(BEFORE, BEFORE, BEFORE)

        self.assertEqual(1, status)
        self.assertIn("cas présent deux fois après : ShopTest.test_an_order_is_paid", err)

    # --- refused, because the case would no longer run ------------------------------------

    def test_a_class_that_is_no_longer_a_test_class_is_refused(self):
        after = BEFORE.replace("class ShopTest(unittest.TestCase):", "class ShopTest:")

        self.refused(after, "cas qui ne tournerait plus comme avant : ShopTest.test_an_order_is_paid",
                     "héritait de (unittest.TestCase), elle hérite de ()")

    def test_a_case_skipped_by_a_decorator_is_refused(self):
        after = BEFORE.replace("        def test_the_page_answers", "        @unittest.skip('plus tard')\n        def test_the_page_answers")

        err = self.refused(after, "cas qui ne tournerait plus comme avant : ShopTest.test_the_page_answers, "
                                  "décorateur ou skipTest ajouté")
        self.assertNotIn("test_an_order_is_paid", err)

    def test_a_case_that_skips_itself_through_a_helper_is_refused(self):
        after = BEFORE.replace("            self.assertTrue(order)\n", "            self.skipTest('plus tard')\n            self.assertTrue(order)\n")

        self.refused(after, "cas qui ne tournerait plus comme avant : ShopTest.test_an_order_is_paid")

    # --- what runs around the cases, and helpers reached another way ------------------------

    def test_a_verification_removed_from_the_set_up_is_refused(self):
        set_up = "\n        def setUp(self):\n            self.assertTrue(page('http://localhost'))\n"
        after_set_up = "\n        def setUp(self):\n            page('http://localhost')\n"

        status, out, err = self.compare(BEFORE + set_up, BEFORE + after_set_up)

        self.assertEqual((1, ""), (status, out))
        self.assertIn("vérifications en moins : ShopTest.setUp en avait 2, en a 1", err)

    def test_a_verification_moved_from_the_set_up_into_what_it_calls_is_accepted(self):
        set_up = "\n        def setUp(self):\n            self.assertTrue(page('http://localhost'))\n"
        staged = ("\n        def setUp(self):\n            self.stage('seeded', self.seed)\n"
                  "\n        def seed(self):\n            self.assertTrue(page('http://localhost'))\n")

        status, out, err = self.compare(BEFORE + set_up, BEFORE + staged)

        self.assertEqual((0, ""), (status, err))
        self.assertIn("identiques", out)

    def test_a_verification_removed_from_a_helper_reached_through_super_is_refused(self):
        before = BEFORE + ("\n\n    class LateShopTest(ShopTest):\n        def paid(self, order):\n"
                           "            return super().paid(order)\n")
        after = before.replace('            self.assertEqual("paid", order["state"])\n', "")

        status, _out, err = self.compare(before, after)

        self.assertEqual(1, status)
        self.assertIn("vérifications en moins : LateShopTest.test_an_order_is_paid en avait 3, en a 2", err)

    def test_a_case_with_no_counted_verification_is_named(self):
        before = BEFORE + "\n        def test_the_door_opens(self):\n            open_door(self)\n"

        status, out, err = self.compare(before, before)

        self.assertEqual((0, ""), (status, err))
        self.assertIn("1 cas sans vérification comptée, non prouvés par ce contrôle : ShopTest.test_the_door_opens", out)

    def test_the_count_of_helpers_that_call_each_other_does_not_depend_on_the_order_of_the_cases(self):
        loop = ("\n        def ping(self, left):\n            self.assertTrue(left)\n            return left and self.pong(left - 1)\n"
                "\n        def pong(self, left):\n            self.assertTrue(left)\n            return left and self.ping(left - 1)\n")
        first = "\n        def test_ping(self):\n            self.ping(3)\n"
        second = "\n        def test_pong(self):\n            self.pong(3)\n"

        status, out, err = self.compare(BEFORE + loop + first + second, BEFORE + loop + second + first)

        self.assertEqual((0, ""), (status, err))
        self.assertIn("identiques", out)

    # --- what is read ----------------------------------------------------------------

    def test_a_revision_of_a_file_is_read_through_git(self):
        def git(*args):
            subprocess.run(("git", "-c", "user.name=essai", "-c", "user.email=essai@example.invalid", *args),
                           cwd=self.tmp, check=True, capture_output=True)

        self.source("shop-test.py", BEFORE)
        git("init", "-q")
        git("add", "shop-test.py")
        git("commit", "-q", "-m", "base")
        self.source("shop-test.py", BEFORE.replace('self.assertIn("state", order)', "pass"))

        proc = subprocess.run((str(TOOL), "--before", "HEAD:shop-test.py", "--after", "shop-test.py"),
                              cwd=self.tmp, text=True, capture_output=True)

        self.assertEqual((1, ""), (proc.returncode, proc.stdout), proc.stderr)
        self.assertIn("vérifications en moins : ShopTest.test_an_order_is_paid en avait 3, en a 2", proc.stderr)

    def test_the_command_line_accepts_identical_files(self):
        path = self.source("shop-test.py", BEFORE)

        proc = subprocess.run((str(TOOL), "--before", str(path), "--after", str(path)), text=True, capture_output=True)

        self.assertEqual((0, ""), (proc.returncode, proc.stderr))
        self.assertIn("2 cas, 5 vérifications avant, 5 après sur les mêmes cas : identiques", proc.stdout)

    def test_a_source_that_cannot_be_read_or_holds_no_case_is_a_usage_error(self):
        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(2, tool.main(["--before", str(self.tmp / "absent-test.py"), "--after", str(self.tmp / "absent-test.py")],
                                      stdout=out, stderr=err))
        self.assertIn("illisible", err.getvalue())

        empty = self.source("empty-test.py", "import unittest\n")
        err = io.StringIO()
        self.assertEqual(2, tool.main(["--before", str(empty), "--after", str(empty)], stdout=out, stderr=err))
        self.assertIn("aucun cas", err.getvalue())

        err = io.StringIO()
        self.assertEqual(2, tool.main(["--before", str(empty)], stdout=out, stderr=err))
        self.assertIn("usage:", err.getvalue())
        self.assertEqual("", out.getvalue())


if __name__ == "__main__":
    unittest.main()
