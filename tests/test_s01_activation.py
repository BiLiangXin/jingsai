"""Synthetic project fixtures only: no real source or native journal access."""
from __future__ import annotations
import copy
import datetime
import hashlib
import json
import pickle
import sys
from pathlib import Path
from unittest.mock import patch
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mosei.s01 import authorization as auth
from mosei.s01.contracts import synthetic_batch


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def project(tmp_path, monkeypatch):
    root, output, ledger = tmp_path/"project", tmp_path/"private"/"run", tmp_path/"ledger"
    ledger.mkdir()
    cfg = json.loads((ROOT/"configs/s01_execution.json").read_text(encoding="utf-8"))
    cfg.update(task_id=auth.TASK, training_authorized=True, status="ACTIVE_AUTHORIZED", resource_cap_status="USER_PREAUTHORIZED",
        owner_authorization_mode=auth.MODE, execution_fit_budget=30, resource_walltime_cap_hours=12, per_fit_walltime_cap_hours=2,
        budget_decided_at="2026-09-25T04:00:00+08:00", campaign_id="synthetic-campaign-20260925-01", q3_authorized=False,
        private_output_sha256=auth.path_digest(output))
    for rel in auth.CRITICAL:
        put(root/rel, {"synthetic_fixture":True})
    put(root/"configs/s01_execution.json", cfg)
    put(root/"state/LATEST_RESEARCH.json", dict(s01_training_authorized=True,campaign_id=cfg["campaign_id"]))
    (root/"TASK_SPEC.md").write_text(f"task_id: {auth.TASK}\nstatus: ACTIVE_AUTHORIZED\ns01_training_authorized: true\n")
    (root/"DECISIONS.md").write_text("| D-DATA-01 | FROZEN_FOR_BASELINE | synthetic-fixture |\n")
    put(root/"docs/research/R01/FREEZE_01.json", dict(status="FROZEN_FOR_S01_PROTOCOL"))
    put(root/auth.AUTH_RECORD, dict(authorization_id="S01-EXEC-AUTH-01",source="EXPLICIT_CURRENT_USER_INSTRUCTION",
        instruction_sha256=auth.INSTRUCTION_SHA256,mode=auth.MODE,campaign_id=cfg["campaign_id"],selected_budget=[30,12,2],
        budget_decided_at=cfg["budget_decided_at"],private_output_sha256=cfg["private_output_sha256"],synthetic_fixture=True))
    def manifest():
        put(root/auth.MANIFEST,dict(base_commit=auth.BASE_COMMIT,campaign_id=cfg["campaign_id"],files=[
            dict(path=r,sha256=hashlib.sha256((root/r).read_bytes()).hexdigest(),size=(root/r).stat().st_size) for r in sorted(auth.CRITICAL)]))
        put(root/auth.REVIEW,dict(status="TECHNICAL_PASS",blocking_critical=0,blocking_major=0,synthetic_fixture=True,
            authorized_manifest_sha256=hashlib.sha256((root/auth.MANIFEST).read_bytes()).hexdigest()))
    manifest()
    answers={('branch','--show-current'):'codex/mosei-auto',('remote','get-url','origin'):'https://github.com/BiLiangXin/jingsai.git',
        ('status','--porcelain'):'',('rev-parse','HEAD'):'a'*40,
        ('ls-remote','origin','refs/heads/codex/mosei-auto'):'a'*40+'\trefs/heads/codex/mosei-auto',
        ('diff','--name-only',auth.BASE_COMMIT,'--',*auth.FROZEN_PATHS):'',
        ('show',auth.BASE_COMMIT+':DECISIONS.md'):(root/'DECISIONS.md').read_text()}
    monkeypatch.setattr(auth,'_git',lambda root,*args:answers[args])
    monkeypatch.setattr(auth,'_claims_root',lambda:ledger)
    monkeypatch.setattr(auth,'_now',lambda:datetime.datetime.fromisoformat('2026-09-25T04:10:00+08:00'))
    monkeypatch.setattr(auth,'_ACTIVE_BINDING',None)
    return root,output,cfg,answers,manifest


def launch(p, **changes):
    root,output,cfg,_,_=p
    return auth.require_official_authority(dict(cfg,**changes),split='train',optimizer=True,root=root,output_dir=output,device='cuda',launch=True)


def test_explicit_preauthorization_and_claim_required_before_source(project):
    root,output,cfg,_,_=project
    grant=launch(project)
    assert grant['owner_authorization']['mode']==auth.MODE
    assert not hasattr(auth,'verify_native_owner') and not hasattr(auth,'HOST_THREAD')
    with pytest.raises(auth.AuthorizationError,match="claimed campaign"):
        auth.require_official_authority(cfg,split='valid',root=root,output_dir=output,device='cuda')
    auth.claim_campaign(grant)
    assert auth.require_official_authority(cfg,split='valid',root=root,output_dir=output,device='cuda')['binding']==grant['binding']
    with pytest.raises(auth.AuthorizationError,match='already claimed'):
        launch(project)
    with pytest.raises(auth.AuthorizationError,match='already launched'):
        auth.claim_campaign(grant)


@pytest.mark.parametrize('key,value',[
 ('training_authorized',False),('task_id','WRONG'),('protocol_freeze','WRONG'),('owner_authorization_mode','FAKE'),
 ('status','DRAFT'),('resource_cap_status','OWNER_APPROVED'),('execution_fit_budget',39),('execution_fit_budget',24),
 ('resource_walltime_cap_hours',13),('per_fit_walltime_cap_hours',3),('retry_training_budget',1),('device','cpu'),
 ('test_authorized',True),('attachment3_4_authorized',True),('q3_authorized',True),('train_mask_root',2),
 ('valid_mask_root',2),('model_seeds',[17]),('nominal_conditions',144),('views',96),('random_replicates',4),
 ('storage_cap_gib',50),('gpu_memory_guard_fraction',1),('latest_compute_finish','2026-09-26T18:00:00+08:00'),
 ('official_source_sha256','b'*64),('private_output_sha256','b'*64),('campaign_id','wrong-campaign')])
def test_wrong_scope_or_configuration_rejected(project,key,value):
    with pytest.raises(auth.AuthorizationError):launch(project,**{key:value})


@pytest.mark.parametrize('command,value',[
 (('branch','--show-current'),'main'),(('remote','get-url','origin'),'https://example.com/repo.git'),
 (('status','--porcelain'),' M changed.py'),(('ls-remote','origin','refs/heads/codex/mosei-auto'),'b'*40+'\trefs/heads/codex/mosei-auto'),
 (('diff','--name-only',auth.BASE_COMMIT,'--',*auth.FROZEN_PATHS),'research/r01/reference.py')])
def test_git_preflight_rejects(project,command,value):
    project[3][command]=value
    with pytest.raises(auth.AuthorizationError):launch(project)


@pytest.mark.parametrize('split,optimizer',[('test',False),('attachment3',False),('attachment4',False),('valid',True)])
def test_split_quarantine_precedes_all_io(project,split,optimizer):
    with patch('pathlib.Path.read_bytes',side_effect=AssertionError('No file read expected')):
        with pytest.raises(auth.AuthorizationError):
            auth.require_official_authority(project[2],split=split,optimizer=optimizer,root=project[0],output_dir=project[1],device='cuda')


def test_manifest_code_hash_and_review_binding_rejected(project):
    root,_,_,_,_=project
    with (root/'src/mosei/s01/models.py').open('a') as stream:stream.write('changed')
    with pytest.raises(auth.AuthorizationError,match='manifest hash'):launch(project)


def test_missing_critical_manifest_member_rejected(project):
    root=project[0];p=root/auth.MANIFEST;value=json.loads(p.read_bytes());value['files']=value['files'][1:];put(p,value)
    with pytest.raises(auth.AuthorizationError,match='incomplete'):launch(project)


def test_changed_independent_review_binding_rejected(project):
    root=project[0];p=root/auth.REVIEW;value=json.loads(p.read_bytes());value['authorized_manifest_sha256']='0'*64;put(p,value)
    with pytest.raises(auth.AuthorizationError,match='Independent review'):launch(project)


def test_existing_output_refused_before_claim(project):
    project[1].mkdir(parents=True)
    with pytest.raises(auth.AuthorizationError,match='new private'):launch(project)


def test_deadline_selection_and_locked_launch_boundary(project,monkeypatch):
    dt=datetime.datetime.fromisoformat
    assert auth.select_budget(dt('2026-09-25T06:00:00+08:00'))==(30,12,2)
    assert auth.select_budget(dt('2026-09-25T06:00:01+08:00'))==(24,4,1)
    assert auth.select_budget(dt('2026-09-25T14:00:00+08:00'))==(24,4,1)
    with pytest.raises(auth.AuthorizationError,match='DEADLINE_BLOCKED'):auth.select_budget(dt('2026-09-25T14:00:01+08:00'))
    monkeypatch.setattr(auth,'_now',lambda:dt('2026-09-25T06:00:01+08:00'))
    with pytest.raises(auth.AuthorizationError,match='DEADLINE_BLOCKED'):launch(project)
    monkeypatch.setattr(auth,'_now',lambda:dt('2026-09-25T18:00:00+08:00'))
    with pytest.raises(auth.AuthorizationError,match='deadline passed'):launch(project)


def test_authorized_24_plan_locked_before_source(project,monkeypatch):
    root,output,cfg,_,rebuild=project
    cfg.update(execution_fit_budget=24,resource_walltime_cap_hours=4,per_fit_walltime_cap_hours=1,budget_decided_at='2026-09-25T07:00:00+08:00')
    put(root/'configs/s01_execution.json',cfg)
    r=json.loads((root/auth.AUTH_RECORD).read_bytes());r.update(selected_budget=[24,4,1],budget_decided_at=cfg['budget_decided_at']);put(root/auth.AUTH_RECORD,r)
    rebuild()
    monkeypatch.setattr(auth,'_now',lambda:datetime.datetime.fromisoformat('2026-09-25T07:01:00+08:00'))
    assert launch(project)['binding']['execution_fit_budget']==24


def test_loader_reads_only_after_both_preflights_and_only_train_valid(tmp_path):
    from mosei.s01 import execution
    source=tmp_path/'aligned_50.pkl'
    source.write_bytes(pickle.dumps({'train':'synthetic','valid':'synthetic','test':'DO_NOT_INDEX'}))
    calls=[]
    cfg=dict(official_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    batch=synthetic_batch(2)
    class FakeDataset:
        def __len__(self):return 2
        def batch(self,indices):return 'SYNTHETIC_BRIDGE'
    def guard(*a,**kw):calls.append('guard-'+kw['split'])
    def factory(container,split):
        assert calls[:2]==['guard-train','guard-valid']
        assert split in ('train','valid')
        calls.append('dataset-'+split);return FakeDataset()
    original=Path.open
    def opened(path,*a,**kw):
        if path==source:assert calls[:2]==['guard-train','guard-valid']
        return original(path,*a,**kw)
    with patch.object(execution,'require_official_authority',side_effect=guard),patch('pathlib.Path.open',opened),\
         patch('mosei.data.dataset.create_aligned_dataset',side_effect=factory),patch.object(execution,'from_aligned',return_value=batch):
        result,h=execution.load_official(cfg,source)
    assert set(result)=={'train','valid'} and calls==['guard-train','guard-valid','dataset-train','dataset-valid']


def test_changed_source_fingerprint_never_deserializes(tmp_path):
    from mosei.s01 import execution
    source = tmp_path/'aligned_50.pkl'
    source.write_bytes(b'synthetic wrong fingerprint')
    with patch.object(execution, 'require_official_authority'), patch('pickle.load', side_effect=AssertionError('Must not deserialize')):
        with pytest.raises(ValueError, match='fingerprint changed'):
            execution.load_official(dict(official_source_sha256='0'*64), source)


def test_campaign_summary_failure_preserves_original_exception(tmp_path):
    from mosei.s01 import execution
    output = tmp_path/'private'
    def failed(config, source, destination, *, device, run_state):
        output.mkdir()
        (output/'events.jsonl').write_text('{corrupt incomplete record')
        run_state['claimed'] = True
        raise OSError('original campaign failure')
    with patch.object(execution, '_execute_core', side_effect=failed):
        with pytest.raises(OSError, match='original campaign failure'):
            execution.execute_core(dict(execution_fit_budget=30,campaign_id='synthetic'), 'unused', output)
