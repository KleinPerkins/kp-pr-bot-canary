# Local review capture (Q16 canary)

`scripts/local_review.py` captures one fresh Codex CLI review using an explicitly
enrolled existing ChatGPT account. This is **operational trust in the local
adapter and authenticated GitHub sender**, accepted in Q16. It is not a
provider-signed attestation. Someone with the same local/GitHub privileges can
fabricate a receipt; this adapter does not claim resistance to that forgery.

The adapter never publishes a PR, comment, Check, review, approval, or merge.
The reviewer App remains responsible for remote repository identity, current
head/base/policy, origin enrollment, required checks, finding admission and merge.
Source delivery alone does not authorize activation or qualify either account.

## Enrollment and immutable input

Keep enrollment and receipts private. The owner enrolls exactly these non-secret
fields outside the candidate repository:

```json
{
  "id": "opaque-owner-assigned-enrollment",
  "origin_account": "opaque-origin-account",
  "email": "owner@example.invalid",
  "workspace": "owner-declared-workspace",
  "cli_version": "codex-cli 0.148.0",
  "credential_store": "keyring",
  "codex_home": "/absolute/private/codex-profile"
}
```

`codex_home` is the explicit private absolute configuration profile directory.
It must equal the effective process `CODEX_HOME` (or the standard default when
unset); the path is never emitted in the receipt. An isolated personal profile
may be selected only for that process, without changing the work default.
`credential_store` is `keyring` or `file`, never credential material. Both
`account/read` and the review use the same explicit selector. `account/read`
currently exposes email/type, not a stable account ID or workspace identity.
The adapter requires an exact email match and ChatGPT login, strips API-key and
base-URL environment overrides, and refuses API-key billing. Workspace and origin
labels are owner declarations: nonempty is checked locally; the App must match
the enrolled ID and origin against its owner-controlled registry. There is no
claim that CLI identity equals desktop identity without explicit enrollment.
Wrong/missing enrollment or CLI-version drift requires owner requalification.

The request has exactly these fields (full lowercase commit/hash values):

```json
{
  "repository": "owner/repository",
  "repository_id": 123,
  "head_sha": "<40 hex>",
  "base_sha": "<40 hex>",
  "merge_base_sha": "<40 hex>",
  "diff_sha256": "<64 hex>",
  "policy_sha256": "<64 hex>",
  "origin_account": "opaque-origin-account"
}
```

The adapter requires a clean local checkout at exactly `head_sha`, an exact
GitHub origin remote match, and the expected merge base. `repository_id` is a
positive integer supplied by the owner; the App verifies it against GitHub.
Local Git inspection uses a minimal environment without inherited Git overrides,
system/global configuration, credentials or runtime account state. It disables
fsmonitor, hooks, external diff/textconv and every configured clean/smudge/process
filter before examining the working tree. Local configuration is parsed as data
to preserve repository/worktree identity and neutralize named filter drivers.
Submodule traversal is disabled; a candidate index containing a Git submodule is
refused because this bounded adapter cannot review its separate contents.
The diff digest hashes the exact UTF-8 bytes emitted by:

```sh
git diff --no-ext-diff --no-textconv --no-color --binary BASE...HEAD --
```

This is three-dot comparison from `merge-base(BASE, HEAD)` to HEAD, **not** a
base-to-head two-dot diff. The policy digest hashes the supplied trusted policy
file's raw bytes. Policy must be owner-frozen; candidate policy is not authority.
The adapter reads no candidate instruction files. Binary/non-UTF8/empty changes
and input over 1 MiB fail closed; they need a separately qualified review route.

## Launch and capture

The active authoring agent automatically coordinates this step as part of PR
delivery; the operator does not run a review command or review the code. It first
binds the PR-creation account to its private owner-enrolled profile, freezes the
current head/base/trusted policy, and invokes the qualified route. After any
relevant tuple change it captures a new review and resolves findings before
creating the PR through the [account-bound creation adapter](pr-creation.md)
and publishing an unedited review receipt for the App. The creation adapter
records the signed-in account around its own create operation, independently of
this review. An existing PR must retain that creation binding; a later receipt
cannot select a new account. The command below is the coordinator's
interface, not an operator handoff. An unknown origin or unavailable matching
runtime remains blocked until that same-account coordinator can resume. This
source introduces no always-on review daemon or GitHub self-hosted runner.

```sh
python3 scripts/local_review.py \
  --repo /absolute/clean/checkout \
  --request /private/request.json \
  --policy /private/frozen-policy.txt \
  --enrollment /private/enrollment.json \
  --output /private/new-receipt.json
```

The executable defaults to `codex`; `--cli` may name the enrolled installation.
The reviewer starts with `codex exec`, never resume/fork, in a new temporary
empty directory outside the candidate. It ignores user configuration and rules,
disables project instruction loading and plugins, supplies frozen model
instructions from this adapter, selects a read-only sandbox and passes the
candidate diff only as labeled untrusted JSON data. Candidate code is never
executed by the adapter. Tool-use output is rejected. No author conversation,
custom prompt, author verdict, report file, or preexisting review is accepted as
an input. The strict JSON response schema requires explicit complete/incomplete
coverage, verdict, all findings and unresolved finding IDs. Unknown coverage is
incomplete; it cannot produce a pass. Review scope is all supplied changed lines,
not a whole-repository verification claim.

Admission requires successful process exit, exactly one new thread and turn,
definitive `turn.completed`, one complete agent report matching the direct last
message, a valid closed report schema, and no unknown runtime error or tool items. CLI 0.148.0 serializes configuration
warnings as `item.completed` with `type: error`; the two exact observed startup
messages frozen in `STARTUP_NOTICES` are recorded as hashes in `runtime.startup_notice_sha256`; full notice text stays in private runtime evidence.
They concern unknown `ultrafast_mode` speed policy and the stricter managed
approval fallback to `UnlessTrusted`. All other error items, top-level errors,
failed turns and unknown event types are fatal; tool items are rejected even
when only started/updated. The App must bind its allowed notice hashes to the
qualified producer enrollment. The
adapter rechecks account and the local tuple after completion. Output/time bounds
fail closed; child process groups are terminated/reaped and temporary files are
removed on failure or completion. No partial streaming result is a receipt.

A `g1-local-review/v1` receipt contains the exact tuple, opaque enrollment/origin
IDs, frozen instructions hash, runtime CLI version/credential-store/thread ID,
start/completion UTC times, direct report and digests. CLI event JSON does not
expose a turn ID, so `runtime.turn_id` is explicitly null. `report_sha256` hashes
only the `review` object serialized as sorted-key compact JSON, UTF-8 with
`ensure_ascii=False`. `event_stream_sha256` hashes captured raw stdout bytes.
Neither hash establishes provider authenticity. The email/workspace text never
appears in the receipt; report text must still be inspected for sensitive content
before any authorized publication. Pre-PR reviews have no PR number. The App
binds their immutable tuple to the subsequently created PR and frozen origin.

All findings remain unresolved in the captured report. A pass requires complete
coverage and zero findings. Corrections require a new candidate tuple and fresh
review; editing a receipt cannot resolve a finding. Failed/incomplete reports
are useful evidence but must never satisfy the App's passing gate. The App must
also reject stale base/head/policy, changed receipt comments, wrong senders,
wrong enrollment/origin and replay to a different PR/repository.

## Verification

Do not use keyring and file stores under one home as durable account isolation.
In Codex 0.148.0 a keyring save/refresh deletes the file fallback; a personal
file login could disappear during a work-account refresh. Separate account
runtime qualification remains an owner responsibility.

Run `python3 -B -m unittest discover -s tests -p test_local_review.py -v`.
Tests exercise real temporary Git histories plus malformed/incomplete streams,
account and origin mismatch, missing workspace declaration, CLI drift, dirty or
stale tuples, policy mismatch, unresolved findings, subprocess limits and
candidate instruction injection remaining data. Runtime qualification must also
record actual `account/read` and a harmless fresh review for each enrolled
account. Mocked fixtures do not establish that qualification. Auth/config
failures leave the gate blocked; no login, account switching or API billing is
performed automatically.
