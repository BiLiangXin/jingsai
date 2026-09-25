"""One fixed visible-UNK frontend for VALID replay and gated aligned special inference."""
import argparse,csv,datetime,hashlib,json,os,pickle,subprocess,sys
from pathlib import Path
import numpy as np
import torch
import transformers
from transformers import AutoTokenizer,BertModel

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'src'))
from mosei.s04.inference import load_locked_model,model_state_hash,CLASS_NAMES
from mosei.s03.core import adapter
from research.r01.reference import generate

CONFIG=json.loads((ROOT/'configs/s04_deploy_03.json').read_bytes())

def need(ok,msg):
    if not ok:raise ValueError(msg)
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda:f.read(1<<20),b''):h.update(part)
    return h.hexdigest()
def save(path,obj):
    path=Path(path);need(not path.exists(),'OUTPUT_EXISTS');path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes((json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())
def time_guard():
    now=datetime.datetime.now(datetime.timezone.utc)
    deadline=datetime.datetime.fromisoformat(CONFIG['deadline_utc'].replace('Z','+00:00'))
    submit=datetime.datetime.fromisoformat(CONFIG['submission_deadline_beijing']).astimezone(datetime.timezone.utc)-datetime.timedelta(minutes=CONFIG['submission_buffer_minutes'])
    need(now<min(deadline,submit),'S04_DEPLOY_03_DEADLINE')
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()

def verify_local(encoder_dir,checkpoint):
    encoder_dir=Path(encoder_dir);need(transformers.__version__==CONFIG['transformers'],'TRANSFORMERS_VERSION')
    for file,key in [('pytorch_model.bin','encoder_weights_sha256'),('config.json','encoder_config_sha256'),('vocab.txt','vocab_sha256'),('tokenizer.json','tokenizer_sha256')]:
        need(sha(encoder_dir/file)==CONFIG[key],'ENCODER_FILE_'+file)
    need(sha(checkpoint)==CONFIG['checkpoint_sha256'],'M2_CHECKPOINT_SHA')
    tokenizer=AutoTokenizer.from_pretrained(encoder_dir,local_files_only=True,use_fast=True)
    ids={'unk':tokenizer.unk_token_id,'pad':tokenizer.pad_token_id,'cls':tokenizer.cls_token_id,'sep':tokenizer.sep_token_id,'mask':tokenizer.mask_token_id}
    need(ids=={'unk':100,'pad':0,'cls':101,'sep':102,'mask':103},'TOKENIZER_SPECIAL_IDS')
    need(tokenizer.convert_ids_to_tokens(100)=='[UNK]' and tokenizer.vocab_size==30522,'UNK_VOCAB_SEMANTICS')
    model,norm=load_locked_model(checkpoint,device='cuda')
    need(norm.fit_split=='train','SCALER_FIT_SPLIT')
    encoder=BertModel.from_pretrained(encoder_dir,local_files_only=True).to('cuda').eval()
    encoder.requires_grad_(False)
    return encoder,model,norm,ids

def validate_tokens(value):
    b=np.asarray(value)
    if b.ndim==2:b=b[None]
    need(b.ndim==3 and b.shape[1:]==(3,50) and b.shape[0]>0,'TOKEN_SHAPE')
    need(np.issubdtype(b.dtype,np.number) and np.isfinite(b).all(),'TOKEN_FINITE_NUMERIC')
    need(np.equal(b,np.floor(b)).all(),'TOKEN_INTEGRAL_VALUES')
    ids,mask,segment=b[:,0],b[:,1],b[:,2]
    need(np.logical_and(ids>=0,ids<30522).all(),'TOKEN_VOCAB_RANGE')
    need(np.isin(mask,[0,1]).all() and np.isin(segment,[0,1]).all(),'MASK_SEGMENT_BINARY')
    need(np.all(mask[:,0]==1) and not np.any((mask[:,:-1]==0)&(mask[:,1:]==1)),'SUPPORT_PREFIX')
    length=mask.sum(axis=1).astype(int)
    need(np.all(length>=2) and np.all(ids[:,0]==101) and np.all(ids[np.arange(len(b)),length-1]==102),'CLS_SEP_BOUNDARY')
    need(np.all(ids[mask==0]==0) and np.all(segment[mask==0]==0),'PADDING_SEGMENT_RULE')
    return b.astype(np.int64),mask.astype(bool)

@torch.no_grad()
def encode_visible(encoder,tokens):
    b,support=validate_tokens(tokens)
    tensor=torch.as_tensor(b,device='cuda',dtype=torch.long)
    result=encoder(input_ids=tensor[:,0],attention_mask=tensor[:,1],token_type_ids=tensor[:,2]).last_hidden_state
    need(tuple(result.shape)==(len(b),50,768) and bool(torch.isfinite(result).all()),'ENCODER_OUTPUT')
    return result.float(),support

@torch.no_grad()
def predict(model,norm,text,audio,vision,support):
    visible={'text':text,'audio':torch.as_tensor(audio,dtype=torch.float32,device='cuda'),'vision':torch.as_tensor(vision,dtype=torch.float32,device='cuda')}
    mask=torch.as_tensor(support,dtype=torch.bool,device='cuda')
    return model(adapter(visible,mask,norm,'V1'))

def verify_prior(prior_dir):
    root=Path(prior_dir)
    for name,key in [('A3_EXPANDED_REPLAY_FINAL.json','old_96_replay_sha256'),('A2_BERT_REPLAY.json','initial_strict_replay_sha256'),('A2_BERT_CPU_GPU_COMPARISON.json','cpu_gpu_envelope_sha256')]:
        need(sha(root/name)==CONFIG[key],'PRIOR_RECEIPT_'+name)
    old=json.loads((root/'A3_EXPANDED_REPLAY_FINAL.json').read_bytes())
    need(old['clean_expanded_replay']['train']['class_agreement']==64 and old['clean_expanded_replay']['valid']['class_agreement']==32,'OLD_96_CLEAN_REPLAY')
    need(old['clean_expanded_replay']['train']['active_allclose_backend_envelope_5e_4_1e_4'] and old['clean_expanded_replay']['valid']['active_allclose_backend_envelope_5e_4_1e_4'],'OLD_ENVELOPE')
    strict=json.loads((root/'A2_BERT_REPLAY.json').read_bytes())
    need(not strict['results']['train']['active_allclose_1e_5_1e_4'] and not strict['results']['valid']['active_allclose_1e_5_1e_4'],'STRICT_FAILURE_NOT_PRESERVED')

def valid_gate(args):
    time_guard();verify_prior(args.prior)
    need(torch.cuda.is_available(),'CUDA_REQUIRED')
    encoder,model,norm,ids=verify_local(args.encoder,args.checkpoint)
    before=model_state_hash(model)
    need(sha(args.a2)==CONFIG['a2_aligned_sha256'],'A2_SOURCE_SHA')
    with Path(args.a2).open('rb') as f:dataset=pickle.load(f)
    valid=dataset['valid'];n=len(valid['text_bert']);need(n==728,'VALID_COUNT')
    active_allclose=True;max_feature=0.;max_logit=0.;max_reg=0.;agree=0;active_count=0
    clean_logits=[];clean_reg=[]
    for begin in range(0,n,8):
        time_guard();end=min(n,begin+8);tokens=np.asarray(valid['text_bert'][begin:end]);encoded,support=encode_visible(encoder,tokens)
        original=torch.as_tensor(valid['text'][begin:end],dtype=torch.float32,device='cuda')
        active=torch.as_tensor(support,device='cuda');delta=(encoded-original).abs();criterion=delta<=(CONFIG['feature_atol']+CONFIG['feature_rtol']*original.abs())
        active_allclose=active_allclose and bool(criterion[active].all());max_feature=max(max_feature,float(delta[active].max()));active_count+=int(active.sum())
        baseline=predict(model,norm,original,valid['audio'][begin:end],valid['vision'][begin:end],support)
        candidate=predict(model,norm,encoded,valid['audio'][begin:end],valid['vision'][begin:end],support)
        max_logit=max(max_logit,float((baseline['logits']-candidate['logits']).abs().max()));max_reg=max(max_reg,float((baseline['regression']-candidate['regression']).abs().max()))
        agree+=int((baseline['logits'].argmax(-1)==candidate['logits'].argmax(-1)).sum())
        clean_logits.extend(candidate['logits'].detach().cpu().tolist());clean_reg.extend(candidate['regression'].detach().cpu().tolist())
    clean={'rows':n,'active_positions':active_count,'feature_allclose_fixed_envelope':active_allclose,'max_feature_abs':max_feature,'max_logit_abs':max_logit,'max_regression_abs':max_reg,'argmax_agreement':agree}
    need(active_allclose and max_logit<=CONFIG['model_output_max_abs'] and max_reg<=CONFIG['model_output_max_abs'] and agree==n,'CLEAN_VALID_REPLAY_FAIL')
    diagnostics=[]
    for ordinal in range(CONFIG['pressure_ordinals_start'],CONFIG['pressure_ordinals_end_exclusive']):
        time_guard();b,support=validate_tokens(valid['text_bert'][ordinal]);s=support[0];observed={'T':s.tolist(),'A':(s & ~np.all(np.asarray(valid['audio'][ordinal])==0,axis=1)).tolist(),'V':(s & ~np.all(np.asarray(valid['vision'][ordinal])==0,axis=1)).tolist()}
        r=generate(s.tolist(),observed,tuple(CONFIG['pressure_condition']),root_seed=CONFIG['valid_mask_root'],ordinal=ordinal,replicate=0,namespace='valid')
        changed=b.copy();positions=np.flatnonzero(r['C']['T']) if r['status']=='ELIGIBLE' else np.array([],dtype=int)
        eligible=bool(len(positions) and np.all(positions>0) and np.all(positions<int(s.sum())-1))
        if eligible:changed[0,0,positions]=100
        text,after_support=encode_visible(encoder,changed);need(np.array_equal(after_support,support),'PRESSURE_SUPPORT_CHANGED')
        out=predict(model,norm,text,np.asarray(valid['audio'][ordinal:ordinal+1]),np.asarray(valid['vision'][ordinal:ordinal+1]),support)
        prior_log=np.asarray(clean_logits[ordinal]);prior_reg=float(clean_reg[ordinal]);now_log=out['logits'][0].detach().cpu().numpy();now_reg=float(out['regression'][0])
        diagnostics.append({'ordinal':ordinal,'eligible':eligible,'fallback':None if eligible else 'CLEAN_ONCE','unk_replacements':int(len(positions)) if eligible else 0,'class_changed':bool(np.argmax(prior_log)!=np.argmax(now_log)),'max_abs_logit_delta':float(np.max(np.abs(prior_log-now_log))),'abs_regression_delta':abs(prior_reg-now_reg)})
    need(len(diagnostics)==32 and model_state_hash(model)==before,'DIAGNOSTIC_OR_MODEL_STATE')
    report={'status':'PASS','pipeline_id':CONFIG['pipeline_id'],'token_vocab':{'id100':'[UNK]','ids':ids,'vocab_size':30522},'prior_96_replay_verified':True,'initial_strict_replay_failed_preserved':True,'clean_valid':clean,'unk_pressure':{'rows':32,'condition':CONFIG['pressure_condition'],'root':1103,'eligible':sum(x['eligible'] for x in diagnostics),'clean_once':sum(not x['eligible'] for x in diagnostics),'class_changed':sum(x['class_changed'] for x in diagnostics),'max_abs_logit_delta':max(x['max_abs_logit_delta'] for x in diagnostics),'max_abs_regression_delta':max(x['abs_regression_delta'] for x in diagnostics),'not_old_attempted96':True,'not_special_corruption_generator':True},'checkpoint_sha256':sha(args.checkpoint),'encoder_weights_sha256':sha(Path(args.encoder)/'pytorch_model.bin'),'scaler_digest':CONFIG['train_scaler_digest'],'model_state_unchanged':True,'special_metrics':None,'training_fits':0}
    output=Path(args.output);need(not output.exists(),'OUTPUT_EXISTS');output.mkdir(parents=True)
    save(output/'VALID_GATE.json',report);save(output/'UNK_DIAGNOSTIC_PRIVATE.json',diagnostics)
    print(json.dumps(report,ensure_ascii=False))

def infer(args):
    time_guard();need(CONFIG['status']=='ACTIVE_AUTHORIZED' and CONFIG['training_fits']==0,'TASK_CLOSED')
    head=git('rev-parse','HEAD');need(git('branch','--show-current')=='codex/mosei-auto' and git('remote','get-url','origin')=='https://github.com/BiLiangXin/jingsai.git','GIT_IDENTITY')
    need(not git('status','--porcelain') and git('ls-remote','origin','refs/heads/codex/mosei-auto').split()[0]==head,'GIT_PUBLICATION')
    gate=json.loads((ROOT/'reports/s04_deploy_03/GATE.json').read_bytes())
    need(gate['status']=='PASS' and gate['pipeline_id']==CONFIG['pipeline_id'],'GATE_STATUS')
    need(sha(args.valid_gate)==gate['private_valid_gate_sha256'],'VALID_GATE_BINDING')
    review=json.loads((ROOT/'reports/s04_deploy_03/INDEPENDENT_REVIEW.json').read_bytes())
    need(review['status']=='PASS' and review['manifest_sha256']==gate['manifest_sha256'],'INDEPENDENT_REVIEW_BINDING')
    need(sha(args.manifest)==gate['manifest_sha256'],'MANIFEST_BINDING')
    manifest=json.loads(Path(args.manifest).read_bytes())
    for row in manifest['critical_files']:
        rel=row['path'];path=ROOT/rel;need(path.resolve().is_relative_to(ROOT.resolve()) and sha(path)==row['sha256'],'CRITICAL_HASH')
        committed=subprocess.check_output(['git','show',head+':'+rel],cwd=ROOT)
        need(committed==path.read_bytes(),'CRITICAL_NOT_COMMITTED')
    need(torch.cuda.is_available(),'CUDA_REQUIRED')
    encoder,model,norm,_=verify_local(args.encoder,args.checkpoint);before=model_state_hash(model)
    need(sha(args.structure)==CONFIG['a3_prior_structure_sha256'],'SOURCE_AUDIT_BINDING')
    structure=json.loads(Path(args.structure).read_bytes());source=Path(args.source).resolve();need(source.name=='附件3-模态缺失特征样本','SOURCE_ROOT')
    files=sorted(f for f in source.rglob('*.pkl') if f.parent.name.startswith('对齐'))
    need(len(files)==30 and len(structure['files'])==30,'SOURCE_POPULATION')
    for file,row in zip(files,structure['files']):need(sha(file)==row['source_sha256'] and file.stat().st_size==row['size'],'SOURCE_PREHASH')
    time_guard()
    output=Path(args.output);need(not output.exists(),'OUTPUT_EXISTS');claim=Path.home()/'.codex'/'mosei_execution_claims'/(CONFIG['claim_id']+'.json')
    need(not claim.exists(),'CLAIM_ALREADY_USED')
    with claim.open('x',encoding='utf-8') as stream:
        json.dump({'task_id':CONFIG['task_id'],'commit':head,'output_sha256':hashlib.sha256(str(output.resolve()).encode()).hexdigest(),'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},stream)
        stream.flush();os.fsync(stream.fileno())
    output.mkdir(parents=True);save(output/'CLAIM.json',{'claim_sha256':sha(claim),'commit':head,'pipeline_id':CONFIG['pipeline_id']})
    rows=[];embeddings=[];source_manifest=[]
    try:
        for index,file in enumerate(files):
            time_guard();original_sha=sha(file)
            with file.open('rb') as stream:wrapper=pickle.load(stream)
            need(type(wrapper)==dict and set(wrapper)=={'test'},'OFFICIAL_WRAPPER')
            item=wrapper['test'];need(type(item)==dict and set(item)=={'text_bert','audio','vision'},'OFFICIAL_FIELDS')
            token,support=validate_tokens(item['text_bert']);need(len(token)==1,'ONE_ROW_PER_FILE')
            audio=np.asarray(item['audio']);vision=np.asarray(item['vision'])
            need(audio.shape==(1,50,74) and vision.shape==(1,50,35) and np.isfinite(audio).all() and np.isfinite(vision).all(),'AUDIO_VISION_SCHEMA')
            text,again=encode_visible(encoder,token);need(np.array_equal(again,support),'SUPPORT_CHANGED')
            with torch.no_grad():answer=predict(model,norm,text,audio,vision,support)
            logits=answer['logits'][0].detach().cpu().numpy();value=float(answer['regression'][0])
            need(np.isfinite(logits).all() and np.isfinite(value) and -3<=value<=3,'PREDICTION_FINITE_RANGE')
            rel=file.relative_to(source).as_posix();identity=json.dumps([rel,0],ensure_ascii=False,separators=(',',':'))
            rows.append({'sample_index':index,'source_file':rel,'source_row':0,'sample_id':identity,'polarity':CLASS_NAMES[int(np.argmax(logits))],'intensity':value,'pipeline_id':CONFIG['pipeline_id']})
            embeddings.append(text[0].detach().cpu().numpy());source_manifest.append({'source_file':rel,'sha256':original_sha,'size':file.stat().st_size})
            need(sha(file)==original_sha,'SOURCE_POSTHASH')
        need(len(rows)==30 and len({r['sample_id'] for r in rows})==30 and model_state_hash(model)==before,'OUTPUT_POPULATION_OR_MODEL_STATE')
        csv_path=output/'attachment3_predictions.csv'
        with csv_path.open('x',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        with csv_path.open(newline='',encoding='utf-8') as stream:readback=list(csv.DictReader(stream))
        need(len(readback)==30 and len({r['sample_id'] for r in readback})==30 and all(r['polarity'] in CLASS_NAMES and -3<=float(r['intensity'])<=3 for r in readback),'CSV_READBACK')
        np.savez_compressed(output/'DERIVED_E1_TEXT_PRIVATE.npz',text=np.stack(embeddings))
        save(output/'SOURCE_MANIFEST_PRIVATE.json',source_manifest)
        result={'status':'INFERENCE_COMPLETE','pipeline_id':CONFIG['pipeline_id'],'commit':head,'rows':30,'aligned_sources':30,'source_manifest_sha256':sha(output/'SOURCE_MANIFEST_PRIVATE.json'),'csv_sha256':sha(csv_path),'derived_text_sha256':sha(output/'DERIVED_E1_TEXT_PRIVATE.npz'),'checkpoint_sha256':sha(args.checkpoint),'encoder_weights_sha256':sha(Path(args.encoder)/'pytorch_model.bin'),'model_state_unchanged':True,'special_metrics':None,'training_fits':0,'unknown_original_corruption_generator':True}
        save(output/'RESULT.json',result);print(json.dumps(result,ensure_ascii=False))
    except Exception as exc:
        save(output/'FAILURE_PRIVATE.json',{'status':'BLOCKED','error_type':type(exc).__name__,'reason':str(exc)})
        raise

if __name__=='__main__':
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='mode',required=True)
    a=sub.add_parser('valid');[a.add_argument('--'+name,required=True) for name in ('a2','prior','encoder','checkpoint','output')]
    b=sub.add_parser('infer');[b.add_argument('--'+name,required=True) for name in ('source','structure','encoder','checkpoint','valid-gate','manifest','output')]
    args=parser.parse_args()
    valid_gate(args) if args.mode=='valid' else infer(args)
