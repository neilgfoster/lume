"""argv flag parsing: pull global/value flags out of the argument vector.

Both helpers preserve argv[0] (the program name) and remove the matched flag,
returning the remaining tokens for positional dispatch.
"""
from __future__ import annotations


def _extract_bool_flag(argv: list[str], name: str) -> tuple[bool, list[str]]:
    """Pull a valueless flag (e.g. --json) out of argv (anywhere); argv[0] preserved."""
    present = name in argv[1:]
    rest = [argv[0]] + [t for t in argv[1:] if t != name] if argv else []
    return present, rest


def _extract_multi_flag(argv: list[str], aliases: tuple[str, ...], noun: str) -> tuple[list[str], list[str]]:
    """Pull every `<alias> <value>` occurrence out of argv (a repeatable flag).

    Returns (values in argv order, argv with the flags removed). Raises
    ValueError if an alias is given without a following value.
    """
    values: list[str] = []
    rest = [argv[0]] if argv else []
    i = 1
    while i < len(argv):
        tok = argv[i]
        if tok in aliases:
            if i + 1 >= len(argv) or not argv[i + 1].strip():
                raise ValueError(f"{tok} needs {noun}.")
            values.append(argv[i + 1].strip())
            i += 2
            continue
        rest.append(tok)
        i += 1
    return values, rest


def _extract_flag(argv: list[str], aliases: tuple[str, ...], noun: str) -> tuple[str | None, list[str]]:
    """Pull `<alias> <value>` out of argv (anywhere); argv[0] is preserved.

    Returns (value or None, argv with the flag removed). Raises ValueError if an
    alias is given without a following value.
    """
    value: str | None = None
    rest = [argv[0]] if argv else []
    i = 1
    while i < len(argv):
        tok = argv[i]
        if tok in aliases:
            if i + 1 >= len(argv) or not argv[i + 1].strip():
                raise ValueError(f"{tok} needs {noun}.")
            value = argv[i + 1].strip()
            i += 2
            continue
        rest.append(tok)
        i += 1
    return value, rest
