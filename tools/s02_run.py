"""Official S02 entry; committed reviewed preauthorization is mandatory."""
import argparse,json,os,sys
from pathlib import Path
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--backup',type=Path,required=True)
    a=p.parse_args()
    from mosei.s01.contracts import configure_runtime
    from mosei.s02.execution import execute
    configure_runtime();c=json.loads((ROOT/'configs/s02_execution.json').read_bytes())
    return 0 if execute(c,a.source,a.output_dir,a.backup)=='COMPLETED' else 2
if __name__=='__main__':raise SystemExit(main())
