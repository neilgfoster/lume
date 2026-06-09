---
status: active
---
# State is Data

Workstream state today lives in markdown. Markdown is a rendering for
humans and agents, not a source of truth - it can't be validated, queried,
or mutated deterministically. Separate the two: state is JSON, validated
against a schema; markdown becomes a view derived from that state.

Tooling (the lume CLI) is the only writer of state. An LLM interacts with
it through deterministic verbs that read and mutate JSON, never by hand-
editing files. The same tooling lets an agent discover what data exists and
what shape it takes - enumerate entities and surface their schema - so an
agent dropped cold into a repo can orient without prior knowledge of the
format.

Every read and write is schema-validated. Invalid state is rejected at the
tooling boundary, not discovered later by a confused reader.

Done-when: workstream/iteration state is stored as schema-validated JSON;
the CLI is the sole mutator and exposes verbs to discover entities and
fetch their schema; human-readable markdown is regenerated from state
rather than authored; and this workstream itself is tracked under the new
JSON state to prove it.
