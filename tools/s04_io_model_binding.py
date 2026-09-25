"""Verify original and inference-only M2 containers without official data."""
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np,torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from mosei.s01.contracts import DIMS,digest
from mosei.s04.inference import load_locked_model,inputs_from_record,model_state_hash,sha_file,FIXED_CHECKPOINT,FIXED_SCALER
def need(ok,msg):
 if not ok:raise ValueError(msg)
def main():
 p=argparse.ArgumentParser();p.add_argument('--original',required=True);p.add_argument('--export',required=True);p.add_argument('--out',required=True);a=p.parse_args()
 original=Path(a.original);export=Path(a.export)
 need(sha_file(original)==FIXED_CHECKPOINT,'Original hash')
 model,norm=load_locked_model(original,device='cpu')
 cloned,norm2=load_locked_model(export,inference_export=True,device='cpu')
 need(model_state_hash(model)==model_state_hash(cloned),'Tensor state digest')
 s1=norm.state_dict();s2=norm2.state_dict();need(s1==s2 and digest(s1)==FIXED_SCALER,'Scaler equality')
 support=np.zeros(50,dtype=bool);support[:7]=True
 rng=np.random.default_rng(1701);arrays={m:rng.standard_normal((50,d),dtype=np.float32) for m,d in DIMS.items()}
 with torch.no_grad():
  prediction_original=model(inputs_from_record(arrays,support,norm));prediction_export=cloned(inputs_from_record(arrays,support,norm2))
 need(torch.equal(prediction_original['logits'],prediction_export['logits']) and torch.equal(prediction_original['regression'],prediction_export['regression']),'Synthetic output equality')
 result=dict(status='PASS',original_checkpoint_sha256=sha_file(original),export_sha256=sha_file(export),selected_seed=17,selected_epoch=2,scaler_canonical_sha256=FIXED_SCALER,all_model_tensors_and_buffers_exact=True,normalizer_exact=True,synthetic_predictions_exact=True,synthetic_seed=1701,new_training_fits=0)
 dest=Path(a.out);need(not dest.exists(),'No overwrite');dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
