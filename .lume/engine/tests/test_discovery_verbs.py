"""P6: tests for the three discovery verbs (entities, schema, get)."""
import datetime
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from lume import state as state_mod
from lume.cli import main
from lume.clock import FixedClock


def _run(root: Path, *args):
    clock = FixedClock(datetime.date(2026, 6, 9))
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(["lume", *args], start=root, clock=clock)
    return code, out.getvalue(), err.getvalue()


def _make_ws(lume_dir: Path, slug: str = "demo") -> None:
    d = lume_dir / "workstreams" / slug
    d.mkdir(parents=True)
    (d / "objective.md").write_text(f"---\nstatus: active\n---\n# Demo\nobj\n")
    doc = {
        "workstream": {
            "slug": slug,
            "title": "Demo",
            "status": "active",
            "objective_artifact": "objective.md",
        },
        "iterations": [
            {
                "id": 1,
                "type": "execution",
                "phase": "accepted",
                "opened": "2026-06-09",
                "title": "First task",
                "verdicts": [{"date": "2026-06-09", "verdict": "accepted", "reason": None}],
                "dod_artifact": "iterations/001.json",
            }
        ],
        "plan": [
            {
                "id": "P1",
                "type": "execution",
                "iter": 1,
                "tag": "committed",
                "sketch": "the first plan item",
            }
        ],
    }
    state_mod.save(d / state_mod.STATE_FILE, doc)


class EntitiesVerbTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".lume" / "workstreams").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_entities_lists_core_kinds(self):
        code, out, _ = _run(self.root, "entities")
        self.assertEqual(code, 0)
        lines = out.strip().splitlines()
        for name in ("iteration", "plan_item", "workstream"):
            self.assertIn(name, lines)
        self.assertGreaterEqual(len(lines), 3)

    def test_entities_needs_no_workstream(self):
        # No workstream under .lume/ — should still succeed.
        code, _, _ = _run(self.root, "entities")
        self.assertEqual(code, 0)

    def test_entities_output_is_sorted(self):
        code, out, _ = _run(self.root, "entities")
        self.assertEqual(code, 0)
        lines = out.strip().splitlines()
        self.assertEqual(lines, sorted(lines))


class SchemaVerbTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".lume" / "workstreams").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_schema_known_entity_outputs_valid_json(self):
        for entity in ("iteration", "plan_item", "workstream"):
            with self.subTest(entity=entity):
                code, out, _ = _run(self.root, "schema", entity)
                self.assertEqual(code, 0, entity)
                parsed = json.loads(out)
                self.assertEqual(parsed.get("title"), entity)

    def test_schema_output_contains_required_fields(self):
        code, out, _ = _run(self.root, "schema", "iteration")
        self.assertEqual(code, 0)
        schema = json.loads(out)
        self.assertIn("phase", schema.get("required", []))
        self.assertIn("id", schema.get("required", []))

    def test_schema_unknown_entity_exits_1(self):
        code, _, err = _run(self.root, "schema", "bogus")
        self.assertEqual(code, 1)
        self.assertIn("bogus", err)
        self.assertIn("iteration", err)  # known set listed

    def test_schema_missing_arg_exits_2(self):
        code, _, err = _run(self.root, "schema")
        self.assertEqual(code, 2)
        self.assertIn("schema", err)

    def test_schema_needs_no_workstream(self):
        code, _, _ = _run(self.root, "schema", "workstream")
        self.assertEqual(code, 0)


class GetVerbTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        lume_dir = self.root / ".lume"
        lume_dir.mkdir(parents=True)
        _make_ws(lume_dir)

    def tearDown(self):
        self._tmp.cleanup()

    def test_get_no_entity_emits_full_state(self):
        code, out, _ = _run(self.root, "get")
        self.assertEqual(code, 0)
        doc = json.loads(out)
        self.assertIn("workstream", doc)
        self.assertIn("iterations", doc)
        self.assertIn("plan", doc)

    def test_get_workstream_emits_workstream_entity(self):
        code, out, _ = _run(self.root, "get", "workstream")
        self.assertEqual(code, 0)
        entity = json.loads(out)
        self.assertEqual(entity["slug"], "demo")
        self.assertEqual(entity["status"], "active")

    def test_get_iteration_emits_iterations_array(self):
        code, out, _ = _run(self.root, "get", "iteration")
        self.assertEqual(code, 0)
        arr = json.loads(out)
        self.assertIsInstance(arr, list)
        self.assertEqual(len(arr), 1)
        self.assertEqual(arr[0]["title"], "First task")

    def test_get_plan_item_emits_plan_array(self):
        code, out, _ = _run(self.root, "get", "plan_item")
        self.assertEqual(code, 0)
        arr = json.loads(out)
        self.assertIsInstance(arr, list)
        self.assertEqual(arr[0]["id"], "P1")

    def test_get_iteration_by_id(self):
        code, out, _ = _run(self.root, "get", "iteration", "001")
        self.assertEqual(code, 0)
        entity = json.loads(out)
        self.assertEqual(entity["id"], 1)
        self.assertEqual(entity["title"], "First task")

    def test_get_iteration_by_id_without_padding(self):
        code, out, _ = _run(self.root, "get", "iteration", "1")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["id"], 1)

    def test_get_plan_item_by_id(self):
        code, out, _ = _run(self.root, "get", "plan_item", "P1")
        self.assertEqual(code, 0)
        entity = json.loads(out)
        self.assertEqual(entity["id"], "P1")
        self.assertEqual(entity["sketch"], "the first plan item")

    def test_get_iteration_not_found_exits_1(self):
        code, _, err = _run(self.root, "get", "iteration", "999")
        self.assertEqual(code, 1)
        self.assertIn("999", err)

    def test_get_plan_item_not_found_exits_1(self):
        code, _, err = _run(self.root, "get", "plan_item", "P99")
        self.assertEqual(code, 1)
        self.assertIn("P99", err)

    def test_get_workstream_with_id_exits_1(self):
        code, _, err = _run(self.root, "get", "workstream", "anything")
        self.assertEqual(code, 1)
        self.assertIn("workstream", err)
        self.assertIn("single entity", err)

    def test_get_unknown_entity_exits_1(self):
        code, _, err = _run(self.root, "get", "bogus")
        self.assertEqual(code, 1)
        self.assertIn("bogus", err)

    def test_get_output_is_valid_json_for_all_forms(self):
        for args in (
            ("get",),
            ("get", "workstream"),
            ("get", "iteration"),
            ("get", "plan_item"),
            ("get", "iteration", "1"),
            ("get", "plan_item", "P1"),
        ):
            with self.subTest(args=args):
                code, out, _ = _run(self.root, *args)
                self.assertEqual(code, 0, args)
                json.loads(out)  # must not raise


if __name__ == "__main__":
    unittest.main()
