import unittest

from lume import validate
from lume.errors import SchemaError


def _workstream(**over):
    base = {
        "slug": "state-as-data",
        "title": "State is Data",
        "status": "active",
        "objective_artifact": "objective.md",
    }
    base.update(over)
    return base


def _iteration(**over):
    base = {
        "id": 3,
        "type": "execution",
        "phase": "working",
        "opened": "2026-06-09",
        "title": "P1: schemas + validator",
        "verdicts": [{"date": "2026-06-09", "verdict": "accepted", "reason": None}],
        "dod_artifact": "iterations/003.md",
    }
    base.update(over)
    return base


def _plan_item(**over):
    base = {
        "id": "P1",
        "type": "execution",
        "iter": 3,
        "tag": "committed",
        "sketch": "schemas + validator",
    }
    base.update(over)
    return base


class EntityDiscoveryTest(unittest.TestCase):
    def test_known_kinds_includes_core_entities(self):
        kinds = validate.entity_kinds()
        for name in ("iteration", "plan_item", "workstream"):
            self.assertIn(name, kinds)
        self.assertEqual(kinds, sorted(kinds))

    def test_load_schema_returns_titled_schema(self):
        self.assertEqual(validate.load_schema("workstream")["title"], "workstream")

    def test_unknown_entity_is_a_named_error(self):
        with self.assertRaises(SchemaError) as ctx:
            validate.load_schema("nonsense")
        self.assertIn("unknown entity 'nonsense'", str(ctx.exception))


class ValidInstancesTest(unittest.TestCase):
    def test_each_entity_accepts_a_valid_instance(self):
        # No exception == pass.
        validate.validate_entity("workstream", _workstream())
        validate.validate_entity("iteration", _iteration())
        validate.validate_entity("plan_item", _plan_item())

    def test_nullable_fields_accept_null(self):
        validate.validate_entity("plan_item", _plan_item(iter=None))
        validate.validate_entity(
            "iteration",
            _iteration(verdicts=[{"date": "x", "verdict": "rejected", "reason": None}]),
        )


class InvalidInstancesTest(unittest.TestCase):
    def test_missing_required_names_the_field(self):
        bad = _workstream()
        del bad["status"]
        with self.assertRaises(SchemaError) as ctx:
            validate.validate_entity("workstream", bad)
        msg = str(ctx.exception)
        self.assertIn("workstream", msg)
        self.assertIn("status", msg)

    def test_wrong_type_names_the_field(self):
        with self.assertRaises(SchemaError) as ctx:
            validate.validate_entity("iteration", _iteration(id="3"))
        msg = str(ctx.exception)
        self.assertIn("id", msg)
        self.assertIn("integer", msg)

    def test_bad_enum_names_the_field(self):
        with self.assertRaises(SchemaError) as ctx:
            validate.validate_entity("iteration", _iteration(phase="done"))
        self.assertIn("phase", str(ctx.exception))

    def test_bool_is_not_an_integer(self):
        # Python's bool-is-int trap: True must not satisfy an integer field.
        with self.assertRaises(SchemaError):
            validate.validate_entity("iteration", _iteration(id=True))

    def test_malformed_nested_verdict_item_is_caught_with_index(self):
        with self.assertRaises(SchemaError) as ctx:
            validate.validate_entity(
                "iteration",
                _iteration(verdicts=[{"date": "2026-06-09"}]),  # missing 'verdict'
            )
        msg = str(ctx.exception)
        self.assertIn("verdicts[0]", msg)
        self.assertIn("verdict", msg)

    def test_bad_enum_inside_nested_item_is_caught(self):
        with self.assertRaises(SchemaError) as ctx:
            validate.validate_entity(
                "iteration",
                _iteration(
                    verdicts=[{"date": "x", "verdict": "maybe"}]
                ),
            )
        self.assertIn("verdicts[0].verdict", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
