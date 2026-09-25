"""Auditable file operations and bounded resources for S02."""
import datetime, hashlib, json, os, time
from pathlib import Path
from mosei.s01.contracts import require

CUTOFF='2026-09-25T18:00:00+08:00'
SOURCE_HASH='66e867aa74bc70a844e806e5571e371c9abb4a35f9e2887ce9b4d97ff2cb8fcd'

def now(): return datetime.datetime.now(datetime.timezone.utc)

def sha(path, guard=None):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(2**20),b''):
            if guard: guard()
            h.update(block)
    return h.hexdigest()

def write_json(path,value):
    path=Path(path);tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('x',encoding='utf8') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    tmp.replace(path)

def event(path,value):
    with Path(path).open('a',encoding='utf8') as f:
        f.write(json.dumps(dict(time=now().isoformat(),**value),allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())

class ResourceStop(RuntimeError): pass

class Budget:
    def __init__(self,output,hours=4,cutoff=CUTOFF):
        require(0<hours<=4 and cutoff==CUTOFF,'S02 cap cannot expand')
        self.started=time.monotonic(); self.output=Path(output)
        self.deadline=self.started+min(hours*3600,(datetime.datetime.fromisoformat(cutoff)-now()).total_seconds())
        self.fit_deadline=None;self.last_disk_check=0
        self()
    def __call__(self):
        t=time.monotonic()
        if t>=self.deadline or now()>=datetime.datetime.fromisoformat(CUTOFF):raise ResourceStop('Campaign/deadline cap reached')
        if self.fit_deadline is not None and t>=self.fit_deadline:raise ResourceStop('Per-fit cap reached')
        if t-self.last_disk_check>5:
            self.last_disk_check=t
            if sum(p.stat().st_size for p in self.output.rglob('*') if p.is_file())>5*2**30:raise ResourceStop('Storage cap reached')
        import torch
        if torch.cuda.is_available():
            free,total=torch.cuda.mem_get_info()
            if total-free>=total*.8:raise ResourceStop('GPU memory guard reached')
    def start_fit(self):self.fit_deadline=min(self.deadline,time.monotonic()+2700)
    def end_fit(self):self.fit_deadline=None

def verify_source(path,guard=None):
    path=Path(path)
    require(path.name=='aligned_50.pkl' and sha(path,guard)==SOURCE_HASH,'Official source fingerprint changed')
    return SOURCE_HASH
