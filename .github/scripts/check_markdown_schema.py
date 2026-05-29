#!/usr/bin/env python3
"""
check_markdown_schema.py — validate markdown files against schema definitions.

Schemas are loaded from .work/config/markdown-schemas.json (or --schemas override).

Usage:
  python3 .github/scripts/check_markdown_schema.py
  python3 .github/scripts/check_markdown_schema.py file1.md file2.md
  python3 .github/scripts/check_markdown_schema.py --json
  python3 .github/scripts/check_markdown_schema.py --schemas path/to/schemas.json

Exits 0 when all validated files pass. Exits 1 when violations are found.
Files that match no schema are silently skipped.
"""

import argparse
import glob as glob_module
import json
import os
import re
import subprocess
import sys
from typing import Any, Optional

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# .github/scripts/ -> .github/ -> repo root
_SCRIPT_RELATIVE_ROOT = os.path.dirname(os.path.dirname(_SCRIPT_DIR))


def _find_repo_root() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            text=True,
            timeout=10,
            stderr=subprocess.DEVNULL,
        ).strip()
        if out:
            return out
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass
    return _SCRIPT_RELATIVE_ROOT


def load_schemas(schemas_path: str) -> list[dict[str, Any]]:
    with open(schemas_path, encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    result: list[dict[str, Any]] = data.get("schemas", [])
    return result


def _parse_frontmatter(content: str) -> tuple[Optional[dict[str, Any]], str]:
    """Parse simple key: value frontmatter from a markdown file.

    Returns (frontmatter_dict, remaining_body). Returns (None, content) when
    no frontmatter block is present. Only handles scalar key: value lines —
    list-style YAML values are captured as raw strings, which is sufficient
    for presence checks.
    """
    if not content.startswith("---"):
        return None, content

    lines = content.splitlines()
    if len(lines) < 2:
        return None, content

    end: Optional[int] = None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end = i
            break

    if end is None:
        return None, content

    fm: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip()

    body = "\n".join(lines[end + 1:])
    return fm, body


def _first_heading(content: str, level: int = 1) -> Optional[str]:
    """Return the text of the first heading at the given level, or None."""
    prefix = "#" * level + " "
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix):].strip()
    return None


def _first_heading_line(content: str, level: int = 1) -> Optional[str]:
    """Return the full first heading line at the given level, or None."""
    prefix = "#" * level + " "
    for line in content.splitlines():
        if line.strip().startswith(prefix):
            return line.strip()
    return None


def _all_headings(content: str, level: int = 2) -> list[str]:
    """Return text of all headings at the given level."""
    prefix = "#" * level + " "
    result = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            result.append(stripped[len(prefix):].strip())
    return result


def _glob_files(pattern: str, repo_root: str) -> list[str]:
    abs_pattern = os.path.join(repo_root, pattern)
    return glob_module.glob(abs_pattern, recursive=True)


def _matches_any_glob(filepath: str, patterns: list[str], repo_root: str) -> bool:
    """Return True if filepath matches any of the given glob patterns."""
    try:
        rel_path = os.path.relpath(filepath, repo_root).replace(os.sep, "/")
    except ValueError:
        rel_path = filepath

    for pattern in patterns:
        expanded = {
            os.path.relpath(f, repo_root).replace(os.sep, "/")
            for f in _glob_files(pattern, repo_root)
        }
        if rel_path in expanded:
            return True
    return False


def validate_file(filepath: str, schema: dict[str, Any], repo_root: str) -> list[dict[str, Any]]:
    """Validate one file against one schema. Returns a list of violation dicts."""
    violations: list[dict[str, Any]] = []

    try:
        with open(filepath, encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except OSError as exc:
        return [{"file": filepath, "schema": schema["id"], "field": "file", "message": str(exc)}]

    try:
        rel_path = os.path.relpath(filepath, repo_root).replace(os.sep, "/")
    except ValueError:
        rel_path = filepath

    def add(field: str, message: str) -> None:
        violations.append({"file": rel_path, "schema": schema["id"], "field": field, "message": message})

    frontmatter, _body = _parse_frontmatter(content)

    # Frontmatter validation
    fm_schema = schema.get("frontmatter")
    if fm_schema is not None:
        required_fields: list[str] = fm_schema.get("required", [])
        field_rules: dict[str, Any] = fm_schema.get("fields", {})

        if frontmatter is None:
            add("frontmatter", "no frontmatter block found (expected ---...--- at top of file)")
        else:
            for field_name in required_fields:
                if field_name not in frontmatter:
                    add(field_name, f"required frontmatter field '{field_name}' is missing")
                    continue

                value = frontmatter[field_name]
                rules = field_rules.get(field_name, {})

                if "enum" in rules and value not in rules["enum"]:
                    allowed = ", ".join(f"'{v}'" for v in rules["enum"])
                    add(field_name, f"'{field_name}' value '{value}' not in allowed values: [{allowed}]")

                if "pattern" in rules and not re.search(rules["pattern"], value):
                    add(field_name, f"'{field_name}' value '{value}' does not match pattern '{rules['pattern']}'")

                min_len = rules.get("min_length")
                if min_len is not None and len(value) < min_len:
                    add(field_name, f"'{field_name}' too short ({len(value)} chars, minimum {min_len})")

                max_len = rules.get("max_length")
                if max_len is not None and len(value) > max_len:
                    add(field_name, f"'{field_name}' too long ({len(value)} chars, maximum {max_len})")

    # Title checks
    if schema.get("required_title"):
        title = _first_heading(content, level=1)
        if title is None:
            add("title", "required title (# heading) not found")
        else:
            max_len = schema.get("title_max_length")
            if max_len is not None and len(title) > max_len:
                add("title", f"title too long ({len(title)} chars, maximum {max_len}): '{title[:60]}'")

    if "title_pattern" in schema:
        heading_line = _first_heading_line(content, level=1)
        if heading_line is None:
            add("title", f"no # heading found (expected to match pattern '{schema['title_pattern']}')")
        elif not re.match(schema["title_pattern"], heading_line):
            add("title", f"title line '{heading_line}' does not match pattern '{schema['title_pattern']}'")

    # Required headings (## level)
    if "required_headings" in schema:
        present = _all_headings(content, level=2)
        for heading in schema["required_headings"]:
            if heading not in present:
                add("heading", f"required section '## {heading}' not found")

    # Required patterns (regex anywhere in document)
    if "required_patterns" in schema:
        for pat_def in schema["required_patterns"]:
            pattern = pat_def["pattern"]
            desc = pat_def.get("description", pattern)
            if not re.search(pattern, content):
                add("pattern", f"required pattern not found: {desc}")

    return violations


def find_schema_for_file(
    filepath: str,
    schemas: list[dict[str, Any]],
    repo_root: str,
) -> Optional[dict[str, Any]]:
    """Return the first schema whose glob matches filepath and no exclude_glob matches it."""
    try:
        rel_path = os.path.relpath(filepath, repo_root).replace(os.sep, "/")
    except ValueError:
        rel_path = filepath

    for schema in schemas:
        glob_pattern = schema.get("glob", "")
        matched = {
            os.path.relpath(f, repo_root).replace(os.sep, "/")
            for f in _glob_files(glob_pattern, repo_root)
        }
        if rel_path not in matched:
            continue

        exclude_globs: list[str] = schema.get("exclude_globs", [])
        if exclude_globs and _matches_any_glob(filepath, exclude_globs, repo_root):
            continue

        return schema

    return None


def validate_all(
    schemas: list[dict[str, Any]],
    repo_root: str,
    specific_files: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """Validate files against schemas. Returns all violations."""
    all_violations: list[dict[str, Any]] = []

    if specific_files is not None:
        for filepath in specific_files:
            abs_path = os.path.abspath(filepath)
            if not os.path.isfile(abs_path):
                continue
            schema = find_schema_for_file(abs_path, schemas, repo_root)
            if schema is None:
                continue
            all_violations.extend(validate_file(abs_path, schema, repo_root))
    else:
        validated: set[str] = set()
        for schema in schemas:
            glob_pattern = schema.get("glob", "")
            exclude_globs: list[str] = schema.get("exclude_globs", [])
            matched_files = _glob_files(glob_pattern, repo_root)

            for filepath in sorted(matched_files):
                if not os.path.isfile(filepath):
                    continue
                abs_fp = os.path.abspath(filepath)
                if abs_fp in validated:
                    continue
                if exclude_globs and _matches_any_glob(filepath, exclude_globs, repo_root):
                    continue
                validated.add(abs_fp)
                all_violations.extend(validate_file(filepath, schema, repo_root))

    return all_violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate markdown files against schema definitions")
    parser.add_argument("files", nargs="*", help="Specific files to validate (default: all matching files)")
    parser.add_argument("--json", action="store_true", dest="as_json", help="JSON output")
    parser.add_argument(
        "--schemas",
        default=None,
        help="Path to schemas JSON file (default: .work/config/markdown-schemas.json)",
    )
    args = parser.parse_args()

    repo_root = _find_repo_root()
    schemas_path = args.schemas or os.path.join(repo_root, ".work", "config", "markdown-schemas.json")

    if not os.path.isfile(schemas_path):
        if args.as_json:
            print(json.dumps({
                "passed": False,
                "violation_count": 0,
                "violations": [],
                "error": f"schemas file not found: {schemas_path}",
            }))
        else:
            print(f"Error: schemas file not found: {schemas_path}", file=sys.stderr)
        return 1

    try:
        schemas = load_schemas(schemas_path)
    except (json.JSONDecodeError, KeyError) as exc:
        if args.as_json:
            print(json.dumps({
                "passed": False,
                "violation_count": 0,
                "violations": [],
                "error": f"schemas file malformed: {exc}",
            }))
        else:
            print(f"Error: schemas file malformed: {exc}", file=sys.stderr)
        return 1

    specific_files = args.files if args.files else None
    violations = validate_all(schemas, repo_root, specific_files)
    passed = len(violations) == 0

    if args.as_json:
        print(json.dumps({
            "passed": passed,
            "violation_count": len(violations),
            "violations": violations,
        }, indent=2))
    else:
        if violations:
            for v in violations:
                print(f"  {v['file']}: [{v['schema']}] {v['message']}")
            print(f"\n{len(violations)} violation(s) found.")
        else:
            print("All markdown files pass schema validation.")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
