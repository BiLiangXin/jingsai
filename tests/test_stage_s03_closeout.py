"""Synthetic packaging regressions, no competition input."""
import hashlib,json,subprocess,sys,tempfile,unittest,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from s03_materials_check import safe
SCRIPT=Path(__file__).resolve().parents[1]/'tools/s03_materials_check.py'
class CloseoutTests(unittest.TestCase):
 def test_member_paths(self):
  safe('code/example.py')
  for name in ['../escape','/absolute','C:/drive','a\\b','.git/config','a/.env']:
   with self.subTest(name=name),self.assertRaises(ValueError):safe(name)
 def test_round_trip(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);folder=root/'SUBMISSION_DRAFT_INCOMPLETE';folder.mkdir();(folder/'README.md').write_text('Synthetic incomplete fixture')
   result=subprocess.run([sys.executable,'-B','-X','utf8',str(SCRIPT),'--folder',str(folder),'--zip',str(root/'out.zip'),'--report',str(root/'report.json')],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   report=json.loads((root/'report.json').read_bytes());self.assertFalse(report['all_mandatory_deliverables_present'])
   self.assertEqual(report['members'],2);self.assertEqual(report['zip_sha256'],hashlib.sha256((root/'out.zip').read_bytes()).hexdigest())
   with zipfile.ZipFile(root/'out.zip') as z:self.assertIsNone(z.testzip())
 def test_identity_rejected_before_archive(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);folder=root/'SUBMISSION_DRAFT_INCOMPLETE';folder.mkdir();(folder/'README.md').write_text('SYNTHETIC_PERSON_IDENTITY')
   result=subprocess.run([sys.executable,'-B','-X','utf8',str(SCRIPT),'--folder',str(folder),'--zip',str(root/'out.zip'),'--report',str(root/'report.json'),'--identity-token','SYNTHETIC_PERSON_IDENTITY'],capture_output=True,text=True)
   self.assertNotEqual(result.returncode,0);self.assertFalse((root/'out.zip').exists())
if __name__=='__main__':unittest.main()

