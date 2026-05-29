#!/usr/bin/env python3
"""
check_pr_template.py — validate a PR body against the project template.

Reads the body from the PR_BODY environment variable. Exits non-zero with
per-section errors if validation fails.

Hardening (from adversarial review findings):
- Heading regex is line-anchored and code-fenced blocks are stripped before
  scanning, so `## Heading` inside a code block does not satisfy or terminate
  sections.
- The "Work item" `none` path requires the literal token `none` as the leading
  word of the section AND a non-trivial justification.
- `WORK-XXXX` references must be uppercase (downstream `grep` and
  `am_i_done.py:check_commands()` rely on canonical casing).
- `[x]` checkbox match is line-anchored.
- `Changes` bullets require `- ` (dash space) followed by non-empty content
  (rejects a bare `-`).
"""

import os
import re
import sys

PR_BODY = os.environ.get("PR_BODY", "")

ERRORS: list[str] = []

_FENCED_BLOCK = re.compile(r"```.*?```", re.DOTALL)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def strip_noise(body: str) -> str:
    """Remove fenced code blocks before heading detection.

    Fenced blocks can otherwise contain literal `## Heading` lines that
    confuse the section parser (SEC8 / EC2).
    """
    return _FENCED_BLOCK.sub("", body)


def section_content(body: str, heading: str) -> str:
    """Return the text between this heading and the next `## ` heading.

    Heading match is anchored to start-of-line via re.MULTILINE so headings
    embedded inside paragraphs cannot satisfy validation.
    """
    pattern = rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)"
    match = re.search(pattern, body, re.DOTALL | re.IGNORECASE | re.MULTILINE)
    if not match:
        return ""
    return match.group(1).strip()


def is_placeholder(text: str) -> bool:
    """True if the text is only HTML comments or whitespace."""
    return not _HTML_COMMENT.sub("", text).strip()


def check_section_filled(body: str, heading: str) -> None:
    content = section_content(body, heading)
    if not content or is_placeholder(content):
        ERRORS.append(f"Section '## {heading}' is empty or not filled out.")


def check_work_item(body: str) -> None:
    content = section_content(body, "Work item")
    if not content or is_placeholder(content):
        ERRORS.append("Section '## Work item' is empty.")
        return

    # Strip HTML comments so `<!-- ... -->` does not satisfy validation.
    visible = _HTML_COMMENT.sub("", content).strip()

    # Must contain an uppercase `WORK-\d+` reference OR an explicit `none`
    # token at the start with non-trivial justification.
    if re.search(r"\bWORK-\d+\b", visible):
        return

    # `none` must be the leading content of the section (case-insensitive),
    # followed by separator + justification of at least 12 characters.
    none_match = re.match(
        r"\s*none\b[\s:—\-]+(?P<just>.+)",
        visible,
        re.IGNORECASE | re.DOTALL,
    )
    if none_match and len(none_match.group("just").strip()) >= 12:
        return

    ERRORS.append(
        "Section '## Work item' must contain a WORK-XXXX reference (uppercase) "
        "or start with 'none' followed by a justification (>=12 chars)."
    )


def check_type_selected(body: str) -> None:
    content = section_content(body, "Type")
    if not content or is_placeholder(content):
        ERRORS.append("Section '## Type' is empty.")
        return
    # Anchor to start-of-line so an embedded `- [x]` in a paragraph does not
    # falsely satisfy the check (EC4).
    if not re.search(r"^\s*- \[x\] ", content, re.IGNORECASE | re.MULTILINE):
        ERRORS.append("Section '## Type' requires at least one option marked with [x].")


def check_changes(body: str) -> None:
    content = section_content(body, "Changes")
    if not content or is_placeholder(content):
        ERRORS.append("Section '## Changes' is empty.")
        return
    # Must have at least one bullet of form `- <non-empty>` (EC5).
    # `[ \t]+` (not `\s+`) so a bare `-\n-` does not satisfy via newline.
    bullet_pattern = re.compile(r"^[ \t]*-[ \t]+\S", re.MULTILINE)
    if not bullet_pattern.search(content):
        ERRORS.append(
            "Section '## Changes' must have at least one bullet of form '- <text>'."
        )


def main() -> int:
    # Reset module-level list so repeated calls within the same process
    # (e.g., test suites) do not accumulate findings across invocations.
    ERRORS.clear()

    if not PR_BODY.strip() or PR_BODY.strip().lower() == "null":
        print("ERROR: PR body is empty. Use the PR template.")
        return 1

    body = strip_noise(PR_BODY)

    check_section_filled(body, "Summary")
    check_work_item(body)
    check_type_selected(body)
    check_changes(body)
    check_section_filled(body, "Validation")

    if ERRORS:
        print("PR template validation failed:\n")
        for err in ERRORS:
            print(f"  - {err}")
        print(
            "\nFill out all required sections in the PR description. "
            "See .github/PULL_REQUEST_TEMPLATE.md."
        )
        return 1

    print("PR template validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
