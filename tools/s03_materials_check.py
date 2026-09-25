"""Package an explicitly incomplete private draft; verify bytes and safe members."""
import argparse,hashlib,json,re,stat,zipfile
from pathlib import Path,PurePosixPath
from pypdf import PdfReader
def need(ok,msg):
 if not ok:raise ValueError(msg)
def sha(blob):return hashlib.sha256(blob).hexdigest()
def safe(name):
 p=PurePosixPath(name)
 need(not p.is_absolute() and '..' not in p.parts and '\\' not in name and ':' not in name and not any(s.lower() in {'.git','.env','__pycache__'} for s in p.parts),'Unsafe member')
def main():
 p=argparse.ArgumentParser();p.add_argument('--folder',required=True);p.add_argument('--zip',required=True);p.add_argument('--report',required=True);p.add_argument('--identity-token',action='append',default=[]);a=p.parse_args()
 root=Path(a.folder).resolve();dest=Path(a.zip).resolve()
 need(root.name=='SUBMISSION_DRAFT_INCOMPLETE' and not dest.exists() and not dest.is_relative_to(root),'New incomplete archive outside source required')
 needles=[n.casefold() for n in a.identity_token]
 def scan(text):
  need(not re.search(r'[a-zA-Z]:[\\/]+Users[\\/]',text,re.I),'Private absolute path')
  need(not any(n in text.casefold() for n in needles),'Identity token')
 files=[]
 for f in sorted(root.rglob('*')):
  need(not f.is_symlink(),'Symlink')
  if not f.is_file():continue
  rel=f.relative_to(root).as_posix();safe(rel)
  blob=f.read_bytes()
  if f.suffix in {'.py','.md','.json','.csv','.svg','.html'}:scan(blob.decode('utf-8'))
  if f.suffix=='.docx':
   with zipfile.ZipFile(f) as z:
    need(z.testzip() is None,'DOCX CRC')
    for n in z.namelist():
     safe(n)
     if n.endswith(('.xml','.rels')):scan(z.read(n).decode('utf-8'))
  if f.suffix=='.pdf':
   doc=PdfReader(f);scan(str(doc.metadata));scan('\n'.join(page.extract_text() or '' for page in doc.pages))
  if f.suffix in {'.npz','.pt'}:
   with zipfile.ZipFile(f) as z:
    need(z.testzip() is None,'Array/checkpoint CRC')
    for n in z.namelist():safe(n)
  files.append(dict(path=rel,sha256=sha(blob),size=len(blob)))
 need(not (root/'MANIFEST.json').exists(),'Do not overwrite manifest')
 manifest=dict(status='INCOMPLETE_NOT_FOR_SUBMISSION',all_mandatory_deliverables_present=False,missing=['Attachment3 final CSV','Attachment4 final prediction/explanation CSV','Verified official feature-to-source mapping','Final team paper review'],manifest_self_excluded=True,files=files)
 (root/'MANIFEST.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 with zipfile.ZipFile(dest,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for row in files:z.write(root/row['path'],row['path'])
  z.write(root/'MANIFEST.json','MANIFEST.json')
 with zipfile.ZipFile(dest) as z:
  members=z.infolist();need(len(members)==len(files)+1 and len({i.filename for i in members})==len(members),'Duplicate/missing')
  need({i.filename for i in members}=={r['path'] for r in files}|{'MANIFEST.json'},'Member set')
  need(z.testzip() is None,'CRC')
  for i in members:safe(i.filename);need(not stat.S_ISLNK(i.external_attr>>16),'ZIP symlink')
  need(z.read('MANIFEST.json')==(root/'MANIFEST.json').read_bytes(),'Manifest bytes')
  for row in files:
   blob=z.read(row['path']);need(len(blob)==row['size'] and sha(blob)==row['sha256'],'Member bytes')
 need(dest.stat().st_size<=50_000_000,'Over 50MB')
 result=dict(status='PASS_INCOMPLETE_DRAFT_ONLY',all_mandatory_deliverables_present=False,zip_sha256=sha(dest.read_bytes()),zip_bytes=dest.stat().st_size,zip_decimal_MB=dest.stat().st_size/1e6,members=len(files)+1,member_hash_size_checks=len(files),crc='PASS',exact_member_set='PASS',path_safety='PASS',identity_scan='PASS_KNOWN_TOKENS_METADATA_AND_TEXT',manifest_sha256=sha((root/'MANIFEST.json').read_bytes()),no_submission_performed=True)
 Path(a.report).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()

