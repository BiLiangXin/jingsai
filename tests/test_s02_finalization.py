"""Permanent stdlib-only regression derived from independent failure probes.
Actual unchanged execute() AST is used with synthetic non-model mocks.
"""
import ast,copy,hashlib,json,platform,tempfile,time,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_terminal_evidence_must_precede_atomic_champion_pointer():
    sha=lambda b:hashlib.sha256(b).hexdigest()
    checks=[]
    def record(name,ok,**detail):
        checks.append(dict(name=name,passed=bool(ok),**detail))
    selection_path=ROOT/'src/mosei/s02/selection.py'
    selection_bytes=selection_path.read_bytes();ns={}
    exec(compile(selection_bytes,str(selection_path),'exec'),ns)
    def candidate(name,change=None,seeds=(17,29,43)):
        rows={s:dict(status='COMPLETED',clean=dict(Accuracy=.6,macro_F1=.5,MAE=.7,Pearson=.4,Pearson_reason=None),attempted96=dict(macro_F1=.4,MAE=.8)) for s in seeds}
        for seed,scope,key,value in change or []: rows[seed][scope][key]=value
        return ns['summarize_candidate'](name,rows,parameters=1,inference_cost=1.)
    base=candidate('BASE')
    partial=candidate('PARTIAL',seeds=(17,29))
    record('incomplete_seed_rejected_and_mean_null',partial['means'] is None and not ns['promotion_eligibility'](base,partial)['eligible'])
    good=candidate('GOOD',[(s,'attempted96','macro_F1',.5) for s in (17,29,43)])
    record('all_metric_nondegradation_with_gain_proposes_only',ns['choose_champion'](base,[good],comparison_complete=True)['selected_id']=='GOOD')
    trade=candidate('TRADE',[(s,'attempted96','macro_F1',.5) for s in (17,29,43)]+[(17,'clean','MAE',.7001)])
    record('fixed_seed_degradation_rejected',not ns['promotion_eligibility'](base,trade)['eligible'])
    record('open_comparison_cannot_promote',ns['choose_champion'](base,[good],comparison_complete=False)['selected_id']=='BASE')
    tiny=candidate('TINY',[(s,'attempted96','macro_F1',.4+5e-9) for s in (17,29,43)])
    record('tolerance_not_gain',not ns['promotion_eligibility'](base,tiny)['eligible'])
    unknown=candidate('UNKNOWN',[(17,'clean','Pearson',None),(17,'clean','Pearson_reason','zero_prediction_variance'),(17,'attempted96','macro_F1',.5)])
    record('undefined_pearson_rejected',not ns['promotion_eligibility'](base,unknown)['eligible'])
    # Execute only the unchanged execute() AST using non-model mocks. This injects
    # final disk failures after a mocked eligible winner/restore, not model results.
    source_path=ROOT/'src/mosei/s02/execution.py';source=source_path.read_bytes()
    fn=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='execute')
    code=compile(ast.Module(body=[fn],type_ignores=[]),str(source_path),'exec')
    class Budget:
        def __init__(self,*a):pass
        def __call__(self):pass
    class Model:
        def to(self,*a):return self
        def cpu(self):return self
    class Norm:
        def __init__(self,method):self.method=method
        def state_dict(self):return {'method':self.method}
        def transform(self,b):return b
    class Stop(Exception):pass
    class Torch:
        def save(self,v,p):Path(p).write_bytes(b'SYNTHETIC_CACHE_NO_TENSORS')
        def load(self,*a,**k):return {}
    def require(ok,reason):
        if not ok:raise ValueError(reason)
    def metric():return dict(clean=dict(Accuracy=.6,macro_F1=.5,MAE=.7,Pearson=.4),attempted96=dict(macro_F1=.4,MAE=.8),condition_reports={},parameters=1,checkpoint_sha256='a'*64,config_hash='b'*64,provenance={})
    faults=[]
    for failing in (None,'comparison.json','campaign_status.json','CURRENT_CHAMPION.json'):
        with tempfile.TemporaryDirectory(prefix='s02_reviewer_finalization_') as temp:
            home=Path(temp);backup=home/'backup';output=home/'new_output'
            for seed in (17,29,43):
                folder=backup/'campaign'/f'B-CAT-zscore-T0-s{seed}';folder.mkdir(parents=True)
                (folder/'evaluation.json').write_text(json.dumps(metric()))
            def write_json(path,value):
                if Path(path).name==failing and (failing!='CURRENT_CHAMPION.json' or Path(path).exists()):raise OSError('INJECTED_FINAL_REPORT_WRITE_FAILURE')
                Path(path).write_text(json.dumps(value),encoding='utf8')
            def restore(folder):return Model(),Norm('zscore' if 'CAT' in str(folder) else 'identity'),metric()
            batch=types.SimpleNamespace(support=[True])
            candidate_row=dict(id='W0-bN-zero',variant='W0',beta=0.)
            g=dict(Path=Path,json=json,time=time,torch=Torch(),SEEDS=(17,29,43),require=require,
              auth=types.SimpleNamespace(preflight=lambda *a:{'commit':'b'*40,'manifest_sha256':'c'*64},claim=lambda *a:None,stable_code=lambda *a:None),
              now=lambda:types.SimpleNamespace(isoformat=lambda:'SYNTHETIC_TIMESTAMP'),write_json=write_json,
              Budget=Budget,ResourceStop=Stop,load_official=lambda *a:{'train':batch,'valid':batch},ValidationLibrary=lambda b:None,
              SOURCE_HASH='d'*64,restore_s01=restore,collect_views=lambda *a:{'parameters':1,'runtime_seconds':1.},
              digest=lambda v:'e'*64,sha=lambda p:'f'*64,summarize_candidate=lambda *a,**k:{'complete':True,'id':'BASE'},
              postprocessing_candidates=lambda:[candidate_row],event=lambda p,v:None,combined_cache=lambda *a:{},score_cache=lambda *a:metric(),
              reference=types.SimpleNamespace(aggregate=lambda *a:None),summarize=lambda *a:[],
              choose_champion=lambda *a,**k:dict(promotion_proposed=True,selected_id='W0-bN-zero'),
              exact_output_values=lambda *a:None,robust_ranking=lambda *a:[],clean_pareto=lambda *a:[],print=lambda *a,**k:None)
            exec(code,g)
            exc=None
            returned=None
            try:returned=g['execute']({'recipes':[]},home/'DO_NOT_OPEN',output,backup)
            except Exception as e:exc=type(e).__name__+': '+str(e)
            pointer=json.loads((output/'CURRENT_CHAMPION.json').read_bytes())
            faults.append(dict(injected_failed_file=failing,returned_status=returned,escaped_exception=exc,winner_restore_completed=(output/'winner_restore.json').exists(),finalization_failure_receipt=(output/'finalization_failure.json').exists(),pointer=pointer['current_champion'],terminal_receipt_exists=(output/'campaign_status.json').exists(),
                               original_preserved=pointer['current_champion']=='S01-B-CAT-zscore'))
    assert all(x['passed'] for x in checks)

    assert all(x['winner_restore_completed'] for x in faults)
    assert faults[0]['pointer']=='W0-bN-zero' and faults[0]['returned_status']=='COMPLETED'
    assert all(x['original_preserved'] and x['returned_status']=='BLOCKED' and x['finalization_failure_receipt'] for x in faults[1:])
