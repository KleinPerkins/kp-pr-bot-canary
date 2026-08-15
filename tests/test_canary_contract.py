#!/usr/bin/env python3
"""Verify that this repository remains a safe, inert runnerless canary."""

from __future__ import annotations

import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / ".github" / "pr-automation.json"
RECIPE_PATH = ROOT / ".github" / "pr-recipe.json"
CODEOWNERS_PATH = ROOT / ".github" / "CODEOWNERS"
README_PATH = ROOT / "README.md"
JOB_ID = "repo.kp-pr-bot-canary.m3-verify"
CANNED_ID = "canned.repository-contract.v1"


def load_json(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    assert isinstance(value, dict), f"{path.relative_to(ROOT)} must contain a JSON object"
    return value


def regular_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(ROOT).parts
    )


def test_policy_identity() -> None:
    policy = load_json(POLICY_PATH)
    expected = {
        "activation_generation": 3,
        "check_name": "pr-automation / verify",
        "default_branch": "main",
        "name": "kp-pr-bot-canary",
        "owner": "KleinPerkins",
        "repository_id": 1297059298,
        "reviewer_app_id": 4269364,
        "reviewer_integration_id": 4269364,
        "verifier_app_id": 4274739,
        "verifier_integration_id": 4274739,
        "version": "pr-automation/v3",
    }
    for key, expected_value in expected.items():
        assert policy.get(key) == expected_value, (
            f"{POLICY_PATH.relative_to(ROOT)} {key!r} drifted: "
            f"expected {expected_value!r}, got {policy.get(key)!r}"
        )
    assert policy.get("protected_paths") == [".github", "CODEOWNERS", "_ops"], (
        "protected_paths must keep the complete runnerless automation surface owner-controlled"
    )


def test_recipe_topology() -> None:
    recipe = load_json(RECIPE_PATH)
    expected_job = {
        "argv": ["run-literal", "python3", "-B", "tests/test_canary_contract.py"],
        "depends_on": [CANNED_ID],
        "environment": {},
        "id": JOB_ID,
    }
    assert recipe.get("repository_id") == "kp-pr-bot-canary"
    assert recipe.get("schema") == "pr-automation-recipe/v1"
    assert recipe.get("custom_jobs") == [expected_job], (
        "recipe must contain exactly the repository-owned canary contract job"
    )
    assert recipe.get("pipeline") == {
        "aggregate": "all_required",
        "jobs": [
            {"depends_on": [], "id": CANNED_ID},
            {"depends_on": [CANNED_ID], "id": JOB_ID},
        ],
        "pipeline_id": "kp-pr-bot-canary-m3-pipeline",
        "version": "pr-automation-pipeline/v1",
    }, "recipe pipeline must fail closed after the canned repository contract"


def test_protected_ownership() -> None:
    text = CODEOWNERS_PATH.read_text(encoding="utf-8")
    required_rules = {
        "/.github/** @KleinPerkins",
        "/.github/pr-automation.json @KleinPerkins",
        "/.github/pr-verification.json @KleinPerkins",
        "/_ops/** @KleinPerkins",
    }
    missing = sorted(rule for rule in required_rules if rule not in text.splitlines())
    assert not missing, f"CODEOWNERS lost protected automation rules: {missing}"


def test_runnerless_inert_surface() -> None:
    workflows = ROOT / ".github" / "workflows"
    assert not workflows.exists() or not any(workflows.rglob("*")), (
        "native GitHub Actions workflow content is forbidden; this canary is runnerless"
    )

    allowed_code = {"tests/test_canary_contract.py"}
    allowed_suffixes = {".json", ".md", ".txt", ".yml"}
    suffix_exceptions = {".canary-bypass-test", ".gitignore", ".github/CODEOWNERS"}
    unexpected_code: list[str] = []
    executables: list[str] = []
    for path in regular_files():
        relative = path.relative_to(ROOT).as_posix()
        if relative not in allowed_code | suffix_exceptions and path.suffix not in allowed_suffixes:
            unexpected_code.append(relative)
        if path.stat().st_mode & 0o111:
            executables.append(relative)
    assert not unexpected_code, (
        "unexpected production-code surface in disposable fixture: "
        f"{unexpected_code}"
    )
    assert not executables, f"canary fixture files must not be executable: {executables}"


def test_operator_description_matches_live_design() -> None:
    text = README_PATH.read_text(encoding="utf-8")
    required_phrases = {
        "runnerless",
        "verifier App `4274739`",
        "reviewer App `4269364`",
        "GitHub Actions remain paused",
    }
    missing = sorted(phrase for phrase in required_phrases if phrase not in text)
    assert not missing, f"README does not describe the live runnerless design: {missing}"
    assert ".github/workflows/controller.yml" not in text
    assert ".github/workflows/required.yml" not in text


def main() -> None:
    test_policy_identity()
    test_recipe_topology()
    test_protected_ownership()
    test_runnerless_inert_surface()
    test_operator_description_matches_live_design()
    print("kp-pr-bot-canary contract passed")


if __name__ == "__main__":
    os.chdir(ROOT)
    main()
