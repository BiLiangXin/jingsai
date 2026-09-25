"""Explicit new S02 authority; one-shot claim and reviewed immutable code binding.

Host-account trust, not a sandbox against malicious same-account modifications.
No CLI grant, no S01 claim reuse and no hidden owner approval event.
"""
import ctypes,datetime,json,os,subprocess
from pathlib import Path,PurePosixPath
from mosei.s01.contracts import ROOT,require,digest
from mosei.s01.authorization import reject_redirected_path,path_digest
from .common import CUTOFF,SOURCE_HASH,sha,now

TASK='S02_CHAMPION_CHALLENGER_IMPROVEMENT'
BASE='95342eb58bf0494bcc90934f76958b71becb8687'
MANIFEST='reports/s02_preparation/AUTHORIZED_MANIFEST.json'
REVIEW='reports/s02_preparation/independent_review.json'
ACTIVE=None

def git(*args):return subprocess.check_output(['git','--no-optional-locks',*args],cwd=ROOT,timeout=30).decode().strip()

def validate_config(c):
    expected=dict(task_id=TASK,status='ACTIVE_AUTHORIZED',training_authorized=True,authorization_id='S02-EXEC-AUTH-01',
        execution_fit_budget=12,postprocess_budget=15,retry_training_budget=0,model_seeds=[17,29,43],
        recipes=['M1','M2','M3','M4'],variants=['W0','W1','W2'],betas=[-.4,-.2,0.,.2,.4],
        resource_walltime_cap_hours=4,per_fit_walltime_cap_minutes=45,latest_compute_finish=CUTOFF,
        test_authorized=False,attachment3_4_authorized=False,q3_authorized=False,source_sha256=SOURCE_HASH,
        train_mask_root=2207,valid_mask_root=1103,nominal_conditions=96,views=144,device='cuda')
    require(all(c.get(k)==v for k,v in expected.items()),'S02 exact scope/cap mismatch')
    require(c['campaign_id'].startswith('S02-') and len(c['campaign_id'])<100,'Separate S02 campaign required')

def claims_root():
    require(os.name=='nt','Windows fixed claim ledger')
    profile=ctypes.create_unicode_buffer(32768)
    require(ctypes.windll.shell32.SHGetFolderPathW(None,0x28,None,0,profile)==0,'Native profile unavailable')
    path=Path(profile.value)/'.codex'/'mosei_s02_claims'
    reject_redirected_path(path);path.mkdir(exist_ok=True)
    return path

def verify_manifest(c):
    manifest=ROOT/MANIFEST;value=json.loads(manifest.read_bytes());names=[r['path'] for r in value['files']]
    require(value['campaign_id']==c['campaign_id'] and value['base_commit']==BASE,'Manifest campaign mismatch')
    require(len(names)==len(set(n.casefold() for n in names)),'Manifest duplicate')
    critical={p.relative_to(ROOT).as_posix() for folder in ('src/mosei/s02','src/mosei/s01','src/mosei/data','research/r01') for p in (ROOT/folder).rglob('*.py')}
    critical|={'configs/s02_execution.json','TASK_SPEC.md','DECISIONS.md','docs/S02_EXEC_AUTH_01.json','docs/research/S02/PROTOCOL.md',
        'tools/s02_run.py','tests/test_s02_execution.py','tests/test_s02_models.py','reports/s02_preparation/BACKUP_MANIFEST.json',
        'reports/s02_preparation/RESTORE_RECEIPT.json','reports/s02_preparation/TEST_RESULTS.json','reports/s02_preparation/RESOURCE_PROFILE.json'}
    require(critical<=set(names),'Missing critical binding')
    for row in value['files']:
        n=row['path'];p=ROOT/n
        require(not PurePosixPath(n).is_absolute() and '..' not in PurePosixPath(n).parts and ':' not in n and '\\' not in n,'Unsafe manifest path')
        reject_redirected_path(p)
        require(p.stat().st_size==row['size'] and sha(p)==row['sha256'],'Manifest changed: '+n)
    review=json.loads((ROOT/REVIEW).read_bytes())
    require(review['status']=='TECHNICAL_PASS' and review['blocking_critical']==review['blocking_major']==0 and
        review['authorized_manifest_sha256']==sha(manifest),'Exact independent review required')
    return sha(manifest)

def preflight(c,output,backup):
    validate_config(c)
    require(now()<datetime.datetime.fromisoformat(CUTOFF),'Deadline passed')
    require(now()+datetime.timedelta(hours=4)<=datetime.datetime.fromisoformat(CUTOFF),'Four-hour window no longer fits')
    for p in (output,backup):reject_redirected_path(p)
    output=Path(output).resolve();backup=Path(backup).resolve()
    require(not output.exists() and not output.is_relative_to(ROOT) and not output.is_relative_to(backup),'New outside output required')
    require(path_digest(output)==c['private_output_sha256'] and path_digest(backup)==c['backup_root_sha256'],'Private binding mismatch')
    require(not (claims_root()/(c['campaign_id']+'.json')).exists(),'S02 authorization already consumed')
    require(git('branch','--show-current')=='codex/mosei-auto' and git('remote','get-url','origin')=='https://github.com/BiLiangXin/jingsai.git','Wrong repository')
    require(not git('status','--porcelain'),'Worktree/index/untracked not clean')
    head=git('rev-parse','HEAD');remote=git('ls-remote','origin','refs/heads/codex/mosei-auto').split()
    require(len(remote)==2 and remote[0]==head,'Remote mismatch')
    require(c==json.loads((ROOT/'configs/s02_execution.json').read_bytes()),'Not committed config')
    require(not git('diff','--name-only',BASE,'--','src/mosei/s01','src/mosei/data','research/r01','docs/research/R01','configs/s01_execution.json','state/LATEST_RUN.json'),'Old frozen implementation/state changed')
    contract=lambda t:[l for l in t.splitlines() if l.startswith('| D-DATA-')]
    require(contract(git('show',BASE+':DECISIONS.md'))==contract((ROOT/'DECISIONS.md').read_text(encoding='utf8')),'Data contract changed')
    old=json.loads((ROOT/'configs/s01_execution.json').read_bytes())
    require(old['training_authorized'] is False and old['authorization_status']=='CONSUMED','S01 must remain closed')
    auth=json.loads((ROOT/'docs/S02_EXEC_AUTH_01.json').read_bytes())
    require(auth['config_hash']==digest(c) and auth['authorization_id']=='S02-EXEC-AUTH-01' and auth['instruction_sha256']==c['instruction_sha256'],'User authorization scope mismatch')
    manifest=verify_manifest(c)
    b=json.loads((ROOT/'reports/s02_preparation/BACKUP_MANIFEST.json').read_bytes())
    require(b['status']=='PASS' and b['old_best_count']==b['old_last_count']==30,'Complete backup required')
    require(json.loads((ROOT/'reports/s02_preparation/RESTORE_RECEIPT.json').read_bytes())['status']=='PASS','Restore required')
    for r in b['files']:
        p=backup/r['path'];require(p.stat().st_size==r['size'] and sha(p)==r['sha256'],'Backup mutated')
    return dict(task_id=TASK,campaign_id=c['campaign_id'],commit=head,config_hash=digest(c),manifest_sha256=manifest,
        private_output_sha256=path_digest(output),backup_root_sha256=path_digest(backup))

def claim(c,binding):
    global ACTIVE
    require(ACTIVE is None,'Process already claimed')
    p=claims_root()/(c['campaign_id']+'.json')
    with p.open('x',encoding='utf8') as f:
        json.dump(dict(binding=binding,pid=os.getpid(),status='CONSUMED',time=now().isoformat()),f);f.flush();os.fsync(f.fileno())
    ACTIVE=dict(binding=binding,pid=os.getpid())

def require_active(c,*,split,optimizer=False):
    require(split in ('train','valid') and (not optimizer or split=='train'),'TEST/special/valid optimizer forbidden')
    require(ACTIVE is not None and ACTIVE['pid']==os.getpid() and ACTIVE['binding']['campaign_id']==c['campaign_id'] and ACTIVE['binding']['config_hash']==digest(c),'S02 claimed process required')
    on_disk=json.loads((claims_root()/(c['campaign_id']+'.json')).read_bytes())
    require(on_disk['pid']==os.getpid() and on_disk['binding']==ACTIVE['binding'],'Claim changed')

def stable_code(c):
    require_active(c,split='train')
    require(git('rev-parse','HEAD')==ACTIVE['binding']['commit'] and not git('status','--porcelain'),'Source tree changed during S02')
    require(verify_manifest(c)==ACTIVE['binding']['manifest_sha256'],'Execution manifest changed')
