"""Nonoracle deployment and fixed-mask group explanation primitives."""
import math
import torch
from mosei.s01.contracts import MODS, DIMS, require, validate_inputs
from mosei.s01.normalization import Normalizer

def adapter(visible, support, normalizer, profile):
    """No labels, identifiers, original O, corruption C or clean input accepted."""
    require(profile in ('V0','V1'), 'Unknown profile')
    require(set(visible)==set(MODS), 'Continuous features only')
    require(support.dtype==torch.bool and support.ndim==2 and support.shape[1]==50,'Support schema')
    require(normalizer.fit_split=='train','Frozen TRAIN statistics required')
    active={};features={}
    for m in MODS:
        x=visible[m]
        require(x.shape==(*support.shape,DIMS[m]) and x.dtype==torch.float32,'Feature schema')
        require(bool(torch.isfinite(x).all()),'Nonfinite visible input')
        a=support.clone() if profile=='V0' and m=='text' else support & ~x.eq(0).all(-1)
        y=torch.zeros_like(x)
        if normalizer.method=='identity':y[a]=x[a]
        else:
            stats=normalizer.statistics[m]
            mean=torch.tensor(stats['mean'],dtype=torch.float64,device=x.device)
            std=torch.tensor(stats['std'],dtype=torch.float64,device=x.device)
            y[a]=((x[a].double()-mean)/torch.where(std==0,1.,std)).float()
        active[m]=a;features[m]=y
    result=dict(features=features,support=support,available=active)
    validate_inputs(result)
    return result

def coalition(inputs,bits):
    require(type(bits)==int and 0<=bits<8,'Coalition bits')
    return dict(features={m:inputs['features'][m] if bits & (1<<i) else torch.zeros_like(inputs['features'][m]) for i,m in enumerate(MODS)},support=inputs['support'],available=inputs['available'])

def shapley(values):
    """values [8,N,K] -> [N,3,K], exact group Shapley."""
    require(values.shape[0]==8 and bool(torch.isfinite(values).all()),'Eight finite coalitions')
    result=[]
    for m in range(3):
        total=torch.zeros_like(values[0])
        for bits in range(8):
            if bits & (1<<m):continue
            k=bits.bit_count();weight=math.factorial(k)*math.factorial(2-k)/6
            total=total+weight*(values[bits|(1<<m)]-values[bits])
        result.append(total)
    return torch.stack(result,dim=1)

def content_window(inputs,positions,*,retain=False):
    """Fixed mask; replace only active contents, never change b/rho."""
    select=torch.zeros_like(inputs['support']);select[:,positions]=True
    x={}
    for m in MODS:
        changed=inputs['available'][m] & (~select if retain else select)
        x[m]=inputs['features'][m].clone();x[m][changed]=0
    return dict(features=x,support=inputs['support'],available=inputs['available'])

def mapped_interval(start,end,mapping=None):
    if mapping is None:return dict(feature_start=start,feature_end_exclusive=end,timestamp=None,status='UNVERIFIED_MAPPING')
    require(mapping.get('verified_official_correspondence') is True,'Unverified mapping cannot supply timestamps')
    raise ValueError('No official correspondence implementation is frozen')

def disjoint_top(scores,width=3,limit=3):
    chosen=[];occupied=set()
    for start in sorted(range(len(scores)),key=lambda i:(-abs(float(scores[i])),i)):
        positions=set(range(start,start+width))
        if not occupied & positions:
            chosen.append(start);occupied.update(positions)
            if len(chosen)==limit:break
    return chosen

def paired_random(n,k,rng,width=3):
    require(k>=0 and n>=width*k,'Cannot allocate matched disjoint windows')
    compressed=sorted(rng.sample(range(n-(width-1)*k),k))
    return [v+(width-1)*i for i,v in enumerate(compressed)]
