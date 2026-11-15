#!/usr/bin/env python3
"""Execute fail-closed CI mutations and the canary executable-fixture regression."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


ci = module("canary_verify", "scripts/verify.py")
contract = module("canary_contract", "tests/test_canary_contract.py")
ENV = dict(GITHUB_REPOSITORY="KleinPerkins/kp-pr-bot-canary", GITHUB_REPOSITORY_ID="1297059298",
           GITHUB_EVENT_NAME="pull_request", GITHUB_SHA="a"*40, GITHUB_WORKFLOW_SHA="a"*40,
           GITHUB_RUN_ID="100", GITHUB_RUN_ATTEMPT="2", GITHUB_REF="refs/pull/12/merge",
           CI_HEAD_SHA="c"*40, CI_BASE_SHA="d"*40,
           GITHUB_WORKFLOW_REF="KleinPerkins/kp-pr-bot-canary/.github/workflows/ci.yml@refs/pull/12/merge",
           GITHUB_WORKFLOW="CI")


def needs():
    return {shard:{"result":"success", "outputs":{"receipt":json.dumps({
        "schema":"canary-ci-shard/v1", "shard":shard, "identity":ci.identity(ENV),
        "tests":paths, "result":"success"})}} for shard, paths in ci.SHARDS.items()}


class AggregateTests(unittest.TestCase):
    def test_complete_exact_run_passes(self):
        ci.validate_aggregate(needs(), ci.identity(ENV))

    def test_every_nonsuccess_result_fails(self):
        for shard in ci.SHARDS:
            for result in ("failure", "cancelled", "skipped", "neutral", "timed_out", "", None):
                with self.subTest(shard=shard, result=result):
                    data = needs()
                    data[shard]["result"] = result
                    with self.assertRaises(ci.ContractError):
                        ci.validate_aggregate(data, ci.identity(ENV))

    def test_missing_extra_duplicate_or_empty_evidence_fails(self):
        mutations = [None, {}, {"contract":needs()["contract"]}, dict(needs(), extra={})]
        for value in ("", "null", "[]", "{}", "not-json"):
            data = needs()
            data["contract"]["outputs"]["receipt"] = value
            mutations.append(data)
        for field in ("outputs", "result"):
            data = needs()
            del data["contract"][field]
            mutations.append(data)
        data = needs()
        data["ci-negative"] = data["contract"]
        mutations.append(data)
        for data in mutations:
            with self.subTest(data=data), self.assertRaises(ci.ContractError):
                ci.validate_aggregate(data, ci.identity(ENV))

    def test_each_stale_identity_field_fails(self):
        for key in ci.IDENTITY_KEYS:
            data = needs()
            receipt = json.loads(data["contract"]["outputs"]["receipt"])
            receipt["identity"][key] += "-stale"
            data["contract"]["outputs"]["receipt"] = json.dumps(receipt)
            with self.subTest(key=key), self.assertRaises(ci.ContractError):
                ci.validate_aggregate(data, ci.identity(ENV))

    def test_incomplete_receipt_suite_or_schema_fails(self):
        for key, value in (("tests", []), ("tests", ["echo passed"]), ("shard", "other"),
                           ("schema", "canary-ci-shard/v0"), ("result", "failure")):
            data = needs()
            receipt = json.loads(data["contract"]["outputs"]["receipt"])
            receipt[key] = value
            data["contract"]["outputs"]["receipt"] = json.dumps(receipt)
            with self.subTest(key=key, value=value), self.assertRaises(ci.ContractError):
                ci.validate_aggregate(data, ci.identity(ENV))


class SourceTests(unittest.TestCase):
    def test_reject_wrong_or_incomplete_environment(self):
        for key in ENV:
            data = dict(ENV)
            data[key] = ""
            with self.subTest(key=key), self.assertRaises(ci.ContractError):
                ci.identity(data)
        for key, value in (("GITHUB_EVENT_NAME", "pull_request_target"), ("GITHUB_REPOSITORY_ID", "1"),
                           ("GITHUB_REF", "refs/heads/main"), ("GITHUB_RUN_ATTEMPT", "0")):
            with self.subTest(key=key), self.assertRaises(ci.ContractError):
                ci.identity(dict(ENV, **{key:value}))

    def test_push_main_identity_and_rejections(self):
        env = dict(ENV, GITHUB_EVENT_NAME="push", GITHUB_REF="refs/heads/main", CI_HEAD_SHA="", CI_BASE_SHA="",
                   GITHUB_WORKFLOW_REF="KleinPerkins/kp-pr-bot-canary/.github/workflows/ci.yml@refs/heads/main")
        self.assertEqual(ci.identity(env)["event"], "push")
        for change in ({"GITHUB_REF":"refs/heads/other"}, {"CI_HEAD_SHA":"c"*40}):
            with self.subTest(change=change), self.assertRaises(ci.ContractError):
                ci.identity(dict(env, **change))

    def test_revision_and_merge_parents_must_match(self):
        expected = ci.identity(ENV)
        with mock.patch.object(ci.subprocess, "check_output", side_effect=["a"*40, "d"*40+" "+"c"*40]):
            ci.check_checkout(expected)
        for outputs in (["f"*40], ["a"*40, "c"*40+" "+"d"*40], ["a"*40, "d"*40]):
            with self.subTest(outputs=outputs), mock.patch.object(ci.subprocess, "check_output", side_effect=outputs):
                with self.assertRaises(ci.ContractError):
                    ci.check_checkout(expected)

    def test_real_git_merge_objects_bind_both_parents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*arguments, content=None):
                return subprocess.check_output(["git", "-C", str(root), *arguments],
                                               input=content, text=True, stderr=subprocess.DEVNULL).strip()
            git("init", "--quiet")
            tree = git("hash-object", "-t", "tree", "-w", "--stdin", content="")
            def commit(message, *parents):
                args = ["-c", "user.name=Canary Fixture", "-c", "user.email=fixture@example.invalid",
                        "commit-tree", tree]
                for parent in parents:
                    args += ["-p", parent]
                return git(*args, content=message+"\n")
            base = commit("base")
            head = commit("head", base)
            merge = commit("merge", base, head)
            git("update-ref", "HEAD", merge)
            expected = dict(ci.identity(ENV), revision=merge, base_sha=base, head_sha=head)
            with mock.patch.object(ci, "ROOT", root):
                ci.check_checkout(expected)
                for change in ({"revision":head}, {"base_sha":head}, {"head_sha":base}):
                    with self.subTest(change=change), self.assertRaises(ci.ContractError):
                        ci.check_checkout(dict(expected, **change))

    def test_failed_suite_cannot_emit_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/"output"
            with mock.patch.dict(ci.os.environ, dict(ENV, GITHUB_OUTPUT=str(output)), clear=True), \
                 mock.patch.object(ci, "check_checkout"), \
                 mock.patch.object(ci.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "test")):
                with self.assertRaises(subprocess.CalledProcessError):
                    ci.run_shard("contract")
            self.assertFalse(output.exists())

    def test_successful_suite_emits_bound_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/"output"
            with mock.patch.dict(ci.os.environ, dict(ENV, GITHUB_OUTPUT=str(output)), clear=True), \
                 mock.patch.object(ci, "check_checkout"), mock.patch.object(ci.subprocess, "run") as run:
                ci.run_shard("ci-negative")
                self.assertEqual(run.call_count, 1)
                self.assertEqual(run.call_args.args[0][-1], "tests/test_ci.py")
            value = json.loads(output.read_text().removeprefix("receipt="))
            self.assertEqual(value["identity"], ci.identity(ENV))
            self.assertEqual(value["tests"], ["tests/test_ci.py"])


class ContractMutationTests(unittest.TestCase):
    def test_workflow_rejects_unsafe_or_incomplete_mutations(self):
        original = contract.load_json(ROOT/".github/workflows/ci.yml")
        def mutation(path, value):
            data = copy.deepcopy(original)
            target = data
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            return data
        cases = [mutation(["permissions"], {"contents":"write"}),
                 mutation(["on"], {"pull_request_target":{}}),
                 mutation(["jobs", "ci-required", "if"], "success()"),
                 mutation(["jobs", "ci-required", "needs"], ["contract"]),
                 mutation(["jobs", "ci-required", "needs"], ["contract", "contract"]),
                 mutation(["jobs", "contract", "runs-on"], "self-hosted"),
                 mutation(["jobs", "contract", "steps"], [{"run":"echo success"}]),
                 mutation(["jobs", "contract", "steps", 0, "uses"], "actions/checkout@main"),
                 mutation(["jobs", "contract", "steps", 0, "with", "persist-credentials"], True),
                 mutation(["jobs", "contract", "steps", 0, "with", "ref"], "main"),
                 mutation(["jobs", "contract", "steps", 1, "env"], {"TOKEN":"${{ secrets.KEY }}"})]
        for data in cases:
            with self.subTest(data=data), self.assertRaises(AssertionError):
                contract.check_workflow(data)

    def test_executable_unknown_code_and_symlink_fixtures_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root/"harmless.txt"
            fixture.write_text("inert fixture\n")
            contract.check_surface(root)
            fixture.chmod(0o755)
            with self.assertRaisesRegex(AssertionError, "executable"):
                contract.check_surface(root)
            fixture.chmod(0o644)
            code = root/"unexpected.py"
            code.write_text("raise SystemExit(0)\n")
            with self.assertRaisesRegex(AssertionError, "unexpected code"):
                contract.check_surface(root)
            code.unlink()
            (root/"link.md").symlink_to(fixture)
            with self.assertRaisesRegex(AssertionError, "symlink"):
                contract.check_surface(root)

    def test_missing_and_overridden_ownership_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/".github").mkdir()
            path = root/".github/CODEOWNERS"
            path.write_text("\n".join(contract.OWNER_RULES))
            contract.check_ownership(root)
            path.write_text("\n".join(contract.OWNER_RULES - {"/scripts/** @KleinPerkins"}))
            with self.assertRaisesRegex(AssertionError, "missing protected ownership"):
                contract.check_ownership(root)
            path.write_text("\n".join(contract.OWNER_RULES)+"\n/scripts/** @someone-else\n")
            with self.assertRaisesRegex(AssertionError, "override"):
                contract.check_ownership(root)

    def test_policy_symlink_and_immutable_identity_drift_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/".github").mkdir()
            path = root/".github/ci-contract.json"
            data = contract.load_json(ROOT/".github/ci-contract.json")
            data["repository"]["id"] = 1
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(AssertionError, "repository identity"):
                contract.check_policy(root)
            path.unlink()
            path.symlink_to(ROOT/".github/ci-contract.json")
            with self.assertRaisesRegex(AssertionError, "non-symlink"):
                contract.check_policy(root)

    def test_workflow_directory_is_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/".github/workflows").mkdir(parents=True)
            (root/".github/workflows/unreviewed.yml").write_text("name: surprise\n")
            with self.assertRaisesRegex(AssertionError, "unexpected workflow"):
                contract.check_surface(root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
