"""One conditional, committed-gate Attachment3 inference; no Attachment4 access."""
import argparse,csv,datetime,hashlib,json,pickle,subprocess,sys,re,os
from pathlib import Path,PurePosixPath
import numpy as np
import torch
from s03_evaluate import ROOT,CONFIG,guard,restore,sha,save,state_digest,infer
from mosei.s01.contracts import MODS,DIMS,configure_runtime,require,digest
from mosei.data.masks import support_from_text_bert
from mosei.s03.core import adapter

CHECKPOINT='f99426be8d90b8abf196faf9cf92a41c5ab607da661a7a91530f1fe481a0ceb9'
SCALER='83a95b4acd9254fdd20675832ca4d25ed9e5bd62f284e7ec48e3cc6cb996cf2e'
FINAL='reports/s03_readiness/FINAL_MANIFEST.json'

def verify_review_binding(manifest,review,gate,manifest_hash):
    required={'tools/s04_infer.py','tools/s03_evaluate.py','configs/s03_execution.json','docs/research/S03/FINAL_INFERENCE_SPEC.md','research/r01/reference.py','reports/s03_readiness/DEPLOYMENT.json','reports/s03_readiness/RESTORE.json','reports/s03_readiness/TESTS.json','reports/s02_execution/S02-20260925-BOUNDED-12F15W/FITS.json','reports/s02_execution/S02-20260925-BOUNDED-12F15W/MODEL_REGISTRY.json'}
    required.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'src/mosei').rglob('*.py'))
    rows=manifest['critical_files'];mapping={r['path']:r['sha256'] for r in rows}
    require(bool(rows) and len(mapping)==len(rows) and required<=set(mapping),'Incomplete critical manifest')
    for path in mapping:
        posix=PurePosixPath(path);require(not posix.is_absolute() and '..' not in posix.parts and '\\' not in path and ':' not in path,'Unsafe critical path')
    require(review['status']=='PASS' and review['independent'] is True,'Independent review missing')
    require(review['review_inputs_sha256']==manifest_hash==gate['manifest_sha256'],'Review/manifest digest mismatch')
    reviewed={r['path']:r['sha256'] for r in review['critical_files']}
    require(reviewed==mapping and len(reviewed)==len(review['critical_files']),'Review source set mismatch')
    require(gate['checkpoint_sha256']==CHECKPOINT and gate['normalizer_sha256']==SCALER,'Fixed predictor binding changed')
    return rows

def select_aligned_files(folder):
    paths=sorted(folder.rglob('*.pkl'),key=lambda p:p.relative_to(folder).as_posix())
    chosen=[];excluded=[]
    for p in paths:
        require(not p.is_symlink() and p.resolve().is_relative_to(folder.resolve()),'Redirected source path')
        name=p.relative_to(folder).as_posix().lower()
        # Reuse the Chinese/English convention already present in the S00B inventory.
        if '未对齐' in name or re.search(r'(?<![a-z])unaligned(?![a-z])',name):excluded.append(p)
        elif '对齐' in name or re.search(r'(?<![a-z])aligned(?![a-z])',name):chosen.append(p)
        else:raise ValueError('Feature version not identifiable from existing filename/directory convention')
    require(len(chosen)==30 and len(excluded)==30,'Existing aligned30/unaligned30 inventory changed')
    return chosen

def claim_once(output):
    require(hashlib.sha256(str(output.resolve()).encode()).hexdigest()==CONFIG['attachment3_output_binding_sha256'],'Unbound private output')
    claims=Path.home()/'.codex'/'mosei_execution_claims';claims.mkdir(exist_ok=True)
    path=claims/(CONFIG['attachment3_claim_id']+'.json')
    with path.open('x',encoding='utf-8') as f:
        json.dump(dict(task=CONFIG['attachment3_claim_id'],time=datetime.datetime.now(datetime.timezone.utc).isoformat()),f);f.flush();os.fsync(f.fileno())
    return path

def recover_precontent_once(output,head):
    """Append one audited recovery event, never delete/reset the original claim."""
    require(hashlib.sha256(str(output.resolve()).encode()).hexdigest()==CONFIG['attachment3_output_binding_sha256'],'Unbound recovery output')
    rule=CONFIG['precontent_recovery_01'];require(rule['max_recoveries']==1,'Invalid recovery budget')
    require({p.name for p in output.iterdir()}=={'ATTACHMENT3_CLAIM.json','FAILURE_PRIVATE.json'},'Any content/progress/additional output blocks recovery')
    old=output/'ATTACHMENT3_CLAIM.json';failure=output/'FAILURE_PRIVATE.json'
    require(sha(old)==rule['original_claim_receipt_sha256'] and sha(failure)==rule['original_failure_sha256'],'Prior failure proof changed')
    receipt=json.loads(old.read_bytes());error=json.loads(failure.read_bytes())
    require(receipt['commit']==rule['original_commit'],'Prior commit mismatch')
    require(error=={'status':'BLOCKED','error_type':'ValueError','error':'Feature version not identifiable from existing filename/directory convention'},'Not the proven precontent path failure')
    claims=Path.home()/'.codex'/'mosei_execution_claims';original=claims/(CONFIG['attachment3_claim_id']+'.json')
    require(sha(original)==rule['original_global_claim_sha256']==receipt['claim_sha256'],'Original task claim changed')
    event=claims/(CONFIG['attachment3_claim_id']+'.RECOVERY01.json')
    record=dict(status='APPENDED_PRECONTENT_RECOVERY_ONLY',original_claim_sha256=sha(original),prior_failure_sha256=sha(failure),prior_commit=receipt['commit'],execution_commit=head,time=datetime.datetime.now(datetime.timezone.utc).isoformat(),no_more_recoveries=True)
    with event.open('x',encoding='utf-8') as f:json.dump(record,f);f.flush();os.fsync(f.fileno())
    save(output/'RECOVERY01.json',record)
    return event

def validate_special(item):
    require(isinstance(item,dict),'Feature dictionary required')
    # A special-file serialization wrapper named test is not the Attachment2 TEST split.
    # This reader is reachable only for the gated Attachment3 source directory.
    if len(item)==1 and next(iter(item)) in {'data','special','test'}:item=item[next(iter(item))]
    require(isinstance(item,dict),'Feature dictionary required')
    require(not set(item)&{'label','labels','classification_labels','regression_labels','target','targets','train','valid','test'},'Label/split schema not permitted')
    arrays={m:np.asarray(item[m]) for m in MODS}
    unbatched=arrays['text'].shape==(50,DIMS['text'])
    if unbatched:arrays={m:v[None] for m,v in arrays.items()}
    n=arrays['text'].shape[0]
    require(n>0,'Empty source')
    for m in MODS:require(arrays[m].shape==(n,50,DIMS[m]) and np.issubdtype(arrays[m].dtype,np.number) and np.isfinite(arrays[m]).all(),'Invalid continuous schema')
    bert=np.asarray(item['text_bert'])
    if unbatched and bert.shape==(3,50):bert=bert[None]
    support=support_from_text_bert(bert)
    require(support.shape==(n,50),'Support population')
    ids=[k for k in ('id','ids') if k in item];require(len(ids)<=1,'Ambiguous identifier fields')
    if ids:
        source=item[ids[0]]
        if n==1 and isinstance(source,(str,int,float,np.generic)):source=[source]
        require(len(source)==n,'Identifier length')
        def scalar(v):
            if isinstance(v,np.generic):v=v.item()
            require(isinstance(v,(str,int,float)) and not isinstance(v,bool),'Identifier scalar type')
            if isinstance(v,float):require(np.isfinite(v),'Identifier finite')
            return v
        names=[]
        for v in source:
            if isinstance(v,(list,tuple,np.ndarray)):names.append(json.dumps([scalar(w) for w in v],ensure_ascii=False,separators=(',',':')))
            else:names.append(str(scalar(v)))
    else:names=[str(i) for i in range(n)]
    require(len(set(names))==n and all(names),'Duplicate/empty identifiers')
    return arrays,support,names

def preflight():
    guard()
    git=lambda *args:subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
    require(git('branch','--show-current')=='codex/mosei-auto','Branch')
    require(git('remote','get-url','origin')=='https://github.com/BiLiangXin/jingsai.git','Origin')
    require(not git('status','--porcelain'),'Dirty worktree/index')
    head=git('rev-parse','HEAD');remote=git('ls-remote','origin','refs/heads/codex/mosei-auto').split()[0];require(head==remote,'Local/remote mismatch')
    gate_path=ROOT/'reports/s03_readiness/Q2_GATE.json';gate=json.loads(gate_path.read_bytes());require(gate['status']=='PASS','Q2 gate blocked')
    manifest_path=ROOT/FINAL;manifest=json.loads(manifest_path.read_bytes())
    review_path=ROOT/gate['review_path'];require(sha(review_path)==gate['review_sha256'],'Review receipt changed')
    review=json.loads(review_path.read_bytes())
    rows=verify_review_binding(manifest,review,gate,sha(manifest_path))
    for entry in rows:
        p=ROOT/entry['path'];require(sha(p)==entry['sha256'],'Changed frozen file')
        committed=subprocess.check_output(['git','show',head+':'+entry['path']],cwd=ROOT)
        require(hashlib.sha256(committed.replace(b'\r\n',b'\n')).hexdigest()==hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),'File not committed')
    for p in [gate_path,manifest_path,review_path]:
        rel=p.relative_to(ROOT).as_posix();require(git('ls-files','--error-unmatch',rel),'Gate/manifest/review not tracked')
        committed=subprocess.check_output(['git','show',head+':'+rel],cwd=ROOT)
        require(committed.replace(b'\r\n',b'\n')==p.read_bytes().replace(b'\r\n',b'\n'),'Uncommitted gate/review')
    deploy=json.loads((ROOT/'reports/s03_readiness/DEPLOYMENT.json').read_bytes());require(deploy['status']=='PASS' and deploy['selected_profile']==gate['profile'],'Profile changed')
    return gate,head

def main():
    p=argparse.ArgumentParser();p.add_argument('--source-dir',required=True);p.add_argument('--campaign',required=True);p.add_argument('--output',required=True);p.add_argument('--recover-precontent-path-failure',action='store_true');a=p.parse_args()
    configure_runtime();gate,head=preflight();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    # Restore and bind every predictor dependency BEFORE any special content is opened.
    campaign=Path(a.campaign);require(sha(campaign/'M2-s17/best.pt')==CHECKPOINT,'Fixed checkpoint mismatch')
    model,norm,ck=restore(campaign,17);before=state_digest(model)
    require(digest(ck['normalizer'])==SCALER,'Fixed scaler mismatch')
    if a.recover_precontent_path_failure:claim=recover_precontent_once(out,head)
    else:
        claim=claim_once(out)
        save(out/'ATTACHMENT3_CLAIM.json',dict(commit=head,gate_sha256=sha(ROOT/'reports/s03_readiness/Q2_GATE.json'),claim_sha256=sha(claim)))
    try:
        folder=Path(a.source_dir);require(folder.name=='附件3-模态缺失特征样本','Wrong special source')
        files=select_aligned_files(folder);rows=[];source_manifest=[];count=0
        # Persist before any source-content hash/read, so later recovery is impossible.
        with (out/'CONTENT_OPENED.json').open('x',encoding='utf-8') as f:json.dump(dict(commit=head,about_to_read_content=True,aligned_files=30),f)
        for source in files:
            guard();source_hash=sha(source);rel=source.relative_to(folder).as_posix()
            with source.open('rb') as f:item=pickle.load(f)
            arrays,support,names=validate_special(item);del item
            source_manifest.append(dict(path=rel,sha256=source_hash,size=source.stat().st_size,rows=len(names)))
            for start in range(0,len(names),32):
                guard();end=min(start+32,len(names));visible={m:torch.tensor(arrays[m][start:end],dtype=torch.float32,device='cuda') for m in MODS};s=torch.tensor(support[start:end],dtype=torch.bool,device='cuda')
                pred=infer(model,adapter(visible,s,norm,gate['profile']))
                for j in range(end-start):
                    value=float(pred['regression'][j]);require(np.isfinite(value) and -3<=value<=3,'Invalid prediction range')
                    identity=json.dumps([rel,names[start+j]],ensure_ascii=False,separators=(',',':'))
                    rows.append(dict(sample_index=count+start+j,source_file=rel,source_row=start+j,sample_id=identity,polarity=['Negative','Neutral','Positive'][int(pred['logits'][j].argmax())],intensity=value))
            count+=len(names);require(sha(source)==source_hash,'Source changed')
        require(len(rows)==count and state_digest(model)==before,'Count/state invariant')
        save(out/'SOURCE_MANIFEST_PRIVATE.json',source_manifest)
        dest=out/'attachment3_predictions.csv'
        with dest.open('x',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,['sample_index','source_file','source_row','sample_id','polarity','intensity']);w.writeheader();w.writerows(rows)
        with dest.open(newline='',encoding='utf-8') as f:check=list(csv.DictReader(f))
        require(len(check)==count and len({r['sample_id'] for r in check})==count,'Output round-trip')
        report=dict(status='COMPLETED',commit=head,profile=gate['profile'],aligned_files=30,unaligned_files_not_read=30,rows=len(rows),source_manifest_sha256=sha(out/'SOURCE_MANIFEST_PRIVATE.json'),output_sha256=sha(dest),checkpoint_sha256=sha(campaign/'M2-s17/best.pt'),schema_checks='PASS',metrics=None,model_unchanged=True,attachment4_opened=False)
        save(out/'RESULT.json',report);save(ROOT/'reports/s03_readiness/ATTACHMENT3_RESULT.json',report);print(json.dumps(report))
    except Exception as e:
        failure_name='FAILURE_RECOVERY01_PRIVATE.json' if a.recover_precontent_path_failure else 'FAILURE_PRIVATE.json'
        save(out/failure_name,dict(status='BLOCKED',error_type=type(e).__name__,error=str(e)));raise
if __name__=='__main__':main()
