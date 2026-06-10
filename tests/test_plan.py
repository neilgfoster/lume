import unittest

from lume.iteration import Iteration
from lume.plan import parse_plan
from lume.snapshot import build_snapshot

SAMPLE = """# plan

## Schema
    - P<n> | <type> | iter:<NNN|-> | <committed|optional> | <sketch>
- **done** = the item's iter is accepted

## Items
- P1 | execution | iter:004 | committed | Did the first thing
- P2 | execution | iter:005 | committed | Did the second | with a pipe in sketch
- P3 | execution | iter:- | committed | Not yet opened
- P4 | closeout | iter:- | optional | Maybe later

some trailing prose line
"""


def _it(id, phase):
    return Iteration(id=id, type="execution", phase=phase, opened="d",
                     body=f"# Iteration {id:03d} - t\n")


class ParsePlanTest(unittest.TestCase):
    def test_parses_items_ignores_noise(self):
        items = parse_plan(SAMPLE)
        self.assertEqual([i.id for i in items], ["P1", "P2", "P3", "P4"])
        self.assertEqual(items[0].iter_id, 4)
        self.assertIsNone(items[2].iter)
        self.assertIsNone(items[2].iter_id)
        self.assertEqual(items[3].type, "closeout")
        self.assertEqual(items[3].tag, "optional")

    def test_schema_example_and_prose_ignored(self):
        # `- P<n> | ...` has no digits after P, and prose lines do not match.
        self.assertTrue(all(i.id.removeprefix("P").isdigit() for i in parse_plan(SAMPLE)))

    def test_sketch_keeps_trailing_pipe_content(self):
        self.assertIn("with a pipe", parse_plan(SAMPLE)[1].sketch)

    def test_empty_text(self):
        self.assertEqual(parse_plan("# nothing here\n"), [])


class DerivedNextTest(unittest.TestCase):
    def test_next_is_first_not_done(self):
        iters = [_it(4, "accepted"), _it(5, "accepted")]  # P1, P2 done -> P3 next
        out = build_snapshot("# s\n", iters, "2026-01-02", plan_items=parse_plan(SAMPLE))
        self.assertIn("step 3 of 4", out)
        self.assertIn("> P3 (execution)", out)
        self.assertIn("then: P4 (closeout)", out)

    def test_linked_but_not_accepted_is_not_done(self):
        iters = [_it(4, "accepted"), _it(5, "working")]  # P2's iter 005 not accepted
        out = build_snapshot("# s\n", iters, "2026-01-02", plan_items=parse_plan(SAMPLE))
        self.assertIn("step 2 of 4", out)
        self.assertIn("> P2 (execution)", out)

    def test_all_done(self):
        plan = parse_plan("## Items\n- P1 | execution | iter:004 | committed | a\n")
        out = build_snapshot("# s\n", [_it(4, "accepted")], "d", plan_items=plan)
        self.assertIn("all 1 items done", out)

    def test_empty_plan_message(self):
        out = build_snapshot("# s\n", [], "d", plan_items=[])
        self.assertIn("plan has no items", out)

    def test_no_plan_preserves_handauthored_next(self):
        existing = "# s\n\n## Done\n- x\n\n## Now\n- y\n\n## Next\n- HAND AUTHORED\n"
        out = build_snapshot(existing, [], "d")  # plan_items default None
        self.assertIn("HAND AUTHORED", out)


if __name__ == "__main__":
    unittest.main()
