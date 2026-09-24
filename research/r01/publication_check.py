"""R01 publication check only: scan and verify explicit paths; never stage/publish."""
import argparse,csv,hashlib,json,subprocess,sys
from pathlib import Path,PurePosixPath
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from stage_handoff import scan_tracked_public_tree,scan_public_bytes,forbidden_path

def need(v,msg):
    if not v:raise ValueError(msg)
def git(*args):return subprocess.check_output(['git','--no-optional-locks',*args],cwd=ROOT)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check(manifest,index=False):
    m=json.loads(manifest.read_text(encoding='utf-8'));allowed=m['publication_files']
    need(len(allowed)==len(set(allowed))==len({p.casefold() for p in allowed}),'duplicate paths')
    changed=set(x.decode() for x in git('diff','--name-only','HEAD','-z').split(b'\0') if x)
    untracked=set(x.decode() for x in git('ls-files','--others','--exclude-standard','-z').split(b'\0') if x)
    need(changed|untracked==set(allowed),'unexpected or missing task paths')
    need(git('rev-parse','HEAD').decode().strip()==m['base_commit'],'base HEAD changed')
    need(git('branch','--show-current').decode().strip()=='codex/mosei-auto','wrong branch')
    need(git('remote','get-url','origin').decode().strip()=='https://github.com/BiLiangXin/jingsai.git','wrong remote')
    for rel in allowed:
        p=PurePosixPath(rel);path=ROOT/rel
        need(not p.is_absolute() and '..' not in p.parts and '\\' not in rel and ':' not in rel,'unsafe path')
        need(not forbidden_path(rel) and p.suffix in ('.md','.json','.csv','.py'),'forbidden publication path')
        need(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(ROOT),'linked path')
        need(not scan_public_bytes(rel,path.read_bytes()),'unsafe content at '+rel)
    for entry in m['files']:
        path=ROOT/entry['path'];need(digest(path)==entry['sha256'] and path.stat().st_size==entry['size_bytes'],'payload fingerprint mismatch '+entry['path'])
    scan=scan_tracked_public_tree(ROOT);need(not scan['findings'],'tracked tree/index unsafe')
    if index:
        staged={x.decode() for x in git('diff','--cached','--name-only','-z').split(b'\0') if x}
        need(staged==set(allowed),'staged set not exact')
        for rel in allowed:need(git('show',':'+rel)==(ROOT/rel).read_bytes(),'index/worktree byte mismatch '+rel)
    frozen=lambda text:[line for line in text.splitlines() if line.startswith('| D-DATA-')]
    need(frozen(git('show',m['base_commit']+':DECISIONS.md').decode())==frozen((ROOT/'DECISIONS.md').read_text(encoding='utf-8')),'frozen contract changed')
    need(git('show',m['base_commit']+':state/LATEST_RUN.json')==(ROOT/'state/LATEST_RUN.json').read_bytes(),'LATEST_RUN changed')
    trials=json.loads((ROOT/'docs/research/R01/trials.json').read_text(encoding='utf-8'))['trials']
    need(len(trials)==66 and len({t['trial_id'] for t in trials})==66,'finite trial enumeration')
    need(sum(t['enabled_proposal'] for t in trials)==39,'core cap')
    need(all(t['execution_status']=='NOT_RUN' and t['metrics'] is None and t['authorization'] is False for t in trials),'invented trial result or authorization')
    protocol=json.loads((ROOT/'docs/research/R01/protocol.json').read_text(encoding='utf-8'))
    need(sum(protocol['runs_by_block'].values())==66 and protocol['training_authorized'] is False,'budget or authorization')
    for name in ('R01_experiment_matrix.csv','R01_ablation_matrix.csv'):
        rows=list(csv.DictReader((ROOT/'docs/research/R01'/name).open(encoding='utf-8')))
        need(all(r['execution_status']=='NOT_RUN' and r['metrics_value']=='null' for r in rows),'matrix real result')
        total=sum(int(r['new_training_runs']) for r in rows);need(total==(66 if 'experiment' in name else 0),'matrix budget')
    checks=json.loads((ROOT/'reports/research/R01_LOCAL_CLOSEOUT/checks.json').read_text(encoding='utf-8'))
    need(checks['exit_code']==0 and checks['failures']==checks['errors']==checks['skipped']==0,'reference checks failed')
    for rel,h in checks['source_sha256'].items():need(digest(ROOT/rel)==h,'tested source changed')
    decisions=json.loads((ROOT/'docs/research/R01/decisions.json').read_text(encoding='utf-8'))
    need(len(decisions)==11 and all(x['status']=='PROVISIONAL' and x['approved'] is False for x in decisions),'self-approved decisions')
    return {'status':'PASS','mode':'INDEX_AND_WORKTREE' if index else 'PRESTAGE_TRACKED_AND_CANDIDATE','base_commit':m['base_commit'],'publication_file_count':len(allowed),'payload_hashes_checked':len(m['files']),'tracked_text_files_scanned':scan['scanned_text_files'],'findings':scan['findings'],'candidate_paths_scanned':len(allowed),'exact_staged_set_verified':index,'index_equals_worktree_verified':index,'latest_run_unchanged':True,'data_contract_unchanged':True,'finite_budget_checks':True,'model_experiments':'NOT_RUN','exit_code':0,'limitations':['Pattern/content scan is not a universal secrecy proof','Historical Git objects were not republished or inspected for sample contents'],'command':'python -X utf8 -B research/r01/publication_check.py --manifest reports/research/R01_LOCAL_CLOSEOUT/MANIFEST.json'+(' --index' if index else '')+' --output <RESULT_JSON>'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--index',action='store_true');a=p.parse_args()
    result=check(a.manifest,a.index);a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
