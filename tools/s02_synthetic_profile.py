"""Closed synthetic cost probe; cannot accept an official data path."""
import argparse,json,os,platform,sys,time
from pathlib import Path
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import torch
from mosei.s01.contracts import configure_runtime,synthetic_batch
from mosei.s01.models import R01Model,parameter_count
from mosei.s02.models import ResidualAttentionModel,supervised_loss,distillation_loss
from mosei.s02.engine import train_available
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise ValueError('No profile overwrite')
    configure_runtime();b=synthetic_batch(32,220701,dense=True).to('cuda');rows=[]
    for recipe in ('M1','M4'):
        model=ResidualAttentionModel(recipe).to('cuda');teacher=R01Model('B-CAT').to('cuda').eval();teacher.requires_grad_(False)
        optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.0001)
        torch.cuda.reset_peak_memory_stats();times=[]
        for step in range(12):
            torch.cuda.synchronize();t=time.perf_counter();optimizer.zero_grad(set_to_none=True)
            active=train_available(b,17,step)[0] if recipe=='M4' else None
            out=model(b.inputs(active));loss=supervised_loss(out,b.classes,b.values)
            if recipe=='M4':
                with torch.no_grad():teach=teacher(b.inputs())['logits']
                loss=loss+distillation_loss(out['logits'],teach,split='train')
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.,error_if_nonfinite=True);optimizer.step()
            torch.cuda.synchronize();times.append(time.perf_counter()-t)
        model.eval();forward=[]
        with torch.no_grad():
            for step in range(12):
                torch.cuda.synchronize();t=time.perf_counter();model(b.inputs());torch.cuda.synchronize();forward.append(time.perf_counter()-t)
        rows.append(dict(recipe=recipe,parameters=parameter_count(model),measured_steps=10,warmup_steps=2,
            step_mean_seconds=sum(times[2:])/10,forward_mean_seconds=sum(forward[2:])/10,peak_allocated_bytes=torch.cuda.max_memory_allocated()))
    # Conservative planning only: assume max100epochs,106train/23valid batches and144final views.
    slow=max(r['step_mean_seconds'] for r in rows);inf=max(r['forward_mean_seconds'] for r in rows)
    estimate=12*(100*(107*slow+23*inf)+145*23*inf)
    result=dict(status='PASS',data_kind='SYNTHETIC_ONLY',official_model_experiment=False,predictive_metrics=None,
        environment=dict(python=platform.python_version(),torch=torch.__version__,cuda=torch.version.cuda,cudnn=torch.backends.cudnn.version(),
            gpu=torch.cuda.get_device_name(0),platform=platform.platform(),threads=torch.get_num_threads(),tf32=False),rows=rows,
        planning_only_max100_epoch_12fit_seconds=estimate,planning_overhead_multiplier=2,
        planning_with_double_overhead_seconds=estimate*2,
        limitations=['Synthetic dense inputs and12steps do not guarantee official runtime.','No official metrics or extrapolated accuracy.','Four-hour hard cap and partial results prevail.'])
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result))
if __name__=='__main__':main()
