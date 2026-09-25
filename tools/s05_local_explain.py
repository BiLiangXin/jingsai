"""Bounded VALID36 check and one frozen A4 per-modality explanation pass."""
import argparse,csv,hashlib,json,pickle,sys
from collections import Counter
from pathlib import Path
import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from mosei.s03.core import adapter
from mosei.s04.inference import CLASS_NAMES,load_locked_model,model_state_hash,parse_aligned_special
from mosei.s05.local import explain_fixed

CONFIG=json.loads((ROOT/'configs/s05_execution.json').read_bytes())
def need(x,msg):
    if not x:raise ValueError(msg)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def locked(checkpoint):
    need(sha(checkpoint)==CONFIG['m2_checkpoint_sha256'],'CHECKPOINT_CHANGED')
    model,norm=load_locked_model(checkpoint,device='cuda')
    need(norm.fit_split=='train','SCALER_FIT_SPLIT')
    return model,norm
def prepared(arrays,support,norm):
    visible={m:torch.as_tensor(arrays[m][None],device='cuda',dtype=torch.float32) for m in ('text','audio','vision')}
    return adapter(visible,torch.as_tensor(support[None],device='cuda',dtype=torch.bool),norm,'V1')
def valid36(args):
    need(torch.cuda.is_available(),'CUDA_REQUIRED')
    need(sha(args.a2)=='66e867aa74bc70a844e806e5571e371c9abb4a35f9e2887ce9b4d97ff2cb8fcd','A2_SOURCE')
    need(sha(args.cases)==CONFIG['fixed_valid36_cases_sha256'] and sha(args.old_cards)==CONFIG['old_valid_cards_sha256'] and sha(args.old_tensors)==CONFIG['old_valid_tensors_sha256'],'HISTORICAL_VALID36_BINDING')
    model,norm=locked(args.checkpoint);before=model_state_hash(model)
    cases=json.loads(Path(args.cases).read_bytes())['ordinals'];need(len(cases)==36 and len(set(cases))==36,'FIXED36_CASES')
    old=json.loads(Path(args.old_cards).read_bytes());need(len(old)==728,'OLD_VALID_CARDS')
    old_tensors=torch.load(args.old_tensors,map_location='cpu',weights_only=True)
    old_values=old_tensors['coalition_values'];need(tuple(old_values.shape)==(8,728,2),'OLD_FULL_VALUES')
    with Path(args.a2).open('rb') as stream:dataset=pickle.load(stream)
    valid=dataset['valid'];need(len(valid['text'])==728,'VALID_SIZE')
    counts=Counter();details=[];invariants=0
    for ordinal in cases:
        arrays={m:np.asarray(valid[m][ordinal],dtype=np.float32) for m in ('text','audio','vision')}
        support=np.asarray(valid['text_bert'][ordinal][1])==1
        x=prepared(arrays,support,norm)
        for modality in ('text','audio','vision'):
            for start in range(max(0,int(support.sum())-2)):
                if not bool(x['available'][modality][:,start:start+3].any()):continue
                from mosei.s05.local import one_modality_window
                changed=one_modality_window(x,modality,start)
                need(torch.equal(changed['support'],x['support']) and all(torch.equal(changed['available'][m],x['available'][m]) for m in ('text','audio','vision')),'VALID_MASK_CHANGED')
                need(all(torch.equal(changed['features'][m],x['features'][m]) for m in ('text','audio','vision') if m!=modality),'VALID_OTHER_MODALITY_CHANGED')
                expected=x['features'][modality].clone();selected=x['available'][modality][:,start:start+3]
                expected[:,start:start+3][selected]=0
                need(torch.equal(changed['features'][modality],expected),'VALID_TARGET_MODALITY_CHANGED_INCORRECTLY')
                invariants+=1
        result=explain_fixed(model,x)
        previous=old[ordinal]
        need(result['predicted_class_index']==previous['predicted_class'] and abs(result['full_class_logit']-float(old_values[7,ordinal,0]))<=1e-5 and abs(result['full_regression']-float(old_values[7,ordinal,1]))<=1e-5,'FIXED_PREDICTION_MISMATCH')
        for m,v in result['modalities'].items():
            for t,entry in v.items():
                counts[m+'_'+t+'_'+entry['status']]+=1
                for w in entry['windows']:
                    need(0<=w['feature_start']<w['feature_end_exclusive']<=int(support.sum()),'SUPPORT_WINDOW')
        details.append({'ordinal':ordinal,'result':result})
    need(model_state_hash(model)==before,'MODEL_MUTATED')
    out=Path(args.output);need(not out.exists(),'OUTPUT_EXISTS');out.mkdir(parents=True)
    (out/'VALID36_PRIVATE.json').write_text(json.dumps(details,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    report={'status':'PASS','rows':36,'old_full_predictions_matched':36,'actual_window_invariants_checked':invariants,'source_sha256':sha(args.a2),'checkpoint_sha256':sha(args.checkpoint),'fixed_cases_sha256':sha(args.cases),'old_cards_sha256':sha(args.old_cards),'old_tensors_sha256':sha(args.old_tensors),'local_code_sha256':sha(ROOT/'src/mosei/s05/local.py'),'runner_code_sha256':sha(__file__),'config_sha256':sha(ROOT/'configs/s05_execution.json'),'model_state_unchanged':True,'counts':dict(counts),'training_fits':0}
    (out/'VALID36_CHECK.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
def a4(args):
    need(torch.cuda.is_available(),'CUDA_REQUIRED')
    need(sha(args.old_csv)==CONFIG['a4_old_csv_sha256'],'OLD_A4_CSV_CHANGED')
    prior=json.loads(Path(args.valid_gate).read_bytes());need(prior['status']=='PASS' and prior['rows']==36 and prior['old_full_predictions_matched']==36 and prior['actual_window_invariants_checked']>0,'VALID36_GATE')
    need(prior['fixed_cases_sha256']==CONFIG['fixed_valid36_cases_sha256'] and prior['old_cards_sha256']==CONFIG['old_valid_cards_sha256'] and prior['old_tensors_sha256']==CONFIG['old_valid_tensors_sha256'],'VALID36_SOURCE_BINDING')
    need(prior['local_code_sha256']==sha(ROOT/'src/mosei/s05/local.py') and prior['runner_code_sha256']==sha(__file__) and prior['config_sha256']==sha(ROOT/'configs/s05_execution.json') and prior['checkpoint_sha256']==sha(args.checkpoint),'VALID36_CODE_MODEL_BINDING')
    model,norm=locked(args.checkpoint);before=model_state_hash(model)
    oldrows=list(csv.DictReader(Path(args.old_csv).open(encoding='utf-8-sig',newline='')))
    need(len(oldrows)==20,'OLD20')
    source=Path(args.source).resolve();out=Path(args.output);need(not out.exists(),'OUTPUT_EXISTS')
    records=[];counts=Counter()
    for ordinal,row in enumerate(oldrows):
        need(int(row['sample_index'])==ordinal,'OLD_ORDER')
        feature=(source/row['source_file']).resolve();need(feature.is_relative_to(source) and feature.is_file(),'SOURCE_PATH')
        old_map=json.loads((Path(args.prior_map)/f'row_{ordinal:02d}.json').read_bytes())
        need(old_map['ordinal']==ordinal and old_map['source_file']==row['source_file'] and old_map['source_sha256']==sha(feature),'SOURCE_PRIOR_BINDING')
        with feature.open('rb') as stream:item=pickle.load(stream)
        arrays,support,_=parse_aligned_special(item)
        x=prepared(arrays,support,norm);result=explain_fixed(model,x)
        need(CLASS_NAMES[result['predicted_class_index']]==row['polarity'] and abs(result['full_regression']-float(row['intensity']))<1e-5,'OLD_PREDICTION_CHANGED')
        need(result['predicted_class_index']==int(row['class_target']),'FIXED_CLASS_TARGET')
        addition=dict(row)
        addition['class_per_modality_v1_json']=json.dumps({m:result['modalities'][m]['class'] for m in ('text','audio','vision')},ensure_ascii=False,separators=(',',':'),allow_nan=False)
        addition['reg_per_modality_v1_json']=json.dumps({m:result['modalities'][m]['reg'] for m in ('text','audio','vision')},ensure_ascii=False,separators=(',',':'),allow_nan=False)
        addition['per_modality_method']='S05-EXPL-01_WIDTH3_TRAIN_ZERO_FIXED_TARGET'
        records.append(addition)
        for m in result['modalities']:
            for target,entry in result['modalities'][m].items():counts[m+'_'+target+'_'+entry['status']]+=1
    need(model_state_hash(model)==before,'MODEL_MUTATED')
    out.mkdir(parents=True)
    csv_path=out/'attachment4_predictions_explanations_SUPPLEMENTED_PRIVATE.csv'
    with csv_path.open('x',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    check=list(csv.DictReader(csv_path.open(encoding='utf-8',newline='')))
    need(len(check)==20 and all(all(check[i][k]==v for k,v in row.items()) for i,row in enumerate(oldrows)),'OLD_COLUMNS_MUTATED')
    report={'status':'PASS','rows':20,'old_csv_sha256':sha(args.old_csv),'new_csv_sha256':sha(csv_path),'old_columns_unchanged':True,'model_state_unchanged':True,'checkpoint_sha256':sha(args.checkpoint),'counts':dict(counts),'special_metrics':None,'training_fits':0}
    (out/'A4_SUPPLEMENT_RESULT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='mode',required=True)
    v=sub.add_parser('valid36');[v.add_argument('--'+x,required=True) for x in ('a2','cases','old-cards','old-tensors','checkpoint','output')]
    a=sub.add_parser('a4');[a.add_argument('--'+x,required=True) for x in ('source','old-csv','checkpoint','valid-gate','prior-map','output')]
    args=p.parse_args();valid36(args) if args.mode=='valid36' else a4(args)
