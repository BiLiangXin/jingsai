import unittest,sys,tempfile
from pathlib import Path
import numpy as np
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from mosei.s01.contracts import DIMS
from mosei.s01.normalization import Normalizer
from mosei.s02.models import ResidualAttentionModel
from mosei.s04.inference import parse_aligned_special,predict_and_explain,contribution_card
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from s04_io_run import classify,format_row,FIELDS

class S04IOSyntheticTests(unittest.TestCase):
 def fixture(self):
  x={m:np.ones((50,d),dtype=np.float64 if m!='text' else np.float32) for m,d in DIMS.items()}
  x['text_bert']=np.zeros((3,50),dtype=np.int64);x['text_bert'][1,:9]=1
  x['id']='synthetic';x['raw_text']='must not enter model'
  return x
 def test_exact_aligned_conversion_and_order(self):
  raw=self.fixture();a,s,identity=parse_aligned_special(raw)
  self.assertEqual(identity,'synthetic')
  self.assertTrue(np.array_equal(a['audio'],raw['audio'].astype(np.float32)))
  self.assertEqual([m for m in a],['text','audio','vision'])
  self.assertEqual(s.tolist(),[True]*9+[False]*41)
  raw['id']=('synthetic',1)
  _,_,identity=parse_aligned_special(raw);self.assertEqual(identity,'["synthetic",1]')
 def test_missing_ambiguous_and_label_rejection(self):
  for change in [lambda x:x.pop('text'),lambda x:x.update(labels=[1]),lambda x:x.update(extra=np.zeros(1))]:
   a=self.fixture();change(a)
   with self.assertRaises(ValueError):parse_aligned_special(a)
 def test_dimension_dtype_nonfinite_and_bad_support(self):
  cases=[]
  a=self.fixture();a['text']=a['text'][:49];cases.append(a)
  a=self.fixture();a['audio']=np.array(a['audio'],dtype=object);cases.append(a)
  a=self.fixture();a['vision'][0,0]=np.nan;cases.append(a)
  a=self.fixture();a['text_bert'][1,2]=0;cases.append(a)
  a=self.fixture();a['text_bert'][1,2]=2;cases.append(a)
  a=self.fixture();a['text_bert']=a['text_bert'].astype(np.float32);cases.append(a)
  for a in cases:
   with self.subTest(case=len(cases)),self.assertRaises(ValueError):parse_aligned_special(a)
 def test_zero_contribution_is_not_equal_thirds(self):
  a=contribution_card([0,0,0]);self.assertEqual(a['status'],'NO_RESOLVABLE_EFFECT');self.assertEqual(a['relative'],[None]*3)
 def test_source_version_and_wrong_root(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'附件4-可解释专项视频样本与特征文件'
   for version in ['对齐','未对齐']:
    (root/version).mkdir(parents=True)
    for i in range(20):
     (root/version/f'synthetic{i}.pkl').write_bytes(b'not deserialized')
     (root/version/f'synthetic{i}.mp4').write_bytes(b'not decoded')
   allfiles,aligned=classify(root);self.assertEqual((len(allfiles),len(aligned)),(40,20));self.assertTrue(all(x.parent.name=='对齐' for x in aligned))
   with self.assertRaises(ValueError):classify(Path(tmp))
   (root/'对齐/synthetic0.pkl').unlink()
   with self.assertRaises(ValueError):classify(root)
 def test_partial_row_schema_and_null_mapping(self):
  card=contribution_card([1.,-2.,0.])
  result=dict(polarity='Neutral',intensity=.25,class_target=1,class_card=card,reg_card=card,class_windows=[dict(feature_start=0,feature_end_exclusive=3,timestamp_start=None,timestamp_end=None)],reg_windows=[],mapping_status='UNVERIFIED_MAPPING')
  row=format_row(0,'对齐/synthetic.pkl','synthetic',result)
  self.assertEqual(set(row),set(FIELDS));self.assertEqual(row['mapping_status'],'UNVERIFIED_MAPPING')
 def test_synthetic_prediction_feature_explanation_and_state(self):
  from mosei.s04.inference import model_state_hash
  raw=self.fixture();a,s,_=parse_aligned_special(raw)
  model=ResidualAttentionModel('M2',17);model.requires_grad_(False);model.eval()
  norm=Normalizer('identity');norm.fit_split='train'
  before=model_state_hash(model)
  result=predict_and_explain(model,norm,a,s,device='cpu')
  self.assertEqual(model_state_hash(model),before)
  self.assertIn(result['polarity'],('Negative','Neutral','Positive'))
  self.assertLess(result['efficiency_error'],1e-6)
  self.assertEqual(result['mapping_status'],'UNVERIFIED_MAPPING')
  for name in ['class_windows','reg_windows']:
   self.assertLessEqual(len(result[name]),3)
   self.assertTrue(all(row['timestamp_start'] is None and row['timestamp_end'] is None for row in result[name]))
if __name__=='__main__':unittest.main()
