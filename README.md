# kp-pr-bot-canary

**Disposable canary — safe to delete.**

This repository is a throwaway test bed for validating the repo-local GitHub Actions
**PR review-bot** model (a "chaos-scheduler-style but hardened" design). It exists only to
exercise the branch-protection rulesets, the unprivileged CI producer, and the trusted
default-branch controller against real GitHub platform behavior.

Nothing here is production code. Do not depend on it. It may be deleted at any time.

## Design under test

- `.github/workflows/required.yml` — unprivileged CI producer (no secrets, `contents: read`),
  ending in an aggregator job `ci` that fails closed.
- `.github/workflows/controller.yml` — trusted default-branch controller
  (`workflow_run`), read-only preflight, mints a narrowly-scoped App token only after every
  safety assertion passes.
- `.github/CODEOWNERS` — protects the automation surface.

Two rulesets guard the default branch: `kleinperkins-merge-safety` (required PR + required
`required / ci` check from GitHub Actions, no bypass) and `kleinperkins-review-gate`
(one code-owner approval, stale-approval dismissal).

<!-- runnerless generation-1 ordinary canary -->

<!-- runnerless generation-2 smoke -->
