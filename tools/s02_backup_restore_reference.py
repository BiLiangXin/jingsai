# Historical S02 preparation implementation, path bindings parameterized for privacy.
# Executed original SHA256 is in reports/s02_preparation/ACTUAL_COMMANDS.json.
# Logic preserved including legacy exact-value/bitwise wording corrected by independent companion.
# Final independent pre/post snapshots and external deadline supervisor supplement this historical script.
"""S02 preregistered read-only S01 backup and checkpoint recovery audit."""
import datetime, hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('action',choices=['backup','restore'])
for name in ('root','old','work','source'):parser.add_argument('--'+name,type=Path,required=True)
args=parser.parse_args()
ROOT=args.root;OLD=args.old;WORK=args.work;SOURCE=args.source
BACKUP=WORK/'S01_INDEPENDENT_BACKUP'
SOURCE_HASH='66e867aa74bc70a844e806e5571e371c9abb4a35f9e2887ce9b4d97ff2cb8fcd'
def check(ok, why):
    if not ok: raise ValueError(why)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()
def write(p,v):
    Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf8')
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT).decode().strip()
def backup():
    check(git('rev-parse','HEAD')=='95342eb58bf0494bcc90934f76958b71becb8687','Unexpected baseline HEAD')
    check(not git('status','--porcelain'),'Unexpected worktree changes before backup')
    check(not BACKUP.exists(),'Backup directory already exists; no overwrite')
    BACKUP.mkdir()
    rows=[]
    paths=[('campaign/'+p.relative_to(OLD).as_posix(),p) for p in sorted(OLD.rglob('*')) if p.is_file()]
    paths += [('repository/'+n,ROOT/n) for n in git('ls-files').splitlines() if not n.startswith('"')]
    # git -z avoids quoted non-ASCII paths; include every tracked file.
    tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    paths=[r for r in paths if not r[0].startswith('repository/')]+[('repository/'+n,ROOT/n) for n in tracked if n]
    for rel,src in paths:
        check(not src.is_symlink() and not (src.stat().st_file_attributes & 1024),'Reparse point rejected')
        dst=BACKUP/rel;dst.parent.mkdir(parents=True,exist_ok=True)
        before=(src.stat().st_size,sha(src));shutil.copyfile(src,dst)
        check(before==(dst.stat().st_size,sha(dst))==(src.stat().st_size,sha(src)),'Backup mismatch')
        check(not os.path.samefile(src,dst),'Hardlink/source alias rejected')
        rows.append(dict(path=rel,size=before[0],sha256=before[1],source=str(src),backup=str(dst)))
    for commit in ('98c2b20a3ea8b01d99b6500fbf27e91ea59c5cb7','95342eb58bf0494bcc90934f76958b71becb8687'):
        out=BACKUP/(commit+'.zip')
        subprocess.run(['git','archive','--format=zip','-o',str(out),commit],cwd=ROOT,check=True)
    write(WORK/'backup_private_manifest.json',rows)
    public=[{k:v for k,v in r.items() if k not in ('source','backup')} for r in rows]
    write(WORK/'backup_public_manifest.json',dict(status='PASS',ordinary_independent_copies=True,files=public,
         count=len(rows),total_bytes=sum(r['size'] for r in rows),baseline_commit=git('rev-parse','HEAD'),
         old_best_count=len(list((BACKUP/'campaign').glob('*/best.pt'))),old_last_count=len(list((BACKUP/'campaign').glob('*/last.pt')))))
    print(json.dumps(dict(event='BACKUP_PASS',files=len(rows),bytes=sum(r['size'] for r in rows))),flush=True)
def restore():
    check((WORK/'backup_public_manifest.json').is_file(),'Backup required')
    # Written with exclusive creation BEFORE source access / inference, never after observing differences.
    policy=dict(evidence='SPECIFIED_BEFORE_RESTORE',metric_abs_tolerance=1e-7,classification_confusion_exact=True,
        original_vs_backup_prediction_atol=0.0,original_vs_backup_prediction_rtol=0.0,
        saved_individual_predictions='NOT_PRESENT_IN_S01; compare saved clean metrics and original-vs-backup predictions',
        scope='ALL_30_BEST_CHECKPOINTS_CLEAN_AND_ATTEMPTED96_VALID; all60best/last states load validated',
        dtype='float32',device='cuda',batch_size=32,mode='eval/inference_only',time=datetime.datetime.now(datetime.timezone.utc).isoformat())
    with (WORK/'restore_policy.json').open('x',encoding='utf8') as f:json.dump(policy,f,indent=2)
    os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8'
    sys.path.insert(0,str(ROOT/'src'))
    import torch,pickle
    from mosei.s01.contracts import configure_runtime,from_aligned
    from mosei.s01.models import R01Model
    from mosei.s01.normalization import Normalizer
    from mosei.s01.engine import predict,evaluate
    from mosei.s01.protocol import metric_report,ValidationLibrary
    from mosei.data.dataset import create_aligned_dataset
    configure_runtime()
    check(datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-09-25T18:00:00+08:00'),'Deadline')
    before=SOURCE.stat()
    with SOURCE.open('rb') as f:
        h=hashlib.sha256()
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
        check(h.hexdigest()==SOURCE_HASH,'Official source fingerprint changed')
        f.seek(0);container=pickle.load(f)
    check((before.st_size,before.st_mtime_ns)==(SOURCE.stat().st_size,SOURCE.stat().st_mtime_ns),'Source mutated')
    ds=create_aligned_dataset(container,'valid')
    valid=from_aligned(ds.batch(list(range(len(ds)))),list(range(len(ds))));del container,ds
    results=[];library=ValidationLibrary(valid)
    def restored(path):
        ck=torch.load(path,map_location='cpu',weights_only=True)
        model=R01Model(ck['architecture'],ck['seed'],prior=ck['model']['prior'].tolist(),median=float(ck['model']['median']))
        model.load_state_dict(ck['model'],strict=True);model.to('cuda').eval()
        return ck,model,Normalizer.from_state_dict(ck['normalizer'])
    for folder in sorted((BACKUP/'campaign').iterdir()):
        if not folder.is_dir():continue
        for name in ('best.pt','last.pt'):
            ck,model,norm=restored(folder/name)
            check(len(ck['selector_trace'])==ck['epoch'] and ck['optimizer']['state'],'Checkpoint training state incomplete')
            del model
        ck,model,norm=restored(folder/'best.pt')
        normalized=norm.transform(valid)
        c,y=predict(model,normalized,batch_size=32)
        metrics=metric_report(valid,c,y)
        old=json.loads((folder/'evaluation.json').read_text())
        check(metrics['confusion']==old['clean']['confusion'],'Class confusion mismatch')
        diffs={k:abs(metrics[k]-old['clean'][k]) for k in ('Accuracy','macro_F1','MAE','Pearson') if metrics[k] is not None and old['clean'][k] is not None}
        check(all(d<=policy['metric_abs_tolerance'] for d in diffs.values()),'Historical clean metric mismatch')
        check((metrics['Pearson'] is None)==(old['clean']['Pearson'] is None),'Pearson null mismatch')
        original,original_model,original_norm=restored(OLD/folder.name/'best.pt')
        oc,oy=predict(original_model,original_norm.transform(valid),batch_size=32)
        check(torch.equal(c,oc) and torch.equal(y,oy),'Source/backup predictions differ')
        check(sha(folder/'best.pt')==old['checkpoint_sha256'],'Original evaluation checkpoint mismatch')
        all_scores=evaluate(model,normalized,seed=ck['seed'],library=library)
        def compare(a,b):
            if isinstance(a,dict):
                check(set(a)==set(b),'Report keys changed')
                for k in a:compare(a[k],b[k])
            elif isinstance(a,list):
                check(len(a)==len(b),'Report length changed')
                for x,z in zip(a,b):compare(x,z)
            elif isinstance(a,float):check(abs(a-b)<=policy['metric_abs_tolerance'],'Full condition metric changed')
            else:check(a==b,'Report value or pairing changed')
        compare(all_scores['attempted96'],old['attempted96'])
        compare(all_scores['condition_reports'],old['condition_reports'])
        out=WORK/'restore_private_predictions';out.mkdir(exist_ok=True)
        torch.save(dict(classes=c,regression=y,ordinals=valid.ordinals),out/(folder.name+'.pt'))
        results.append(dict(trial_id=folder.name,checkpoint_sha256=sha(folder/'best.pt'),status='PASS',metric_max_abs_difference=max(diffs.values()),
            original_backup_predictions_bitwise_equal=True,normalizer_equal=original['normalizer']==ck['normalizer'],clean=metrics,
            full96_144_metrics_and_pairing_match=True,attempted96=all_scores['attempted96']))
        print(json.dumps(dict(event='RESTORE_PASS',trial_id=folder.name,max_abs_difference=max(diffs.values()))),flush=True)
    check(len(results)==30,'Expected30restoredfits')
    check(sha(SOURCE)==SOURCE_HASH,'Source changed after restore')
    write(WORK/'restore_receipt.json',dict(status='PASS',policy=policy,restored_best_models=30,loaded_checkpoint_states=60,
        official_training_performed=False,valid_count=len(valid.support),source_sha256=SOURCE_HASH,results=results,
        source_test_objects_deserialized_by_monolithic_pickle=True,test_arrays_accessed_or_evaluated=False,
        limitation='PKL is monolithic; only valid allowlisted fields accessed; no stored S01 per-row predictions existed.'))
    print('ALL_30_RESTORE_PASS',flush=True)
if __name__=='__main__':
    if args.action=='backup':backup()
    elif args.action=='restore':restore()
    else:raise ValueError('backup or restore')
