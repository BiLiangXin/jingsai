"""Reuse extracted Q1 features; repair only failed aligner initialization."""
import argparse,csv,html,json,wave
from pathlib import Path
import numpy as np
from s03_q1 import align_pcm,tokenize,guard,save,sha,ROOT

def main():
    p=argparse.ArgumentParser();p.add_argument('--extracted',required=True);p.add_argument('--output',required=True);p.add_argument('--acoustic-model',required=True);a=p.parse_args()
    source=Path(a.extracted);out=Path(a.output);out.mkdir(exist_ok=False);model=Path(a.acoustic_model)
    expected=json.loads((ROOT/'reports/s03_readiness/Q1_TOOLS.json').read_bytes())
    for entry in expected['model_files']:
        if sha(model/entry['path'])!=entry['sha256']:raise ValueError('Model copy differs')
    traces=[];example=None
    for i in range(100):
        guard();folder=source/f'{i:03d}';row=json.loads((folder/'official_row.json').read_bytes());old=json.loads((folder/'alignment.json').read_bytes());trace=json.loads((folder/'trace.json').read_bytes())
        with wave.open(str(folder/'audio.wav'),'rb') as f:pcm=f.readframes(f.getnframes())
        with np.load(folder/'features.npz',allow_pickle=False) as arrays:
            alignment=align_pcm(pcm,tokenize(row['text']),old['audio_start'],old['audio_contiguous'],arrays['audio_pts'],arrays['video_pts'],model)
        if any(c.isalpha() and not c.isascii() for c in row['text']):alignment.update(status='UNALIGNED',reason='NON_ASCII_TRANSCRIPT',words=[])
        result={**old,**alignment};save(out/f'{i:03d}.json',result)
        trace.update(word_alignment=result['status'],reason=result['reason'],alignment_file=f'{i:03d}.json');traces.append(trace)
        if example is None and result['status']=='COMPUTED_TEMPORAL_CHECKS_PASS':example=i
        if (i+1)%10==0:print(json.dumps({'processed':i+1,'aligned':sum(t['word_alignment']=='COMPUTED_TEMPORAL_CHECKS_PASS' for t in traces)}),flush=True)
    keys=list(dict.fromkeys(k for r in traces for k in r))
    with (out/'TRACE_100.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,keys);w.writeheader();w.writerows(traces)
    if example is not None:
        result=json.loads((out/f'{example:03d}.json').read_bytes())
        body=''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in [r['token_index'],r['word'],r['start'],r['end'],r['video_pts']])+'</tr>' for r in result['words'])
        page=f'<!doctype html><meta charset="utf-8"><title>Q1 acoustic alignment evidence</title><h1>Computed alignment — manual boundary accuracy UNKNOWN</h1><audio controls src="../q1/{example:03d}/audio.wav"></audio><img src="../q1/{example:03d}/frame.png"><table><tr><th>index</th><th>word</th><th>start PTS</th><th>end PTS</th><th>video PTS</th></tr>{body}</table>'
        (out/'ALIGNMENT_CASE.html').write_text(page,encoding='utf-8')
    result=json.loads((source/'SUMMARY.json').read_bytes());result.update(computed_temporal_checks_pass=sum(t['word_alignment']=='COMPUTED_TEMPORAL_CHECKS_PASS' for t in traces),failures={r:sum(t['reason']==r for t in traces) for r in sorted(set(t['reason'] for t in traces if t['reason']))},example_available=example is not None,trace_sha256=sha(out/'TRACE_100.csv'),initial_attempt_preserved=True,repair='Byte-identical acoustic model relocated to ASCII path; features/audio unchanged')
    save(out/'SUMMARY.json',result)
    pub=ROOT/'reports/s03_readiness';initial=pub/'Q1_INITIAL_ATTEMPT.json'
    if initial.exists():raise ValueError('Initial attempt already archived')
    initial.write_bytes((pub/'Q1_SUMMARY.json').read_bytes());save(pub/'Q1_SUMMARY.json',result);print(json.dumps(result))
if __name__=='__main__':main()
