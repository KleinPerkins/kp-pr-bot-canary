# kp-pr-bot-canary

**Disposable canary — safe to delete.**

This repository is a throwaway test bed for validating the runnerless PR automation model. It
exists only to exercise branch-protection rulesets, exact-head verification, and reviewer-driven
native auto-merge against real GitHub platform behavior.

Nothing here is production code. Do not depend on it. It may be deleted at any time.

## Design under test

- verifier App `4274739` posts the aggregate and repository job Checks after isolated,
  credential-free execution;
- reviewer App `4269364` approves the exact passing head and arms native squash auto-merge;
- `.github/pr-automation.json`, `.github/pr-recipe.json`, and the generated lock define the
  protected repository contract; and
- `.github/CODEOWNERS` keeps that automation surface owner-controlled.

GitHub Actions remain paused and no workflow content belongs in this repository.

<!-- runnerless generation-1 ordinary canary -->

<!-- runnerless generation-2 smoke -->

<!-- G4 informational proof: the repository-owned safety Check rejected an executable fixture and permits this restored inert head. -->
