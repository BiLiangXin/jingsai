"""Synthetic records only; no live artifacts, GPU, models or original dataset."""
import copy,hashlib,importlib.util,json,math,types,unittest
from pathlib import Path
H=Path(__file__).resolve().parent

def module(name):
 s=importlib.util.spec_from_file_location(name,H/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
V=module('verify_frozen_choices');F=module('test_export_campaign')
REFERENCE=F.PROJECT_ROOT/'research/r01/reference.py'
raw=REFERENCE.read_bytes();assert hashlib.sha256(raw).hexdigest()==V.REF_SHA
REF=types.ModuleType('synthetic_frozen_reference');exec(compile(raw,'<SYNTHETIC_FROZEN_REFERENCE>','exec'),REF.__dict__)

def write(p,v): p.write_text(json.dumps(v,allow_nan=False),encoding='utf-8')
def metric(errors=0):
 y=[-1.]*100+[0.]*100+[1.]*100;c=[0]*100+[1]*100+[2]*100;pc=c.copy();pc[:errors]=[2]*errors
 return REF.metrics(c,y,pc,y)

class VerifyTests(unittest.TestCase):
 def setUp(self):
  self.case=F.ExportTests();self.case.setUp();self.addCleanup(self.case.doCleanups)
  self.campaign=self.case.campaign;self.root=self.case.root
 def fixture(self,count=30,variant='normal'):
  common='zscore' if variant=='normalizer_zscore' else 'identity'
  for index in range(count):
   self.case.fit(index);row=F.CANONICAL[index];tid=row['trial_id'];p=self.campaign/tid/'evaluation.json';ev=json.loads(p.read_bytes())
   errors=1 if variant=='normalizer_zscore' and row['architecture']=='B-CAT' and row['normalizer']=='identity' else 0
   if variant=='seed17_fallback' and row['architecture']=='C0' and row['seed']==17:errors=5
   if variant=='mean_guard' and row['architecture']=='C0':errors=30
   ev['clean']=metric(errors)
   if row['architecture'] in ('C0','R0'):
    ev['normalizer']=common;ev['config_hash']=F.M.sha(F.M.canonical(dict(row['config'],normalizer=common)))
    self.case.events[-2].update(normalizer=common,config_hash=ev['config_hash'])
   ev['attempted96']=dict(macro_F1=.8 if row['architecture']=='C0' else .7,MAE=.4)
   ev['evaluated_epochs']=11;write(p,ev)
   self.case.events[-1]['metrics']=dict(clean=ev['clean'],attempted96=ev['attempted96'])
   objective='clean' if row['architecture'].startswith('B-') else 'attempted96'
   epochs=[dict(epoch=e,selected_epoch=1,early_stop=e==11,clean=ev['clean'],objective=objective,objective_score=ev[objective],elapsed_seconds=e,data_kind='OFFICIAL_TRAIN_VALID') for e in range(1,12)]
   (p.parent/'epoch_events.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in epochs),encoding='utf-8')
  self.case.finish('COMPLETED' if count==30 else 'FAILED')
  source=self.campaign/'source_verification.json';v=json.loads(source.read_bytes());v['valid_count']=300;write(source,v)
  if count>=24:
   self.case.selection()
   p=self.campaign/'baseline_lock.json';b=json.loads(p.read_bytes());b['common_normalizer']=common
   for cid,rows in b['baseline_clean_reports'].items():
    for seed,item in rows.items():
     item['clean']=metric();item['parameters']=0 if cid=='PRIOR' else 20
   for index in range(24):
    row=F.CANONICAL[index];ev=json.loads((self.campaign/row['trial_id']/'evaluation.json').read_bytes())
    b['baseline_clean_reports'][row['architecture']+'-'+row['normalizer']][str(row['seed'])]['clean']=ev['clean']
   scores=[V.config_score(cid,{int(s):row for s,row in rows.items()}) for cid,rows in b['baseline_clean_reports'].items()]
   b['ranked']=REF.rank_configs(scores);b['B_star']=b['ranked'][0]['id'];write(p,b)
   selection=self.campaign/'selection.json'
   if count<30:selection.unlink()
   else:
    chosen='PRIOR' if variant=='seed17_fallback' else 'R0-'+common if variant=='mean_guard' else 'C0-'+common
    reason='CLEAN_REFERENCE_FALLBACK' if variant=='seed17_fallback' else 'WINNER_FIXED_SEED_GUARD_PASS'
    write(selection,dict(B_star=b['B_star'],common_normalizer=common,provenance=self.case.provenance,executed_budget=30,decision=dict(configuration=chosen,seed=17,reason=reason)))
  self.case.export();return self.root/'safe_export'
 def verify(self): return V.verify(self.root/'safe_export',self.campaign,REFERENCE,synthetic=True)
 def edit_safe(self,name,edit):
  root=self.root/'safe_export';p=root/name;v=json.loads(p.read_bytes());edit(v);write(p,v)
  p=root/'MANIFEST.json';m=json.loads(p.read_bytes())
  for row in m['files']:
   raw=(root/row['path']).read_bytes();row.update(sha256=hashlib.sha256(raw).hexdigest(),size=len(raw))
  write(p,m)
 def test_complete_tied_normalizer_and_all_checkpoint_rules(self):
  self.fixture();r=self.verify();self.assertEqual(r['common_normalizer'],'identity');self.assertEqual(r['B_star'],'PRIOR')
  self.assertEqual(r['verified_recorded_selection']['configuration'],'C0-identity');self.assertEqual(len(r['epoch_audits']),30)
  self.assertTrue(r['final_choice_verified']);self.assertEqual(r['data_kind'],'SYNTHETIC_FIXTURES_ONLY')
 def test_zscore_rule(self):
  self.fixture(variant='normalizer_zscore');self.assertEqual(self.verify()['common_normalizer'],'zscore')
 def test_wrong_normalizer_rejected(self):
  self.fixture(variant='normalizer_zscore')
  self.edit_safe('BASELINE_AND_SELECTION.json',lambda v:v['baseline'].update(common_normalizer='identity'))
  with self.assertRaisesRegex(V.VerificationError,'normalizer rule'):self.verify()
 def test_wrong_baseline_rank_rejected(self):
  self.fixture()
  self.edit_safe('BASELINE_AND_SELECTION.json',lambda v:v['baseline']['ranked'].reverse())
  with self.assertRaisesRegex(V.VerificationError,'means/ranking'):self.verify()
 def test_wrong_final_winner_rejected(self):
  self.fixture()
  self.edit_safe('BASELINE_AND_SELECTION.json',lambda v:v['selection'].update(configuration='R0-identity'))
  with self.assertRaisesRegex(V.VerificationError,'final choice'):self.verify()
 def test_mean_guard_filters_higher_attempted_candidate(self):
  self.fixture(variant='mean_guard');self.assertEqual(self.verify()['verified_recorded_selection']['configuration'],'R0-identity')
 def test_seed17_guard_falls_back_to_baseline_only(self):
  self.fixture(variant='seed17_fallback');r=self.verify();self.assertEqual(r['ranked_winner_before_seed17_guard'],'C0-identity')
  self.assertEqual(r['verified_recorded_selection'],dict(configuration='PRIOR',seed=17,reason='CLEAN_REFERENCE_FALLBACK'))
 def test_final_checkpoint_epoch_rejected(self):
  self.fixture();self.edit_safe('FITS.json',lambda v:v['fits'][24].update(selected_epoch=2))
  with self.assertRaisesRegex(V.VerificationError,'checkpoint epoch'):self.verify()
 def test_selected_epoch_final_metric_mismatch_rejected(self):
  self.fixture();self.edit_safe('FITS.json',lambda v:v['fits'][24]['metrics']['clean'].update(MAE=.123))
  with self.assertRaisesRegex(V.VerificationError,'clean metrics'):self.verify()
 def test_changed_private_epoch_bytes_rejected(self):
  self.fixture();p=self.campaign/F.CANONICAL[0]['trial_id']/'epoch_events.jsonl';p.write_bytes(p.read_bytes()+b'\n')
  with self.assertRaisesRegex(V.VerificationError,'epoch fingerprint'):self.verify()
 def test_partial_seed_records_preserved_without_final_choice(self):
  self.fixture(count=25);r=self.verify();self.assertFalse(r['final_choice_verified']);self.assertIsNone(r['verified_recorded_selection'])
  self.assertEqual(len(r['incomplete_fits_preserved']),14);self.assertEqual(r['completed_fits'],25)
 def test_terminal_evidence_required_before_epoch_read(self):
  self.fixture();self.edit_safe('SUMMARY.json',lambda v:v.update(S01_EXECUTION_STATUS='RUNNING'))
  with self.assertRaisesRegex(V.VerificationError,'not terminated'):self.verify()
 def test_baseline_only24_completed_choice(self):
  self.fixture(count=24)
  p=self.campaign/'campaign.json';v=json.loads(p.read_bytes());v['execution_fit_budget']=24
  v['authorization']['binding'].update(execution_fit_budget=24,resource_walltime_cap_hours=4,per_fit_walltime_cap_hours=1)
  v['deferred_trial_ids']=[r['trial_id'] for r in F.CANONICAL[24:]];write(p,v)
  p=self.campaign/'campaign_status.json';v=json.loads(p.read_bytes());v.update(execution_fit_budget=24,status='COMPLETED',error=None);write(p,v)
  write(self.campaign/'selection.json',dict(B_star='PRIOR',common_normalizer='identity',provenance=self.case.provenance,executed_budget=24,
   decision=dict(configuration='PRIOR',seed=17,reason='WINNER_FIXED_SEED_GUARD_PASS')))
  dst=self.root/'safe24';F.M.export_campaign(self.campaign,dst,self.case.registry)
  result=V.verify(dst,self.campaign,REFERENCE,synthetic=True)
  self.assertEqual(result['completed_fits'],24);self.assertEqual(result['verified_recorded_selection']['configuration'],'PRIOR')
 def test_empty_epoch_file_on_failed_attempt_is_preserved(self):
  self.fixture(count=24)
  self.case.fit(24,status='FAILED')
  (self.campaign/F.CANONICAL[24]['trial_id']/'epoch_events.jsonl').write_bytes(b'')
  self.case.finish('FAILED');p=self.campaign/'source_verification.json';v=json.loads(p.read_bytes());v['valid_count']=300;write(p,v)
  dst=self.root/'failed_empty_epoch';F.M.export_campaign(self.campaign,dst,self.case.registry)
  result=V.verify(dst,self.campaign,REFERENCE,synthetic=True)
  failed=[x for x in result['epoch_audits'] if x['status']=='FAILED'];self.assertEqual(failed[0]['epoch_records'],0)
if __name__=='__main__':unittest.main(verbosity=2)
