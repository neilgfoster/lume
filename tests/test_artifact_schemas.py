"""P8: tests for the four new artifact schemas (objective, iteration_content,
decisions, retro)."""
import unittest

from lume.errors import SchemaError
from lume.validate import entity_kinds, validate_entity


class EntityKindsTest(unittest.TestCase):
    def test_nine_kinds_present(self):
        kinds = entity_kinds()
        self.assertEqual(len(kinds), 9)

    def test_new_kinds_in_list(self):
        kinds = entity_kinds()
        for name in ("objective", "iteration_content", "decisions", "retro", "discovery", "gap"):
            self.assertIn(name, kinds)

    def test_kinds_sorted(self):
        kinds = entity_kinds()
        self.assertEqual(kinds, sorted(kinds))


class ObjectiveSchemaTest(unittest.TestCase):
    _valid = {
        "slug": "my-workstream",
        "title": "My Workstream",
        "status": "active",
        "text": "Objective prose here.",
    }

    def test_valid_instance_passes(self):
        validate_entity("objective", self._valid)

    def test_with_done_when_passes(self):
        validate_entity("objective", {**self._valid, "done_when": "When X is true."})

    def test_missing_text_fails(self):
        doc = {k: v for k, v in self._valid.items() if k != "text"}
        with self.assertRaises(SchemaError):
            validate_entity("objective", doc)

    def test_invalid_status_fails(self):
        with self.assertRaises(SchemaError):
            validate_entity("objective", {**self._valid, "status": "pending"})

    def test_missing_slug_fails(self):
        doc = {k: v for k, v in self._valid.items() if k != "slug"}
        with self.assertRaises(SchemaError):
            validate_entity("objective", doc)


class IterationContentSchemaTest(unittest.TestCase):
    _valid = {
        "id": 1,
        "dod": {
            "items": [
                {"text": "Do the thing.", "checked": True},
                {"text": "Verify the thing.", "checked": False},
            ]
        },
    }

    def test_valid_instance_passes(self):
        validate_entity("iteration_content", self._valid)

    def test_with_all_optional_fields_passes(self):
        doc = {
            **self._valid,
            "dod": {**self._valid["dod"], "preamble": "Context prose."},
            "self_review": "Looks good.",
            "handback": "Ready for review.",
        }
        validate_entity("iteration_content", doc)

    def test_null_self_review_passes(self):
        validate_entity("iteration_content", {**self._valid, "self_review": None})

    def test_missing_id_fails(self):
        doc = {k: v for k, v in self._valid.items() if k != "id"}
        with self.assertRaises(SchemaError):
            validate_entity("iteration_content", doc)

    def test_missing_dod_fails(self):
        with self.assertRaises(SchemaError):
            validate_entity("iteration_content", {"id": 1})

    def test_dod_item_missing_checked_fails(self):
        doc = {"id": 1, "dod": {"items": [{"text": "thing"}]}}
        with self.assertRaises(SchemaError):
            validate_entity("iteration_content", doc)

    def test_dod_item_non_bool_checked_fails(self):
        doc = {"id": 1, "dod": {"items": [{"text": "t", "checked": "yes"}]}}
        with self.assertRaises(SchemaError):
            validate_entity("iteration_content", doc)


class DecisionsSchemaTest(unittest.TestCase):
    _valid = {
        "entries": [
            {
                "date": "2026-06-09",
                "context": "002 planning",
                "decision": "GO",
                "rationale": "Cost is bounded.",
            }
        ]
    }

    def test_valid_instance_passes(self):
        validate_entity("decisions", self._valid)

    def test_empty_entries_passes(self):
        validate_entity("decisions", {"entries": []})

    def test_missing_entries_fails(self):
        with self.assertRaises(SchemaError):
            validate_entity("decisions", {})

    def test_entry_missing_rationale_fails(self):
        doc = {"entries": [{"date": "2026-06-09", "context": "x", "decision": "y"}]}
        with self.assertRaises(SchemaError):
            validate_entity("decisions", doc)

    def test_entry_wrong_type_fails(self):
        with self.assertRaises(SchemaError):
            validate_entity("decisions", {"entries": "not-an-array"})


class RetroSchemaTest(unittest.TestCase):
    _valid = {
        "overall_verdict": "Net positive.",
        "carry_forwards": ["Prove multi-workstream live.", "Re-orientation gap."],
    }

    def test_valid_minimal_instance_passes(self):
        validate_entity("retro", self._valid)

    def test_with_all_optional_fields_passes(self):
        doc = {
            **self._valid,
            "stage_verdicts": [
                {"stage": "Discovery", "iterations": "001", "cost": "1 iter",
                 "saved": "Grounded design", "net": "Positive"}
            ],
            "done_when": [
                {"clause": "State is JSON", "verdict": "MET", "evidence": "state.json exists"}
            ],
        }
        validate_entity("retro", doc)

    def test_missing_overall_verdict_fails(self):
        doc = {"carry_forwards": []}
        with self.assertRaises(SchemaError):
            validate_entity("retro", doc)

    def test_missing_carry_forwards_fails(self):
        doc = {"overall_verdict": "Good."}
        with self.assertRaises(SchemaError):
            validate_entity("retro", doc)

    def test_stage_verdict_missing_net_fails(self):
        doc = {
            **self._valid,
            "stage_verdicts": [{"stage": "X", "cost": "c", "saved": "s"}],
        }
        with self.assertRaises(SchemaError):
            validate_entity("retro", doc)

    def test_done_when_missing_evidence_fails(self):
        doc = {
            **self._valid,
            "done_when": [{"clause": "X", "verdict": "MET"}],
        }
        with self.assertRaises(SchemaError):
            validate_entity("retro", doc)


if __name__ == "__main__":
    unittest.main()
