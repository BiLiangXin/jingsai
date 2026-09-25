"""Paired full-population clean/144-view predictions; private caches only."""
import json,time
from pathlib import Path
import torch
from mosei.s01.contracts import MODS,require,digest
from mosei.s01.models import R01Model,parameter_count
from mosei.s01.normalization import Normalizer
from mosei.s01.protocol import reference,metric_report
from .common import sha
from .models import combine_outputs,sign_disagreement

def restore_s01(folder):
    folder=Path(folder);p=folder/'best.pt';record=json.loads((folder/'evaluation.json').read_bytes())
    require(sha(p)==record['checkpoint_sha256'],'S01 checkpoint changed')
    ck=torch.load(p,map_location='cpu',weights_only=True)
    model=R01Model(ck['architecture'],ck['seed'],prior=ck['model']['prior'].tolist(),median=float(ck['model']['median']))
    model.load_state_dict(ck['model'],strict=True);model.eval()
    normalizer=Normalizer.from_state_dict(ck['normalizer'])
    require(ck['config_hash']==record['config_hash'] and ck['provenance']==record['provenance'],'Checkpoint provenance mismatch')
    return model,normalizer,record

@torch.no_grad()
def outputs(model,batch,*,available=None,indices=None,guard=lambda:None):
    model.eval();device=next(model.parameters(),model.prior).device
    indices=list(range(len(batch.support))) if indices is None else indices
    out={'logits':[],'regression':[]}
    for start in range(0,len(indices),32):
        guard();ix=indices[start:start+32];part=batch.take(ix).to(device)
        active=None if available is None else {m:available[m][ix].to(device) for m in MODS}
        row=model(part.inputs(active))
        for k in out:out[k].append(row[k].detach().cpu())
    return {k:torch.cat(v) if v else torch.empty((0,3) if k=='logits' else (0,)) for k,v in out.items()}

def collect_views(model,normalized,library,guard):
    library.validate_population(normalized);start=time.perf_counter()
    clean=outputs(model,normalized,guard=guard);views={}
    for cid,rows in library.views.items():
        views[cid]=[]
        for row in rows:
            ix=[i for i,yes in enumerate(row['eligible']) if yes]
            damaged=outputs(model,normalized,available=row['available'],indices=ix,guard=guard)
            merged={k:v.clone() for k,v in clean.items()}
            for k in merged:merged[k][ix]=damaged[k]
            views[cid].append(dict(output=merged,fingerprint=row['fingerprint'],replicate=row['replicate']))
    return dict(clean=clean,views=views,population=digest(normalized.ordinals),
                mask_fingerprint=library.mask_fingerprint,runtime_seconds=time.perf_counter()-start,
                parameters=parameter_count(model))

def validate_cache(cache,batch,library):
    library.validate_population(batch)
    require(cache['population']==digest(batch.ordinals) and cache['mask_fingerprint']==library.mask_fingerprint,'Cache population/masks changed')
    require(set(cache['views'])==set(library.views),'Cache condition set changed')
    for cid,rows in library.views.items():
        require(len(cache['views'][cid])==len(rows),'Cache replicate count changed')
        for cached,row in zip(cache['views'][cid],rows):
            require(cached['fingerprint']==row['fingerprint'] and cached['replicate']==row['replicate'],'Cache view changed')
            require(len(cached['output']['regression'])==len(batch.ordinals),'Cache population length changed')

def combined_cache(cat,text,candidate,batch,library):
    validate_cache(cat,batch,library);validate_cache(text,batch,library)
    combine=lambda a,b:combine_outputs(a,b,variant=candidate['variant'],beta=candidate['beta'])
    return dict(clean=combine(cat['clean'],text['clean']),views={cid:[dict(output=combine(a['output'],b['output']),
        fingerprint=a['fingerprint'],replicate=a['replicate']) for a,b in zip(cat['views'][cid],text['views'][cid])] for cid in cat['views']},
        population=cat['population'],mask_fingerprint=cat['mask_fingerprint'])

def score_cache(cache,batch,library,seed):
    validate_cache(cache,batch,library);clean=cache['clean'];cc=clean['logits'].argmax(1);cy=clean['regression']
    reports={};signs={}
    for cid,rows in library.views.items():
        reports[cid]=[];signs[cid]=[]
        for cached,row in zip(cache['views'][cid],rows):
            output=cached['output']
            reports[cid].append(reference.attempted_report(batch.classes.tolist(),batch.values.tolist(),cc.tolist(),cy.tolist(),
                output['logits'].argmax(1).tolist(),output['regression'].tolist(),row['eligible'],ordered_rows=batch.ordinals,
                view_fingerprint=row['fingerprint'],replicate=row['replicate']))
            signs[cid].append(sign_disagreement(output)['fraction'])
    return dict(clean=metric_report(batch,cc,cy),attempted96=reference.checkpoint_score(reports,seed),condition_reports=reports,
        sign_disagreement_clean=sign_disagreement(clean),sign_disagreement_attempted96=sum(sum(v)/len(v) for v in signs.values())/96)
