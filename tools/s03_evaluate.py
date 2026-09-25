"""One bounded restore/deployment/Q3 operation; private caches, aggregate reports."""
import argparse, datetime, hashlib, json, pickle, sys, time, random
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import torch
from mosei.s01.contracts import MODS, from_aligned, configure_runtime, digest, require
from mosei.s01.normalization import Normalizer
from mosei.s01.protocol import ValidationLibrary, metric_report, reference
from mosei.s02.models import ResidualAttentionModel
from mosei.s02.evaluation import outputs, score_cache
from mosei.data.dataset import create_aligned_dataset
from mosei.s03.core import adapter,coalition,shapley,content_window,mapped_interval,disjoint_top,paired_random

CONFIG=json.loads((ROOT/'configs/s03_execution.json').read_bytes())
PUB=ROOT/'reports/s03_readiness'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def guard():
    require(CONFIG['status']=='ACTIVE_AUTHORIZED' and CONFIG['new_fit_budget']==0 and not CONFIG['training_authorized'],'Scope closed')
    require(datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(CONFIG['compute_deadline']),'Compute budget expired')
def load_batch(path):
    guard();require(sha(path)=='66e867aa74bc70a844e806e5571e371c9abb4a35f9e2887ce9b4d97ff2cb8fcd','Source hash mismatch')
    # Pickle container materializes all objects. Only allowlisted VALID fields are selected.
    with open(path,'rb') as f:container=pickle.load(f)
    ds=create_aligned_dataset(container,'valid');del container
    batch=from_aligned(ds.batch(list(range(len(ds)))),list(range(len(ds))))
    require(len(batch.ordinals)==728,'VALID population mismatch');return batch
def restore(campaign,seed):
    guard();folder=campaign/f'M2-s{seed}';p=folder/'best.pt'
    fit=next(f for f in json.loads((ROOT/'reports/s02_execution/S02-20260925-BOUNDED-12F15W/FITS.json').read_bytes()) if f['id']==f'M2-s{seed}')
    require(sha(p)==fit['checkpoint_sha256'],'Checkpoint hash mismatch')
    ck=torch.load(p,map_location='cpu',weights_only=True)
    require(ck['epoch']==fit['selected_epoch'] and ck['config_hash']==fit['config_sha256'],'Checkpoint binding mismatch')
    model=ResidualAttentionModel('M2',seed,prior=ck['model']['prior'].tolist(),median=float(ck['model']['median']))
    model.load_state_dict(ck['model'],strict=True);model.requires_grad_(False);model.eval();model.to('cuda')
    return model,Normalizer.from_state_dict(ck['normalizer']),ck
def state_digest(model):
    h=hashlib.sha256()
    for k,v in sorted(model.state_dict().items()):h.update(k.encode());h.update(v.detach().cpu().numpy().tobytes())
    return h.hexdigest()
@torch.no_grad()
def infer(model,inputs):
    guard();r=model(inputs);return {k:r[k].detach().cpu() for k in ['logits','regression']}
@torch.no_grad()
def deploy_outputs(model,batch,normalizer,profile,availability=None):
    rows=[]
    for start in range(0,len(batch.ordinals),32):
        guard();ix=list(range(start,min(start+32,len(batch.ordinals))));part=batch.take(ix).to('cuda')
        visible={m:part.features[m].clone() for m in MODS}
        if availability is not None:
            # Only evaluation sees O/Atruth. Proxy receives zeroed visible values, never these masks.
            for m in MODS:
                corrupted=part.observed[m] & ~availability[m][ix].to('cuda')
                visible[m][corrupted]=0
        rows.append(infer(model,adapter(visible,part.support,normalizer,profile)))
    return {k:torch.cat([r[k] for r in rows]) for k in rows[0]}
def restore_check(batch,campaign,out):
    model,norm,ck=restore(campaign,17);before=state_digest(model)
    result=outputs(model,norm.transform(batch),guard=guard)
    old=torch.load(campaign/'M2-s17/predictions_private.pt',map_location='cpu',weights_only=True)['clean']
    delta={k:float((result[k]-old[k]).abs().max()) for k in result}
    require(all(torch.allclose(result[k],old[k],atol=CONFIG['restore_atol'],rtol=CONFIG['restore_rtol']) for k in result),'Restore prediction mismatch')
    require(state_digest(model)==before,'Model mutated')
    receipt=dict(status='PASS',seed=17,epoch=ck['epoch'],max_abs_difference=delta,exact_equal=all(torch.equal(result[k],old[k]) for k in result),atol=CONFIG['restore_atol'],rtol=CONFIG['restore_rtol'],n=728,model_unchanged=True,checkpoint_sha256=sha(campaign/'M2-s17/best.pt'),normalizer_sha256=digest(ck['normalizer']))
    save(PUB/'RESTORE.json',receipt);print(json.dumps(receipt))
def deployment(batch,campaign,out):
    require(json.loads((PUB/'RESTORE.json').read_bytes())['status']=='PASS','Restore prerequisite')
    library=ValidationLibrary(batch);results={}
    for profile in CONFIG['profiles']:
        results[profile]={}
        for seed in CONFIG['seeds']:
            guard();target=out/f'{profile}-s{seed}';require(not target.exists(),'No silent repeat/overwrite of profile result')
            model,norm,ck=restore(campaign,seed);before=state_digest(model);started=time.perf_counter()
            clean=deploy_outputs(model,batch,norm,profile);views={}
            for cid,items in library.views.items():
                views[cid]=[]
                for item in items:
                    prediction=deploy_outputs(model,batch,norm,profile,item['available'])
                    # Explicit CLEAN_ONCE for every ineligible row.
                    invalid=[i for i,eligible in enumerate(item['eligible']) if not eligible]
                    for k in prediction:prediction[k][invalid]=clean[k][invalid]
                    views[cid].append(dict(output=prediction,fingerprint=item['fingerprint'],replicate=item['replicate']))
            cache=dict(clean=clean,views=views,population=digest(batch.ordinals),mask_fingerprint=library.mask_fingerprint)
            score=score_cache(cache,batch,library,seed)
            require(state_digest(model)==before and sha(campaign/f'M2-s{seed}/best.pt')==next(f['checkpoint_sha256'] for f in json.loads((ROOT/'reports/s02_execution/S02-20260925-BOUNDED-12F15W/FITS.json').read_bytes()) if f['id']==f'M2-s{seed}'),'Weights changed')
            target.mkdir();torch.save(cache,target/'predictions.pt');save(target/'evaluation.json',score)
            results[profile][seed]=dict(clean=score['clean'],attempted96=score['attempted96'],runtime_seconds=time.perf_counter()-started)
            print(json.dumps(dict(profile=profile,seed=seed,clean=score['clean']['macro_F1'],attempted96=score['attempted96'])),flush=True)
            del model,cache,views
    fits=json.loads((ROOT/'reports/s02_execution/S02-20260925-BOUNDED-12F15W/FITS.json').read_bytes());baseline={f['seed']:f['metrics'] for f in fits if f['recipe']=='M2'}
    summary={}
    for p,rs in results.items():
        means={scope:{k:sum(rs[s][scope][k] for s in CONFIG['seeds'])/3 for k in ['macro_F1','MAE']} for scope in ['clean','attempted96']}
        base={k:sum(baseline[s]['clean'][k] for s in CONFIG['seeds'])/3 for k in ['macro_F1','MAE']}
        checks=[means['clean']['macro_F1']>=base['macro_F1']-.01,means['clean']['MAE']<=base['MAE']+.05,rs[17]['clean']['macro_F1']>=baseline[17]['clean']['macro_F1']-.01,rs[17]['clean']['MAE']<=baseline[17]['clean']['MAE']+.05]
        summary[p]=dict(per_seed=rs,mean=means,clean_guard_checks=checks,eligible=all(checks))
    qualified=[p for p in summary if summary[p]['eligible']]
    winner=min(qualified,key=lambda p:(-summary[p]['mean']['attempted96']['macro_F1'],summary[p]['mean']['attempted96']['MAE'],-summary[p]['mean']['clean']['macro_F1'],summary[p]['mean']['clean']['MAE'],p!='V0')) if qualified else None
    save(PUB/'DEPLOYMENT.json',dict(status='PASS' if winner else 'BLOCKED',selected_profile=winner,results=summary,models_unchanged=True,new_fits=0,mask_truth_at_adapter=False,special_data_opened=False))

def explanations(batch,campaign,out):
    require(json.loads((PUB/'RESTORE.json').read_bytes())['status']=='PASS','Restore prerequisite')
    target=out/'q3';require(not target.exists(),'Do not overwrite explanation run');target.mkdir()
    model,norm,ck=restore(campaign,17);before=state_digest(model);normalized=norm.transform(batch)
    full=outputs(model,normalized,guard=guard);classes=full['logits'].argmax(1);groups=[]
    for bits in range(8):
        predictions=[]
        for start in range(0,len(batch.ordinals),32):
            part=normalized.take(list(range(start,min(start+32,len(batch.ordinals))))).to('cuda')
            predictions.append(infer(model,coalition(part.inputs(),bits)))
        logits=torch.cat([r['logits'] for r in predictions]);reg=torch.cat([r['regression'] for r in predictions])
        if bits==7:
            require(torch.allclose(logits,full['logits'],atol=1e-6,rtol=1e-5) and torch.allclose(reg,full['regression'],atol=1e-6,rtol=1e-5),'Full coalition does not reproduce')
        groups.append(torch.stack([logits.gather(1,classes[:,None]).squeeze(1),reg],dim=-1))
    values=torch.stack(groups).double();phi=shapley(values);efficiency=phi.sum(1)-(values[7]-values[0])
    require(torch.allclose(phi.sum(1),values[7]-values[0],atol=1e-6,rtol=1e-5),'Shapley efficiency failed')
    cards=[]
    for i in range(len(batch.ordinals)):
        card={'ordinal':batch.ordinals[i],'predicted_class':int(classes[i]),'regression':float(full['regression'][i]),'mapping':mapped_interval(0,int(batch.support[i].sum()))}
        for k,name in enumerate(['classification','regression']):
            signed=phi[i,:,k];total=float(signed.abs().sum())
            card[name]=dict(signed=signed.tolist(),relative_absolute=(signed.abs()/total).tolist() if total else None,dominant_modality=MODS[int(signed.abs().argmax())] if total else None,status='RESOLVABLE_CONTENT_EFFECT' if total else 'NO_RESOLVABLE_EFFECT',directions=['positive_support' if x>0 else 'negative_suppression' if x<0 else 'zero' for x in signed.tolist()])
        cards.append(card)
    save(target/'group_explanations_private.json',cards);torch.save({'coalition_values':values,'phi':phi},target/'group_tensors.pt')
    cases=[];strata=[]
    for cls in range(3):
        for correct in [True,False]:
            ix=[i for i in range(len(batch.ordinals)) if int(batch.classes[i])==cls and bool(classes[i]==batch.classes[i])==correct][:6]
            cases.extend(ix);strata.append(dict(true_class=cls,correct=correct,count=len(ix)))
    save(target/'local_cases_preregistered.json',dict(ordinals=cases,strata=strata,selection='first6 per stratum before local computation',random_seed=3103))
    local=[]
    for ordinal in cases:
        guard();part=normalized.take([ordinal]).to('cuda');inp=part.inputs();n=int(part.support.sum());cls=int(classes[ordinal]);full_pair=values[7,ordinal]
        if n<3:
            local.append(dict(ordinal=ordinal,status='INELIGIBLE_SHORT_SEQUENCE'));continue
        deltas=[]
        for start in range(n-2):
            pred=infer(model,content_window(inp,list(range(start,start+3))))
            deltas.append((full_pair-torch.tensor([float(pred['logits'][0,cls]),float(pred['regression'][0])],dtype=torch.float64)).tolist())
        entry=dict(ordinal=ordinal,status='COMPUTED',feature_window_width=3,mapping_status='UNVERIFIED_MAPPING',timestamp=None,window_deltas=deltas)
        for k,name in enumerate(['classification','regression']):
            chosen=disjoint_top([d[k] for d in deltas]);random_starts=paired_random(n,len(chosen),random.Random(3103+ordinal*2+k))
            measures={}
            for label,starts in [('key',chosen),('random',random_starts)]:
                positions=[j for s in starts for j in range(s,s+3)];responses={}
                for retain in [False,True]:
                    pred=infer(model,content_window(inp,positions,retain=retain));scalar=float(pred['logits'][0,cls]) if k==0 else float(pred['regression'][0])
                    responses['retained_minus_empty' if retain else 'full_minus_deleted']=scalar-float(values[0,ordinal,k]) if retain else float(full_pair[k])-scalar
                measures[label]=dict(starts=starts,**responses)
            entry[name]=measures
        local.append(entry)
    save(target/'local_explanations_private.json',local)
    measures={}
    for name in ['classification','regression']:
        valid=[r for r in local if r['status']=='COMPUTED']
        measures[name]={}
        for key in ['full_minus_deleted','retained_minus_empty']:
            differences=[abs(r[name]['key'][key])-abs(r[name]['random'][key]) for r in valid]
            measures[name][key]=dict(n=len(valid),mean_key_absolute=sum(abs(r[name]['key'][key]) for r in valid)/len(valid) if valid else None,mean_random_absolute=sum(abs(r[name]['random'][key]) for r in valid)/len(valid) if valid else None,mean_paired_absolute_difference=sum(differences)/len(differences) if differences else None,negative_or_zero_cases=sum(d<=0 for d in differences),interpretation='DESCRIPTIVE_INTERVENTION_MAGNITUDE_NOT_CAUSAL_OR_SIGNIFICANCE')
    require(state_digest(model)==before,'Q3 mutated model')
    save(PUB/'Q3_VALIDATION.json',dict(status='PASS_NUMERICAL_FEATURE_SPACE_ONLY',n_group=728,coalitions=8,max_efficiency_error=float(efficiency.abs().max()),full_coalition_reproduced=True,local_cases=len(cases),strata=strata,local_summary=measures,mean_absolute_phi=phi.abs().mean(0).tolist(),models_unchanged=True,mapping='UNVERIFIED',timestamp_policy='null',attachment4_gate='BLOCKED',special_data_opened=False,private_cards_sha256=sha(target/'group_explanations_private.json'),private_local_sha256=sha(target/'local_explanations_private.json')))
    print(json.dumps({'q3':'PASS_NUMERICAL_FEATURE_SPACE_ONLY','n':728,'local':len(cases),'mapping':'UNVERIFIED'}))

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['restore','deploy','q3']);p.add_argument('--source',required=True);p.add_argument('--campaign',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    configure_runtime();guard();batch=load_batch(a.source);out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    {'restore':restore_check,'deploy':deployment,'q3':explanations}[a.mode](batch,Path(a.campaign),out)
if __name__=='__main__':main()
