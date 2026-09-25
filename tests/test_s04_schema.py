import sys,unittest,tempfile,hashlib,copy
from unittest.mock import patch
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from s04_infer import validate_special,select_aligned_files,claim_once,verify_review_binding,CONFIG,ROOT,CHECKPOINT,SCALER

class SpecialSchemaTests(unittest.TestCase):
    def fixture(self):
        row={m:np.ones((2,50,d),np.float32) for m,d in [('text',768),('audio',74),('vision',35)]}
        row['text_bert']=np.zeros((2,3,50),np.int64);row['text_bert'][:,1,:8]=1
        return row
    def test_unlabelled_shapes_and_stable_ordinals(self):
        a,s,ids=validate_special(self.fixture());self.assertEqual(ids,['0','1']);self.assertEqual(s.sum(),16)
    def test_no_labels_or_split(self):
        for key in ['labels','regression_labels','classification_labels','test','train','valid']:
            with self.assertRaises(ValueError):validate_special({**self.fixture(),key:None})
    def test_duplicate_ids_rejected(self):
        with self.assertRaises(ValueError):validate_special({**self.fixture(),'id':['same','same']})
    def test_holes_and_nonfinite_rejected(self):
        a=self.fixture();a['text_bert'][0,1,9]=1
        with self.assertRaises(ValueError):validate_special(a)
        a=self.fixture();a['text'][0,0,0]=np.nan
        with self.assertRaises(ValueError):validate_special(a)
    def test_wrapper_and_tuple_identity(self):
        a=self.fixture();a['id']=[('synthetic',1),('synthetic',2)]
        _,_,ids=validate_special({'data':a});self.assertEqual(ids,['["synthetic",1]','["synthetic",2]'])
    def test_unused_metadata_never_indexed(self):
        class Unreadable:
            def __array__(self):raise RuntimeError('raw text accessed')
        a=self.fixture();a['raw_text']=Unreadable();validate_special(a)
    def test_single_sample_dimensions(self):
        a={k:v[0] for k,v in self.fixture().items()};a['id']='synthetic'
        values,s,ids=validate_special(a);self.assertEqual(values['audio'].shape,(1,50,74));self.assertEqual(ids,['synthetic'])
    def test_aligned_only_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for kind in ['aligned','unaligned']:
                (root/kind).mkdir()
                for i in range(30):(root/kind/f'synthetic{i}.pkl').write_bytes(b'never deserialize this fixture')
            files=select_aligned_files(root);self.assertEqual(len(files),30);self.assertTrue(all(p.parent.name=='aligned' for p in files))
            (root/'unknown.pkl').write_bytes(b'')
            with self.assertRaises(ValueError):select_aligned_files(root)
    def test_task_claim_not_output_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);(home/'.codex').mkdir();out=home/'result'
            with patch('pathlib.Path.home',return_value=home),patch.dict(CONFIG,{'attachment3_output_binding_sha256':hashlib.sha256(str(out.resolve()).encode()).hexdigest(),'attachment3_claim_id':'SYNTHETIC_TEST'}):
                claim_once(out)
                with self.assertRaises(FileExistsError):claim_once(out)
                with self.assertRaises(ValueError):claim_once(home/'different')
    def test_review_set_and_digest_binding(self):
        files=[p.relative_to(ROOT).as_posix() for p in (ROOT/'src/mosei').rglob('*.py')]
        files+=['tools/s04_infer.py','tools/s03_evaluate.py','configs/s03_execution.json','docs/research/S03/FINAL_INFERENCE_SPEC.md','research/r01/reference.py','reports/s03_readiness/DEPLOYMENT.json','reports/s03_readiness/RESTORE.json','reports/s03_readiness/TESTS.json','reports/s02_execution/S02-20260925-BOUNDED-12F15W/FITS.json','reports/s02_execution/S02-20260925-BOUNDED-12F15W/MODEL_REGISTRY.json']
        rows=[dict(path=p,sha256='synthetic-hash') for p in files]
        m={'critical_files':rows};r=dict(status='PASS',independent=True,review_inputs_sha256='digest',critical_files=rows);g=dict(manifest_sha256='digest',checkpoint_sha256=CHECKPOINT,normalizer_sha256=SCALER)
        verify_review_binding(m,r,g,'digest')
        for bad in [{**m,'critical_files':[]},{**m,'critical_files':rows[:-1]}]:
            with self.assertRaises(ValueError):verify_review_binding(bad,r,g,'digest')
        with self.assertRaises(ValueError):verify_review_binding(m,{**r,'review_inputs_sha256':'changed'},g,'digest')
        with self.assertRaises(ValueError):verify_review_binding(m,{**r,'critical_files':rows[:-1]},g,'digest')

if __name__=='__main__':unittest.main()
