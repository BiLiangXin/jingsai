"""Single-use bounded S02 campaign, with persistent failures and immutable S01."""
import hashlib,json,pickle,time
from pathlib import Path
import torch
from mosei.s01.contracts import ROOT,SEEDS,require,from_aligned,digest
from mosei.s01.protocol import ValidationLibrary,reference
from . import authorization as auth
from .common import Budget,ResourceStop,write_json,event,sha,verify_source,now,SOURCE_HASH
from .models import postprocessing_candidates,ResidualAttentionModel
from .evaluation import restore_s01,collect_views,combined_cache,score_cache
from .engine import fit
from .selection import summarize_candidate,choose_champion,robust_ranking,clean_pareto

def load_official(c,source,budget):
    auth.require_active(c,split='train',optimizer=True);auth.require_active(c,split='valid')
    source=Path(source);require(source.name=='aligned_50.pkl','Frozen aligned source only');before=source.stat()
    with source.open('rb') as stream:
        h=hashlib.sha256()
        for block in iter(lambda:stream.read(2**20),b''):budget();h.update(block)
        require(h.hexdigest()==SOURCE_HASH,'Source hash mismatch')
        stream.seek(0);container=pickle.load(stream)
    require((before.st_size,before.st_mtime_ns)==(source.stat().st_size,source.stat().st_mtime_ns),'Source changed during load')
    from mosei.data.dataset import create_aligned_dataset
    data={}
    for split in ('train','valid'):
        ds=create_aligned_dataset(container,split);data[split]=from_aligned(ds.batch(list(range(len(ds)))),list(range(len(ds))))
    return data

def summarize(records,costs):
    return [summarize_candidate(cid,rows,parameters=costs[cid]['parameters'],inference_cost=costs[cid]['seconds']) for cid,rows in records.items()]

def exact_output_values(left,right):
    require(left['population']==right['population'] and left['mask_fingerprint']==right['mask_fingerprint'],'Restore population mismatch')
    def check(a,b):
        for k in ('logits','regression'):require(a[k].dtype==b[k].dtype and torch.equal(a[k],b[k]),'Winner restored predictions differ')
    check(left['clean'],right['clean'])
    require(set(left['views'])==set(right['views']),'Winner restore condition mismatch')
    for cid in left['views']:
        require(len(left['views'][cid])==len(right['views'][cid]),'Winner restore replicates mismatch')
        for a,b in zip(left['views'][cid],right['views'][cid]):
            require(a['fingerprint']==b['fingerprint'],'Winner restore masks mismatch');check(a['output'],b['output'])

def execute(c,source,output,backup):
    output=Path(output);backup=Path(backup)
    binding=auth.preflight(c,output,backup);auth.claim(c,binding);output.mkdir(parents=True)
    started=time.monotonic();budget=None
    status='BLOCKED';error=None;current=None;records={};costs={};fit_count=0;post_count=0;champion=None
    selection=None;promotion_ready=False;promoted=False;phase='SOURCE';private_registry=dict(current_champion='S01-B-CAT-zscore',seed=17,
        baseline=dict(campaign='S01-20260924T202319Z-30-1cf4769f',checkpoint_sha256='f34dc27a35be1c149907852094ba9f69a759fb312e65fbc6e50981a41b24fee1'))
    write_json(output/'CURRENT_CHAMPION.json',private_registry)
    write_json(output/'campaign.json',dict(binding=binding,config=c,started=now().isoformat()))
    try:
        phase='RESOURCE_PREFLIGHT';budget=Budget(output)
        phase='SOURCE'
        data=load_official(c,source,budget);train,valid=data['train'],data['valid'];library=ValidationLibrary(valid);budget()
        write_json(output/'source_verification.json',dict(source_sha256=SOURCE_HASH,train_count=len(train.support),valid_count=len(valid.support),
            splits_used=['train','valid'],test_used=False,special_sets_opened=False,
            monolithic_pickle_deserialized=True,test_fields_accessed=False))
        original={};components={};component_cost={};component_receipt={};norm=None
        phase='POSTPROCESS';auth.stable_code(c)
        for seed in SEEDS:
            original[seed]=dict(json.loads((backup/'campaign'/f'B-CAT-zscore-T0-s{seed}'/'evaluation.json').read_bytes()),status='COMPLETED')
            components[seed]={}
            component_receipt[seed]={}
            for name,trial in [('cat',f'B-CAT-zscore-T0-s{seed}'),('text',f'B-T-identity-T0-s{seed}')]:
                budget();model,n,old=restore_s01(backup/'campaign'/trial)
                require(n.method==('zscore' if name=='cat' else 'identity'),'Component normalizer changed')
                if name=='cat':
                    if norm is None:norm=n
                    else:require(norm.state_dict()==n.state_dict(),'S01 shared zscore changed')
                normalized=n.transform(valid);model.to('cuda')
                cache=collect_views(model,normalized,library,budget)
                cache.update(checkpoint_sha256=old['checkpoint_sha256'],normalizer_hash=digest(n.state_dict()),seed=seed)
                torch.save(cache,output/f'component_{name}_s{seed}.pt');components[seed][name]=cache
                component_receipt[seed][name]=dict(checkpoint_sha256=old['checkpoint_sha256'],config_hash=old['config_hash'],
                    normalizer_hash=cache['normalizer_hash'],parameters=cache['parameters'],runtime_seconds=cache['runtime_seconds'],
                    provenance=old['provenance'],cache_sha256=sha(output/f'component_{name}_s{seed}.pt'))
                component_cost[(name,seed)]=cache['runtime_seconds'];model.cpu();del model
        write_json(output/'component_restore_receipt.json',component_receipt)
        champion=summarize_candidate('S01-B-CAT-zscore',original,parameters=original[17]['parameters'],
            inference_cost=sum(component_cost[('cat',s)] for s in SEEDS)/3)
        for candidate in postprocessing_candidates():
            current=candidate['id'];rows={};event(output/'events.jsonl',dict(kind='POSTPROCESS',id=current,status='RUNNING'))
            folder=output/current;folder.mkdir()
            for seed in SEEDS:
                budget();cache=combined_cache(components[seed]['cat'],components[seed]['text'],candidate,valid,library)
                scores=score_cache(cache,valid,library,seed);scores.update(status='COMPLETED',seed=seed,candidate=candidate,
                    component_provenance=component_receipt[seed],execution_config_hash=digest(c),code_commit=binding['commit'])
                if candidate['variant']=='W0' and candidate['beta']==0:
                    for scope,keys in [('clean',('Accuracy','macro_F1','MAE','Pearson')),('attempted96',('macro_F1','MAE'))]:
                        require(all(abs(scores[scope][k]-original[seed][scope][k])<=1e-7 for k in keys),'Original control failed to reproduce')
                torch.save(cache,folder/f'predictions_s{seed}.pt');write_json(folder/f'evaluation_s{seed}.json',scores);rows[seed]=scores
            reference.aggregate({s:rows[s]['condition_reports'] for s in SEEDS})
            records[current]=rows
            params=components[17]['cat']['parameters']+(0 if candidate['variant']=='W0' else components[17]['text']['parameters'])
            cost=sum(component_cost[('cat',s)]+(0 if candidate['variant']=='W0' else component_cost[('text',s)]) for s in SEEDS)/3
            costs[current]=dict(parameters=params,seconds=cost);post_count+=1
            event(output/'events.jsonl',dict(kind='POSTPROCESS',id=current,status='COMPLETED',seeds=list(SEEDS)))
            print(json.dumps(dict(event='POSTPROCESS_COMPLETED',candidate=current)),flush=True)
        phase='TRAIN';normalized_train=norm.transform(train);normalized_valid=norm.transform(valid)
        provenance=dict(code_commit=binding['commit'],source_sha256=SOURCE_HASH,execution_config_hash=digest(c),protocol='S02-RES-01',
            authorization_manifest_sha256=binding['manifest_sha256'])
        for recipe in c['recipes']:
            records[recipe]={};costs[recipe]=dict(parameters=77542,seconds=None)
            timings=[]
            for seed in SEEDS:
                budget();auth.stable_code(c);current=f'{recipe}-s{seed}';phase='FIT_PREFLIGHT'
                before=verify_source(source,budget);event(output/'events.jsonl',dict(kind='FIT',id=current,status='RUNNING',source_before=before))
                teacher=None
                if recipe=='M4':
                    teacher,teacher_norm,_=restore_s01(backup/'campaign'/f'B-CAT-zscore-T0-s{seed}')
                    require(teacher_norm.state_dict()==norm.state_dict(),'Teacher normalization mismatch')
                phase='FIT';folder=output/current
                result=fit(c,recipe,seed,normalized_train,normalized_valid,norm,library,teacher,folder,provenance,budget)
                after=verify_source(source,budget);auth.stable_code(c)
                write_json(folder/'source_verification.json',dict(before=before,after=after))
                result['status']='COMPLETED';write_json(folder/'evaluation.json',result)
                records[recipe][seed]=result;fit_count+=1;timings.append(result['inference_seconds'])
                costs[recipe]['parameters']=result['parameters'];costs[recipe]['seconds']=sum(timings)/len(timings)
                event(output/'events.jsonl',dict(kind='FIT',id=current,status='COMPLETED',checkpoint_sha256=result['checkpoint_sha256']))
                print(json.dumps(dict(event='FIT_COMPLETED',id=current,completed=fit_count)),flush=True)
            reference.aggregate({s:records[recipe][s]['condition_reports'] for s in SEEDS})
        phase='SELECTION';summaries=summarize(records,costs)
        selection=choose_champion(champion,summaries,comparison_complete=True)
        if selection['promotion_proposed']:
            phase='WINNER_RESTORE';winner=selection['selected_id'];budget();s=17
            if winner.startswith('W'):
                candidate=next(x for x in postprocessing_candidates() if x['id']==winner);again={}
                for name,trial in [('cat','B-CAT-zscore-T0-s17'),('text','B-T-identity-T0-s17')]:
                    model,n,_=restore_s01(backup/'campaign'/trial);model.to('cuda')
                    again[name]=collect_views(model,n.transform(valid),library,budget);model.cpu()
                restored=combined_cache(again['cat'],again['text'],candidate,valid,library)
                saved=torch.load(output/winner/'predictions_s17.pt',weights_only=True)
            else:
                ck=torch.load(output/f'{winner}-s17'/'best.pt',map_location='cpu',weights_only=True)
                model=ResidualAttentionModel(winner,17,prior=ck['model']['prior'].tolist(),median=float(ck['model']['median']))
                model.load_state_dict(ck['model'],strict=True);model.to('cuda')
                restored=collect_views(model,normalized_valid,library,budget);saved=torch.load(output/f'{winner}-s17'/'predictions_private.pt',weights_only=True)
            exact_output_values(saved,restored)
            write_json(output/'winner_restore.json',dict(status='PASS',winner=winner,seed=17,exact_tensor_values_equal=True,full144_views=True))
            budget();promotion_ready=True
        status='COMPLETED'
    except Exception as exc:
        error=type(exc).__name__+': '+str(exc);status='PARTIAL_RESOURCE_STOP' if isinstance(exc,ResourceStop) else 'BLOCKED'
        if phase in ('FIT','FIT_PREFLIGHT'):
            event(output/'events.jsonl',dict(kind='FIT',id=current,status='RESOURCE_CAP_STOP' if isinstance(exc,ResourceStop) else 'FAILED',error=error))
        event(output/'events.jsonl',dict(kind='CAMPAIGN_FAILURE',id=current,phase=phase,status=status,error=error))
        print(json.dumps(dict(event='CAMPAIGN_STOP',status=status,phase=phase,error=error)),flush=True)
    finally:
        summary=dict(status=status,error=error,phase=phase,current=current,fit_completed=fit_count,
            postprocess_completed=post_count,fit_budget=12,postprocess_budget=15,promoted=promoted,current_champion=private_registry['current_champion'],
            runtime_seconds=time.monotonic()-started,binding=binding,finished=now().isoformat(),authorization_status='CONSUMED',retry_budget=0)
        try:
            summaries=summarize(records,costs)
            if selection is None and champion is not None:selection=choose_champion(champion,summaries,comparison_complete=False)
            if champion is not None:
                write_json(output/'comparison.json',dict(baseline=champion,candidates=summaries,selection=selection,
                    robust_ranking=robust_ranking(champion,summaries),clean_pareto=clean_pareto([champion,*summaries])))
            if promotion_ready and status=='COMPLETED':
                budget()
                summary.update(promoted=True,current_champion=selection['selected_id'],
                    promotion_requires_matching_atomic_pointer=True,comparison_sha256=sha(output/'comparison.json'))
            write_json(output/'campaign_status.json',summary)
            # Last fallible operation: no promotion occurs before all terminal evidence is durable.
            # A crash between PREPARE and this atomic commit is detected by status/pointer mismatch.
            if promotion_ready and status=='COMPLETED':
                final_pointer=dict(private_registry,current_champion=selection['selected_id'],promotion_restore='winner_restore.json',
                    terminal_status_sha256=sha(output/'campaign_status.json'),comparison_sha256=sha(output/'comparison.json'))
                write_json(output/'CURRENT_CHAMPION.json',final_pointer)
                promoted=True
        except Exception as exc:
            status='PARTIAL_RESOURCE_STOP' if isinstance(exc,ResourceStop) else 'BLOCKED'
            error='FINALIZATION_FAILED: '+type(exc).__name__+': '+str(exc)
            summary.update(status=status,error=error,promoted=False,current_champion='S01-B-CAT-zscore')
            # All fallible terminal writes precede pointer publication; old pointer remains intact.
            for name in ('finalization_failure.json','campaign_status.json'):
                try:write_json(output/name,summary)
                except Exception:pass
    return status
