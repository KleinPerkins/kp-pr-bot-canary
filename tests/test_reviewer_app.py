"""Adversarial admission tests; no network, credentials, checkout or API writes."""
import copy
import datetime as dt
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('reviewer_app', Path(__file__).resolve().parents[1] / 'scripts/reviewer_app.py')
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)
NOW = dt.datetime(2026, 11, 15, 12, tzinfo=dt.timezone.utc)

def fixture():
    current = dict(repository=gate.REPOSITORY, repository_id=gate.REPOSITORY_ID, head_sha='a'*40,
                   base_sha='b'*40, merge_base_sha='b'*40, diff_sha256='d'*64, policy_sha256='e'*64)
    producer = dict(id='personal-opaque', enabled=True, origin_account='origin-opaque',
                    github_user_id=gate.OWNER_ID, instructions_sha256='f'*64, cli_version='1.0', credential_store='keyring')
    review = dict(verdict='pass', coverage='complete', summary='No findings after full diff review.', findings=[], unresolved_findings=[])
    receipt = dict(schema='g1-local-review/v1', capture_id='capture-uuid', trust_model='q16-operational-local',
        tuple=dict(current, origin_account=producer['origin_account']), reviewer_enrollment_id=producer['id'],
        reviewer_origin_account=producer['origin_account'], workspace_binding='owner-declared-enrollment',
        instructions_sha256=producer['instructions_sha256'], runtime=dict(status='completed', thread_id='fresh-thread-id',
        cli_version='1.0', credential_store='keyring', event_stream_sha256='c'*64, turn_id=None),
        started_at='2026-11-15T11:00:00Z', completed_at='2026-11-15T11:30:00Z', review=review,
        report_sha256=gate.digest(gate.canonical(review)))
    comment = dict(id=1, user=dict(id=gate.OWNER_ID,type='User'), created_at='2026-11-15T11:31:00Z', updated_at='2026-11-15T11:31:00Z', body=gate.MARKER+json.dumps(receipt))
    return current, producer, receipt, comment

class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.current, self.producer, self.receipt, self.comment = fixture()
    def valid(self):
        gate.validate_receipt(self.receipt, self.producer, self.current, 'e'*64, NOW)
    def test_complete_current_receipt(self):
        self.valid()
    def test_tuple_drift_every_field(self):
        for field in self.current:
            with self.subTest(field=field):
                receipt = copy.deepcopy(self.receipt)
                receipt['tuple'][field] = 'wrong'
                with self.assertRaises(gate.Rejected):
                    gate.validate_receipt(receipt,self.producer,self.current,'e'*64,NOW)
    def test_failed_partial_findings_stale_future_runtime_and_digest(self):
        mutations = [lambda r:r['review'].update(verdict='fail'),lambda r:r['review'].update(coverage='incomplete'),
            lambda r:r['review'].update(findings=[{'id':'P1'}]),lambda r:r['review'].update(unresolved_findings=['P1']),
            lambda r:r.update(started_at='2026-11-13T11:00:00Z'),lambda r:r.update(completed_at='2026-11-16T11:00:00Z'),
            lambda r:r['runtime'].update(status='running'),lambda r:r['runtime'].update(thread_id=''),
            lambda r:r['runtime'].update(credential_store='file'),lambda r:r['runtime'].update(startup_notice_sha256=['0'*64]),lambda r:r.update(report_sha256='0'*64),
            lambda r:r.update(instructions_sha256='0'*64),lambda r:r.update(reviewer_origin_account='other')]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                r=copy.deepcopy(self.receipt);mutation(r)
                with self.assertRaises(gate.Rejected):gate.validate_receipt(r,self.producer,self.current,'e'*64,NOW)
    def choose(self,comments,producers=None):
        return gate.choose_receipt(comments,{'producers':producers or [self.producer]},self.current,'e'*64,NOW)
    def test_owner_receipt_required_untrusted_sender_cannot_bind(self):
        bad=copy.deepcopy(self.comment);bad['user']['id']=999
        with self.assertRaises(gate.Rejected):self.choose([bad])
        self.assertEqual(self.choose([bad,self.comment]),self.receipt)
    def test_edited_unknown_oversized_receipts_fail_closed(self):
        for change in [dict(updated_at='2026-11-15T12:00:00Z'),dict(body=gate.MARKER+'x'*60000),dict(body=gate.MARKER+'{}')]:
            with self.subTest(change=str(change)[:70]):
                bad=dict(self.comment,**change)
                with self.assertRaises(gate.Rejected):self.choose([bad])
    def test_origin_is_oldest_binding_not_newest_receipt(self):
        other=dict(self.producer,id='other-producer',origin_account='other-origin')
        second=copy.deepcopy(self.receipt);second.update(reviewer_enrollment_id=other['id'],reviewer_origin_account=other['origin_account']);second['tuple']['origin_account']=other['origin_account']
        with self.assertRaisesRegex(gate.Rejected,'frozen PR origin'):
            self.choose([self.comment,dict(self.comment,id=2,body=gate.MARKER+json.dumps(second))],[self.producer,other])
    def test_latest_failed_review_supersedes_old_pass(self):
        failed=copy.deepcopy(self.receipt);failed['review']['verdict']='fail'
        with self.assertRaises(gate.Rejected):self.choose([self.comment,dict(self.comment,id=2,body=gate.MARKER+json.dumps(failed))])

class APIAndControlsTests(unittest.TestCase):
    def test_readonly_rejects_post_without_network(self):
        with self.assertRaises(gate.Rejected):gate.API('fake').request('/graphql','POST',{})
    def test_pagination_reads_past_first_page(self):
        api=gate.API('fake')
        with patch.object(api,'request',side_effect=[{'jobs':list(range(100))},{'jobs':[100]}]) as request:
            self.assertEqual(len(api.pages('/jobs','jobs')),101)
            self.assertIn('page=2',request.call_args.args[0])
    def test_pagination_never_silently_truncates(self):
        api=gate.API('fake')
        with patch.object(api,'request',return_value=[{}]*100):
            with self.assertRaises(gate.Rejected):api.pages('/things')
    def controls(self):
        repo=dict(id=gate.REPOSITORY_ID,full_name=gate.REPOSITORY,default_branch='main',private=False,
                  allow_squash_merge=True,allow_merge_commit=False,allow_rebase_merge=False,allow_auto_merge=True)
        rules=[dict(type='required_status_checks',ruleset_id=1,parameters=dict(strict_required_status_checks_policy=True,required_status_checks=[dict(context='ci-required',integration_id=15368)])),
               dict(type='pull_request',ruleset_id=1,parameters=dict(required_approving_review_count=1,dismiss_stale_reviews_on_push=True,required_review_thread_resolution=True,allowed_merge_methods=['squash'])),
               dict(type='required_linear_history',ruleset_id=1),dict(type='deletion',ruleset_id=1),dict(type='non_fast_forward',ruleset_id=1)]
        return repo,rules,[dict(id=1,enforcement='active',bypass_actors=[])]
    def test_control_positive(self):gate.validate_controls(*self.controls())
    def test_owner_admin_pr_only_exception_preserved(self):
        repo,rules,sets=self.controls();sets[0]['bypass_actors']=[dict(actor_id=5,actor_type='RepositoryRole',bypass_mode='pull_request')]
        gate.validate_controls(repo,rules,sets)
    def test_app_redacted_bypass_is_not_treated_as_empty(self):
        repo,rules,sets=self.controls();del sets[0]['bypass_actors']
        gate.validate_controls(repo,rules,sets)
    def test_no_protection_gap_or_producer_substitution(self):
        mutations=[lambda r,q,s:r.update(allow_merge_commit=True),lambda r,q,s:q[0]['parameters'].update(strict_required_status_checks_policy=False),
                   lambda r,q,s:q[0]['parameters']['required_status_checks'][0].update(integration_id=4274739),
                   lambda r,q,s:q[1]['parameters'].update(dismiss_stale_reviews_on_push=False),
                   lambda r,q,s:s[0].update(bypass_actors=[{'actor_id':5}]),lambda r,q,s:s[0].update(enforcement='evaluate')]
        for mutation in mutations:
            args=self.controls();mutation(*args)
            with self.assertRaises(gate.Rejected):gate.validate_controls(*args)

class DeliveryTests(unittest.TestCase):
    def fake_apis(self):
        read=gate.API('fake');write=gate.API('fake',writable=True)
        read.request=lambda path:{'id':gate.BOT_ID,'type':'Bot','login':gate.APP_SLUG+'[bot]'}
        write.pages=lambda *args:[{'id':gate.REPOSITORY_ID,'full_name':gate.REPOSITORY}]
        return read,write
    def test_disabled_means_no_mutation(self):
        read,write=self.fake_apis()
        with patch.object(write,'request') as request:
            with self.assertRaises(gate.Rejected):gate.deliver(read,write,1,{'enabled':False},'hash',NOW,gate.APP_SLUG,'123')
            request.assert_not_called()
    def test_base_race_before_approval_prevents_all_writes(self):
        read,write=self.fake_apis()
        with patch.object(gate,'snapshot',side_effect=[{'base':'old'},{'base':'new'}]),patch.object(write,'request') as request:
            with self.assertRaisesRegex(gate.Rejected,'before approval'):gate.deliver(read,write,1,{'enabled':True},'hash',NOW,gate.APP_SLUG,'123')
            request.assert_not_called()
    def test_base_race_after_approval_never_arms(self):
        read,write=self.fake_apis();proof={'tuple':{'head_sha':'a'*40},'node_id':'PR_node'}
        with patch.object(gate,'snapshot',side_effect=[proof,proof,dict(proof,changed=True)]),patch.object(write,'request',return_value={'state':'APPROVED','commit_id':'a'*40,'user':{'login':gate.APP_SLUG+'[bot]','id':gate.BOT_ID,'type':'Bot'}}) as request:
            with self.assertRaisesRegex(gate.Rejected,'after approval'):gate.deliver(read,write,1,{'enabled':True},'hash',NOW,gate.APP_SLUG,'123')
            self.assertEqual(request.call_count,1)
            self.assertEqual(request.call_args.args[2]['commit_id'],'a'*40)
    def test_success_writes_exact_head_then_native_squash_only(self):
        read,write=self.fake_apis();proof={'tuple':{'head_sha':'a'*40},'node_id':'PR_node'}
        replies=[{'state':'APPROVED','commit_id':'a'*40,'user':{'login':gate.APP_SLUG+'[bot]','id':gate.BOT_ID,'type':'Bot'}},
                 {'data':{'enablePullRequestAutoMerge':{'pullRequest':{'autoMergeRequest':{'mergeMethod':'SQUASH'}}}}}]
        with patch.object(gate,'snapshot',return_value=proof) as snapshot,patch.object(write,'request',side_effect=replies) as request:
            result=gate.deliver(read,write,1,{'enabled':True},'hash',NOW,gate.APP_SLUG,'123')
            self.assertEqual(result,{'status':'armed','head_sha':'a'*40,'merged':False})
            self.assertEqual(snapshot.call_count,3)
            self.assertEqual(request.call_count,2)
            self.assertEqual(request.call_args_list[0].args[2]['commit_id'],'a'*40)
            self.assertIn('mergeMethod:SQUASH',request.call_args_list[1].args[2]['query'])
    def test_other_app_or_multirepo_token_cannot_write(self):
        read,write=self.fake_apis();write.pages=lambda *args:[{'id':gate.REPOSITORY_ID},{'id':99}]
        with patch.object(write,'request') as request:
            with self.assertRaises(gate.Rejected):gate.deliver(read,write,1,{'enabled':True},'hash',NOW,gate.APP_SLUG,'123')
            request.assert_not_called()

class CITests(unittest.TestCase):
    def fixture(self):
        pr={'number':1,'head':{'sha':'a'*40},'base':{'sha':'b'*40}}
        run={'id':10,'run_attempt':2,'status':'completed','conclusion':'success','event':'pull_request',
             'head_sha':'a'*40,'repository':{'id':gate.REPOSITORY_ID},'head_repository':{'id':gate.REPOSITORY_ID},
             'pull_requests':[{'number':1,'head':{'sha':'a'*40},'base':{'sha':'b'*40}}], 'check_suite_id':50}
        jobs=[{'id':i,'name':name,'status':'completed','conclusion':'success','run_id':10,
               'check_run_url':'https://api.github.com/check-runs/'+str(i)} for i,name in enumerate(gate.CI_JOBS,1)]
        checks={str(i):{'name':job['name'],'app':{'id':15368},'status':'completed','conclusion':'success',
                       'head_sha':'a'*40,'check_suite':{'id':50}} for i,job in enumerate(jobs,1)}
        api=gate.API('fake')
        api.request=lambda path:({'id':5,'path':'.github/workflows/ci.yml','state':'active'} if path.endswith('ci.yml') else checks[path.rsplit('/',1)[-1]])
        api.pages=lambda path,key:([run] if key=='workflow_runs' else jobs)
        api.job_log=lambda job:self.log(pr,run)
        return api,pr,run,jobs,checks
    def log(self,pr,run):
        identity={'repository':gate.REPOSITORY,'repository_id':str(gate.REPOSITORY_ID),'event':'pull_request',
                  'revision':'c'*40,'workflow_sha':'c'*40,'run_id':str(run['id']),'run_attempt':str(run['run_attempt']),
                  'ref':'refs/pull/1/merge','head_sha':'a'*40,'base_sha':'b'*40,
                  'workflow_ref':gate.REPOSITORY+'/.github/workflows/ci.yml@refs/pull/1/merge','workflow':'CI'}
        return '2026-11-15T12:00:00.1234567Z CANARY_CI_AGGREGATE_V1 '+json.dumps({'schema':'canary-ci-aggregate/v1','identity':identity,'result':'success'})
    def test_immutable_log_tuple_required(self):
        api,pr,run,_,_=self.fixture();valid=self.log(pr,run)
        for bad in ('no marker',valid+'\n'+valid,valid.replace('b'*40,'d'*40),valid.replace('"run_attempt": "2"','"run_attempt": "1"'),valid.replace('c'*40,'f'*40)):
            with self.subTest(log=bad[:90]):
                with self.assertRaises(gate.Rejected):gate.validate_ci_log(bad,pr,'c'*40,run)
    def test_current_attempt_and_all_shards(self):
        api,pr,_,_,_=self.fixture()
        self.assertEqual(gate.validate_ci(api,'/repos/'+gate.REPOSITORY,pr,'c'*40),(10,2))
    def test_stale_wrong_producer_missing_skipped_failed_ci(self):
        mutations=[lambda run,jobs,checks:run['pull_requests'][0]['base'].update(sha='x'*40),
            lambda run,jobs,checks:run.update(conclusion='failure'),
            lambda run,jobs,checks:run.update(status='in_progress'),
            lambda run,jobs,checks:run['head_repository'].update(id=999),
            lambda run,jobs,checks:jobs.pop(),
            lambda run,jobs,checks:jobs[0].update(conclusion='skipped'),
            lambda run,jobs,checks:checks['3']['app'].update(id=4274739),
            lambda run,jobs,checks:checks['3']['check_suite'].update(id=51),
            lambda run,jobs,checks:checks['3'].update(head_sha='x'*40)]
        for mutation in mutations:
            api,pr,run,jobs,checks=self.fixture();mutation(run,jobs,checks)
            with self.assertRaises(gate.Rejected):gate.validate_ci(api,'/repos/'+gate.REPOSITORY,pr,'c'*40)
    def test_newer_failed_run_blocks_older_success(self):
        api,pr,run,jobs,_=self.fixture();failed=dict(run,id=11,conclusion='failure')
        api.pages=lambda path,key:([run,failed] if key=='workflow_runs' else jobs)
        with self.assertRaises(gate.Rejected):gate.validate_ci(api,'/repos/'+gate.REPOSITORY,pr,'c'*40)

class ReadinessTests(unittest.TestCase):
    def fixture(self):
        read, _, run, jobs, checks = CITests().fixture()
        revision = 'c'*40
        run.update(event='push', head_sha=revision, head_branch='main', pull_requests=[])
        for check in checks.values():
            check['head_sha'] = revision
        old_request = read.request
        read.request = lambda path: ({'object': {'sha': revision}} if path.endswith('/git/ref/heads/main') else
            {'id':gate.BOT_ID,'type':'Bot','login':gate.APP_SLUG+'[bot]'} if path.startswith('/users/') else old_request(path))
        identity = {'repository':gate.REPOSITORY, 'repository_id':str(gate.REPOSITORY_ID), 'event':'push',
            'revision':revision, 'workflow_sha':revision, 'run_id':'10', 'run_attempt':'2',
            'ref':'refs/heads/main', 'head_sha':'', 'base_sha':'',
            'workflow_ref':gate.REPOSITORY+'/.github/workflows/ci.yml@refs/heads/main','workflow':'CI'}
        read.job_log=lambda job: 'CANARY_CI_AGGREGATE_V1 '+json.dumps({'schema':'canary-ci-aggregate/v1','identity':identity,'result':'success'})
        app=gate.API('fake')
        app.pages=lambda path,key:[{'id':gate.REPOSITORY_ID,'full_name':gate.REPOSITORY}]
        return read,app,run,jobs,checks,identity
    def qualify(self, read, app):
        return gate.qualify_app(read,app,'c'*40,gate.APP_SLUG,'123')
    def test_main_readiness_no_writes_no_receipt_or_policy_enrollment_needed(self):
        read,app,*_=self.fixture()
        with patch.object(gate,'controls_snapshot',return_value={'controls_sha256':'hash','bypass_visibility':{'1':'redacted-or-unavailable'}}), patch.object(app,'request') as app_request:
            result=self.qualify(read,app)
        self.assertEqual(result['status'],'qualified-app-read-only')
        self.assertFalse(result['mutated'])
        self.assertEqual(result['revision'],'c'*40)
        self.assertEqual(result['bypass_visibility']['1'],'redacted-or-unavailable')
        app_request.assert_not_called()
    def test_main_receipt_and_all_new_shards_are_mandatory(self):
        for mutation in (lambda run,jobs,checks,i:i.update(base_sha='b'*40),
                         lambda run,jobs,checks,i:i.update(event='pull_request'),
                         lambda run,jobs,checks,i:i.update(workflow_sha='d'*40),
                         lambda run,jobs,checks,i:jobs.pop(3),
                         lambda run,jobs,checks,i:jobs[2].update(conclusion='skipped'),
                         lambda run,jobs,checks,i:checks['4']['app'].update(id=99),
                         lambda run,jobs,checks,i:run.update(conclusion='failure'),
                         lambda run,jobs,checks,i:run.update(head_branch='other')):
            read,app,run,jobs,checks,identity=self.fixture();mutation(run,jobs,checks,identity)
            with patch.object(gate,'controls_snapshot',return_value={}):
                with self.assertRaises(gate.Rejected):self.qualify(read,app)
    def test_main_movement_and_control_drift_reject(self):
        read,app,*_=self.fixture();original=read.request;calls=[]
        def request(path):
            if path.endswith('/git/ref/heads/main'):
                calls.append(path)
                return {'object':{'sha':('c' if len(calls)==1 else 'd')*40}}
            return original(path)
        read.request=request
        with patch.object(gate,'controls_snapshot',return_value={}):
            with self.assertRaisesRegex(gate.Rejected,'main moved'):self.qualify(read,app)
        read,app,*_=self.fixture()
        with patch.object(gate,'controls_snapshot',side_effect=[{'hash':'a'},{'hash':'b'}]):
            with self.assertRaisesRegex(gate.Rejected,'controls moved'):self.qualify(read,app)
    def test_invalid_token_scope_or_bot_or_outputs_reject(self):
        read,app,*_=self.fixture()
        with self.assertRaises(gate.Rejected):gate.validate_app_identity(read,app,'wrong','123')
        for installation in (None,'','0','unknown'):
            with self.assertRaises(gate.Rejected):gate.validate_app_identity(read,app,gate.APP_SLUG,installation)
        for repositories in ([],[{'id':gate.REPOSITORY_ID,'full_name':'other'}],
                             [{'id':gate.REPOSITORY_ID,'full_name':gate.REPOSITORY},{'id':99}]):
            app.pages=lambda *args:repositories
            with self.assertRaises(gate.Rejected):gate.validate_app_identity(read,app,gate.APP_SLUG,'123')
        read,app,*_=self.fixture();read.request=lambda path:{'id':999,'type':'Bot','login':gate.APP_SLUG+'[bot]'}
        with self.assertRaises(gate.Rejected):gate.validate_app_identity(read,app,gate.APP_SLUG,'123')
        read,app,*_=self.fixture();app.pages=lambda *args: (_ for _ in ()).throw(gate.Rejected('invalid token'))
        with self.assertRaisesRegex(gate.Rejected,'invalid token'):self.qualify(read,app)
    def test_qualification_cli_requires_separate_flag_and_writer_off(self):
        for qualify,enabled,accepted in (('false','false',False),('true','true',False),('true','false',True)):
            api=gate.API('fake');api.request=lambda path:{'object':{'sha':'c'*40}}
            env={'GITHUB_REPOSITORY':gate.REPOSITORY,'TRUSTED_WORKFLOW_SHA':'c'*40,
                 'CI_READ_TOKEN':'fake','APP_TOKEN':'fake','APP_SLUG':gate.APP_SLUG,
                 'APP_INSTALLATION_ID':'123','REVIEWER_APP_QUALIFY':qualify,'REVIEWER_APP_ENABLED':enabled}
            with patch.dict(gate.os.environ,env,clear=True), patch('sys.argv',['reviewer_app.py','--qualify-app']), \
                 patch.object(gate.subprocess,'check_output',return_value='c'*40), \
                 patch.object(gate,'API',return_value=api), patch.object(gate,'qualify_app',return_value={'mutated':False}) as qualification, \
                 patch('builtins.print'):
                if accepted:
                    gate.main();qualification.assert_called_once()
                else:
                    with self.assertRaises(gate.Rejected):gate.main()
                    qualification.assert_not_called()
    def test_writable_api_never_accepted_for_qualification(self):
        read,app,*_=self.fixture();app.writable=True
        with self.assertRaises(gate.Rejected):self.qualify(read,app)
    def test_history_only_owner_always_preserved_without_broadening_merge_rules(self):
        repo,rules,sets=APIAndControlsTests().controls()
        history=[dict(type=name,ruleset_id=2) for name in ('deletion','non_fast_forward')]
        extra=dict(id=2,enforcement='active',rules=[{'type':r['type']} for r in history],
                   bypass_actors=[dict(actor_id=5,actor_type='RepositoryRole',bypass_mode='always')])
        gate.validate_controls(repo,rules+history,sets+[extra])
        for change in ('app','extra_rule','merge_always'):
            badsets=copy.deepcopy(sets+[extra]);badrules=copy.deepcopy(rules+history)
            if change=='app':badsets[1]['bypass_actors'][0].update(actor_type='Integration',actor_id=gate.APP_ID)
            if change=='extra_rule':badsets[1]['rules'].append({'type':'pull_request'})
            if change=='merge_always':badsets[0]['bypass_actors']=[dict(actor_id=5,actor_type='RepositoryRole',bypass_mode='always')]
            with self.assertRaises(gate.Rejected):gate.validate_controls(repo,badrules,badsets)
    def test_public_runtime_notices_are_hashes_only(self):
        current,producer,receipt,_=fixture()
        notice_hash=gate.digest(b'private startup notice')
        producer['allowed_startup_notice_sha256']=[notice_hash]
        receipt['runtime']['startup_notice_sha256']=[notice_hash]
        gate.validate_receipt(receipt,producer,current,'e'*64,NOW)
        receipt['runtime']['startup_notices']=['private text']
        with self.assertRaises(gate.Rejected):gate.validate_receipt(receipt,producer,current,'e'*64,NOW)

if __name__=='__main__':unittest.main()
