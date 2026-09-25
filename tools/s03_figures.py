"""Render only recorded aggregate S02 evidence; no model or original data access."""
import argparse, csv, hashlib, json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'reports/s02_execution/S02-20260925-BOUNDED-12F15W'

def run(private_campaign):
    out=ROOT/'reports/s03_readiness/figures';out.mkdir(parents=True,exist_ok=True)
    read=lambda name:list(csv.DictReader((SOURCE/name).open(encoding='utf-8-sig',newline='')))
    curves=read('EPOCH_CURVES.csv');fits=json.loads((SOURCE/'FITS.json').read_bytes())
    if len(curves)!=148 or len(fits)!=12:raise ValueError('Unexpected epoch/fit count')
    for fit in fits:
        epochs=[int(r['epoch']) for r in curves if r['trial_id']==fit['id']]
        if epochs!=list(range(1,fit['evaluated_epochs']+1)) or fit['selected_epoch'] not in epochs:
            raise ValueError('Epoch continuity/final binding failed')
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':220})
    artifacts=[]
    def finish(fig,name):
        fig.tight_layout()
        for ext in ['png','svg']:
            p=out/(name+'.'+ext);fig.savefig(p,bbox_inches='tight');artifacts.append(p)
        plt.close(fig)
    candidates=read('CANDIDATE_COMPARISON.csv')
    selected=[r for r in candidates if r['configuration'] in ['S01-B-CAT-zscore','M1','M2','M3','M4']]
    labels=[r['configuration'].replace('S01-B-CAT-zscore','S01 CAT') for r in selected]
    for scope,metrics in [('clean',['Accuracy','macro_F1','MAE','Pearson']),('attempted96',['macro_F1','MAE'])]:
        fig,axes=plt.subplots(1,len(metrics),figsize=(3.3*len(metrics),3.6),squeeze=False)
        for ax,metric in zip(axes[0],metrics):
            base=scope+'_'+metric;x=np.arange(len(selected))
            ax.errorbar(x,[float(r[base+'_mean']) for r in selected],yerr=[float(r[base+'_seed_sd_ddof1']) for r in selected],fmt='o',capsize=4,label='3-seed mean ± sample SD')
            ax.scatter(x+.08,[float(r[base+'_seed17']) for r in selected],marker='x',color='#c35c35',label='fixed seed17')
            ax.set_xticks(x,labels,rotation=35,ha='right');ax.set_title(metric);ax.grid(axis='y',alpha=.2)
        axes[0,0].legend(fontsize=7);fig.suptitle(scope+' VALID — descriptive, repeatedly selected VALID',y=1.03)
        finish(fig,scope+'_comparison')
    for recipe in ['M1','M2','M3','M4']:
        fig,axes=plt.subplots(3,3,figsize=(12,8))
        for row,seed in enumerate([17,29,43]):
            fit=next(f for f in fits if f['id']==f'{recipe}-s{seed}')
            rows=[r for r in curves if r['trial_id']==fit['id']];x=[int(r['epoch']) for r in rows]
            for col,(field,title) in enumerate([('train_loss_total','TRAIN online loss'),('clean_valid_macro_F1','clean VALID F1'),('clean_valid_MAE','clean VALID MAE')]):
                ax=axes[row,col];ax.plot(x,[float(r[field]) for r in rows],marker='.',color='#326ca2');ax.axvline(fit['selected_epoch'],color='#c35c35',ls='--',label='final selected epoch')
                ax.set_title(f'seed{seed} | {title}');ax.set_xlabel('Completed epoch');ax.set_xticks(x[::2]);ax.grid(alpha=.2)
        axes[0,0].legend(fontsize=7);fig.suptitle(recipe+': TRAIN online current-view ≠ end-checkpoint clean TRAIN',y=1.01)
        finish(fig,recipe+'_all_seed_curves')
    factors=read('FACTOR_DESCRIPTIVES.csv')
    for dimension in sorted(set(r['dimension'] for r in factors)):
        fig,axes=plt.subplots(1,2,figsize=(11,4))
        values=list(dict.fromkeys(r['value'] for r in factors if r['dimension']==dimension))
        for recipe in ['M1','M2','M3','M4']:
            for ax,metric in zip(axes,['macro_F1','MAE']):
                groups=[[float(r[metric]) for r in factors if r['configuration']==recipe and r['dimension']==dimension and r['value']==v] for v in values]
                ax.errorbar(range(len(values)),[np.mean(g) for g in groups],yerr=[np.std(g,ddof=1) for g in groups],capsize=3,marker='o',label=recipe)
                ax.set_xticks(range(len(values)),values);ax.set_title(metric);ax.set_xlabel(dimension+' (supported coordinates; not seconds)');ax.grid(alpha=.2)
        axes[0].legend();finish(fig,'robustness_'+dimension)
    clean=json.loads((Path(private_campaign)/'M2-s17/evaluation.json').read_bytes())['clean']
    matrix=np.asarray(clean['confusion']);fig,axes=plt.subplots(1,2,figsize=(10,4))
    axes[0].pcolormesh(np.arange(4)-.5,np.arange(4)-.5,matrix,cmap='Blues',shading='flat')
    axes[0].invert_yaxis();axes[0].set_aspect('equal')
    names=['Negative','Neutral','Positive']
    for i in range(3):
        for j in range(3):axes[0].text(j,i,str(matrix[i,j]),ha='center',va='center')
    axes[0].set_xticks(range(3),names);axes[0].set_yticks(range(3),names);axes[0].set_xlabel('Predicted');axes[0].set_ylabel('True');axes[0].set_title('M2 seed17 clean VALID')
    for k,metric in enumerate(['precision','recall','F1']):axes[1].bar(np.arange(3)+(k-1)*.24,[r[metric] for r in clean['per_class']],width=.24,label=metric)
    axes[1].set_xticks(range(3),names);axes[1].set_ylim(0,1);axes[1].legend();finish(fig,'M2_confusion_per_class')
    fig,axes=plt.subplots(1,2,figsize=(13,8))
    for ax,metric in zip(axes,['macro_F1','MAE']):
        y=np.arange(len(candidates));base='attempted96_'+metric
        ax.errorbar([float(r[base+'_mean']) for r in candidates],y,xerr=[float(r[base+'_seed_sd_ddof1']) for r in candidates],fmt='o',capsize=3)
        ax.set_yticks(y,[r['configuration'] for r in candidates]);ax.set_xlabel(metric+' mean ± sample SD');ax.grid(axis='x',alpha=.2)
    fig.suptitle('All fixed candidates retained, including negative results');finish(fig,'all_candidates')
    # The complete immutable source tables remain canonical plot data, not regenerated scores.
    manifest={'status':'VERIFIED','epoch_rows':len(curves),'fits':len(fits),'candidates':len(candidates),'new_model_runs':0,
      'limitations':['Repeated VALID selection optimism','SD is not CI or significance','144 views are not independent samples','TRAIN online is not clean checkpoint TRAIN'],
      'source_files':[{ 'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in [SOURCE/x for x in ['EPOCH_CURVES.csv','FITS.json','CANDIDATE_COMPARISON.csv','FACTOR_DESCRIPTIVES.csv']]],
      'figures':[{'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size} for p in artifacts]}
    (out/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    (out/'M2_AGGREGATE_CONFUSION.json').write_text(json.dumps(clean,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'figures':len(artifacts),'epoch_rows':148,'status':'VERIFIED'}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--private-campaign',required=True);run(p.parse_args().private_campaign)
