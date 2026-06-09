"""P9: tests for the plan flip — state.json as sole source, plan.md as view."""
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
from lume.plan import PlanItem, parse_plan, render_plan
from lume.workstream import Workstream


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _clock():
    return FixedClock(datetime.date(2026, 6, 9))


def _make_ws(tmp: Path, plan_items=None):
    ws_dir = tmp / "demo"
    ws_dir.mkdir(parents=True)
    (ws_dir / "objective.md").write_text("---\nstatus: active\n---\n# Demo\nobj\n")
    doc = {
        "workstream": {
            "slug": "demo", "title": "Demo",
            "status": "active", "objective_artifact": "objective.md",
        },
        "iterations": [],
        "plan": plan_items or [],
    }
    state_mod.save(ws_dir / state_mod.STATE_FILE, doc)
    return ws_dir


def _ws(ws_dir):
    doc = state_mod.load(ws_dir / state_mod.STATE_FILE)
    return Workstream(ws_dir, _clock(), doc)


def _run(root, *args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(["lume", *args], start=root, clock=_clock())
    return code, out.getvalue(), err.getvalue()


# ---------------------------------------------------------------------------
# PlanItem.from_entity
# ---------------------------------------------------------------------------

class FromEntityTest(unittest.TestCase):
    def test_round_trips_through_to_entity(self):
        item = PlanItem(id="P3", type="closeout", iter=7, tag="optional", sketch="retro")
        self.assertEqual(PlanItem.from_entity(item.to_entity()), item)

    def test_null_iter_survives(self):
        entity = {"id": "P1", "type": "execution", "iter": None,
                  "tag": "committed", "sketch": "do the thing"}
        item = PlanItem.from_entity(entity)
        self.assertIsNone(item.iter)
        self.assertIsNone(item.iter_id)

    def test_integer_iter_survives(self):
        entity = {"id": "P2", "type": "execution", "iter": 5,
                  "tag": "committed", "sketch": "done"}
        self.assertEqual(PlanItem.from_entity(entity).iter, 5)


# ---------------------------------------------------------------------------
# render_plan
# ---------------------------------------------------------------------------

class RenderPlanTest(unittest.TestCase):
    def test_renders_items_parseable_by_parse_plan(self):
        items = [
            PlanItem("P1", "execution", 3, "committed", "First slice"),
            PlanItem("P2", "closeout", None, "optional", "Retro"),
        ]
        text = render_plan(items, "my-ws")
        parsed = parse_plan(text)
        self.assertEqual([p.id for p in parsed], ["P1", "P2"])
        self.assertEqual(parsed[0].iter, 3)
        self.assertIsNone(parsed[1].iter)

    def test_iter_formatted_as_three_digits(self):
        items = [PlanItem("P1", "execution", 4, "committed", "s")]
        self.assertIn("iter:004", render_plan(items, "ws"))

    def test_unlinked_iter_renders_as_dash(self):
        items = [PlanItem("P1", "execution", None, "committed", "s")]
        self.assertIn("iter:-", render_plan(items, "ws"))


# ---------------------------------------------------------------------------
# plan_items() reads from state, not plan.md
# ---------------------------------------------------------------------------

class PlanItemsFromStateTest(unittest.TestCase):
    def test_plan_items_from_state_not_plan_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws_dir = _make_ws(Path(tmp), plan_items=[
                {"id": "P1", "type": "execution", "iter": None,
                 "tag": "committed", "sketch": "state item"}
            ])
            # Write a conflicting plan.md — must be ignored.
            (ws_dir / "plan.md").write_text(
                "## Items\n- P99 | execution | iter:- | committed | from markdown\n"
            )
            items = _ws(ws_dir).plan_items()
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].id, "P1")

    def test_empty_state_plan_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws_dir = _make_ws(Path(tmp))
            self.assertIsNone(_ws(ws_dir).plan_items())


# ---------------------------------------------------------------------------
# lume plan add
# ---------------------------------------------------------------------------

class PlanAddVerbTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        lume_dir = self.root / ".lume"
        lume_dir.mkdir(parents=True)
        self.ws_dir = _make_ws(lume_dir / "workstreams")
        # Restructure: _make_ws put files in lume_dir/workstreams/demo, but
        # we need root/.lume/workstreams/demo.
        import shutil
        shutil.rmtree(self.root, ignore_errors=True)
        self.root = Path(self._tmp.name)
        (self.root / ".lume" / "workstreams").mkdir(parents=True)
        self.ws_dir = _make_ws(self.root / ".lume" / "workstreams")

    def tearDown(self):
        self._tmp.cleanup()

    def test_add_creates_plan_item_in_state(self):
        code, out, _ = _run(self.root, "plan", "add", "Do the first thing")
        self.assertEqual(code, 0)
        doc = state_mod.load(self.ws_dir / state_mod.STATE_FILE)
        self.assertEqual(len(doc["plan"]), 1)
        self.assertEqual(doc["plan"][0]["id"], "P1")
        self.assertEqual(doc["plan"][0]["sketch"], "Do the first thing")

    def test_add_auto_increments_id(self):
        _run(self.root, "plan", "add", "First")
        _run(self.root, "plan", "add", "Second")
        doc = state_mod.load(self.ws_dir / state_mod.STATE_FILE)
        self.assertEqual([p["id"] for p in doc["plan"]], ["P1", "P2"])

    def test_add_regenerates_plan_md(self):
        _run(self.root, "plan", "add", "First item")
        plan_text = (self.ws_dir / "plan.md").read_text()
        self.assertIn("P1", plan_text)
        self.assertIn("First item", plan_text)

    def test_add_missing_sketch_exits_2(self):
        code, _, err = _run(self.root, "plan", "add")
        self.assertEqual(code, 2)

    def test_add_outputs_new_id(self):
        code, out, _ = _run(self.root, "plan", "add", "My item")
        self.assertEqual(code, 0)
        self.assertIn("P1", out)


# ---------------------------------------------------------------------------
# lume plan link
# ---------------------------------------------------------------------------

class PlanLinkVerbTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".lume" / "workstreams").mkdir(parents=True)
        self.ws_dir = _make_ws(
            self.root / ".lume" / "workstreams",
            plan_items=[
                {"id": "P1", "type": "execution", "iter": None,
                 "tag": "committed", "sketch": "the task"}
            ],
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_link_sets_iter_in_state(self):
        code, out, _ = _run(self.root, "plan", "link", "P1", "3")
        self.assertEqual(code, 0)
        doc = state_mod.load(self.ws_dir / state_mod.STATE_FILE)
        self.assertEqual(doc["plan"][0]["iter"], 3)

    def test_link_regenerates_plan_md(self):
        _run(self.root, "plan", "link", "P1", "3")
        plan_text = (self.ws_dir / "plan.md").read_text()
        self.assertIn("iter:003", plan_text)

    def test_link_not_found_exits_1(self):
        code, _, err = _run(self.root, "plan", "link", "P99", "1")
        self.assertEqual(code, 1)
        self.assertIn("P99", err)

    def test_link_missing_args_exits_2(self):
        code, _, err = _run(self.root, "plan", "link", "P1")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
