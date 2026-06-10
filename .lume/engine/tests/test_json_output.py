"""E1: the opt-in --json flag - structured output for read verbs + structured errors.

Back-compat is covered by the rest of the suite (which never passes --json and is
unchanged); these tests cover the --json behaviour and that exit codes are intact.
"""
import datetime
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from lume.cli import main
from lume.clock import FixedClock


class JsonOutputTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".lume" / "workstreams").mkdir(parents=True)
        self.clock = FixedClock(datetime.date(2026, 6, 10))
        # one workstream with an open iteration (phase proposed)
        self._run("new", "demo", "Demo")
        self._run("-w", "demo", "open", "First", "-t", "execution")

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["lume", *args], start=self.root, clock=self.clock)
        return code, out.getvalue(), err.getvalue()

    # --- flag parsing ----------------------------------------------------
    def test_json_flag_recognised_anywhere(self):
        code, out, _ = self._run("--json", "entities")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), sorted(json.loads(out)))  # parseable JSON array
        code2, out2, _ = self._run("entities", "--json")  # flag after the verb
        self.assertEqual(out, out2)

    # --- read verbs ------------------------------------------------------
    def test_entities_json_is_array(self):
        _, out, _ = self._run("--json", "entities")
        kinds = json.loads(out)
        self.assertIn("workstream", kinds)
        self.assertIn("iteration", kinds)

    def test_status_detail_json_object(self):
        _, out, _ = self._run("--json", "-w", "demo", "status")
        obj = json.loads(out)
        self.assertEqual(obj["name"], "demo")
        self.assertEqual(obj["status"], "active")
        self.assertEqual(obj["current_iteration"]["phase"], "proposed")

    def test_status_queue_json_object(self):
        _, out, _ = self._run("--json", "status")  # no -w => queue
        obj = json.loads(out)
        self.assertEqual(set(obj), {"awaiting", "in_progress", "closed"})
        self.assertEqual(obj["in_progress"][0]["workstream"], "demo")

    def test_snapshot_json_object(self):
        _, out, _ = self._run("--json", "-w", "demo", "snapshot")
        obj = json.loads(out)
        self.assertIn("snapshot", obj)
        self.assertIn("## Done", obj["snapshot"])

    # --- structured errors ----------------------------------------------
    def test_usage_error_json(self):
        code, _, err = self._run("--json", "-w", "demo", "open")  # missing title
        self.assertEqual(code, 2)
        payload = json.loads(err)
        self.assertEqual(payload["error"]["code"], "usage")

    def test_gate_error_json(self):
        # iteration is 'proposed'; accept is illegal from there -> GateError.
        code, _, err = self._run("--json", "-w", "demo", "accept")
        self.assertEqual(code, 1)
        payload = json.loads(err)
        self.assertEqual(payload["error"]["code"], "gate")

    def test_not_found_error_json(self):
        code, _, err = self._run("--json", "-w", "nope", "status")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(err)["error"]["code"], "not_found")

    def test_human_errors_unchanged_without_flag(self):
        code, _, err = self._run("-w", "demo", "open")  # no --json
        self.assertEqual(code, 2)
        self.assertTrue(err.startswith("lume: usage: lume open"))


class JsonMutatingVerbsTest(unittest.TestCase):
    """E2: mutating verbs emit a structured result object under --json."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".lume" / "workstreams").mkdir(parents=True)
        self.clock = FixedClock(datetime.date(2026, 6, 10))

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["lume", *args], start=self.root, clock=self.clock)
        return code, out.getvalue()

    def test_new_result(self):
        code, out = self._run("--json", "new", "demo", "Demo")
        self.assertEqual(code, 0)
        obj = json.loads(out)
        self.assertEqual(obj, {"result": "new", "workstream": "demo", "status": "active"})

    def test_open_and_transition_results(self):
        self._run("--json", "new", "demo", "Demo")
        _, out = self._run("--json", "-w", "demo", "open", "First", "-t", "execution")
        obj = json.loads(out)
        self.assertEqual(obj["result"], "open")
        self.assertEqual((obj["iteration"], obj["phase"], obj["type"]),
                         (1, "proposed", "execution"))
        _, out = self._run("--json", "-w", "demo", "approve")
        obj = json.loads(out)
        self.assertEqual((obj["result"], obj["phase"]), ("approve", "approved"))

    def test_decide_result(self):
        self._run("--json", "new", "demo", "Demo")
        _, out = self._run("--json", "-w", "demo", "decide", "use json", "because")
        obj = json.loads(out)
        self.assertEqual(obj["result"], "decide")
        self.assertEqual(obj["decision"], "use json")

    def test_plan_add_result(self):
        self._run("--json", "new", "demo", "Demo")
        _, out = self._run("--json", "-w", "demo", "plan", "add", "-g", "optional", "an item")
        obj = json.loads(out)
        self.assertEqual((obj["result"], obj["id"], obj["tag"]), ("plan_add", "P1", "optional"))

    def test_close_result(self):
        self._run("--json", "new", "demo", "Demo")
        _, out = self._run("--json", "-w", "demo", "close")
        self.assertEqual(json.loads(out),
                         {"result": "close", "workstream": "demo", "status": "closed"})

    def test_human_output_unchanged_without_flag(self):
        code, out = self._run("new", "demo", "Demo")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("created workstream 'demo'"))


if __name__ == "__main__":
    unittest.main()
