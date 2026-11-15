# G1 staged GitHub delivery

This is source for the accepted G1 successor. It does not report that publication,
Actions, enrollment, App credentials, controls, or live native merging are qualified.
The staged policy contains separately qualified opaque work and personal producers.
Its policy admission switch is enabled, but repository `REVIEWER_APP_ENABLED` must
remain OFF until the root verifies the accepted qualification and cutover gates.
This source state alone does not authorize writes. Workflow dispatch is always read-only. Automated writes additionally require the repository variable
`REVIEWER_APP_ENABLED` to equal `true`, enabled trusted enrollment policy, and every
live gate. Only existing App **4217367** approves a head and arms native **SQUASH**.
No agent/manual merge command is part of this helper.

## Trust and publication

Q16 explicitly accepts an owner-enrolled local review adapter and authenticated
GitHub sender as operational trust. This does **not** prevent a principal with the
same local/GitHub privileges from fabricating, deleting, or replacing receipts.
Hashes bind bytes; they are not provider signatures or independent attestations.
Unknown GitHub senders and producers fail admission. Account emails and workspace
identity enrollment evidence stay private. Only opaque origin/enrollment identifiers,
qualified runtime version/store, frozen instruction and startup-notice hashes, and the owner GitHub ID
belong in the public producer policy. Public receipt text needs exposure review too.

The independent review is a fresh completed runtime thread launched by the trusted
local adapter with frozen instructions and candidate isolation. The gate validates
its complete no-findings report, runtime and exact tuple. An App policy approval
alone is not substantive code review. No human-review requirement is inferred for
all protected paths: the accepted owner-author policy admits owner ID 49759187;
other authors, forks and base branches are rejected. Changes to protected policy
still pass the accepted independent originating-account review and exact source gates.

## Receipt interface

Publish one unedited PR comment containing the exact marker followed immediately by
JSON (no code fence):

```text
<!-- g1-review-receipt:v1 -->
{"schema":"g1-local-review/v1", ...}
```

`local_review.py` owns the receipt schema. Required tuple fields are `repository`,
`repository_id`, `head_sha`, `base_sha`, `merge_base_sha`, `diff_sha256`,
`policy_sha256`, and `origin_account`. The policy digest is SHA-256 of the **raw
trusted `.github/review-enrollments.json` bytes**. The diff digest is SHA-256 of
`git diff --no-ext-diff --no-textconv --binary --no-color BASE...HEAD --` bytes;
Git objects are fetched to a temporary bare repository, never checked out or run.
The report digest is SHA-256 of canonical JSON for the `review` object only:
UTF-8, sorted keys, compact separators, `ensure_ascii=False`.

The gate checks `reviewer_enrollment_id`, matching `reviewer_origin_account`,
`workspace_binding=owner-declared-enrollment`, frozen `instructions_sha256`,
qualified `runtime.cli_version` and `runtime.credential_store`, only explicitly
enrolled `allowed_startup_notice_sha256` (unknown hashes reject). Public runtime
`startup_notice_sha256` contains SHA-256 digests only; raw notices reject and private
account, workspace, path and configuration text stays in private qualification evidence, a nonempty fresh
thread identifier, `runtime.status=completed`, and direct event-stream digest.
Start/completion must be ordered, not future-dated, and within 24 hours. Review
must have `verdict=pass`, `coverage=complete`, a nonempty summary, and no findings
or unresolved findings. Failed/incomplete latest receipts supersede old passing
ones; they cannot silently fall back to an older pass.

The trusted creation adapter captures the enrolled account before and after its
own GitHub PR-create operation, then publishes a separate `g1-pr-origin/v1`
record. See [PR creation](pr-creation.md). Exactly one unedited owner creation
record must match this PR's numeric/node IDs, server creation time, repository,
author and creation nonce in its body. The enrolled helper hashes and account
runtime must match; creation and posting must complete within ten minutes.
Missing, duplicate, malformed, edited or conflicting creation evidence blocks
admission. Review receipts never establish or change the originating account.
Every receipt must match the separately frozen creation account; a first review
from another enabled account is rejected too. Later receipts refresh the current
head/base/policy tuple without changing origin. Unknown/pre-existing or browser-
created PRs without this qualified record remain blocked. Q16 operational trust
still cannot protect against an owner fabricating or deleting comment history.
A receipt is
bounded to 60,000 bytes; Git diff/output to 5,000,000 bytes; pagination is bounded
and refuses overflow rather than truncating. Candidate Git inspection strips the
inherited environment (including App credentials), configuration, hooks, attributes,
credential helpers and prompts; disables external diff/textconv; and sets CPU,
file-size and wall-time limits. The fetch is read-only and has no submodule update.
Ancestry fetches deepen from 256 through at most 4,096 commits when necessary to
find the common ancestor. Each command retains its CPU, file-size and wall-time
limits; missing ancestry at the final bound refuses admission without guessing.
The coordinator must diagnose that unsupported history before delivery.

Producer entries are owner-qualified records with these fields:

```json
{
  "id": "opaque-enrollment-id",
  "enabled": true,
  "origin_account": "opaque-origin-id",
  "github_user_id": 49759187,
  "instructions_sha256": "qualified-frozen-instruction-sha256",
  "cli_version": "qualified-version",
  "credential_store": "keyring",
  "allowed_startup_notice_sha256": [],
  "creation_adapter_sha256": "qualified-create-review-pr-source-sha256",
  "capture_adapter_sha256": "qualified-local-review-source-sha256"
}
```

This example is not an enrollment or instruction to enable the shipped policy.

## CI and control binding

The ruleset-list, ruleset-detail and branch-rules GET endpoints require Metadata
read permission, including for GitHub App installation tokens; they do not require
Administration read. GitHub documents this in [REST repository rules](https://docs.github.com/en/rest/repos/rules).
Metadata read is inherent in the installation. Administration is therefore not
requested. Rule-suite evaluation-history endpoints are different and are not used.
Read access can redact bypass actors; the owner-visible preimage remains a separate
cutover check as described below.

Repository merge settings are read through one fixed GraphQL repository query.
GitHub omits the corresponding REST fields for read-only App credentials; absence
must not be interpreted as a disabled setting. The query checks the immutable
repository identity and requires all four boolean settings. Missing fields, GraphQL
errors, disagreement with visible REST fields, or disallowed settings reject. The
read-only API permits only this exact query body as POST; arbitrary GraphQL queries
and mutations remain refused. This requires no additional App permissions.

Native workflow **CI** supplies `contract`, `ci-negative`, `local-review`, `app-gate`, and `ci-required` from
GitHub Actions producer **15368**. The latest PR run and latest attempt must be
completed and successful; all five jobs must succeed, including the fail-closed
aggregate. Every check must match the workflow run's check suite and head/merge
revision. The run's PR head/base must equal the current PR tuple. The current
synthetic merge commit must have exactly `[current main, current PR head]` as
parents. The CI shards themselves assert checkout/ref/event/source identity and parent
ordering. After validating every shard receipt, the aggregate emits exactly one
`CANARY_CI_AGGREGATE_V1 ` JSON log record with schema `canary-ci-aggregate/v1`,
its complete `identity` and `result=success`. The App reads that exact aggregate
job's bounded log and compares every field to the current merge SHA, base/head,
run and attempt. Missing/duplicate/malformed logs or an old tested merge revision
fail admission even if GitHub's linked PR metadata has changed. Redirected log
downloads strip authorization headers. No artifacts are downloaded or executed.

Effective main rules must require strict `ci-required@15368`, at least one approval,
stale-approval dismissal, resolved conversations, squash-only PR merging, linear history, no deletion
and no non-fast-forward updates. Repository metadata must allow squash/auto-merge and
disallow merge commits and rebase. All contributing rulesets must be active. Where bypass fields are visible, exactly one
established `RepositoryRole` actor 5 with `pull_request` bypass is allowlisted
for merge controls; empty or duplicate entries reject. A distinct ruleset whose declared and effective rules are exactly
`deletion` and `non_fast_forward` preserves actor 5 with `always` bypass for that
history-only ruleset. This does not permit `always` on merge, CI or review controls.
Broader or App bypass is rejected. App reads can redact that field: the result
reports this as `redacted-or-unavailable`, never observed empty. Root owner-authenticated
GETs must qualify the exact preserved bypass policy during cutover. This helper
never exercises that owner authority. Missing API fields,
inaccessible rules, pagination overflow, unknown mergeability and stale source fail
closed. The helper rechecks all gates before approval and again before arming.

The enable-auto-merge mutation sends the reviewed current head as `expectedHeadOid`
in its actual `EnablePullRequestAutoMergeInput`; GitHub rejects a head mismatch.
GraphQL errors or missing squash confirmation reject without retrying or reporting
`armed`. See [GitHub's input contract](https://docs.github.com/en/graphql/reference/pulls#enablepullrequestautomergeinput).
The mutation has no expected-base compare-and-swap parameter.
A base can move after the last read. The final protection therefore depends on live
native strict required checks and stale-approval behavior. Mocked race tests only
prove local rejection when a changed snapshot is observed. They do not establish
GitHub's race behavior or a completed merge; the live G1 base-race canary remains a
mandatory root qualification. The helper reports `armed`, never `merged`.

## Bootstrap and cutover

1. Preserve exact source/settings/control preimages and clear actual public exposure.
   Review the initial CI/App/capture candidate independently under its originating
   account. The initial source bootstrap keeps both write switches off and producers
   empty. Qualified enrollment is a separate source admission.
2. After the accepted publication gate, enable authorized hosted candidate PR CI
   while retaining legacy blockers. Prove current head/base/merge checkout and
   fail-closed negative canaries on the actual candidate.
3. If the retired controller blocks initial source admission, present the exact
   reviewed PR/head/base/settings to the human owner/admin under the accepted
   PR-only route. This helper never performs that bypass.
4. Verify initial merged-main CI. Add strict successor check/review/history/squash
   controls while retaining both legacy blockers. Install the existing App for this
   repository and provision its credential with `REVIEWER_APP_ENABLED` OFF. Preserve
   the accepted per-ruleset owner exceptions. Credential identity/scope probes do
   not establish full trusted-main readiness; complete that gate in the selected
   route below. Provisioning and repository controls remain root-owned operations.
5. Select exactly one first-enrollment route. An empty trusted registry cannot
   admit its own enrollment PR; neither route grants agent merge/bypass authority.

   **Ordinary route — qualify before enrollment.** Run the read-only App qualification
   described below on existing main and require success. Qualify each account/runtime,
   then prepare only its opaque producer record in independently reviewed source.
   Complete the account-bound PR creation, fresh originating-account review and hosted
   CI. Request exact owner/admin enrollment admission while the repository writer
   stays OFF and legacy blockers remain. Verify admitted-main CI and rerun read-only
   App readiness on that new revision. Proceed to step 6 only after both pass.

   **Repair route — requires explicit one-time owner acceptance.** If existing-main
   readiness fails because its verifier needs a source repair, prepare the exact
   repair and qualified enrollment together. Complete independent originating-account
   review, account-bound PR creation, hosted CI and prospective read-only credential/
   control probes. The exact owner/admin request must disclose that trusted-main
   readiness has not passed and explicitly seek this sequence adjustment: admit the
   combined repair and policy enrollment first, with source policy `enabled=true`
   but repository writer OFF and both legacy blockers retained. Without that specific
   acceptance, do not admit the candidate. After accepted admission, immediately
   verify the new-main CI and run the read-only App qualification below on the newly
   admitted revision. If either fails, keep the writer OFF and blockers retained;
   repair the bootstrap without proceeding to step 6. A prospective probe is not
   trusted-main qualification. This route is bounded to completing the initial G1
   bootstrap and is not a recurring bypass or human technical-review lane.

6. Both routes join here only after qualified producer source is on main, new-main
   CI passes, and actual trusted-main App readiness passes. With writer still OFF,
   qualify genuine enrolled-receipt acceptance and the intended rejection cases
   against the current raw-main policy. Every policy edit invalidates previous
   policy-bound receipts. Never use candidate policy or bootstrap-packet review as
   ordinary trusted-main admission evidence.
7. Only after these successor gates pass, apply the accepted exact control cutover
   removing retired blockers. Enable the repository writer only at that root gate;
   source policy admission alone does not enable writes. New authenticated receipts
   and successful CI workflow completions wake the gate. Ambiguous workflow-run PR
   bindings fail closed and require diagnosis.
8. Prove ordinary exact-head App-only approval/native squash plus stale head/base,
   wrong-origin/sender, failed/incomplete review, missing/failed CI, control drift and
   live base-race negatives. Verify merged revision/default-branch ancestry and all
   required gates; enabled auto-merge alone is not delivery.

### Read-only App qualification used by either route

Keep `REVIEWER_APP_ENABLED` OFF, set `REVIEWER_APP_QUALIFY=true`, and dispatch
**Reviewer App**, mode `app`, on the main revision specified by the selected route.
No PR number or enrolled receipt is needed. The trusted checkout must equal
`github.workflow_sha` and live main. The pinned create-token action requests
App4217367 with read-only contents/PR permissions and exactly this repository;
the helper receives token, slug and installation-ID outputs directly. It checks
bot `chaos-scheduler-automerge[bot]` (299927791), a live installation credential
and exactly one accessible repository. Bot metadata alone is not issuer proof:
the fixed App ID and pinned trusted mint action bind the credential issuer.
No public App lookup is required for this private App. The qualification client
permits only reads, including the fixed GraphQL query described above.

Qualification verifies effective controls through that credential and latest
successful current-main push CI: all five job producers and the aggregate log's
exact current revision/run/attempt. Main push receipts use `event=push`,
`ref=refs/heads/main`, and empty PR head/base strings. It rechecks main and controls
for drift. Both historical checks from producer4274739 stay required throughout
this qualification. Preserve owner-visible bypass preimages separately when the
App response redacts them. Mint/revocation are credential lifecycle operations;
no PR, control, enrollment, approval or auto-merge mutation occurs. Verify cleanup
before continuing. Mode `receipt` with a PR number is the separate ordinary
CI-token-only receipt snapshot used after both routes join at step 6.

Rollback disables `REVIEWER_APP_ENABLED`, `REVIEWER_APP_QUALIFY` and policy admission, preserving existing
protections and evidence. Do not weaken checks or use this helper to manually merge.
The GitHub token action scopes credentials to this repository and revokes its token
in its cleanup hook. A failed revoke requires root diagnosis; mocked tests do not
qualify token lifecycle. No service, scheduler, signer, billing change or new App is
introduced.

## Local checks

`python3 -I -B -m unittest discover -s tests -p test_reviewer_app.py -v` exercises
receipt drift/failure, origin freezing, sender filtering, pagination, effective
controls, CI identity/attempt/failure and before/after-approval observed races without
network or credentials. The JSON-compatible YAML Reviewer App workflow is parsed
with the standard library. Structural contracts and adversarial mutations cover
trusted checkout, token permissions/scope, trigger and write guards, pinned actions,
read-only dispatch, and the closed set of permitted privileged execution steps.
Integration must also run the successor repository contract,
all four CI shards and their aggregate after the separate source commits are combined.
