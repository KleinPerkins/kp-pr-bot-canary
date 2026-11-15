#!/usr/bin/env python3
"""Repository safety and source-owned successor CI contract (stdlib only)."""
from __future__ import annotations

import json
from pathlib import Path
import stat
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHARDS = {'contract': ['tests/test_canary_contract.py'], 'ci-negative': ['tests/test_ci.py'], 'local-review': ['tests/test_local_review.py'], 'app-gate': ['tests/test_reviewer_app.py']}
CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
PR_ENV = {"CI_HEAD_SHA": "${{ github.event.pull_request.head.sha }}",
          "CI_BASE_SHA": "${{ github.event.pull_request.base.sha }}"}
CODE = {"scripts/verify.py", "tests/test_canary_contract.py", "tests/test_ci.py"}
OPTIONAL_CODE = {"scripts/local_review.py", "tests/test_local_review.py", "scripts/reviewer_app.py", "tests/test_reviewer_app.py"}
OWNER_RULES = {"/.github/** @KleinPerkins", "/.github/pr-automation.json @KleinPerkins",
               "/.github/pr-verification.json @KleinPerkins", "/_ops/** @KleinPerkins",
               "/scripts/** @KleinPerkins", "/tests/** @KleinPerkins", "/docs/** @KleinPerkins",
               "/AGENTS.md @KleinPerkins", "/README.md @KleinPerkins", "/SECURITY.md @KleinPerkins"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def regular(path: Path) -> None:
    require(path.is_file() and not path.is_symlink(), f"not a regular non-symlink file: {path.name}")


def load_json(path: Path) -> dict:
    regular(path)
    result = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(result, dict), f"{path.name} must contain an object")
    return result


def check_policy(root: Path) -> None:
    policy = load_json(root / ".github/ci-contract.json")
    require(set(policy) == {"schema", "repository", "successor", "shards", "protected_paths",
                            "integration_allowlist", "legacy", "coverage_mapping"}, "unexpected contract fields")
    require(policy["schema"] == "canary-ci-contract/v1", "wrong successor schema")
    require(policy["repository"] == {"owner":"KleinPerkins", "name":"kp-pr-bot-canary",
                                    "id":1297059298, "default_branch":"main"}, "repository identity drift")
    require(policy["successor"] == {"actions_app_id":15368, "reviewer_app_id":4217367,
                                    "required_check":"ci-required", "workflow":".github/workflows/ci.yml",
                                    "workflow_name":"CI", "activation":"gated"}, "successor identity drift")
    require(policy["shards"] == SHARDS, "closed shard command set drift")
    require(policy["protected_paths"] == [".github", "scripts", "tests", "docs", "AGENTS.md", "README.md",
                                           "SECURITY.md", "CODEOWNERS", "_ops"], "protected surface drift")
    require(policy["integration_allowlist"] == ["scripts/local_review.py", "tests/test_local_review.py",
                                               "docs/local-review.md", ".github/workflows/reviewer-app.yml",
                                               "scripts/reviewer_app.py", "tests/test_reviewer_app.py",
                                               "docs/github-delivery.md", ".github/review-enrollments.json"], "integration allowlist drift")
    require(policy["legacy"] == {"mode":"historical-until-control-cutover",
                                "files":[".github/pr-automation.json", ".github/pr-recipe.json",
                                         ".github/pr-automation.lock.json", ".github/pr-verification.json"],
                                "aggregate":"pr-automation / verify",
                                "custom":"pr-automation / job:repo.kp-pr-bot-canary.m3-verify"}, "legacy mapping drift")
    require(set(policy["coverage_mapping"]) == {"regular_inputs", "identity", "topology", "ownership",
                                                "inertness", "operator_docs"}, "old obligations unmapped")
    require(all(isinstance(v, str) and len(v) > 30 for v in policy["coverage_mapping"].values()), "empty coverage mapping")
    for name in policy["legacy"]["files"]:
        regular(root / name)
    for name in (".github/CODEOWNERS", "README.md", "AGENTS.md", "scripts/verify.py", *CODE):
        regular(root / name)


def check_workflow(workflow: dict) -> None:
    require(set(workflow) == {"name", "on", "permissions", "concurrency", "jobs"}, "workflow fields drift")
    require(workflow["name"] == "CI", "wrong workflow name")
    require(workflow["on"] == {"pull_request":{"types":["opened", "reopened", "synchronize", "ready_for_review"]},
                                "push":{"branches":["main"]}}, "unsafe or incomplete triggers")
    require(workflow["permissions"] == {"contents":"read"}, "CI must have contents-read only")
    require(workflow["concurrency"] == {"group":"ci-${{ github.event.pull_request.number || github.ref }}",
                                         "cancel-in-progress":True}, "concurrency drift")
    jobs = workflow["jobs"]
    require(set(jobs) == {*SHARDS, "ci-required"}, "missing or extra CI jobs")
    checkout = {"uses":CHECKOUT, "with":{"ref":"${{ github.sha }}", "persist-credentials":False, "fetch-depth":2}}
    for name, job in jobs.items():
        require(job.get("runs-on") == "ubuntu-24.04", "only free standard hosted Ubuntu is allowed")
        require(job.get("timeout-minutes") == 5, "bounded timeout required")
        require(job.get("name") == name, "job/check name drift")
        require(job.get("steps", [None])[0] == checkout, "checkout must pin action and exact revision without credentials")
        if name in SHARDS:
            require(set(job) == {"name", "runs-on", "timeout-minutes", "outputs", "steps"}, "unsafe shard fields")
            require(job["outputs"] == {"receipt":"${{ steps.verify.outputs.receipt }}"}, "shard receipt not exported")
            require(job["steps"] == [checkout, {"name":"Run "+name, "id":"verify", "env":PR_ENV,
                                                "run":"python3 -I -B scripts/verify.py shard --shard "+name}],
                    "shard execution must run its closed nonempty suite")
        else:
            require(set(job) == {"name", "needs", "if", "runs-on", "timeout-minutes", "steps"}, "unsafe aggregate fields")
            require(job["needs"] == list(SHARDS), "aggregate needs every shard exactly once")
            require(job["if"] == "${{ always() }}", "aggregate must always run")
            require(job["steps"] == [checkout, {"name":"Require every exact-run shard",
                                                "env":dict(PR_ENV, CI_NEEDS="${{ toJSON(needs) }}"),
                                                "run":"python3 -I -B scripts/verify.py aggregate"}],
                    "aggregate must verify actual needs and run identity")


def check_ownership(root: Path) -> None:
    path = root / ".github/CODEOWNERS"
    regular(path)
    rules = {line.strip() for line in path.read_text().splitlines() if line.strip() and not line.startswith("#")}
    require(OWNER_RULES <= rules, f"missing protected ownership: {sorted(OWNER_RULES - rules)}")
    # A later rule can override an earlier match. Restrict every effective owner line.
    require(all(line.split()[1:] == ["@KleinPerkins"] for line in rules), "unexpected ownership override")


def check_surface(root: Path) -> None:
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if ".git" in path.relative_to(root).parts:
            continue
        require(not path.is_symlink(), f"symlink fixture is forbidden: {relative}")
        if not path.is_file():
            continue
        require(stat.S_ISREG(path.stat().st_mode), f"nonregular fixture: {relative}")
        require(not path.stat().st_mode & 0o111, f"canary fixture must not be executable: {relative}")
        if relative.startswith(".github/workflows/"):
            require(relative in {".github/workflows/ci.yml", ".github/workflows/reviewer-app.yml"}, f"unexpected workflow: {relative}")
        elif path.suffix == ".py":
            require(relative in CODE | OPTIONAL_CODE, f"unexpected code: {relative}")
        else:
            require(path.suffix in {".json", ".md", ".txt", ".yml"}
                    or relative in {".canary-bypass-test", ".gitignore", ".github/CODEOWNERS"},
                    f"unexpected production-code surface: {relative}")


def check_docs(root: Path) -> None:
    text = (root / "README.md").read_text()
    for phrase in ("1297059298", "15368", "4217367", "ci-required", "contract", "ci-negative",
                   "historical", "publication", "qualified", "independent review", "merge revision"):
        require(phrase in text.lower(), f"README successor contract missing: {phrase}")
    for phrase in ("GitHub Actions remain paused", "no workflow content belongs", "verifier App `4274739` posts"):
        require(phrase not in text, f"README retains obsolete active-design claim: {phrase}")


class CanaryContract(unittest.TestCase):
    def test_policy_identity_and_regular_inputs(self):
        check_policy(ROOT)

    def test_complete_workflow_topology_and_permissions(self):
        check_workflow(load_json(ROOT / ".github/workflows/ci.yml"))

    def test_protected_ownership(self):
        check_ownership(ROOT)

    def test_inert_fixture_surface(self):
        check_surface(ROOT)

    def test_operator_description(self):
        check_docs(ROOT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
