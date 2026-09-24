"""Run only pure-synthetic R01 reference checks. No official model/data imports."""
import argparse,hashlib,io,json,platform,sys,unittest
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def fingerprint():return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(HERE.glob('*.py'))}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    before=fingerprint();stream=io.StringIO()
    suite=unittest.defaultTestLoader.discover(str(HERE),pattern='test_*.py')
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    after=fingerprint()
    if before!=after:raise ValueError('source changed during checks')
    value={'kind':'SYNTHETIC_ONLY_REFERENCE_CHECKS','command':'python -X utf8 -B research/r01/run_checks.py --output reports/research/R01_LOCAL_CLOSEOUT/checks.json','tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'exit_code':0 if result.wasSuccessful() else 1,'environment':{'python':platform.python_version(),'implementation':platform.python_implementation(),'system':platform.system(),'machine':platform.machine()},'source_sha256':before,'output':stream.getvalue().replace(str(ROOT),'<REPOSITORY>'),'historical_64_and_28_not_relabelled':True,'numpy_pytorch_tested':False,'model_experiments':'NOT_RUN','metrics':None}
    Path(args.output).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:value[k] for k in ('kind','tests_run','failures','errors','skipped','exit_code')}))
    return value['exit_code']
if __name__=='__main__':raise SystemExit(main())
