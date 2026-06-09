import unittest

from lume.iteration import Iteration


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

    def test_new_round_trips_through_text(self):
        it = Iteration.new(id=12, title="t", opened="2026-06-09")
        reparsed = Iteration.from_text(it.to_text())
        self.assertEqual(reparsed.id, 12)
        self.assertEqual(reparsed.phase, "proposed")
        self.assertEqual(reparsed.opened, "2026-06-09")


if __name__ == "__main__":
    unittest.main()
