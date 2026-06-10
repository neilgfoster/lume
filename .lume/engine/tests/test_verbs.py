"""E3: the `lume verbs` discovery surface (the tools/list analogue)."""
import datetime
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from lume.cli import main, _CATALOG, _VERB_NAMES
from lume.clock import FixedClock
from lume.iteration import TRANSITIONS


def _run(*args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(["lume", *args], start=Path("/nonexistent"),
                    clock=FixedClock(datetime.date(2026, 6, 10)))
    return code, out.getvalue(), err.getvalue()


class VerbsTest(unittest.TestCase):
    def test_verbs_human_lists_every_verb(self):
        code, out, _ = _run("verbs")
        self.assertEqual(code, 0)
        for name in _VERB_NAMES:
            self.assertIn(name, out)

    def test_verbs_json_is_catalog(self):
        code, out, _ = _run("verbs", "--json")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data, _CATALOG)
        for entry in data:
            self.assertEqual(set(entry), {"name", "summary", "args", "inputs"})

    def test_catalog_includes_transitions_and_verbs_itself(self):
        names = set(_VERB_NAMES)
        for t in TRANSITIONS:
            self.assertIn(t, names)
        self.assertIn("verbs", names)

    def test_catalog_matches_dispatch_set(self):
        # No duplicates, and no catalog verb is rejected as an unknown command
        # (arg-usage errors are fine; we only rule out the membership failure).
        self.assertEqual(len(_VERB_NAMES), len(set(_VERB_NAMES)))
        for name in _VERB_NAMES:
            _, _, err = _run(name)
            self.assertNotIn("unknown command", err, f"{name} not dispatched")

    # --- E4: per-verb input schema ---------------------------------------
    def test_every_entry_has_inputs(self):
        for e in _CATALOG:
            self.assertIn("inputs", e)
            for i in e["inputs"]:
                self.assertIn(i["kind"], ("positional", "flag"))
                self.assertIn("required", i)
                self.assertIn("description", i)

    def test_declared_flags_are_real(self):
        # Every flag a catalog entry declares must be one the parser accepts.
        accepted = {"--json", "-w/--workstream", "-t/--type", "-c/--context", "-g/--tag",
                    "--new", "--existing"}
        for e in _CATALOG:
            for i in e["inputs"]:
                if i["kind"] == "flag":
                    self.assertIn(i["flag"], accepted, f"{e['name']} declares bad flag {i['flag']}")

    def test_single_verb_json(self):
        code, out, _ = _run("verbs", "open", "--json")
        self.assertEqual(code, 0)
        entry = json.loads(out)
        self.assertEqual(entry["name"], "open")
        self.assertTrue(any(i["name"] == "title" for i in entry["inputs"]))

    def test_single_verb_human(self):
        code, out, _ = _run("verbs", "decide")
        self.assertEqual(code, 0)
        self.assertIn("decide", out)
        self.assertIn("usage: lume", out)

    def test_unknown_verb_lookup_errors(self):
        code, _, err = _run("--json", "verbs", "nope")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(err)["error"]["code"], "not_found")


if __name__ == "__main__":
    unittest.main()
