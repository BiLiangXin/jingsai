# Portable equivalent of the independently executed stdin probe; not a second run.
import hashlib, json, math, runpy
from pathlib import Path
root=Path(__file__).resolve().parents[2]
r=runpy.run_path(str(root/'research/r01/reference.py'))
def reject(fn):
    try: fn()
    except ValueError: return True
    return False
def grid():
    g={}
    for seed in r['MODEL_SEEDS']:
        g[seed]={}
        for c in r['conditions']():
            g[seed][r['condition_id'](c)]=[dict(attempted=dict(macro_F1=.5,MAE=1.,n=2),eligible_count=2,total_count=2,pairing=r['pairing_stamp']([0,1],[True,True],str(i)*64,i)) for i in range(3 if c[2]=='random' else 1)]
    return g
ref=dict(configuration='B*',seed=17,clean_F=.8,clean_MAE=.5)
win=dict(configuration='winner',seed=17,clean_F=.6,clean_MAE=.8)
checks={}
checks['positive_common_shift_ce']=math.isclose(r['joint_loss']([1e20]*3,0.,0.),math.log(3))
checks['negative_common_shift_ce']=math.isclose(r['joint_loss']([-1e20]*3,0.,0.),math.log(3))
checks['unrepresentable_ce_rejected']=reject(lambda:r['joint_loss']([1e308,-1e308,0.],0.,0.))
checks['fixed_seed_bad_winner_falls_back']=r['select_final'](win,ref)['configuration']=='B*'
checks['fixed_seed_good_winner_passes']=r['select_final'](dict(win,clean_F=.8,clean_MAE=.5),ref)['configuration']=='winner'
checks['lucky_seed_rejected']=reject(lambda:r['select_final'](dict(win,seed=29),ref))
g=grid()
for seed,runs in g.items():
    for cid,reps in runs.items():
        for i,x in enumerate(reps):
            x['eligible_count']=1
            x['pairing']=r['pairing_stamp']([0,1],[True,False] if seed==17 else [False,True],str(i)*64,i)
checks['different_eligibility_same_count_rejected']=reject(lambda:r['aggregate'](g))
g=grid();g[29]['T:0.1:front'][0]['pairing']=r['pairing_stamp']([1,0],[True,True],'0'*64,0)
checks['different_order_rejected']=reject(lambda:r['aggregate'](g))
g=grid();g[43]['T:0.1:random'][1]['pairing']['view']='f'*64
checks['different_view_same_replica_rejected']=reject(lambda:r['aggregate'](g))
g=grid();g[17]['T:0.1:random'][1]['pairing']['replicate']=0
checks['duplicate_replica_rejected']=reject(lambda:r['aggregate'](g))
checks['distinct_paired_replicas_accepted']=r['aggregate'](grid())['across_seeds']['macro_F1']==.5
checks['one_seed_checkpoint_score']=r['checkpoint_score'](grid()[17])==dict(macro_F1=.5,MAE=1.)
checks['gate_parameter_count']=(66*64+64+64)==4352 and (198*16+16+16*64+64)==4272
protocol=json.loads((root/'docs/research/R01/protocol.json').read_text(encoding='utf-8'))
checks['protocol_objective_and_owner_state']=protocol['status']=='PROVISIONAL' and protocol['training_authorized'] is False and protocol['mechanism_checkpoint_objective']=='attempted96 for C0/R0/R1/R2/R1-CAP' and protocol['baseline_checkpoint_objective']=='clean'
record=json.loads((root/'reports/research/R01_LOCAL_CLOSEOUT/checks.json').read_text(encoding='utf-8'))
checks['recorded_test_source_hashes_match']=all(hashlib.sha256((root/k).read_bytes()).hexdigest()==v for k,v in record['source_sha256'].items())
print(json.dumps(dict(kind='READ_ONLY_SYNTHETIC_DELTA_PROBES',checks=checks,probe_count=len(checks),passed=all(checks.values()),recorded_tests_run=record['tests_run'],recorded_failures=record['failures'],recorded_errors=record['errors'],recorded_skipped=record['skipped'])))
if not all(checks.values()): raise SystemExit(1)
