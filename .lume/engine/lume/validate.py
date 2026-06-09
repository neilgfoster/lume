"""Schema-validated state, dependency-free.

A JSON Schema (a draft-2020-12 subset) is the contract for every state entity.
Schemas live as data in `schemas/`; this module loads them by entity name and
validates a parsed-JSON instance against one, raising a single SchemaError that
names the offending entity + field path on the first failure.

The supported keyword subset - `type`, `enum`, `required`, `properties`,
`items` - is exactly what the flat state shapes use; this is deliberately not a
full validator (decision (b)). If shapes ever outgrow it, swap in `jsonschema`
behind this same `validate`/`load_schema` surface.
"""
from __future__ import annotations

import json
from pathlib import Path

from .errors import SchemaError

_SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"

# JSON type name -> the Python type an instance must be. `integer`/`number` are
# handled separately because Python makes `bool` a subclass of `int`.
_PY_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "null": type(None),
}


def entity_kinds() -> list[str]:
    """The entity names the engine knows, from the schema files present."""
    return sorted(p.stem for p in _SCHEMA_DIR.glob("*.json"))


def load_schema(entity: str) -> dict:
    """The JSON Schema dict for `entity`. Unknown entity is a SchemaError."""
    path = _SCHEMA_DIR / f"{entity}.json"
    if not path.is_file():
        known = ", ".join(entity_kinds()) or "(none)"
        raise SchemaError(f"unknown entity '{entity}'. Known: {known}.")
    return json.loads(path.read_text())


def _type_ok(value: object, json_type: str) -> bool:
    if json_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if json_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, _PY_TYPES[json_type])


def _validate(value: object, schema: dict, entity: str, path: str) -> None:
    where = path or "(root)"

    types = schema.get("type")
    if types is not None:
        allowed = [types] if isinstance(types, str) else types
        if not any(_type_ok(value, t) for t in allowed):
            raise SchemaError(
                f"{entity}: {where} must be {' or '.join(allowed)}, "
                f"got {type(value).__name__}."
            )

    if "enum" in schema and value not in schema["enum"]:
        raise SchemaError(
            f"{entity}: {where} must be one of {schema['enum']}, got {value!r}."
        )

    if isinstance(value, dict) and (schema.get("type") == "object" or "properties" in schema):
        for key in schema.get("required", []):
            if key not in value:
                raise SchemaError(f"{entity}: {where} missing required '{key}'.")
        for key, subschema in schema.get("properties", {}).items():
            if key in value:
                child = key if not path else f"{path}.{key}"
                _validate(value[key], subschema, entity, child)

    if isinstance(value, list) and schema.get("type") == "array":
        item_schema = schema.get("items")
        if item_schema is not None:
            for i, item in enumerate(value):
                _validate(item, item_schema, entity, f"{where}[{i}]")


def validate(instance: object, schema: dict, entity: str | None = None) -> None:
    """Validate `instance` against `schema`; raise SchemaError on the first failure."""
    _validate(instance, schema, entity or schema.get("title", "instance"), "")


def validate_entity(entity: str, instance: object) -> None:
    """Load `entity`'s schema and validate `instance` against it."""
    validate(instance, load_schema(entity), entity)
