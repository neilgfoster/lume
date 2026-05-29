# /pr-ready

Controller loop that drives a branch to an operator-ready PR. Runs the local
gate, opens or updates the PR, then loops gate -> adversarial review -> fix
until the PR is green and clean — or escalates with `/stuck`.

Invoked automatically as the final phase of `/iterate` once implementation
completes; also remains independently invokable to drive an existing branch
through PR cycles without a fresh implementation step.

Natural-language aliases (routed via SKILL.md): "is the PR ready",
"check PR", "pre-PR", "PR ready".

## Stop condition

Stop only when ALL of the following hold:

- `am_i_done.py --pr N` exits 0 (local checks + PR template + threads)
- `am_i_done.py --pr N --check ci` exits 0 (CI matrix green)
- zero BLOCKING findings from `/adversarial-review`

Maximum 3 full review cycles. After the third, invoke `/stuck` instead of
looping again. Never expand scope, delete tests, or merge with known
failures to break out of the loop.

## Phases

1. **Local gate** — run `python3 .github/scripts/am_i_done.py`. Fix every
   failure before going remote. Do not push a red local gate.
2. **Create/update PR** — push the branch; `gh pr create` (or update the
   existing PR). The body must satisfy `.github/PULL_REQUEST_TEMPLATE.md`.
   Run `am_i_done.py --pr N` for the template and thread checks.
3. **Dependabot** — confirm no open Dependabot security alerts via
   `am_i_done.py --pr N --check dependabot` (graceful skip if not configured).
4. **CI gate** — poll `am_i_done.py --pr N --check ci` until the required
   matrix checks (`am_i_done (3.11)`-`(3.14)`) conclude. Red CI returns to
   the fix cycle.
5. **Adversarial review** — run `/adversarial-review` on the diff; use the
   `review-dispatcher` to select the panel.
6. **Fix cycle (if FAIL)** — for each BLOCKING finding: post a PR comment,
   fix or rebut, resolve the thread. After all findings are addressed,
   re-run the local gate and CI gate before returning to review. Count one
   cycle; stop at 3 and escalate via `/stuck`.
7. **Operator handoff** — when the stop condition holds, summarise PR state
   (checks, review verdict, open threads) and hand off. Never merge —
   merging is the operator's decision.

Blast radius: medium (pushes commits, creates or updates a PR). Opening or
updating a PR is an outward action — confirm before the first `gh pr create`
unless already authorised this session.

The same flow is catalogued in `skill/hedl/references/commands.md`; this file
is the executable command, that section is the documentation.
