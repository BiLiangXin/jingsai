"""Read-only S02 publication gate; exact new payload plus entire index/worktree."""
import argparse,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
from s01_campaign_publication_check import (git,need,names,safe_relative,no_redirect,read_public,unique_json,
    LEGACY_PROBLEM_ASSETS,verify_legacy_problem_asset,SUFFIXES)
from stage_handoff import scan_public_bytes,scan_text,RAW_ID,forbidden_path

def check(root,manifest_path,mode):
    root=root.resolve();no_redirect(root);manifest=unique_json(manifest_path.read_bytes());head=git(root,'rev-parse','HEAD').decode().strip()
    need(git(root,'branch','--show-current').decode().strip()=='codex/mosei-auto','Wrong branch')
    need(git(root,'remote','get-url','origin').decode().strip()=='https://github.com/BiLiangXin/jingsai.git','Wrong origin')
    remote=git(root,'ls-remote','origin','refs/heads/codex/mosei-auto').decode().split()
    need(remote==[head,'refs/heads/codex/mosei-auto'] and manifest['base_commit']==head,'HEAD binding mismatch')
    allowed=set(manifest['publication_files']);need(len(allowed)==len(manifest['publication_files']),'Duplicate publication file')
    need(len(allowed)==len({p.casefold() for p in allowed}),'Case alias')
    mp=manifest_path.resolve().relative_to(root).as_posix();need(manifest['hash_exclusions']==[mp] and mp in allowed,'Only self excluded')
    rows=manifest['files'];need({r['path'] for r in rows}==allowed-{mp} and len(rows)==len(allowed)-1,'Exact payload hashes required')
    changed=names(git(root,'diff','--name-only','HEAD','-z'))|names(git(root,'ls-files','--others','--exclude-standard','-z'))
    staged=names(git(root,'diff','--cached','--name-only','-z'));need(changed==allowed and staged<=allowed,'Unexpected worktree/index/untracked files')
    need(not git(root,'ls-files','--unmerged','-z'),'Unmerged index')
    findings=[];assets=[]
    for rel in sorted(allowed):
        p=safe_relative(rel);need(p.suffix in SUFFIXES and rel not in LEGACY_PROBLEM_ASSETS,'Unexpected candidate type')
        blob=read_public(root,rel);issues=scan_public_bytes(rel,blob)
        if issues:findings.append(dict(path=rel,surface='candidate',issues=issues))
        if rel in staged:need(git(root,'show',':'+rel)==blob,'Index/worktree byte mismatch')
    for r in rows:
        blob=read_public(root,r['path']);need(len(blob)==r['size'] and hashlib.sha256(blob).hexdigest()==r['sha256'],'Payload changed')
    tracked=names(git(root,'ls-files','-z'))
    for rel in sorted(tracked):
        safe_relative(rel);need(not forbidden_path(rel),'Forbidden tracked file')
        work=read_public(root,rel);index=git(root,'show',':'+rel)
        if rel in LEGACY_PROBLEM_ASSETS:
            assets.append(verify_legacy_problem_asset(root,rel,work,index,scan_text,RAW_ID));continue
        for surface,blob in [('worktree',work),('index',index)]:
            issues=scan_public_bytes(rel,blob)
            if issues:findings.append(dict(path=rel,surface=surface,issues=issues))
    need(not findings,'Safety findings: '+json.dumps(findings))
    frozen=('src/mosei/s01','src/mosei/data','research/r01','docs/research/R01','configs/s01_execution.json','state/LATEST_RUN.json')
    need(not git(root,'diff','--name-only','95342eb58bf0494bcc90934f76958b71becb8687','--',*frozen),'S01/R01 frozen paths changed')
    rows_of=lambda t:[s for s in t.splitlines() if s.startswith('| D-DATA-')]
    need(rows_of(git(root,'show','95342eb58bf0494bcc90934f76958b71becb8687:DECISIONS.md').decode())==rows_of((root/'DECISIONS.md').read_text(encoding='utf8')),'D-DATA changed')
    old=unique_json((root/'configs/s01_execution.json').read_bytes());need(old['training_authorized'] is False and old['authorization_status']=='CONSUMED','S01 reopened')
    c=unique_json((root/'configs/s02_execution.json').read_bytes())
    sys.path.insert(0,str(root/'src'))
    from mosei.s02 import authorization as auth
    if mode=='activation':auth.validate_config(c);auth.verify_manifest(c)
    else:need(c['training_authorized'] is False and c['authorization_status']=='CONSUMED','S02 not closed')
    probes=['E题数据/probe.dat','configs/paths.local.json','.env','probe.pkl','probe.mp4','probe.pt','probe.ckpt']
    ignored=names(git(root,'check-ignore','--no-index','-z','--stdin',input_bytes=('\0'.join(probes)+'\0').encode()))
    need(ignored==set(probes),'Ignore protections missing')
    return dict(status='PASS',head=head,remote_head=remote[0],mode=mode,publication_files=sorted(allowed),
        exact_staged_set=staged==allowed,staged_count=len(staged),tracked_index_and_worktree_scanned=len(tracked),
        findings=findings,legacy_problem_assets=assets,whole_tree_claimed_free_of_sample_content=False,
        candidate_payload_sample_records=False,frozen_s01_r01_and_data_contract_unchanged=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--mode',choices=['activation','results'],required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    root=Path(__file__).resolve().parents[1];need(not a.output.exists() and not a.output.resolve().is_relative_to(root),'New outside receipt required')
    try:r=check(root,a.manifest,a.mode);code=0
    except Exception as e:r=dict(status='FAIL',error=type(e).__name__+': '+str(e));code=1
    a.output.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n',encoding='utf8');print(json.dumps(dict(status=r['status'],exit_code=code)));return code
if __name__=='__main__':raise SystemExit(main())
