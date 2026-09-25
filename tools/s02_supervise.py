"""Independent wall-clock supervisor for one preauthorized S02 subprocess."""
import argparse,datetime,json,os,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--backup',type=Path,required=True);p.add_argument('--receipt-dir',type=Path,required=True);a=p.parse_args()
    if a.receipt_dir.exists() or a.output_dir.exists():raise ValueError('New supervisor/campaign directories required')
    if a.receipt_dir.resolve().is_relative_to(ROOT):raise ValueError('Private supervisor directory must be outside repository')
    cutoff=datetime.datetime.fromisoformat('2026-09-25T18:00:00+08:00')
    started=datetime.datetime.now(datetime.timezone.utc);seconds=min(14400,(cutoff-started).total_seconds())
    stop_at=time.monotonic()+seconds
    if seconds<14400:raise ValueError('Complete four-hour window required')
    a.receipt_dir.mkdir(parents=True)
    command=[sys.executable,'-B','-X','utf8',str(ROOT/'tools/s02_run.py'),'--source',str(a.source),'--output-dir',str(a.output_dir),'--backup',str(a.backup)]
    env=os.environ.copy();env['CUBLAS_WORKSPACE_CONFIG']=':4096:8';env['PYTHONDONTWRITEBYTECODE']='1'
    record=dict(command=command,started=started.isoformat(),timeout_seconds=seconds,hard_deadline=cutoff.isoformat())
    (a.receipt_dir/'launch.json').write_text(json.dumps(record,indent=2),encoding='utf8')
    timed_out=False
    proc=None
    try:
        with (a.receipt_dir/'stdout.log').open('w',encoding='utf8') as out,(a.receipt_dir/'stderr.log').open('w',encoding='utf8') as err:
            proc=subprocess.Popen(command,cwd=ROOT,env=env,stdout=out,stderr=err)
            try:code=proc.wait(timeout=max(0.,stop_at-time.monotonic()))
            except subprocess.TimeoutExpired:
                timed_out=True;proc.kill();code=proc.wait(timeout=30)
    finally:
        # Exception/interrupt cannot leave this supervisor's child running unattended.
        if proc is not None and proc.poll() is None:
            proc.kill();proc.wait(timeout=30)
    record.update(exit_code=code,forced_resource_stop=timed_out,finished=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (a.receipt_dir/'exit.json').write_text(json.dumps(record,indent=2),encoding='utf8')
    print(json.dumps(dict(exit_code=code,forced_resource_stop=timed_out,finished=record['finished'])),flush=True)
    return 2 if timed_out else code
if __name__=='__main__':raise SystemExit(main())
