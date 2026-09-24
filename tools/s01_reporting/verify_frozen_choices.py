"""Independent stdlib audit of recorded S01 choices after campaign exit.
Reads safe main-export files and ONLY fingerprinted private epoch_events.jsonl.
No model imports, source data, checkpoint tensors, predictions, new selection or writes to inputs.
"""
from __future__ import annotations
import argparse, datetime, hashlib, json, math, re, types
from pathlib import Path
SEEDS=(17,29,43)
REF_SHA='1cd4b73bb748284b4941625d92be89522771eff8a11e4044547e5f513ea62495'
PROTOCOL_SHA='c69c194447c0c220a56e6dddb9c7a3e225f2a949147573d7212d4d0775871b26'
KEYS=('macro_F1','MAE')
class VerificationError(ValueError): pass

def need(ok,message):
    if not ok: raise VerificationError(message)

def sha(raw): return hashlib.sha256(raw).hexdigest()

def read(path):
    path=Path(path).absolute()
    for p in (path,*path.parents):
        if p.exists(): need(not p.is_symlink() and not getattr(p.lstat(),'st_file_attributes',0)&0x400,'Redirected evidence')
    need(path.is_file() and path.stat().st_size<=32*2**20,'Missing or oversized evidence')
    return path.read_bytes()

def parsed(raw):
    def pairs(rows):
        result={}
        for k,v in rows: need(k not in result,'Duplicate JSON key'); result[k]=v
        return result
    return json.loads(raw.decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=lambda x: (_ for _ in ()).throw(VerificationError('Nonfinite JSON')))

def same(a,b):
    if isinstance(a,dict): return isinstance(b,dict) and all(k in b and same(v,b[k]) for k,v in a.items())
    if isinstance(a,list): return isinstance(b,list) and len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
    if type(a) in (int,float): return type(b) in (int,float) and math.isfinite(a) and math.isfinite(b) and math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-12)
    return type(a) is type(b) and a==b

def mean(rows,objective='clean'):
    need(set(rows)==set(SEEDS),'Incomplete or extra seed set')
    values={k:math.fsum(rows[s][objective][k] for s in SEEDS)/3 for k in KEYS}
    need(all(math.isfinite(v) for v in values.values()),'Nonfinite seed mean')
    return values

def config_score(cid,rows,objective='clean'):
    clean,score=mean(rows),mean(rows,objective)
    params={rows[s]['parameters'] for s in SEEDS};need(len(params)==1,'Capacity differs by seed')
    return dict(id=cid,F=score['macro_F1'],MAE=score['MAE'],clean_F=clean['macro_F1'],clean_MAE=clean['MAE'],parameters=params.pop())

def verify(main_export,campaign,reference,*,synthetic=False):
    main_export,campaign,reference=(Path(x).absolute() for x in (main_export,campaign,reference))
    raw=read(reference);need(sha(raw)==REF_SHA,'Frozen reference hash changed')
    protocol=reference.parents[2]/'src/mosei/s01/protocol.py';need(sha(read(protocol))==PROTOCOL_SHA,'Selection bridge source changed')
    ref=types.ModuleType('verified_frozen_reference');exec(compile(raw,'<HASH_VERIFIED_R01_REFERENCE>','exec'),ref.__dict__)
    manifest_raw=read(main_export/'MANIFEST.json');manifest=parsed(manifest_raw)
    names={'SUMMARY.json','FITS.json','EVENTS.json','CONFIGURATION_SUMMARY.json','BASELINE_AND_SELECTION.json'}
    need(len(manifest['files'])==5 and {f['path'] for f in manifest['files']}==names,'Main manifest member set')
    payload={}
    for f in manifest['files']:
        raw=read(main_export/f['path']);need(sha(raw)==f['sha256'] and len(raw)==f['size'],'Main export hash mismatch');payload[f['path']]=parsed(raw)
    summary=payload['SUMMARY.json'];fits=payload['FITS.json']['fits'];locked=payload['BASELINE_AND_SELECTION.json']
    need(summary['evidence_level']=='VERIFIED' and summary['data_kind']=='OFFICIAL_TRAIN_VALID','Main evidence kind')
    need(summary['S01_EXECUTION_STATUS'] in ('COMPLETED','FAILED','PARTIAL_RESOURCE_STOP'),'Campaign has not terminated')
    need(any(e['kind'] in ('CAMPAIGN_STATUS','PRIVATE_WATCHDOG_RECEIPT') for e in summary['private_evidence_fingerprints']),'No termination evidence binding')
    cid=summary['authorization']['campaign_id'];need(manifest['campaign_id']==payload['FITS.json']['campaign_id']==locked['campaign_id']==cid,'Campaign mismatch')
    need(len(fits)==39 and len({f['trial_id'] for f in fits})==39,'Expected39 unique fits')
    budget=summary['EXECUTION_FIT_BUDGET'];need(budget in (24,30),'Unauthorized budget')
    completed=[f for f in fits if f['status']=='COMPLETED'];need(len(completed)==summary['COMPLETED_FITS'],'Completed count mismatch')
    groups={};audits=[]
    for fit in fits:
        tid=fit['trial_id'];need(re.fullmatch(r'[A-Za-z0-9-]{1,80}',tid),'Unsafe trial ID')
        if fit['status']=='COMPLETED':
            need(fit['selected_for_campaign'] and fit['seed'] in SEEDS,'Unauthorized completed fit')
            key=fit['architecture']+'-'+fit['normalizer'];bucket=groups.setdefault(key,{})
            need(fit['seed'] not in bucket,'Duplicate configuration seed')
            bucket[fit['seed']]=dict(**fit['metrics'],parameters=fit['parameters'])
        evidence=[e for e in fit.get('evidence',[]) if e['kind']=='PRIVATE_EPOCH_HISTORY']
        need(len(evidence)<=1,'Duplicate epoch evidence')
        if not evidence:
            need(fit['status']!='COMPLETED','Completed fit lacks epoch history');continue
        raw=read(campaign/tid/'epoch_events.jsonl');need(sha(raw)==evidence[0]['sha256'] and len(raw)==evidence[0]['size'],'Private epoch fingerprint mismatch')
        rows=[parsed(line) for line in raw.splitlines()];need(len(rows)<=100,'Invalid epoch count')
        objective='clean' if fit['architecture'].startswith('B-') else 'attempted96';trace=[]
        if not rows:
            need(fit['status']!='COMPLETED','Completed fit lacks recorded epochs')
            audits.append(dict(trial_id=tid,status=fit['status'],epoch_records=0,objective=objective,rule_best_epoch=None,private_epoch_sha256=sha(raw)));continue
        for epoch,row in enumerate(rows,1):
            need(row['epoch']==epoch and row['data_kind']=='OFFICIAL_TRAIN_VALID' and row['objective']==objective,'Epoch identity/objective mismatch')
            trace.append(tuple(row['objective_score'][k] for k in KEYS));chosen=ref.choose_checkpoint(trace)
            need(chosen['evaluated_epochs']==epoch and row['selected_epoch']==chosen['best_epoch'] and row['early_stop']==(chosen['stop_epoch'] is not None),'Recorded checkpoint trace differs from frozen rule')
            if objective=='clean': need(same(row['objective_score'],row['clean']),'Baseline objective differs from clean')
        if fit['status']=='COMPLETED':
            need(fit['evaluated_epochs']==len(rows) and fit['selected_epoch']==chosen['best_epoch'],'Final checkpoint epoch mismatch')
            need(len(rows)==100 or chosen['stop_epoch']==len(rows),'Completed fit ended before frozen stop rule')
            best=rows[chosen['best_epoch']-1]
            need(same(best['clean'],fit['metrics']['clean']),'Selected-epoch clean metrics differ from final record')
            need(same({k:best['objective_score'][k] for k in KEYS},{k:fit['metrics'][objective][k] for k in KEYS}),'Selected-epoch objective differs from final record')
        audits.append(dict(trial_id=tid,status=fit['status'],epoch_records=len(rows),objective=objective,rule_best_epoch=chosen['best_epoch'],private_epoch_sha256=sha(raw)))
    baseline=locked['baseline'];selection=locked['selection'];common=None;base_id=None;winner=None;expected_selection=None
    base_ids={a+'-'+n for a in ('B-T','B-A','B-V','B-CAT') for n in ('identity','zscore')}
    all_b=all(k in groups and set(groups[k])==set(SEEDS) for k in base_ids)
    if baseline is None:
        need(selection is None and summary['S01_EXECUTION_STATUS']!='COMPLETED','Missing baseline lock with final selection/completion')
    else:
        need(all_b,'Baseline lock without complete B24')
        means={n:mean(groups['B-CAT-'+n]) for n in ('identity','zscore')}
        common=min(means,key=lambda n:(-means[n]['macro_F1'],means[n]['MAE'],n!='identity'))
        need(common==baseline['common_normalizer']==summary['COMMON_NORMALIZER'],'Common normalizer rule mismatch')
        reports={k:{int(s):v for s,v in rows.items()} for k,rows in baseline['baseline_clean_reports'].items()}
        need(set(reports)==base_ids|{'LATE-identity','LATE-zscore','PRIOR'},'All11 baseline candidates required')
        for k in base_ids:
            for s in SEEDS: need(same(groups[k][s]['clean'],reports[k][s]['clean']) and groups[k][s]['parameters']==reports[k][s]['parameters'],'Baseline lock differs from completed B fit')
        ranked=ref.rank_configs([config_score(k,rows) for k,rows in reports.items()])
        need([x['id'] for x in ranked]==[x['id'] for x in baseline['ranked']] and all(same(a,b) for a,b in zip(ranked,baseline['ranked'])),'Recorded11-baseline means/ranking differ')
        base_id=ranked[0]['id'];need(base_id==baseline['B_star']==summary['B_STAR'],'B-star rule mismatch')
        allowed={a+'-'+common for a in ('C0','R0')} if budget==30 else set()
        need(set(groups)-base_ids<=allowed,'Completed mechanism differs from budget/common normalizer')
        if selection is not None:
            need(len(completed)==budget,'Final choice on incomplete campaign')
            need(set(groups)-base_ids==allowed,'Mechanism configuration set mismatch')
            candidates=[config_score(k,groups[k],'attempted96') for k in sorted(allowed)]
            eligible=ref.rank_configs(candidates,dict(F=ranked[0]['F'],MAE=ranked[0]['MAE'])) if candidates else []
            winner=eligible[0]['id'] if eligible else base_id
            combined={**reports,**{k:groups[k] for k in allowed}}
            def seed17(k):
                x=combined[k][17]['clean'];return dict(configuration=k,seed=17,clean_F=x['macro_F1'],clean_MAE=x['MAE'])
            expected_selection=ref.select_final(seed17(winner),seed17(base_id))
            need(same(expected_selection,selection) and same(expected_selection,summary['selection']),'Recorded final choice/seed17 guard differs from frozen rule')
    return dict(stage='S01_FROZEN_CHOICES_INDEPENDENT_AUDIT',status='PASS',data_kind='SYNTHETIC_FIXTURES_ONLY' if synthetic else 'RECORDED_OFFICIAL_AGGREGATES',
        campaign_id=cid,main_export_manifest_sha256=sha(manifest_raw),reference_sha256=REF_SHA,protocol_source_sha256=PROTOCOL_SHA,
        campaign_terminal_status=summary['S01_EXECUTION_STATUS'],completed_fits=len(completed),registered_fits=39,
        epoch_audits=audits,common_normalizer=common,B_star=base_id,ranked_winner_before_seed17_guard=winner,verified_recorded_selection=expected_selection,
        final_choice_verified=selection is not None,incomplete_fits_preserved=[dict(trial_id=f['trial_id'],status=f['status']) for f in fits if f['status']!='COMPLETED'],
        tolerance=dict(relative=1e-10,absolute=1e-12),new_selection_applied=False,new_model_computation=False,
        source_data_read=False,checkpoint_tensors_read=False,private_files_read='Only main-fingerprinted named epoch_events.jsonl',
        limits=['Checks recorded formulas and durable aggregate provenance; does not rerun predictions or derive metrics from sample labels.',
        'PRIOR/LATE aggregate rows are trusted producer evidence; this verifier recalculates their seed means/rank, not their predictions.',
        'Partial campaigns preserve completed checkpoints but do not invent missing seed summaries or a final choice.',
        'This read-only audit creates no training, retry, publication or new owner authority.'])

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--main-export',required=True);ap.add_argument('--campaign',required=True)
    ap.add_argument('--reference',required=True);ap.add_argument('--output',required=True);args=ap.parse_args()
    output=Path(args.output).absolute();need(not output.exists(),'Output already exists')
    for root in (Path(args.main_export),Path(args.campaign),Path(args.reference).parents[2]): need(not output.resolve().is_relative_to(root.resolve()),'Output must be outside inputs/repository')
    result=dict(stage='S01_FROZEN_CHOICES_INDEPENDENT_AUDIT',status='FAIL',new_model_computation=False)
    try: result=verify(args.main_export,args.campaign,args.reference)
    except (ValueError,OSError,KeyError,TypeError) as exc: result.update(error_type=type(exc).__name__,private_error_sha256=sha(str(exc).encode()))
    result.update(verifier_sha256=sha(read(Path(__file__))),verified_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as stream: json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps(dict(status=result['status'],report_sha256=sha(read(output)))));return 0 if result['status']=='PASS' else 1
if __name__=='__main__': raise SystemExit(main())
