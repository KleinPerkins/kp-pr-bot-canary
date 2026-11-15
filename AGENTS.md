# Canary source instructions

This is the disposable `KleinPerkins/kp-pr-bot-canary` repository, immutable GitHub
id `1297059298`, default branch `main`. Preserve its narrow fixture purpose.

- `.github/ci-contract.json` owns the successor CI identity, closed shards and
  coverage mapping. CI source is unprivileged; keep contents-read only, pinned
  actions, standard hosted runners, bounded jobs and exact-run aggregation.
- Run `python3 -I -B scripts/verify.py local` after source changes. Do not replace
  safety tests with success markers or synthesize old controller checks.
- `.github/pr-*` JSON remains historical until the accepted cutover. Existing
  blockers, publication, first admission, independent review, App readiness and
  exact-head native squash merge are distinct gates. Local success proves none
  of the platform state. Do not change settings or publish without those gates.
- Keep all files non-executable, all fixtures inert, no symlinks, no secrets or
  business data. Python source and workflows require exact allowlist entries.
- Optional `scripts/local_review.py`, `tests/test_local_review.py` and
  `docs/local-review.md` are reserved for the separately accepted trusted local
  adapter. Their allowlisting is not implementation or qualification evidence.
- Optional App integration paths are exactly `.github/workflows/reviewer-app.yml`,
  `scripts/reviewer_app.py`, `tests/test_reviewer_app.py`, `docs/github-delivery.md`
  and `.github/review-enrollments.json`. The integration owner must add meaningful
  App test execution and workflow-contract checks before claiming App readiness.
  Their reserved presence does not qualify a privileged listener. Further paths
  require explicit contract updates; no wildcard code/workflow admission.
- `.github/CODEOWNERS` protects policy, scripts, tests and operator docs.
  Independent originating-account substantive review remains a separate gate.
- Respect the inherited personal repository identity, one writer per worktree,
  native workspace attachment and installed commit guards. Never bypass hooks,
  manipulate auto-merge or silently remove unrelated work.
