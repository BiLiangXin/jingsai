"""Closed synthetic one-epoch roundtrips, never official model experiments."""
import json,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import torch
from mosei.s01.contracts import synthetic_batch,configure_runtime
from mosei.s01.models import R01Model
from mosei.s01.normalization import Normalizer
from mosei.s01.protocol import ValidationLibrary
from mosei.s02 import engine

class OneEpochSelector:
    def __init__(self):self.trace=[]
    def update(self,f,m):
        self.trace.append((f,m));return dict(save=True,stop=True,best_epoch=1)
class SyntheticBudget:
    def __call__(self):pass
    def start_fit(self):pass
    def end_fit(self):pass

def test_four_closed_synthetic_checkpoint_epoch_log_roundtrips(tmp_path):
    configure_runtime()
    train,valid=synthetic_batch(8,101),synthetic_batch(4,102)
    norm=Normalizer('zscore').fit([train],split='train')
    train,valid=norm.transform(train),norm.transform(valid);library=ValidationLibrary(valid)
    for recipe in ('M1','M2','M3','M4'):
        teacher=R01Model('B-CAT',17).eval() if recipe=='M4' else None
        folder=tmp_path/recipe
        with patch.object(engine,'require_active'),patch.object(engine,'CheckpointSelector',OneEpochSelector):
            result=engine.fit(dict(recipes=['M1','M2','M3','M4'],model_seeds=[17,29,43]),recipe,17,
                train,valid,norm,library,teacher,folder,dict(data_kind='SYNTHETIC_ONLY'),SyntheticBudget())
        assert result['status']=='VALIDATION_COMPLETE_PENDING_SOURCE_CHECK'
        assert result['selected_epoch']==result['evaluated_epochs']==1
        assert len(result['condition_reports'])==96
        assert sum(map(len,result['condition_reports'].values()))==144
        row=json.loads((folder/'epoch_events.jsonl').read_text())
        assert row['train_samples']==row['corruption_counts']['rows']==8
        losses=row['train_loss']
        assert abs(losses['total']-(losses['weighted_CE']+losses['MAE']/3+losses['KD']))<1e-6
        assert row['learning_rate']==.001 and row['checkpoint_saved'] and row['early_stop']
        assert row['train_metric_scope'].startswith('ONLINE_PRE_UPDATE')
        for filename in ('best.pt','last.pt'):
            saved=torch.load(folder/filename,map_location='cpu',weights_only=True)
            assert saved['normalizer']==norm.state_dict() and saved['epoch']==1
            assert saved['optimizer']['state'] and saved['torch_rng'].numel()>0
        if teacher is not None:
            assert all(p.grad is None and not p.requires_grad for p in teacher.parameters())
