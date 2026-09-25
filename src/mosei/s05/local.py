"""Fixed single-modality local content interventions; no fitting or selection."""
import torch
from mosei.s01.contracts import MODS,require

def one_modality_window(inputs,modality,start,width=3):
    require(modality in MODS and width==3,'Fixed modality/width')
    support=inputs['support'];require(support.ndim==2 and support.shape[0]==1,'Single row')
    n=int(support[0].sum());require(0<=start and start+width<=n,'Supported window')
    features={m:x.clone() for m,x in inputs['features'].items()}
    available=inputs['available'][modality]
    selected=available[:,start:start+width]
    features[modality][:,start:start+width][selected]=0
    return {'features':features,'support':support.clone(),
            'available':{m:a.clone() for m,a in inputs['available'].items()}}

@torch.no_grad()
def explain_fixed(model,inputs):
    support=inputs['support'];require(support.ndim==2 and support.shape[0]==1,'Single row')
    n=int(support[0].sum());full=model(inputs)
    cls=int(full['logits'][0].argmax())
    base=(float(full['logits'][0,cls]),float(full['regression'][0]))
    result={'predicted_class_index':cls,'full_class_logit':base[0],'full_regression':base[1],
            'width':3,'stride':1,'reference':'TRAIN_NORMALIZED_ZERO',
            'fixed_target':'ORIGINAL_FULL_PREDICTED_CLASS_LOGIT_AND_REGRESSION','modalities':{}}
    for modality in MODS:
        starts=[s for s in range(max(0,n-2)) if bool(inputs['available'][modality][:,s:s+3].any())]
        if not starts:
            result['modalities'][modality]={'class':{'status':'NO_AVAILABLE_CONTENT_EFFECT','windows':[]},
                                            'reg':{'status':'NO_AVAILABLE_CONTENT_EFFECT','windows':[]}}
            continue
        deltas=[]
        for start in starts:
            changed=one_modality_window(inputs,modality,start)
            pred=model(changed)
            deltas.append((base[0]-float(pred['logits'][0,cls]),base[1]-float(pred['regression'][0])))
        targets={}
        for axis,key in enumerate(('class','reg')):
            ranked=sorted(range(len(starts)),key=lambda i:(-abs(deltas[i][axis]),starts[i]))
            chosen=[];occupied=set()
            for i in ranked:
                s=starts[i]
                if occupied.isdisjoint(range(s,s+3)):
                    chosen.append(i);occupied.update(range(s,s+3))
                    if len(chosen)==3:break
            windows=[{'feature_start':starts[i],'feature_end_exclusive':starts[i]+3,
                      'signed_full_minus_single_modality_deleted':deltas[i][axis],
                      'available_positions':int(inputs['available'][modality][:,starts[i]:starts[i]+3].sum())} for i in chosen]
            status='ZERO_EFFECT' if all(abs(w['signed_full_minus_single_modality_deleted'])<=1e-12 for w in windows) else 'COMPUTED'
            targets[key]={'status':status,'windows':windows}
        result['modalities'][modality]=targets
    return result
