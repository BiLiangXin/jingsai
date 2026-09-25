"""S03 exact-path publication audit, including all tracked index/worktree files."""
import argparse,hashlib,io,json,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
from s01_campaign_publication_check import safe_relative,no_redirect,read_public,names,LEGACY_PROBLEM_ASSETS,verify_legacy_problem_asset
from stage_handoff import scan_public_bytes,scan_text,RAW_ID,forbidden_path
ROOT=Path(__file__).resolve().parents[1]
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def need(ok,message):
    if not ok:raise ValueError(message)
def audit(manifest):
    head=git('rev-parse','HEAD').decode().strip();need(head==manifest['base_commit'],'Base moved')
    need(git('branch','--show-current').decode().strip()=='codex/mosei-auto','Wrong branch')
    need(git('remote','get-url','origin').decode().strip()=='https://github.com/BiLiangXin/jingsai.git','Wrong origin')
    need(git('ls-remote','origin','refs/heads/codex/mosei-auto').decode().split()[0]==head,'Remote moved')
    candidates={r['path']:r for r in manifest['files']};need(len(candidates)==len(manifest['files']),'Duplicate candidates')
    changed=names(git('diff','--name-only','HEAD','-z'))|names(git('ls-files','--others','--exclude-standard','-z'))
    staged=names(git('diff','--cached','--name-only','-z'))
    need(changed==set(candidates) and staged<=changed,'Unexpected worktree/index paths')
    need(not git('ls-files','--unmerged','-z'),'Unmerged files')
    figures=json.loads((ROOT/'reports/s03_readiness/figures/MANIFEST.json').read_bytes())
    fig_hash={r['path']:r['sha256'] for r in figures['figures']}
    def scan(rel,blob):
        suffix=Path(rel).suffix
        if suffix in ['.png','.svg']:
            need(rel in fig_hash and hashlib.sha256(blob).hexdigest()==fig_hash[rel],'Unbound figure')
            if suffix=='.png':
                with Image.open(io.BytesIO(blob)) as image:
                    image.verify()
                with Image.open(io.BytesIO(blob)) as image:need(not scan_text(json.dumps(image.info)),'Unsafe figure metadata')
            else:
                xml=ET.fromstring(blob)
                for node in xml.iter():
                    need(node.tag.split('}')[-1] not in ['script','foreignObject','image'],'Active/embedded SVG payload')
                    for k,v in node.attrib.items():
                        if k.endswith('href'):need(v.startswith('#'),'External SVG reference')
                need(not scan_text(blob.decode()),'Unsafe SVG text')
            return []
        return scan_public_bytes(rel,blob)
    for rel,row in candidates.items():
        safe_relative(rel);blob=read_public(ROOT,rel)
        need(len(blob)==row['size'] and hashlib.sha256(blob).hexdigest()==row['sha256'],'Candidate changed')
        need(Path(rel).suffix in {'.py','.json','.md','.csv','.log','.png','.svg'},'Unsupported new type')
        need(not scan(rel,blob),'Candidate safety finding: '+rel)
    tracked=names(git('ls-files','-z'));assets=[];findings=[]
    for rel in sorted(tracked):
        safe_relative(rel);need(not forbidden_path(rel),'Forbidden tracked path');work=read_public(ROOT,rel);index=git('show',':'+rel)
        if rel in LEGACY_PROBLEM_ASSETS:
            assets.append(verify_legacy_problem_asset(ROOT,rel,work,index,scan_text,RAW_ID));continue
        for surface,blob in [('worktree',work),('index',index)]:
            issues=scan(rel,blob)
            if issues:findings.append(dict(path=rel,surface=surface,issues=issues))
        if rel in staged:need(work.replace(b'\r\n',b'\n')==index.replace(b'\r\n',b'\n'),'Staged differs from worktree')
    need(not findings,'Tracked safety findings: '+json.dumps(findings))
    frozen=['src/mosei/s01','src/mosei/s02','src/mosei/data','research/r01','docs/research/R01','configs/s01_execution.json','configs/s02_execution.json','state/LATEST_RUN.json','CHATGPT_REVIEW.md','tools/mosei_flow.py','tools/flowlib','tools/gate.py','schemas']
    need(not git('diff','--name-only','d61e399c94719d871aee0bec71210aebf7a11aab','--',*frozen),'Historical/protected files changed')
    for phase in ['s01','s02']:
        cfg=json.loads((ROOT/f'configs/{phase}_execution.json').read_bytes());need(not cfg['training_authorized'] and cfg['authorization_status']=='CONSUMED','Prior authorization reopened')
    rows=lambda text:[s for s in text.splitlines() if s.startswith('| D-DATA-')]
    need(rows(git('show','d61e399c94719d871aee0bec71210aebf7a11aab:DECISIONS.md').decode())==rows((ROOT/'DECISIONS.md').read_text(encoding='utf-8')),'Frozen data contract changed')
    need('E题数据/' in (ROOT/'.gitignore').read_text(encoding='utf-8'),'Data ignore missing')
    return dict(status='PASS',head=head,candidate_count=len(candidates),staged_count=len(staged),exact_staged_set=staged==set(candidates),tracked_files_scanned=len(tracked),index_and_worktree_scanned=True,findings=[],legacy_problem_assets=assets,whole_tree_claimed_free_of_sample_content=False,frozen_history_unchanged=True,files=sorted(candidates))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output)
    need(not out.exists() and not out.resolve().is_relative_to(ROOT),'New external receipt required')
    try:result=audit(json.loads(Path(a.manifest).read_bytes()));code=0
    except Exception as e:result={'status':'FAIL','error':str(e)};code=1
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps({'status':result['status'],'error':result.get('error')}));raise SystemExit(code)
