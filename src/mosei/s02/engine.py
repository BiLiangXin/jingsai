"""Exactly M1..M4; no retries, test data, or S01 execution authority."""
import json,time
import torch
from mosei.s01.contracts import MODS,require,stream_seed,digest
from mosei.s01.models import prior_statistics,parameter_count
from mosei.s01.protocol import CheckpointSelector,reference,SHORT,metric_report
from mosei.s01.engine import save_checkpoint
from .authorization import require_active
from .common import write_json,event,sha,now
from .models import ResidualAttentionModel,class_weights_train,supervised_loss,distillation_loss
from .evaluation import outputs,collect_views,score_cache

def train_available(batch,seed,epoch):
    batch.validate();s=batch.support.cpu().tolist();o={SHORT[m]:batch.observed[m].cpu().tolist() for m in MODS}
    draws=[]
    for i,ordinal in enumerate(batch.ordinals):
        observed={m:mask[i] for m,mask in o.items()};key=('train',2207,seed,epoch,ordinal)
        if reference.choose(4,*key,'clean_or_corrupt')!=3:
            draws.append(dict(A=observed,status='CLEAN_REQUESTED'));continue
        condition=reference.conditions()[reference.choose(96,*key,'condition')]
        draws.append(reference.generate(s[i],observed,condition,root_seed=2207,ordinal=ordinal,replicate=0,namespace=f'train:{seed}:{epoch}'))
    return {m:torch.tensor([d['A'][SHORT[m]] for d in draws],dtype=torch.bool,device=batch.support.device) for m in MODS},dict(
        rows=len(draws),clean_requested=sum(d['status']=='CLEAN_REQUESTED' for d in draws),
        eligible=sum(d['status']=='ELIGIBLE' for d in draws),ineligible=sum(d['status']=='INELIGIBLE' for d in draws))

def fit(c,recipe,seed,train,valid,normalizer,library,teacher,folder,provenance,budget):
    require_active(c,split='train',optimizer=True);require_active(c,split='valid')
    require(recipe in c['recipes'] and seed in c['model_seeds'] and not folder.exists(),'New fixed trial required')
    folder.mkdir();budget.start_fit();started=time.monotonic()
    prior,median=prior_statistics(train,split='train')
    model=ResidualAttentionModel(recipe,seed,prior=prior,median=median).to('cuda')
    optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.0001)
    weights=class_weights_train(train.classes,split='train').to('cuda') if recipe=='M2' else None
    selector=CheckpointSelector();trial=dict(recipe=recipe,seed=seed,architecture=recipe,normalizer='zscore',execution_config_hash=digest(c),
        lr=.001,weight_decay=.0001,batch_size=32,clip_norm=1,max_epochs=100,checkpoint='clean_F_then_MAE',
        p_corrupt=.25 if recipe in ('M3','M4') else 0.,KD=.1 if recipe=='M4' else 0.,tau=2)
    write_json(folder/'config.json',dict(config=trial,provenance=provenance,class_weights=None if weights is None else weights.cpu().tolist()))
    if teacher is not None:
        require(recipe=='M4' and teacher.architecture=='B-CAT' and teacher.seed==seed,'Same-seed S01 TRAIN teacher required')
        teacher.to('cuda').eval();teacher.requires_grad_(False)
    timing=[]
    for epoch in range(100):
        budget();epoch_start=time.perf_counter();model.train();counts=dict(rows=0,clean_requested=0,eligible=0,ineligible=0)
        loss_sums=dict(CE=0.,weighted_CE=0.,MAE=0.,KD=0.,total=0.);seen=0
        online_classes=[];online_values=[];online_targets=[];online_truth=[]
        order=torch.randperm(len(train.support),generator=torch.Generator().manual_seed(stream_seed(seed,f'data-order:{epoch}'))).tolist()
        for start in range(0,len(order),32):
            budget();part=train.take(order[start:start+32]).to('cuda')
            if recipe in ('M3','M4'):
                active,draw=train_available(part,seed,epoch)
                for k in counts:counts[k]+=draw[k]
            else:
                active=None;counts['rows']+=len(part.values);counts['clean_requested']+=len(part.values)
            optimizer.zero_grad(set_to_none=True)
            student=model(part.inputs(active));loss=supervised_loss(student,part.classes,part.values,class_weights=weights)
            kd_value=loss.detach().new_zeros(())
            if recipe=='M4':
                with torch.no_grad():teacher_logits=teacher(part.inputs())['logits']
                kd_value=distillation_loss(student['logits'],teacher_logits,split='train');loss=loss+kd_value
            with torch.no_grad():
                ce=torch.nn.functional.cross_entropy(student['logits'],part.classes,reduction='none')
                weighted=ce if weights is None else ce*weights[part.classes]
                n=len(part.values);seen+=n
                for k,v in dict(CE=ce.mean(),weighted_CE=weighted.mean(),MAE=(student['regression']-part.values).abs().mean(),KD=kd_value,total=loss).items():
                    loss_sums[k]+=float(v.detach())*n
                online_classes.extend(student['logits'].argmax(1).cpu().tolist());online_values.extend(student['regression'].detach().cpu().tolist())
                online_targets.extend(part.classes.cpu().tolist());online_truth.extend(part.values.cpu().tolist())
            if epoch==0 and start==0:write_json(folder/'optimizer_started.json',dict(recipe=recipe,seed=seed,time=now().isoformat(),data_kind='OFFICIAL_TRAIN_VALID'))
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.,error_if_nonfinite=True);optimizer.step()
            require(all(bool(torch.isfinite(p).all()) for p in model.parameters()),'Nonfinite parameter')
        torch.cuda.synchronize();train_time=time.perf_counter()-epoch_start
        validation_started=time.perf_counter()
        out=outputs(model,valid,guard=budget);metrics=metric_report(valid,out['logits'].argmax(1),out['regression'])
        valid_loss=float(supervised_loss(out,valid.classes.cpu(),valid.values.cpu(),class_weights=None if weights is None else weights.cpu()))
        validation_seconds=time.perf_counter()-validation_started
        choice=selector.update(metrics['macro_F1'],metrics['MAE'])
        if choice['save']:save_checkpoint(folder/'best.pt',model,optimizer,normalizer,epoch=epoch+1,trace=selector.trace,config=trial,provenance=provenance)
        save_checkpoint(folder/'last.pt',model,optimizer,normalizer,epoch=epoch+1,trace=selector.trace,config=trial,provenance=provenance)
        row=dict(epoch=epoch+1,selected_epoch=choice['best_epoch'],early_stop=choice['stop'],clean=metrics,corruption_counts=counts,
            train_seconds=train_time,validation_seconds=validation_seconds,epoch_seconds=time.perf_counter()-epoch_start,
            train_loss={k:v/seen for k,v in loss_sums.items()},valid_supervised_loss=valid_loss,
            train_online_metrics=reference.metrics(online_targets,online_truth,online_classes,online_values),
            train_metric_scope='ONLINE_PRE_UPDATE_CURRENT_VIEW_DIAGNOSTIC_NOT_CHECKPOINT_EVALUATION',
            train_samples=seen,learning_rate=optimizer.param_groups[0]['lr'],checkpoint_saved=choice['save'],
            total_elapsed_seconds=time.monotonic()-started)
        timing.append(row);event(folder/'epoch_events.jsonl',row)
        print(json.dumps(dict(event='EPOCH_COMPLETED',recipe=recipe,seed=seed,epoch=epoch+1,early_stop=choice['stop'])),flush=True)
        if choice['stop']:break
    ck=torch.load(folder/'best.pt',map_location='cpu',weights_only=True)
    require(ck['config_hash']==digest(trial) and ck['provenance']==provenance,'Selected checkpoint binding mismatch')
    model.load_state_dict(ck['model'],strict=True)
    cache=collect_views(model,valid,library,budget);torch.save(cache,folder/'predictions_private.pt')
    result=score_cache(cache,valid,library,seed)
    result.update(status='VALIDATION_COMPLETE_PENDING_SOURCE_CHECK',recipe=recipe,seed=seed,parameters=parameter_count(model),selected_epoch=ck['epoch'],
        evaluated_epochs=len(selector.trace),checkpoint_sha256=sha(folder/'best.pt'),last_checkpoint_sha256=sha(folder/'last.pt'),
        config_hash=digest(trial),provenance=provenance,runtime_seconds=time.monotonic()-started,
        inference_seconds=cache['runtime_seconds'],prediction_sha256=sha(folder/'predictions_private.pt'))
    write_json(folder/'evaluation.json',result)
    if teacher is not None:teacher.cpu()
    budget.end_fit();return result
