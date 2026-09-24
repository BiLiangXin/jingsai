"""Read-only governance/safety audit for explicit R01-FREEZE-01 approval; no tests/train."""
import argparse,csv,hashlib,io,json,platform,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
BASE='120a0938c76dd457a3d95c5c2a243f3e451a3f67'
STATUS='FROZEN_FOR_S01_PROTOCOL'
sys.path.insert(0,str(ROOT/'tools'))
from stage_handoff import scan_tracked_public_tree,scan_public_bytes

def need(value,message):
    if not value:raise ValueError(message)
def git(*args):return subprocess.check_output(['git','--no-optional-locks',*args],cwd=ROOT)
def old(path):return git('show',BASE+':'+path)
def current(path):return (ROOT/path).read_bytes()
def load(path):return json.loads(current(path))
def sha(raw):return hashlib.sha256(raw).hexdigest()

def verify(index=False):
    checks=[]
    def check(name,value):need(value,name);checks.append(name)
    freeze=load('docs/research/R01/FREEZE_01.json');p=load('docs/research/R01/protocol.json');state=load('state/LATEST_RESEARCH.json')
    check('local_base',git('rev-parse','HEAD').decode().strip()==BASE)
    check('branch',git('branch','--show-current').decode().strip()=='codex/mosei-auto')
    check('origin',git('remote','get-url','origin').decode().strip()=='https://github.com/BiLiangXin/jingsai.git')
    check('owner_scope',freeze['status']==STATUS and freeze['approved_source_commit']==BASE and [i['number'] for i in freeze['approved_items']]==list(range(1,17)))
    for entry in freeze['approved_source_files']:
        raw=old(entry['path']);check('approved_source:'+entry['path'],sha(raw)==entry['sha256'] and len(raw)==entry['size_bytes'])
    check('current_governance',p['status']==state['research_status']==STATUS and state['approved_research_freeze'] is True)
    before=json.loads(old('docs/research/R01/protocol.json'))
    check('existing_protocol_values_preserved',all(p[k]==v for k,v in before.items() if k!='status'))
    check('null_resource_blocks_bulk_training',p['resource_walltime_cap'] is None and p['resource_walltime_cap_required_before_execution'] is True and p['bulk_training_allowed_when_walltime_cap_null'] is False)
    check('core_budget_and_masks',p['core_budget']==39 and p['fallback_caps']==[24,30] and p['fallback_selection_timing']=='BEFORE_EXECUTION_ONLY' and p['nominal_conditions']==96 and p['views_per_sample_per_seed']==144)
    check('no_execution_authority',p['training_authorized'] is False and state['s01_training_authorized'] is False and freeze['training_authorized'] is False and p['s01_spec_status']=='NOT_ACTIVATED')
    check('noncore_not_authorized',p['disabled_optional_blocks']==['D','T','L'] and p['expanded_cap_authorized'] is False and freeze['expanded_66_fit_authorized'] is False and freeze['q3_authorized'] is False and freeze['test_use_authorized'] is False and freeze['attachment3_4_research_read_authorized'] is False)
    check('deployment_unknown',p['attachment3_mask_availability']==state['attachment3_mask_availability']==freeze['attachment3_mask_availability']=='UNKNOWN' and freeze['natural_structural_zero_is_artificial_missing'] is False)
    check('no_new_metrics',p['predictive_metrics'] is None and state['metrics'] is None and freeze['metrics'] is None and state['official_model_experiments']=='NOT_RUN')
    contracts=lambda b:[line for line in b.decode('utf-8').splitlines() if line.startswith('| D-DATA-')]
    check('all_seven_data_rows_unchanged',len(contracts(current('DECISIONS.md')))==7 and contracts(old('DECISIONS.md'))==contracts(current('DECISIONS.md')))
    check('design_math_body_unchanged',old('docs/research/R01/DESIGN.md').decode().split('## 1.',1)[1]==current('docs/research/R01/DESIGN.md').decode().split('## 1.',1)[1])
    names=[v.decode() for v in git('ls-tree','-r','--name-only','-z',BASE).split(b'\0') if v]
    preserved=[p for p in names if p.startswith(('reports/','research/r01/')) or p in ('state/LATEST_RUN.json','TASK_SPEC.md','AGENTS.md','CHATGPT_REVIEW.md','docs/research/R01/decisions.json','docs/research/R01/CLOSEOUT.md','docs/research/R01/REVISION_TRACE.md','docs/research/R01/SOURCES.md','docs/research/R01/sources.json')]
    checkout_line_endings=[]
    for rel in preserved:
        base_raw=old(rel);index_raw=git('show',':'+rel);work_raw=current(rel)
        need(base_raw==index_raw,'historical index changed '+rel)
        need(base_raw.replace(b'\r\n',b'\n')==work_raw.replace(b'\r\n',b'\n'),'historical content changed '+rel)
        if base_raw!=work_raw:
            checkout_line_endings.append(dict(path=rel,classification='CRLF_ONLY_CHECKOUT_DIFFERENCE',git_sha256=sha(base_raw),git_size_bytes=len(base_raw),worktree_sha256=sha(work_raw),worktree_size_bytes=len(work_raw)))
    check('historical_paths_have_no_git_diff',not git('diff','--name-only',BASE,'--',*preserved).strip())
    checks.append('historical_git_blobs_exact_and_worktree_content_preserved')
    for filename in ('R01_experiment_matrix.csv','R01_ablation_matrix.csv'):
        rel='docs/research/R01/'+filename;prior=list(csv.DictReader(io.StringIO(old(rel).decode())));now=list(csv.DictReader(io.StringIO(current(rel).decode())))
        check(filename+':same_population_and_metrics',len(prior)==len(now) and all(all(b[k]==v for k,v in a.items() if k!='design_status') and b['execution_status']=='NOT_RUN' and b['metrics_value']=='null' and b['execution_authorized']=='false' for a,b in zip(prior,now)))
        core=lambda row:row['budget_block'] in ('B','PRIOR','LATE','C0','R0','CORE') if 'experiment' in filename else row['experiment_id'] in ('AB01','AB02','AB03','AB04','AB07')
        check(filename+':scoped_status',all(b['design_status']==(STATUS if core(b) else 'OUTSIDE_FROZEN_FIRST_ROUND') for b in now))
    trials=load('docs/research/R01/trials.json');old_trials=json.loads(old('docs/research/R01/trials.json'))
    check('trials_preserved_and_not_run',len(trials['trials'])==66 and all(all(b[k]==v for k,v in a.items()) and b['metrics'] is None and b['execution_status']=='NOT_RUN' and b['authorization'] is False for a,b in zip(old_trials['trials'],trials['trials'])))
    check('only39_protocol_frozen',sum(t['protocol_status']==STATUS for t in trials['trials'])==39 and trials['expanded_fits_authorized'] is False)
    register=load('docs/EXPERIMENT_REGISTER.json');prior=json.loads(old('docs/EXPERIMENT_REGISTER.json'))
    check('registry_history_preserved',all(register[k]==v for k,v in prior.items()))
    check('owner_event_registered',register['governance_events'][-1]['decision_id']=='R01-FREEZE-01' and register['governance_events'][-1]['training_authorized'] is False)
    manifest=load('reports/research/R01_FREEZE_01/MANIFEST.json');paths=manifest['publication_files']
    changed={v.decode() for v in git('diff','--name-only','HEAD','-z').split(b'\0') if v};new={v.decode() for v in git('ls-files','--others','--exclude-standard','-z').split(b'\0') if v}
    check('exact_task_changes',changed|new==set(paths))
    for entry in manifest['files']:
        raw=current(entry['path']);need(sha(raw)==entry['sha256'] and len(raw)==entry['size_bytes'],'payload hash mismatch')
    checks.append('payload_hashes_match')
    for rel in paths:need(not scan_public_bytes(rel,current(rel)),'unsafe candidate '+rel)
    scan=scan_tracked_public_tree(ROOT);check('tracked_tree_index_worktree_scan',not scan['findings'])
    if index:
        staged={v.decode() for v in git('diff','--cached','--name-only','-z').split(b'\0') if v}
        check('exact_staged_set',staged==set(paths))
        check('index_worktree_bytes_equal',all(git('show',':'+rel)==current(rel) for rel in paths))
    return dict(status='PASS',scope='GOVERNANCE_AND_SAFETY_ONLY',mode='INDEX' if index else 'PRESTAGE',checks_passed=len(checks),checks=checks,approved_source_commit=BASE,preserved_existing_files=len(preserved),checkout_line_ending_differences=checkout_line_endings,prior_attempt=dict(exit_code=1,reason='Overstrict raw Git/worktree equality rejected existing CRLF checkout in reports/bootstrap/DOCTOR.json',resolution='Verify exact historical index blobs and content equality permitting only CRLF/LF; require no Git diff; record both raw hashes; historical files not edited'),tracked_text_files_scanned=scan['scanned_text_files'],candidate_files_scanned=len(paths),payload_files_sha256_verified=len(manifest['files']),findings=scan['findings'],environment=dict(python=platform.python_version(),system=platform.system()),command='python -X utf8 -B reports/research/R01_FREEZE_01/verify_freeze.py'+(' --index' if index else '')+' --output <RESULT_JSON>',exit_code=0,model_tests_run=False,synthetic_tests_rerun=False,official_model_experiments='NOT_RUN',metrics=None)
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--index',action='store_true');a.add_argument('--output',type=Path,required=True);args=a.parse_args();result=verify(args.index)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps({k:result[k] for k in ('status','scope','mode','checks_passed','preserved_existing_files','tracked_text_files_scanned','candidate_files_scanned','exit_code')}))
