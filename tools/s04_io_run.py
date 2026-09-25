"""Committed-gate, one-claim aligned Attachment4 private PARTIAL inference."""
import argparse,csv,datetime,hashlib,json,os,pickle,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import torch
from mosei.s01.contracts import require
from mosei.s04.inference import load_locked_model,parse_aligned_special,predict_and_explain,model_state_hash,sha_file,FIXED_CHECKPOINT,FIXED_SCALER
CONFIG=json.loads((ROOT/'configs/s04_execution.json').read_bytes())
FIELDS=['sample_index','source_file','source_row','sample_id','polarity','intensity','class_target','class_phi_T','class_phi_A','class_phi_V','reg_phi_T','reg_phi_A','reg_phi_V','class_main_modality','reg_main_modality','class_effect_status','reg_effect_status','class_relative_T','class_relative_A','class_relative_V','reg_relative_T','reg_relative_A','reg_relative_V','class_windows_json','reg_windows_json','mapping_status']
def save_new(path,obj):
 path=Path(path);require(not path.exists(),'No output overwrite');path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def guard_time():
 now=datetime.datetime.now(datetime.timezone.utc)
 for name in ['task_deadline_beijing','absolute_compute_deadline_beijing']:
  require(now<datetime.datetime.fromisoformat(CONFIG[name]),'S04 compute deadline')
def classify(root):
 require(root.name=='附件4-可解释专项视频样本与特征文件','Wrong official Attachment4 source')
 paths=sorted(root.rglob('*.pkl'),key=lambda f:f.relative_to(root).as_posix());aligned=[];unaligned=[]
 for f in paths:
  require(not f.is_symlink() and f.resolve().is_relative_to(root.resolve()),'Redirected source')
  n=f.relative_to(root).as_posix().lower()
  if '未对齐' in n or re.search(r'(?<![a-z])unaligned(?![a-z])',n):unaligned.append(f)
  elif '对齐' in n or re.search(r'(?<![a-z])aligned(?![a-z])',n):aligned.append(f)
  else:raise ValueError('Unclassified source')
 require(len(aligned)==len(unaligned)==20,'20 aligned/20 unaligned required')
 videos=list(root.rglob('*.mp4'));require(len(videos)==40,'40 video inventory')
 require(len({f.stem for f in aligned})==20 and len({f.stem for f in paths})==20,'Unique aligned-source population')
 require({f.stem for f in aligned}=={f.stem for f in videos},'Source/video stem association mismatch')
 return paths,aligned
def preflight():
 guard_time()
 require(CONFIG['status']=='ACTIVE_AUTHORIZED' and CONFIG['new_fit_budget']==0 and not CONFIG['training_authorized'],'Scope')
 require(git('branch','--show-current')=='codex/mosei-auto' and git('remote','get-url','origin')=='https://github.com/BiLiangXin/jingsai.git','Git identity')
 head=git('rev-parse','HEAD');remote=git('ls-remote','origin','refs/heads/codex/mosei-auto').split()[0]
 require(head==remote and not git('status','--porcelain'),'Clean published HEAD required')
 gate=ROOT/'reports/s04_io/GATE_A.json';g=json.loads(gate.read_bytes())
 manifest=ROOT/g['manifest_path'];review=ROOT/g['review_path']
 require(g['status']=='PASS' and g['scope']=='ATTACHMENT4_ALIGNED_GATE_A_ONLY','A4 Gate A')
 require(sha_file(manifest)==g['manifest_sha256'] and sha_file(review)==g['review_sha256'],'Review/manifest digest')
 report=json.loads(review.read_bytes());m=json.loads(manifest.read_bytes())
 require(report['status']=='PASS' and report['independent'] is True and report['review_inputs_sha256']==g['manifest_sha256'],'Independent review')
 require({x['path']:x['sha256'] for x in report['critical_files']}=={x['path']:x['sha256'] for x in m['critical_files']} and len(m['critical_files'])>0,'Critical set')
 for row in m['critical_files']:
  p=ROOT/row['path'];require(p.resolve().is_relative_to(ROOT.resolve()) and sha_file(p)==row['sha256'],'Critical hash')
  require(hashlib.sha256(subprocess.check_output(['git','show',head+':'+row['path']],cwd=ROOT).replace(b'\r\n',b'\n')).hexdigest()==hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),'Critical file uncommitted')
 for path in [gate,manifest,review]:
  rel=path.relative_to(ROOT).as_posix();require(subprocess.check_output(['git','show',head+':'+rel],cwd=ROOT).replace(b'\r\n',b'\n')==path.read_bytes().replace(b'\r\n',b'\n'),'Gate not committed')
 return head
def claim_once(output,head):
 require(hashlib.sha256(str(output.resolve()).encode()).hexdigest()==CONFIG['attachment4_private_output_binding_sha256'],'Unbound private output')
 require(not output.exists(),'No output overwrite/replay')
 claims=Path.home()/'.codex'/'mosei_execution_claims';claims.mkdir(exist_ok=True);claim=claims/(CONFIG['attachment4_claim_id']+'.json')
 with claim.open('x',encoding='utf-8') as f:
  json.dump(dict(task=CONFIG['attachment4_claim_id'],commit=head,output_digest=CONFIG['attachment4_private_output_binding_sha256'],time=datetime.datetime.now(datetime.timezone.utc).isoformat()),f);f.flush();os.fsync(f.fileno())
 output.mkdir(parents=True);return claim
def format_row(index,rel,identity,result):
 cc=result['class_card'];rr=result['reg_card']
 values=dict(sample_index=index,source_file=rel,source_row=0,sample_id=json.dumps([rel,identity],ensure_ascii=False,separators=(',',':')),polarity=result['polarity'],intensity=result['intensity'],class_target=result['class_target'],class_main_modality=cc['main_modality'],reg_main_modality=rr['main_modality'],class_effect_status=cc['status'],reg_effect_status=rr['status'],class_windows_json=json.dumps(result['class_windows'],ensure_ascii=False,separators=(',',':')),reg_windows_json=json.dumps(result['reg_windows'],ensure_ascii=False,separators=(',',':')),mapping_status='UNVERIFIED_MAPPING')
 for k,card in [('class',cc),('reg',rr)]:
  for m,v in zip('TAV',card['signed']):values[f'{k}_phi_{m}']=v
  for m,v in zip('TAV',card['relative']):values[f'{k}_relative_{m}']=v
 require(set(values)==set(FIELDS),'Frozen CSV schema')
 return values
def main():
 p=argparse.ArgumentParser();p.add_argument('--source-dir',required=True);p.add_argument('--original-checkpoint',required=True);p.add_argument('--source-structure-manifest',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 head=preflight();source=Path(a.source_dir)
 require(hashlib.sha256(str(source.resolve()).encode()).hexdigest()==CONFIG['attachment4_source_root_binding_sha256'],'Unbound official Attachment4 source root')
 allpaths,files=classify(source)
 require(sha_file(a.source_structure_manifest)==CONFIG['attachment4_structure_report_sha256'],'Unbound inspected source structure')
 structure=json.loads(Path(a.source_structure_manifest).read_bytes());require(structure['status']=='STRUCTURE_ONLY' and len(structure['rows'])==40,'Frozen structure report')
 model,norm=load_locked_model(a.original_checkpoint,device='cuda');before=model_state_hash(model)
 require(sha_file(a.original_checkpoint)==FIXED_CHECKPOINT,'Champion hash')
 output=Path(a.output);claim=claim_once(output,head)
 try:
  save_new(output/'CLAIM.json',dict(commit=head,claim_sha256=sha_file(claim),original_s03_claim_preserved=True))
  records=[]
  for i,f in enumerate(files):
   guard_time();ordinal=allpaths.index(f);expected=structure['rows'][ordinal]
   source_hash=sha_file(f);require(source_hash==expected['sha256'],'Special source changed')
   with f.open('rb') as stream:item=pickle.load(stream)
   arrays,support,identity=parse_aligned_special(item);del item
   rel=f.relative_to(source).as_posix();answer=predict_and_explain(model,norm,arrays,support,device='cuda')
   records.append(format_row(i,rel,identity or str(i),answer))
   require(sha_file(f)==source_hash,'Source changed during inference')
  require(len(records)==20 and len({x['sample_id'] for x in records})==20 and model_state_hash(model)==before,'Population/model state')
  dest=output/'attachment4_predictions_explanations_PARTIAL.csv'
  with dest.open('x',newline='',encoding='utf-8') as stream:
   writer=csv.DictWriter(stream,fieldnames=FIELDS);writer.writeheader();writer.writerows(records)
  with dest.open(newline='',encoding='utf-8') as stream:roundtrip=list(csv.DictReader(stream))
  require(len(roundtrip)==20 and all(x['polarity'] in ('Negative','Neutral','Positive') and -3<=float(x['intensity'])<=3 and x['mapping_status']=='UNVERIFIED_MAPPING' for x in roundtrip),'CSV round-trip')
  result=dict(status='PARTIAL',gate_a='PASS',gate_b='BLOCKED_NO_VERIFIED_OFFICIAL_TIME_MAPPING',aligned_records=20,unaligned_versions_not_opened_during_inference=20,prior_structure_audit_deserialized_all_40_versions=True,source_video_stem_matches=20,csv_sha256=sha_file(dest),csv_rows=20,checkpoint_sha256=sha_file(a.original_checkpoint),scaler_sha256=FIXED_SCALER,model_state_unchanged=True,timestamps='NULL',special_metrics=None,new_training_fits=0,commit=head,claim_sha256=sha_file(claim))
  save_new(output/'RESULT.json',result);save_new(ROOT/'reports/s04_io/A4_RESULT.json',result);print(json.dumps(result))
 except Exception as exc:
  save_new(output/'FAILURE_PRIVATE.json',dict(status='BLOCKED',error_type=type(exc).__name__,error=str(exc)));raise
if __name__=='__main__':main()
