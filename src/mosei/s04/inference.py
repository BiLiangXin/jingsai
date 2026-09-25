"""Fixed M2/V1 feature-space inference for aligned official special inputs."""
from __future__ import annotations
import hashlib,json,math
from pathlib import Path
import numpy as np
import torch
from mosei.s01.contracts import MODS,DIMS,require,digest
from mosei.s01.normalization import Normalizer
from mosei.s02.models import ResidualAttentionModel
from mosei.s03.core import adapter,coalition,shapley,content_window,disjoint_top

FIXED_CHECKPOINT='f99426be8d90b8abf196faf9cf92a41c5ab607da661a7a91530f1fe481a0ceb9'
FIXED_SCALER='83a95b4acd9254fdd20675832ca4d25ed9e5bd62f284e7ec48e3cc6cb996cf2e'
CLASS_NAMES=('Negative','Neutral','Positive')
EXPECTED_KEYS={'text','audio','vision','text_bert','id','raw_text'}
FORBIDDEN={'label','labels','classification_labels','regression_labels','target','targets','train','valid'}

def sha_file(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
 return h.hexdigest()

def parse_aligned_special(item):
 """One official aligned record; id/raw_text never enter predictor inputs."""
 require(type(item)==dict,'Feature dict required')
 require(not set(item)&FORBIDDEN,'Label or split field forbidden')
 require(set(item)<=EXPECTED_KEYS and {'text','audio','vision','text_bert'}<=set(item),'Missing or ambiguous feature fields')
 result={}
 for modality in MODS:
  raw=np.asarray(item[modality])
  require(raw.shape==(50,DIMS[modality]) and np.issubdtype(raw.dtype,np.floating) and np.isfinite(raw).all(),'Continuous aligned shape/dtype/finite')
  array=raw.astype(np.float32)
  require(np.isfinite(array).all(),'Float32 conversion overflow')
  result[modality]=array
 bert=np.asarray(item['text_bert'])
 require(bert.shape==(3,50) and np.issubdtype(bert.dtype,np.integer),'Token/support container')
 channel=bert[1]
 require(np.isin(channel,[0,1]).all(),'Support binary')
 support=channel==1
 require(bool(support.any()) and not bool(np.any((~support[:-1])&support[1:])),'Support nonempty prefix')
 identifier=item.get('id')
 def scalar(value):
  if isinstance(value,np.generic):value=value.item()
  require(isinstance(value,(str,int,float)) and not isinstance(value,bool),'Identifier scalar type')
  if isinstance(value,float):require(math.isfinite(value),'Identifier finite')
  require(str(value)!='','Identifier empty')
  return value
 if identifier is not None:
  if isinstance(identifier,(tuple,list,np.ndarray)):
   require(len(identifier)>0,'Identifier empty')
   identifier=json.dumps([scalar(v) for v in identifier],ensure_ascii=False,separators=(',',':'))
  else:identifier=str(scalar(identifier))
 return result,support,identifier

def load_locked_model(path,*,inference_export=False,device='cpu'):
 path=Path(path)
 if not inference_export:require(sha_file(path)==FIXED_CHECKPOINT,'Original checkpoint changed')
 data=torch.load(path,map_location='cpu',weights_only=True)
 if inference_export:
  require(data['architecture']=='M2' and data['seed']==17 and data['selected_epoch']==2,'Export binding')
  state=data['model'];norm_state=data['normalizer']
 else:
  require(data['epoch']==2,'Original selected epoch changed')
  state=data['model'];norm_state=data['normalizer']
 require(digest(norm_state)==FIXED_SCALER,'TRAIN scaler changed')
 model=ResidualAttentionModel('M2',17,prior=state['prior'].tolist(),median=float(state['median']))
 model.load_state_dict(state,strict=True);model.requires_grad_(False);model.eval();model.to(device)
 norm=Normalizer.from_state_dict(norm_state)
 return model,norm

def model_state_hash(model):
 h=hashlib.sha256()
 for key,value in sorted(model.state_dict().items()):
  h.update(key.encode());h.update(value.detach().cpu().numpy().tobytes())
 return h.hexdigest()

def inputs_from_record(arrays,support,norm,*,device='cpu'):
 visible={m:torch.as_tensor(arrays[m][None],dtype=torch.float32,device=device) for m in MODS}
 mask=torch.as_tensor(support[None],dtype=torch.bool,device=device)
 return adapter(visible,mask,norm,'V1')

def contribution_card(phi):
 signed=[float(x) for x in phi]
 magnitude=[abs(x) for x in signed];total=sum(magnitude)
 if total==0:return dict(signed=signed,relative=[None,None,None],main_modality=None,status='NO_RESOLVABLE_EFFECT')
 return dict(signed=signed,relative=[x/total for x in magnitude],main_modality=MODS[int(np.argmax(magnitude))],status='RESOLVABLE_CONTENT_EFFECT')

def unmapped_window(start,end,delta):
 return dict(feature_start=start,feature_end_exclusive=end,timestamp_start=None,timestamp_end=None,mapping_status='UNVERIFIED_MAPPING',signed_full_minus_deleted=float(delta))

@torch.no_grad()
def predict_and_explain(model,norm,arrays,support,*,device='cpu'):
 before=model_state_hash(model)
 inp=inputs_from_record(arrays,support,norm,device=device)
 full=model(inp);cls=int(full['logits'][0].argmax());strength=float(full['regression'][0])
 require(math.isfinite(strength) and -3<=strength<=3,'Regression range')
 target=lambda v:torch.stack((v['logits'][:,cls],v['regression']),dim=1).double()
 values=torch.stack([target(model(coalition(inp,bits))) for bits in range(8)])
 require(torch.allclose(values[7],target(full),atol=1e-6,rtol=1e-5),'Full coalition')
 phi=shapley(values)
 require(torch.allclose(phi.sum(1),values[7]-values[0],atol=1e-6,rtol=1e-5),'Shapley efficiency')
 n=int(support.sum());all_deltas=[]
 if n>=3:
  for start in range(n-2):
   changed=model(content_window(inp,list(range(start,start+3))))
   all_deltas.append((values[7,0]-target(changed)[0]).tolist())
 windows={}
 for k,name in enumerate(('class','reg')):
  if not all_deltas:windows[name]=[]
  else:
   starts=disjoint_top([d[k] for d in all_deltas],width=3,limit=3)
   windows[name]=[unmapped_window(s,s+3,all_deltas[s][k]) for s in starts]
 need=model_state_hash(model)==before
 require(need,'Model parameters/buffers mutated')
 return dict(polarity=CLASS_NAMES[cls],intensity=strength,class_target=cls,class_card=contribution_card(phi[0,:,0].tolist()),reg_card=contribution_card(phi[0,:,1].tolist()),class_windows=windows['class'],reg_windows=windows['reg'],mapping_status='UNVERIFIED_MAPPING',efficiency_error=float((phi.sum(1)-(values[7]-values[0])).abs().max()))
