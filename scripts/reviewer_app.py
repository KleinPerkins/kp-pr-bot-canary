#!/usr/bin/env python3
"""Trusted-default-branch G1 gate. Candidate Git objects are data, never executed.

Q16 trusts enrolled local capture operationally; receipts are not anti-forgery
attestations against a principal holding the same local/GitHub privileges.
"""
from __future__ import annotations
import argparse
import base64
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request

REPOSITORY = 'KleinPerkins/kp-pr-bot-canary'
REPOSITORY_ID = 1297059298
APP_ID = 4217367
OWNER_ID = 49759187
CI_APP_ID = 15368
MARKER = '<!-- g1-review-receipt:v1 -->\n'
MAX_RECEIPT = 60000
MAX_DIFF = 5000000
ROOT = Path(__file__).resolve().parents[1]

class Rejected(RuntimeError):
    pass

def require(condition, message):
    if not condition:
        raise Rejected(message)

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()

def digest(value):
    return hashlib.sha256(value).hexdigest()

def timestamp(value):
    result = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'timestamp has no timezone')
    return result

class API:
    def __init__(self, token, writable=False):
        require(bool(token), 'missing API credential')
        self.token, self.writable = token, writable
    def request(self, path, method='GET', data=None):
        require(method == 'GET' or self.writable, 'read-only API cannot mutate')
        require(path.startswith('/') and not path.startswith('//'), 'invalid API path')
        headers = {'Authorization': 'Bearer ' + self.token, 'Accept': 'application/vnd.github+json',
                   'X-GitHub-Api-Version': '2022-11-28'}
        req = urllib.request.Request('https://api.github.com' + path, headers=headers,
                                     method=method, data=None if data is None else canonical(data))
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                raw = response.read(8000001)
                require(len(raw) <= 8000000, 'API response exceeds bound')
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            raise Rejected('GitHub API refused request: HTTP ' + str(error.code)) from None
    def job_log(self, job_id):
        require(type(job_id) is int and job_id > 0, 'invalid log job ID')
        class LogRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                require(urllib.parse.urlsplit(newurl).scheme == 'https', 'unsafe log redirect')
                redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
                if redirected is not None:
                    redirected.remove_header('Authorization')
                return redirected
        request = urllib.request.Request('https://api.github.com/repos/' + REPOSITORY +
            '/actions/jobs/' + str(job_id) + '/logs', headers={
                'Authorization': 'Bearer ' + self.token, 'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28'})
        try:
            with urllib.request.build_opener(LogRedirect()).open(request, timeout=30) as response:
                raw = response.read(8000001)
                require(len(raw) <= 8000000, 'aggregate log exceeds bound')
                return raw.decode('utf-8')
        except urllib.error.HTTPError as error:
            raise Rejected('aggregate log unavailable: HTTP ' + str(error.code)) from None
    def pages(self, path, key=None):
        rows = []
        for page in range(1, 101):
            data = self.request(path + ('&' if '?' in path else '?') + f'per_page=100&page={page}')
            batch = data[key] if key else data
            require(isinstance(batch, list), 'invalid pagination payload')
            rows.extend(batch)
            if len(batch) < 100:
                return rows
        raise Rejected('pagination bound exhausted')

def validate_controls(repo, rules, rulesets):
    require(repo['id'] == REPOSITORY_ID and repo['full_name'] == REPOSITORY, 'repository mismatch')
    require(repo['default_branch'] == 'main' and not repo.get('archived') and not repo.get('private'), 'repository posture')
    require(repo.get('allow_squash_merge') is True and repo.get('allow_merge_commit') is False
            and repo.get('allow_rebase_merge') is False and repo.get('allow_auto_merge') is True, 'merge methods')
    by_type = {}
    for rule in rules:
        by_type.setdefault(rule['type'], []).append(rule.get('parameters', {}))
    required = by_type.get('required_status_checks', [])
    require(any(r.get('strict_required_status_checks_policy') is True and
                any(c.get('context') == 'ci-required' and c.get('integration_id') == CI_APP_ID
                    for c in r.get('required_status_checks', [])) for r in required), 'strict CI15368 required')
    require(any(r.get('required_approving_review_count', 0) >= 1 and r.get('dismiss_stale_reviews_on_push') is True
                and r.get('required_review_thread_resolution') is True and r.get('allowed_merge_methods') == ['squash']
                for r in by_type.get('pull_request', [])), 'review controls missing')
    require(all(name in by_type for name in ('required_linear_history', 'deletion', 'non_fast_forward')), 'history protection missing')
    # Preserve the established owner/admin PR-only exception. App-scoped reads
    # may redact bypass_actors; absence is unknown, never evidence of emptiness.
    source_ids = {r['ruleset_id'] for r in rules}
    require(source_ids and source_ids <= {r['id'] for r in rulesets}, 'rule source unavailable')
    for rule in rulesets:
        if rule['id'] in source_ids:
            require(rule.get('enforcement') == 'active', 'protection enforcement gap')
            if 'bypass_actors' in rule:
                allowed = {'actor_id': 5, 'actor_type': 'RepositoryRole', 'bypass_mode': 'pull_request'}
                require(isinstance(rule['bypass_actors'], list) and all(actor == allowed for actor in rule['bypass_actors']),
                        'unexpected/broadened bypass actor')

def validate_receipt(receipt, producer, current, policy_hash, now):
    require(receipt.get('schema') == 'g1-local-review/v1' and receipt.get('trust_model') == 'q16-operational-local', 'receipt schema/trust')
    require(receipt.get('reviewer_enrollment_id') == producer['id'] and producer.get('enabled') is True, 'producer not enrolled')
    require(receipt['tuple'] == dict(current, origin_account=producer['origin_account']), 'receipt tuple drift')
    require(current['policy_sha256'] == policy_hash, 'policy drift')
    require(receipt.get('reviewer_origin_account') == producer['origin_account'], 'review origin mismatch')
    require(receipt.get('workspace_binding') == 'owner-declared-enrollment', 'workspace binding missing')
    require(receipt.get('instructions_sha256') == producer['instructions_sha256'], 'review instruction drift')
    runtime = receipt['runtime']
    require(runtime.get('status') == 'completed' and isinstance(runtime.get('thread_id'), str)
            and len(runtime['thread_id']) >= 8 and runtime.get('cli_version') == producer['cli_version']
            and runtime.get('credential_store') == producer['credential_store'], 'review runtime incomplete')
    require(re.fullmatch('[0-9a-f]{64}', runtime.get('event_stream_sha256', '')) is not None, 'missing direct capture digest')
    notices = runtime.get('startup_notices', [])
    allowed_notices = producer.get('allowed_startup_notices', [])
    require(isinstance(notices, list) and isinstance(allowed_notices, list)
            and all(isinstance(n, str) and n in allowed_notices for n in notices), 'unqualified runtime notice')
    started, completed = timestamp(receipt['started_at']), timestamp(receipt['completed_at'])
    require(started <= completed <= now and now - started <= dt.timedelta(hours=24), 'stale/future review')
    review = receipt['review']
    require(review.get('verdict') == 'pass' and review.get('coverage') == 'complete'
            and review.get('findings') == [] and review.get('unresolved_findings') == []
            and isinstance(review.get('summary'), str) and review['summary'].strip(), 'review incomplete or findings')
    require(receipt.get('report_sha256') == digest(canonical(review)), 'report digest mismatch')

def choose_receipt(comments, enrollments, current, policy_hash, now):
    producers = {p['id']: p for p in enrollments['producers']}
    eligible = []
    for comment in comments:
        body = comment.get('body', '')
        if not body.startswith(MARKER):
            continue
        # Unknown senders cannot bind or refresh origin.
        sender = comment.get('user', {})
        if sender.get('id') != OWNER_ID or sender.get('type') != 'User':
            continue
        require(len(body.encode()) <= MAX_RECEIPT, 'receipt exceeds bound')
        require(comment['created_at'] == comment['updated_at'], 'edited receipt cannot establish origin')
        try:
            receipt = json.loads(body[len(MARKER):])
        except ValueError:
            raise Rejected('invalid receipt JSON') from None
        producer = producers.get(receipt.get('reviewer_enrollment_id'))
        require(producer is not None and producer.get('github_user_id') == sender['id'], 'unknown receipt producer')
        require(producer.get('enabled') is True, 'disabled producer')
        require(receipt['tuple']['repository_id'] == REPOSITORY_ID and receipt['tuple']['repository'] == REPOSITORY,
                'binding repository mismatch')
        require(receipt['tuple']['origin_account'] == producer['origin_account'] and
                receipt.get('reviewer_origin_account') == producer['origin_account'], 'binding origin mismatch')
        eligible.append((comment['id'], receipt, producer))
    require(bool(eligible), 'no authenticated enrolled receipt')
    eligible.sort(key=lambda item: item[0])
    origin = eligible[0][1]['tuple']['origin_account']
    require(all(r['tuple']['origin_account'] == origin for _, r, _ in eligible), 'frozen PR origin mismatch')
    _, receipt, producer = eligible[-1]
    validate_receipt(receipt, producer, current, policy_hash, now)
    return receipt

def git_tuple(head, base, token):
    for sha in (head, base):
        require(re.fullmatch('[0-9a-f]{40}', sha) is not None, 'invalid Git object')
    with tempfile.TemporaryDirectory(prefix='g1-objects-') as temporary:
        env = {'PATH': '/usr/bin:/bin', 'HOME': temporary, 'LANG': 'C', 'LC_ALL': 'C',
               'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_ATTR_NOSYSTEM': '1',
               'GIT_TERMINAL_PROMPT': '0', 'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'http.https://github.com/.extraheader',
               'GIT_CONFIG_VALUE_0': 'AUTHORIZATION: basic ' + base64.b64encode(('x-access-token:' + token).encode()).decode()}
        def command(*args):
            with tempfile.TemporaryFile() as output:
                # Bound downloaded packs/output and CPU; no checkout, hooks, filters,
                # submodules, external diff, textconv, or inherited credential helpers.
                def limits():
                    import resource
                    resource.setrlimit(resource.RLIMIT_FSIZE, (32000000, 32000000))
                    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
                result = subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'credential.helper=',
                    '-c', 'protocol.file.allow=never', '-c', 'core.attributesFile=/dev/null', *args], cwd=temporary,
                    env=env, stdout=output, stderr=subprocess.DEVNULL, timeout=60, preexec_fn=limits)
                require(result.returncode == 0, 'isolated Git data inspection failed')
                output.seek(0)
                data = output.read(MAX_DIFF + 1)
                require(len(data) <= MAX_DIFF, 'diff/output exceeds bound')
                return data
        command('init', '--bare', '.')
        command('fetch', '--no-tags', '--no-recurse-submodules', '--depth=256',
                'https://github.com/' + REPOSITORY + '.git', base, head)
        merge_base = command('merge-base', base, head).decode().strip()
        patch = command('-c', 'color.ui=false', 'diff', '--no-ext-diff', '--no-textconv', '--binary', base+'...'+head, '--')
        return merge_base, digest(patch)

def validate_ci_log(log, pr, merge_sha, run):
    marker = 'CANARY_CI_AGGREGATE_V1 '
    receipts = []
    for line in log.splitlines():
        # Job log API prefixes each emitted line with an RFC3339 UTC timestamp.
        line = re.sub(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z ', '', line)
        if line.startswith(marker):
            try:
                receipts.append(json.loads(line[len(marker):]))
            except ValueError:
                raise Rejected('malformed aggregate receipt') from None
    require(len(receipts) == 1, 'aggregate receipt missing/duplicated')
    ref = f"refs/pull/{pr['number']}/merge"
    expected = {'repository': REPOSITORY, 'repository_id': str(REPOSITORY_ID), 'event': 'pull_request',
        'revision': merge_sha, 'workflow_sha': merge_sha, 'run_id': str(run['id']),
        'run_attempt': str(run['run_attempt']), 'ref': ref, 'head_sha': pr['head']['sha'],
        'base_sha': pr['base']['sha'], 'workflow_ref': REPOSITORY + '/.github/workflows/ci.yml@' + ref,
        'workflow': 'CI'}
    require(receipts[0] == {'schema': 'canary-ci-aggregate/v1', 'identity': expected, 'result': 'success'},
            'tested CI revision/base/head/run drift')

def validate_ci(api, prefix, pr, merge_sha):
    workflow = api.request(prefix + '/actions/workflows/ci.yml')
    require(workflow['path'] == '.github/workflows/ci.yml' and workflow['state'] == 'active', 'CI workflow identity')
    runs = api.pages(prefix + '/actions/workflows/' + str(workflow['id']) + '/runs?event=pull_request&head_sha=' + pr['head']['sha'], 'workflow_runs')
    runs = [r for r in runs if any(p['number'] == pr['number'] for p in r.get('pull_requests', []))]
    require(bool(runs), 'no CI run for PR')
    run = max(runs, key=lambda r: (r['id'], r.get('run_attempt', 1)))
    require(run.get('status') == 'completed' and run.get('conclusion') == 'success' and run.get('event') == 'pull_request'
            and run.get('head_sha') == pr['head']['sha'] and run['repository']['id'] == REPOSITORY_ID
            and run['head_repository']['id'] == REPOSITORY_ID, 'CI run not current successful origin')
    bindings = [p for p in run['pull_requests'] if p['number'] == pr['number']]
    require(len(bindings) == 1 and bindings[0]['head']['sha'] == pr['head']['sha']
            and bindings[0]['base']['sha'] == pr['base']['sha'], 'CI base/head drift')
    jobs = api.pages(prefix + f"/actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs", 'jobs')
    for name in ('contract', 'ci-negative', 'ci-required'):
        matching = [j for j in jobs if j['name'] == name]
        require(len(matching) == 1, 'missing/duplicate CI job ' + name)
        job = matching[0]
        require(job['status'] == 'completed' and job['conclusion'] == 'success' and job['run_id'] == run['id'], 'failed/skipped CI shard')
        check_id = job['check_run_url'].rsplit('/', 1)[-1]
        require(check_id.isdecimal(), 'invalid check ID')
        check = api.request(prefix + '/check-runs/' + check_id)
        require(check['app']['id'] == CI_APP_ID and check['name'] == name and check['status'] == 'completed'
                and check['conclusion'] == 'success' and check['head_sha'] in (pr['head']['sha'], merge_sha)
                and check['check_suite']['id'] == run['check_suite_id'], 'wrong CI producer/suite')
        if name == 'ci-required':
            validate_ci_log(api.job_log(job['id']), pr, merge_sha, run)
    return run['id'], run['run_attempt']

def snapshot(api, number, policy, policy_hash, now):
    prefix = '/repos/' + REPOSITORY
    repo = api.request(prefix)
    pr = api.request(prefix + '/pulls/' + str(number))
    require(pr['state'] == 'open' and not pr['draft'] and not pr.get('merged'), 'PR is not open ready')
    require(pr['user']['id'] == OWNER_ID and pr['user']['type'] == 'User', 'author policy')
    require(pr['head']['repo']['id'] == REPOSITORY_ID and pr['base']['repo']['id'] == REPOSITORY_ID
            and pr['base']['ref'] == 'main', 'fork/base repository mismatch')
    base = api.request(prefix + '/git/ref/heads/main')['object']['sha']
    require(base == pr['base']['sha'], 'base moved')
    require(pr.get('mergeable') is True and pr.get('mergeable_state') in ('clean', 'blocked'), 'mergeability unknown/conflicting')
    rules = api.request(prefix + '/rules/branches/main')
    summaries = api.pages(prefix + '/rulesets?includes_parents=true')
    rulesets = [api.request(prefix + '/rulesets/' + str(s['id'])) for s in summaries]
    validate_controls(repo, rules, rulesets)
    merge_sha = api.request(prefix + f'/git/ref/pull/{number}/merge')['object']['sha']
    merge = api.request(prefix + '/git/commits/' + merge_sha)
    require([p['sha'] for p in merge['parents']] == [base, pr['head']['sha']], 'synthetic merge tuple drift')
    merge_base, diff_hash = git_tuple(pr['head']['sha'], base, api.token)
    current = {'repository': REPOSITORY, 'repository_id': REPOSITORY_ID, 'head_sha': pr['head']['sha'],
               'base_sha': base, 'merge_base_sha': merge_base, 'diff_sha256': diff_hash, 'policy_sha256': policy_hash}
    comments = api.pages(prefix + f'/issues/{number}/comments')
    receipt = choose_receipt(comments, policy, current, policy_hash, now)
    ci = validate_ci(api, prefix, pr, merge_sha)
    return {'tuple': current, 'receipt': receipt, 'ci': ci, 'merge_sha': merge_sha,
            'node_id': pr['node_id'], 'bypass_visibility': {str(r['id']): ('visible' if 'bypass_actors' in r else 'redacted-or-unavailable') for r in rulesets}, 'controls_sha256': digest(canonical([{k: repo[k] for k in ('id', 'default_branch', 'private', 'allow_squash_merge', 'allow_merge_commit', 'allow_rebase_merge', 'allow_auto_merge')}, rules, rulesets]))}

def deliver(read_api, write_api, number, policy, policy_hash, now, app_slug):
    require(policy.get('enabled') is True, 'App writes disabled by trusted enrollment policy')
    require(re.fullmatch('[a-z0-9-]+', app_slug or '') is not None, 'invalid App slug')
    require(read_api.request('/apps/' + app_slug)['id'] == APP_ID, 'wrong reviewer App')
    repositories = write_api.pages('/installation/repositories', 'repositories')
    require([r['id'] for r in repositories] == [REPOSITORY_ID], 'App token is not repository scoped')
    first = snapshot(read_api, number, policy, policy_hash, now)
    # Re-read all mutable gates immediately before every write. Native strict
    # required checks and stale-approval dismissal arbitrate races after this read.
    require(snapshot(read_api, number, policy, policy_hash, now) == first, 'admission drift before approval')
    head = first['tuple']['head_sha']
    approval = write_api.request('/repos/' + REPOSITORY + f'/pulls/{number}/reviews', 'POST',
        {'event': 'APPROVE', 'commit_id': head, 'body': 'G1: completed enrolled local review and current CI/control gates verified. Q16 operational trust applies.'})
    require(approval['state'] == 'APPROVED' and approval['commit_id'] == head
            and approval['user']['login'] == app_slug + '[bot]', 'approval identity/result mismatch')
    require(snapshot(read_api, number, policy, policy_hash, now) == first, 'admission drift after approval; auto-merge not armed')
    result = write_api.request('/graphql', 'POST', {'query': 'mutation($id:ID!){enablePullRequestAutoMerge(input:{pullRequestId:$id,mergeMethod:SQUASH}){pullRequest{autoMergeRequest{mergeMethod}}}}', 'variables': {'id': first['node_id']}})
    require(not result.get('errors') and result['data']['enablePullRequestAutoMerge']['pullRequest']['autoMergeRequest']['mergeMethod'] == 'SQUASH', 'native auto-merge not confirmed')
    return {'status': 'armed', 'head_sha': head, 'merged': False}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pr', type=int, required=True)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    require(args.pr > 0, 'invalid PR')
    require(os.environ.get('GITHUB_REPOSITORY') == REPOSITORY, 'wrong workflow repository')
    trusted = os.environ.get('TRUSTED_WORKFLOW_SHA', '')
    require(re.fullmatch('[0-9a-f]{40}', trusted) is not None, 'missing trusted workflow revision')
    require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == trusted, 'untrusted checkout')
    policy_bytes = (ROOT / '.github/review-enrollments.json').read_bytes()
    policy = json.loads(policy_bytes)
    require(policy.get('schema') == 'g1-review-enrollments/v1' and policy.get('repository_id') == REPOSITORY_ID, 'enrollment policy identity')
    read = API(os.environ.get('CI_READ_TOKEN'))
    require(read.request('/repos/' + REPOSITORY + '/git/ref/heads/main')['object']['sha'] == trusted, 'trusted default revision moved')
    now = dt.datetime.now(dt.timezone.utc)
    if args.write:
        require(os.environ.get('REVIEWER_APP_ENABLED') == 'true', 'App write flag disabled')
        result = deliver(read, API(os.environ.get('APP_TOKEN'), writable=True), args.pr, policy, digest(policy_bytes), now, os.environ.get('APP_SLUG'))
    else:
        proof = snapshot(read, args.pr, policy, digest(policy_bytes), now)
        result = {'status': 'qualified-read-only', 'tuple': proof['tuple'], 'ci': proof['ci'], 'bypass_visibility': proof['bypass_visibility'], 'mutated': False}
    print(json.dumps(result, sort_keys=True))

if __name__ == '__main__':
    try:
        main()
    except (Rejected, KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError) as error:
        # Errors contain control reasons, never HTTP payloads/headers or tokens.
        print(json.dumps({'status': 'rejected', 'reason': str(error)[:300]}))
        raise SystemExit(1)
