# kp-pr-bot-canary

**Disposable canary — safe to delete.** Repository `KleinPerkins/kp-pr-bot-canary`
(immutable id `1297059298`, default branch `main`) exercises repository protection,
CI and exact-head App review. Nothing here is production code; fixtures must remain
inert and must contain no credentials or private business data.

## Successor source and qualification

The successor CI source uses free standard GitHub-hosted `ubuntu-24.04` runners,
pinned checkout, read-only contents permission and no secrets. The `contract` shard
checks repository identity, protected ownership, a closed workflow, accurate docs
and the inert fixture boundary. The `ci-negative` shard executes failure tests for
missing/failed/cancelled/skipped/stale receipts, source identity, unsafe workflow
changes and an executable fixture. Both contain actual test suites.

The configured required context is `ci-required` (GitHub Actions producer App
`15368`). Its aggregate is defined to run after both shards, including failures,
and fail unless the complete shard set passed for the same repository, event,
revision, workflow revision, run id, run attempt and ref. A pull request tests its
GitHub merge revision and verifies both base and head parents; a push tests the
exact `main` revision. A failed or cancelled aggregate is never a passing check.
No artifact from another run is accepted and no legacy check is fabricated.
The workflow uses JSON-compatible YAML so its complete structure can be checked
with Python's standard library without installing dependencies.

The accepted successor reviewer App identity is `4217367`. The App listener,
credential readiness, substantive independent review, exact-head approval and
native squash merge each require their own implementation and qualification.
CI does not approve PRs or mint an App token. Local review adapter files may be
integrated through the explicit allowlist in `.github/ci-contract.json`.

This source is staged for a governed transition. Publication exposure checks,
initial admission, actual PR and merged-main CI, strict required-check controls,
App write-off readiness and independent review must be proven at their accepted
gates. Source or local-test success does not mean Actions is enabled, a repository
is public, an App is qualified, or a ruleset has changed. No cloud qualification is
claimed by this README.

## Historical controls and coverage mapping

The four `.github/pr-*` JSON files remain historical transition records until the
accepted control cutover. They describe retired controller contracts and are not
the successor CI authority. Preserve old required contexts as blockers until the
verified settings transaction; do not post lookalike retired checks.

| Historical obligation | Successor coverage |
|---|---|
| Canned regular, non-symlink control inputs | `contract`: successor policy, workflow, ownership, runner and legacy records |
| Immutable repository, main and App identities | `contract`: repository `1297059298`, Actions `15368`, reviewer `4217367` |
| Closed command/dependency topology and all-required aggregation | Both shards and exact-run `ci-required`; negative cases execute in `ci-negative` |
| Protected automation ownership | `contract`: explicit CODEOWNERS coverage of policy and source helpers |
| No production/executable fixture surface | `contract` allowlist plus executable, symlink and unexpected-code regression tests |
| Operator description matches design | `contract`: successor roles, historical files and qualification limits |

The old custom context `pr-automation / job:repo.kp-pr-bot-canary.m3-verify` maps to
the substantive two-shard coverage. The old `pr-automation / verify` aggregate maps
to `ci-required` only after the accepted live control transition.

## Local verification

Run `python3 -I -B scripts/verify.py local`. It executes both hosted shard suites
without network or GitHub credentials. Hosted `shard` and `aggregate` modes also
require a valid GitHub run identity and an exact source checkout; local mode does
not manufacture hosted receipts. These checks qualify source behavior only.

Use GitHub's private vulnerability reporting when available, or contact the
repository owner privately. Do not place credentials or sensitive material in
public issues, logs, fixtures or review evidence.

## Integrated review checks

Four nonempty CI shards run the repository contract, CI failure cases, local-review adapter tests and App-gate tests. `ci-required` verifies all four exact-run receipts and emits a bound aggregate record for the trusted App. Local review uses separate enrolled work and personal Codex profiles. The App remains disabled until actual source, credential, CI and control qualification; Q16 trusts enrolled local tooling operationally and does not claim protection against same-user receipt forgery.
