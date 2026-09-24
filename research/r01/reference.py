# AI-assisted research reference: OpenAI Codex; user-confirmed Astra setting; model telemetry/release date UNKNOWN.
"""SYNTHETIC_ONLY standard-library reference. No dataset readers or training entry."""
import hashlib
import json
import math
import re
from fractions import Fraction

MODS=('T','A','V')
GROUPS=('T','A','V','TA','TV','AV')
RATES=('0.1','0.3','0.5','0.7')
POSITIONS=('front','middle','back','random')
MODEL_SEEDS=(17,29,43)
TRAIN_ROOT=2207
VALID_ROOT=1103

def require(condition,message):
    if not condition: raise ValueError(message)

def choose(n,*key):
    """SHA256 counter-based rejection sampler, unbiased for a uniform hash model."""
    require(type(n) is int and 0<n<=2**256,'invalid choice size')
    payload=json.dumps(key,ensure_ascii=True,separators=(',',':')).encode('ascii')
    bound=(2**256//n)*n
    for counter in range(1024):
        value=int.from_bytes(hashlib.sha256(payload+b'|'+str(counter).encode('ascii')).digest(),'big')
        if value<bound:return value%n
    raise RuntimeError('hash rejection bound exceeded')

def conditions():
    return [(m,q,p) for m in GROUPS for q in RATES for p in POSITIONS]

def condition_id(c):return ':'.join(c)

def validate_masks(support,observed):
    require(bool(support) and all(type(v) is bool for v in support),'bool support required')
    length=sum(support)
    require(length>0 and support==[True]*length+[False]*(len(support)-length),'nonempty prefix required')
    require(set(observed)==set(MODS),'three observed masks required')
    for mask in observed.values():
        require(len(mask)==len(support) and all(type(v) is bool for v in mask),'observed shape/type')
        require(all(not a or s for a,s in zip(mask,support)),'observed outside support')
    require(observed['T']==support,'frozen text observed equality')
    return length

def generate(support,observed,condition,*,root_seed=VALID_ROOT,ordinal=0,replicate=0,namespace='valid'):
    length=validate_masks(support,observed)
    group,rate,position=condition
    require(condition in conditions(),'unknown nominal condition')
    require(type(ordinal) is int and ordinal>=0,'ordinal must be nonnegative')
    reps=3 if position=='random' else 1
    require(type(replicate) is int and 0<=replicate<reps,'invalid replicate')
    masks={m:[False]*len(support) for m in MODS}
    width=min(length-1,max(1,math.ceil(Fraction(rate)*length))) if length>1 else 0
    legal=[]
    if width:
        legal=[s for s in range(length-width+1) if all(0<sum(observed[m][s:s+width])<sum(observed[m]) for m in group)]
    target={'front':0,'middle':(length-width)//2,'back':length-width}.get(position)
    if legal:
        start=(legal[choose(len(legal),namespace,root_seed,ordinal,condition_id(condition),replicate)]
               if position=='random' else min(legal,key=lambda s:(abs(s-target),s)))
        for m in group:masks[m]=[o and start<=t<start+width for t,o in enumerate(observed[m])]
        status='ELIGIBLE';reason=None
    else:
        start=None;status='INELIGIBLE'
        reason='short_support' if length<2 else ('insufficient_observed' if any(sum(observed[m])<2 for m in group) else 'no_common_legal_window')
    available={m:[o and not c for o,c in zip(observed[m],masks[m])] for m in MODS}
    return {'condition':condition_id(condition),'status':status,'reason':reason,'requested_start':target,
            'start':start,'width':width,'moved':start is not None and target is not None and start!=target,
            'legal_starts':legal,'C':masks,'A':available,'fallback':'CLEAN_ONCE' if not legal else None,
            'span_ratio':width/length,'realized_observed_rate':{m:sum(masks[m])/sum(observed[m]) if sum(observed[m]) else None for m in MODS},
            'realized_support_rate':{m:sum(masks[m])/length for m in MODS},'replicate':replicate}

def train_attempt(support,observed,model_seed,epoch,ordinal):
    validate_masks(support,observed)
    require(model_seed in MODEL_SEEDS and epoch>=0,'train seed/epoch')
    key=('train',TRAIN_ROOT,model_seed,epoch,ordinal)
    if choose(2,*key,'clean_or_corrupt')==0:
        return {'status':'CLEAN_REQUESTED','A':{m:list(observed[m]) for m in MODS},'C':{m:[False]*len(support) for m in MODS},'weight':1.0}
    c=conditions()[choose(96,*key,'condition')]
    # One sampled condition; no condition resampling on ineligibility. Training has one view.
    out=generate(support,observed,c,root_seed=TRAIN_ROOT,ordinal=ordinal,replicate=0,namespace=f'train:{model_seed}:{epoch}')
    out['weight']=1.0
    return out

def pearson(y,p):
    if len(y)<2:return None,'insufficient_n'
    a=[v-math.fsum(y)/len(y) for v in y];b=[v-math.fsum(p)/len(p) for v in p]
    va=math.fsum(v*v for v in a);vb=math.fsum(v*v for v in b)
    if va==0:return None,'zero_target_variance'
    if vb==0:return None,'zero_prediction_variance'
    return math.fsum(x*z for x,z in zip(a,b))/math.sqrt(va*vb),None

def metrics(classes,regression,pred_classes,pred_regression):
    n=len(classes)
    require(n==len(regression)==len(pred_classes)==len(pred_regression) and n>0,'metric lengths')
    require(all(type(v) is int and v in (0,1,2) for v in classes+pred_classes),'class values')
    require(all(math.isfinite(v) and -3<=v<=3 for v in regression+pred_regression),'regression range/finite')
    require(classes==[0 if y<0 else 1 if y==0 else 2 for y in regression],'strict neutral mapping')
    cm=[[0]*3 for _ in range(3)]
    for y,p in zip(classes,pred_classes):cm[y][p]+=1
    reports=[]
    for k in range(3):
        tp=cm[k][k];sup=sum(cm[k]);pred=sum(row[k] for row in cm);den=sup+pred
        reports.append({'class':k,'precision':tp/pred if pred else 0.,'recall':tp/sup if sup else 0.,'F1':2*tp/den if den else 0.,'support':sup})
    r,reason=pearson(regression,pred_regression)
    return {'Accuracy':sum(cm[k][k] for k in range(3))/n,'macro_F1':sum(v['F1'] for v in reports)/3,
            'weighted_F1':sum(v['F1']*v['support'] for v in reports)/n,'MAE':math.fsum(abs(a-b) for a,b in zip(regression,pred_regression))/n,
            'Pearson':r,'Pearson_reason':reason,'per_class':reports,'confusion':cm,'n':n}

def attempted_report(classes,y,clean_c,clean_y,damaged_c,damaged_y,eligible,*,ordered_rows,view_fingerprint,replicate=0):
    n=len(classes)
    require(len(eligible)==n and len(damaged_c)==n and len(damaged_y)==n and len(clean_c)==n and len(clean_y)==n,'attempted lengths')
    require(all(type(v) is bool for v in eligible),'eligibility bool')
    pc=[damaged_c[i] if eligible[i] else clean_c[i] for i in range(n)]
    py=[damaged_y[i] if eligible[i] else clean_y[i] for i in range(n)]
    attempted=metrics(classes,y,pc,py)
    inds=[i for i,v in enumerate(eligible) if v]
    eligible_only=metrics(*[[arr[i] for i in inds] for arr in (classes,y,pc,py)]) if inds else None
    return {'attempted':attempted,'eligible_only':eligible_only,'eligible_count':len(inds),'total_count':n,'coverage':len(inds)/n,
            'pairing':pairing_stamp(ordered_rows,eligible,view_fingerprint,replicate)}

def aggregate(run_reports,*,expected_seeds=MODEL_SEEDS):
    """Seed -> 96 condition -> 1/3 replica reports. Equal-condition primary score."""
    require(bool(expected_seeds) and len(set(expected_seeds))==len(expected_seeds) and set(expected_seeds)<=set(MODEL_SEEDS),'prespecified seeds required')
    require(set(run_reports)==set(expected_seeds),'all requested prespecified training seeds required')
    ids={condition_id(c):c for c in conditions()}
    per_seed={};coverage_reference={};per_condition={};population=None;population_stamp=None;paired_views={};eligible_stamps={}
    for seed in expected_seeds:
        runs=run_reports[seed]
        require(set(runs)==set(ids),'exactly 96 nominal conditions required')
        condition_scores={}
        for cid,c in ids.items():
            rr=runs[cid];expected=3 if c[2]=='random' else 1
            require(len(rr)==expected,'replicate count mismatch')
            counts=[(v['eligible_count'],v['total_count']) for v in rr]
            require(len(set(counts))==1,'replica eligibility disagreement')
            if population is None:population=counts[0][1]
            require(counts[0][1]==population,'attempted population changed')
            if cid in coverage_reference:require(counts[0]==coverage_reference[cid],'model-dependent eligibility')
            else:coverage_reference[cid]=counts[0]
            for replica,v in enumerate(rr):
                stamp=v.get('pairing',{})
                require(stamp.get('replicate')==replica,'replicate identity mismatch')
                for field in ('population','eligibility','view'):
                    require(isinstance(stamp.get(field),str) and re.fullmatch('[a-f0-9]{64}',stamp[field]),'missing pairing fingerprint')
                require(v['attempted'].get('n')==v['total_count'],'metric population mismatch')
                if population_stamp is None:population_stamp=stamp['population']
                require(stamp['population']==population_stamp,'ordered population mismatch')
                if cid in eligible_stamps:require(eligible_stamps[cid]==stamp['eligibility'],'eligibility set mismatch')
                else:eligible_stamps[cid]=stamp['eligibility']
                vk=(cid,replica)
                if vk in paired_views:require(paired_views[vk]==stamp['view'],'model-dependent corruption view')
                else:paired_views[vk]=stamp['view']
                require(v['total_count']>0 and 0<=v['eligible_count']<=v['total_count'],'coverage counts')
                require(all(math.isfinite(v['attempted'][k]) for k in ('macro_F1','MAE')),'nonfinite primary metric')
            condition_scores[cid]={k:math.fsum(v['attempted'][k] for v in rr)/expected for k in ('macro_F1','MAE')}
        per_seed[seed]={k:math.fsum(v[k] for v in condition_scores.values())/96 for k in ('macro_F1','MAE')}
        per_condition[seed]=condition_scores
    return {'per_seed':per_seed,'across_seeds':{k:math.fsum(v[k] for v in per_seed.values())/len(expected_seeds) for k in ('macro_F1','MAE')},
            'per_condition':per_condition,'conditions':96,'prediction_views_per_sample_per_seed':144,'coverage':coverage_reference}

def joint_loss(logits,reg_pred,y,weights=(1.,1.,1.),kind='mae',lambda_r=1.):
    require(len(logits)==3 and all(math.isfinite(v) for v in logits),'finite three logits')
    require(math.isfinite(y) and -3<=y<=3 and math.isfinite(reg_pred) and -3<=reg_pred<=3,'legal regression')
    require(len(weights)==3 and all(math.isfinite(w) and w>0 for w in weights),'class weights')
    require(kind in ('mae','huber') and math.isfinite(lambda_r) and lambda_r>=0,'loss configuration')
    c=0 if y<0 else 1 if y==0 else 2
    top=max(logits); ce=((top-logits[c])+math.log(math.fsum(math.exp(v-top) for v in logits)))*weights[c]
    e=abs(reg_pred-y);reg=e/3 if kind=='mae' else ((.5*e*e if e<=1 else e-.5)/3)
    value=ce+lambda_r*reg
    require(math.isfinite(value),'loss arithmetic overflow')
    return value

def reconstruction_loss(pred,target,observed,corruption):
    require(set(pred)==set(target)==set(observed)==set(corruption),'reconstruction modalities')
    modality_losses=[]
    for m in pred:
        require(len(pred[m])==len(target[m])==len(observed[m])==len(corruption[m]),'reconstruction rows')
        d=len(target[m][0]) if target[m] else 0
        require(d>0 and all(len(r)==d for r in pred[m]+target[m]),'reconstruction dimensions')
        vals=[]
        for pr,tr,o,c in zip(pred[m],target[m],observed[m],corruption[m]):
            require(type(o) is bool and type(c) is bool and (not c or o),'C must be boolean subset of O')
            if c:
                require(all(math.isfinite(v) for v in pr+tr),'active reconstruction finite')
                vals.append(math.fsum(abs(a-b) for a,b in zip(pr,tr))/d)
        if vals:modality_losses.append(math.fsum(vals)/len(vals))
    return math.fsum(modality_losses)/len(modality_losses) if modality_losses else 0.0

def choose_checkpoint(trace,patience=10,min_delta_f=1e-4,min_delta_mae=1e-4,max_epochs=100):
    require(bool(trace) and patience>0 and max_epochs>0,'trace/patience/epoch limit')
    best=None;anchor=None;stale=0;stop=None
    for epoch,(f,mae) in enumerate(trace[:max_epochs],1):
        require(math.isfinite(f) and math.isfinite(mae),'checkpoint metrics finite')
        if best is None or (f,-mae)>(best[1],-best[2]):best=(epoch,f,mae)
        if anchor is None or f-anchor[0]>=min_delta_f or (f>=anchor[0] and anchor[1]-mae>=min_delta_mae):
            anchor=(f,mae);stale=0
        else:stale+=1
        if stale>=patience:stop=epoch;break
    return {'best_epoch':best[0],'best_F':best[1],'best_MAE':best[2],'stop_epoch':stop,'evaluated_epochs':epoch}

def rank_configs(configs,clean_reference=None,epsilon_f=.01,epsilon_mae=.05):
    require(bool(configs),'no configurations')
    require(len({c['id'] for c in configs})==len(configs),'duplicate config ids')
    valid=[]
    for c in configs:
        require(all(math.isfinite(c[k]) for k in ('F','MAE','clean_F','clean_MAE')),'nonfinite config metrics')
        if clean_reference is None or (c['clean_F']>=clean_reference['F']-epsilon_f and c['clean_MAE']<=clean_reference['MAE']+epsilon_mae):valid.append(c)
    return sorted(valid,key=lambda c:(-c['F'],c['MAE'],c['parameters'],c['id']))


def pairing_stamp(ordered_rows,eligible,view_fingerprint,replicate):
    """Internal whole-population binding. Never export real per-row inputs.

    Caller derives view_fingerprint from the actual ordered generated masks and
    fixed mask-library provenance, not a model-supplied identifier. Digests check
    consistency, not authentication. No labels enter the mask generator.
    """
    require(len(ordered_rows)==len(eligible)>0,'pairing lengths')
    require(all(type(i) is int and i>=0 for i in ordered_rows) and len(set(ordered_rows))==len(ordered_rows),'unique private row ordinals')
    require(all(type(x) is bool for x in eligible),'eligibility boolean')
    require(type(replicate) is int and replicate>=0,'replicate integer')
    require(isinstance(view_fingerprint,str) and re.fullmatch('[a-f0-9]{64}',view_fingerprint),'view digest')
    def digest(v):return hashlib.sha256(json.dumps(v,separators=(',',':')).encode()).hexdigest()
    return {'population':digest(list(ordered_rows)),'eligibility':digest(list(zip(ordered_rows,eligible))),
            'view':view_fingerprint,'replicate':replicate}


def checkpoint_score(condition_reports,seed=17):
    """One run/epoch score; does not invent two untrained seed results."""
    return aggregate({seed:condition_reports},expected_seeds=(seed,))['per_seed'][seed]


def select_final(winner,reference,epsilon_f=.01,epsilon_mae=.05):
    """Winner was ranked across seeds already; fixed-seed check cannot swap seeds."""
    require(all(math.isfinite(v) and v>=0 for v in (epsilon_f,epsilon_mae)),'nonnegative finite tolerances')
    for item in (winner,reference):
        require(item['seed']==17,'final model seed fixed at 17')
        require(0<=item['clean_F']<=1 and 0<=item['clean_MAE']<=6,'final metrics range')
    ok=(winner['clean_F']>=reference['clean_F']-epsilon_f and winner['clean_MAE']<=reference['clean_MAE']+epsilon_mae)
    return {'configuration':(winner if ok else reference)['configuration'],'seed':17,
            'reason':'WINNER_FIXED_SEED_GUARD_PASS' if ok else 'CLEAN_REFERENCE_FALLBACK'}
