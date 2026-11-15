# Account-bound PR creation

The authoring agent coordinates a fresh passing review and creates the ready PR
through `scripts/create_review_pr.py`. The helper captures the enrolled ChatGPT
account around its own GitHub create operation. That independent creation
binding fixes the originating account before a later review receipt is admitted;
the first review comment cannot select or replace the account.

This is Q16 operational trust in an owner-enrolled local adapter and the
authenticated GitHub owner, not provider attestation, signing, or same-user
anti-forgery. An actor controlling that account and trusted local files can forge
equivalent records. Workspace/profile mapping remains owner-declared. Only
qualified helper hashes, CLI version, credential store, and account enrollment
may be admitted by the separate App policy. Source implementation does not
enable enrollment, qualify a runtime, grant publication authority, or enable the
App. No human technical-review step is introduced.

## Coordinator inputs and invocation

Complete [the independent local review](local-review.md) first. The private
request, frozen trusted policy, enrollment, and captured receipt must describe
the same clean candidate head, current main base, merge base, diff, policy, and
origin account. A complete report with zero findings, matching report and
instruction hashes, completed direct event capture, qualified runtime notices,
and timestamps within 24 hours is required. An author-provided verdict alone
cannot satisfy these checks. The receipt is not edited or published by this
helper.

All input files must be regular, owned by the current user, inaccessible to
group/other users, and at most 2 MiB. The output and journal must have distinct,
unused names in an existing private directory (mode 0700); the helper creates
them exclusively with mode 0600. Keep them outside the candidate worktree so its
cleanliness remains meaningful. Title and body are private UTF-8 files, not
shell strings. The body cannot supply a creation or origin marker.

```sh
python3 -I -B scripts/create_review_pr.py \
  --repo /absolute/clean/checkout \
  --request /private/creation/request.json \
  --policy /private/creation/frozen-policy.txt \
  --enrollment /private/creation/enrollment.json \
  --review /private/creation/passing-review.json \
  --title /private/creation/title.txt \
  --body /private/creation/body.md \
  --output /private/creation/new-origin.json \
  --journal /private/creation/new-journal.json
```

`--cli` selects the enrolled Codex installation (default `codex`). The profile,
ChatGPT email, credential store, and exact CLI version must match the private
enrollment. No new login, credential export, billing service, browser action, or
candidate execution occurs. The helper reuses the capture adapter's safe Git
inspection, bounded subprocesses, account/read protocol, and process cleanup.
It calls the fixed `/opt/homebrew/bin/gh` directly, uses JSON on stdin and a
30-second bound per GitHub call, fixes the hostname to github.com, and never
uses a shell or retries a request. The existing GitHub authentication must
resolve to numeric user 49759187, type User.

The target is only public `KleinPerkins/kp-pr-bot-canary`, repository 1297059298,
default branch `main`. The current non-main local branch must be pushed first.
Remote head and main refs must match the frozen tuple, and there must be no
existing open PR from that branch into main. Unknown or malformed lookup
results fail closed. The helper creates a non-draft PR using a generated UUID
and the exact body marker `<!-- g1-pr-creation:UUID -->`. It verifies returned
and subsequently fetched PR number, node ID, repository IDs, author, head/base,
body nonce, state, URL, and GitHub creation time. It checks the local tuple,
account, and CLI again after creation.

## Origin record and failure handling

After these checks, the helper publishes an owner issue comment beginning
`<!-- g1-pr-origin:v1 -->` followed by compact, sorted-key JSON. The closed
`g1-pr-origin/v1` record includes the nonce, immutable repository/PR/user
identifiers, enrolled opaque account and enrollment IDs, initial head/base,
GitHub creation time, local start/completion times, checked runtime, and raw
SHA-256 digests of both helper sources. It includes no email, home or workspace
name, credential, or raw account response. Creation and origin posting must fit
within ten minutes; one second of slack accommodates GitHub timestamp precision.
The private final output contains that same canonical JSON, followed by one
newline. Successful stdout contains only the PR URL and comment ID, one per line.

This initial canary conservatively refuses origin publication if any comment
already exists, including an unrelated bot comment. That is a helper limitation,
not an App requirement that unrelated comments undermine origin integrity.
The App independently requires exactly one unedited owner origin record and
checks the creation nonce, current PR identity, time bounds, and enrolled helper
hashes. Later reviews must retain the fixed creator account.

The journal records the nonce and start time before any network operation and
records the create-attempted/comment-attempted phase before each write. A
returned PR's bounded identifiers are preserved immediately. Existing output
or journal files always stop another invocation, even if the output is empty.
Failures retain `incomplete-no-retry` and the previous phase. Do not delete those
files to retry, silently recreate a PR, publish a replacement origin, or infer
that an API timeout means the operation did not happen.

A failed/acknowledgement-lost comment POST or later local output failure can
leave a valid origin comment on GitHub despite incomplete private state. The
helper cannot undo that distributed ambiguity. The coordinator must withhold
the review receipt and inspect the existing PR, nonce, comments, and private
journal read-only before any separately authorized recovery. An incomplete
local journal is not evidence of no remote publication. No blind retry is
permitted. The helper never posts a review, approves, enables auto-merge, merges,
edits the report, or enables App admission.

## Verification

Run `python3 -I -B -m unittest discover -s tests -p test_create_review_pr.py -v`.
Tests use mocked account and GitHub calls only: exact public bytes, private
state, identity/account/CLI/profile/tuple mismatch, malformed or stale reviews,
existing or unknown PR/comment state, partial network failures, refusal to
retry, and the actual helper-produced origin consumed by the App. The seam test
also proves that a wrong-account first review cannot displace the creation
account. No real API writes or credential operations are part of the tests.
