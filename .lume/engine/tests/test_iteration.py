import unittest

from lume.iteration import Iteration, parse_verdicts


class VerdictParserTest(unittest.TestCase):
    def test_strict_stamp_lines_only(self):
        body = (
            "## DoD\n- [x] reject appends `YYYY-MM-DD | REJECTED | reason`\n"
            "- Attempt 1 REJECTED then redone (prose, not a stamp)\n"
            "## Verdict\n2026-06-09 | REJECTED | too vague\n2026-06-10 | ACCEPTED\n"
        )
        self.assertEqual(
            parse_verdicts(body),
            [
                {"date": "2026-06-09", "verdict": "rejected", "reason": "too vague"},
                {"date": "2026-06-10", "verdict": "accepted", "reason": None},
            ],
        )

    def test_no_stamps_is_empty(self):
        self.assertEqual(parse_verdicts("# Iteration 001 - x\n\n## Verdict\n"), [])


class IterationEntityTest(unittest.TestCase):
    def _entity(self):
        return {
            "id": 6,
            "type": "execution",
            "phase": "working",
            "opened": "2026-06-09",
            "title": "P4: model bridge",
            "verdicts": [{"date": "2026-06-09", "verdict": "accepted", "reason": None}],
            "dod_artifact": "iterations/006.md",
        }

    def test_to_entity_from_body(self):
        it = Iteration.from_text(
            "---\nid: 2\ntype: execution\nphase: accepted\nopened: 2026-06-09\n---\n"
            "# Iteration 002 - Title\n\n2026-06-09 | ACCEPTED\n"
        )
        entity = it.to_entity()
        self.assertEqual(entity["title"], "Title")
        self.assertEqual(entity["dod_artifact"], "iterations/002.md")
        self.assertEqual(entity["verdicts"], [{"date": "2026-06-09", "verdict": "accepted", "reason": None}])

    def test_from_entity_supports_title_and_accepted_on(self):
        it = Iteration.from_entity(self._entity())
        self.assertEqual(it.title, "P4: model bridge")
        self.assertEqual(it.accepted_on(), "2026-06-09")

    def test_round_trip_entity(self):
        entity = self._entity()
        self.assertEqual(Iteration.from_entity(entity).to_entity(), entity)

    def test_accepted_on_prefers_field_over_body(self):
        # verdicts field set -> body is not consulted.
        it = Iteration(1, "execution", "accepted", "2026-06-09", body="# x\n",
                       verdicts=[{"date": "2026-07-01", "verdict": "accepted", "reason": None}])
        self.assertEqual(it.accepted_on(), "2026-07-01")


class IterationTest(unittest.TestCase):
    def test_from_text_parses_frontmatter(self):
        text = "---\nid: 007\ntype: build\nphase: working\nopened: 2026-06-09\n---\n# Iteration 007 - x\n"
        it = Iteration.from_text(text)
        self.assertEqual(it.id, 7)
        self.assertEqual(it.type, "build")
        self.assertEqual(it.phase, "working")
        self.assertEqual(it.opened, "2026-06-09")

    def test_phase_validity(self):
        self.assertTrue(Iteration(1, "build", "accepted", "d").phase_valid)
        self.assertFalse(Iteration(1, "build", "bogus", "d").phase_valid)

    def test_is_accepted(self):
        self.assertTrue(Iteration(1, "build", "accepted", "d").is_accepted)
        self.assertFalse(Iteration(1, "build", "handback", "d").is_accepted)

    def test_new_produces_proposed_with_skeleton(self):
        it = Iteration.new(id=3, title="Do a thing", opened="2026-06-09")
        self.assertEqual(it.id, 3)
        self.assertEqual(it.phase, "proposed")
        for section in ("# Iteration 003 - Do a thing", "## DoD", "## Self-review", "## Handback", "## Verdict"):
            self.assertIn(section, it.body)

    def test_new_seeds_per_type_dod_skeleton(self):
        cases = {
            "discovery": "Context built",
            "planning": "Decisions recorded",
            "closeout": "Retro:",
        }
        for type_, marker in cases.items():
            it = Iteration.new(id=1, title="t", opened="d", type=type_)
            self.assertEqual(it.type, type_)
            self.assertIn(marker, it.body)
            # the shared scaffold is identical across types
            for section in ("## DoD", "## Self-review", "## Handback", "## Verdict"):
                self.assertIn(section, it.body)

    def test_execution_keeps_generic_skeleton(self):
        it = Iteration.new(id=1, title="t", opened="d", type="execution")
        self.assertIn("- [ ] (propose checkable items)", it.body)
        # default (no type given) is execution -> same body
        default = Iteration.new(id=1, title="t", opened="d")
        self.assertEqual(default.body, it.body)

    def test_unmapped_type_falls_back_to_execution_skeleton(self):
        it = Iteration.new(id=1, title="t", opened="d", type="weird")
        self.assertIn("- [ ] (propose checkable items)", it.body)

    def test_new_round_trips_through_text(self):
        it = Iteration.new(id=12, title="t", opened="2026-06-09")
        reparsed = Iteration.from_text(it.to_text())
        self.assertEqual(reparsed.id, 12)
        self.assertEqual(reparsed.phase, "proposed")
        self.assertEqual(reparsed.opened, "2026-06-09")


if __name__ == "__main__":
    unittest.main()
