"""Recompute engineering checks on all100 private Q1 products; no sample printing."""
import argparse,json,wave
from pathlib import Path
import numpy as np
from s03_q1 import audio_features,text_features,vision_features,sha,save,ROOT

def run(source,aligned):
    # Synthetic dimensions and a frequency-sensitive acoustic check.
    t=np.arange(16000)/16000
    low=audio_features(np.sin(2*np.pi*200*t));high=audio_features(np.sin(2*np.pi*2000*t))
    if low.shape!=(98,16) or not high[:,-1].mean()>low[:,-1].mean()*5:raise ValueError('Acoustic synthetic check')
    if text_features(['a','a']).shape!=(2,128) or not np.array_equal(*text_features(['a','a'])):raise ValueError('Text determinism')
    if vision_features(np.zeros((64,64,3),np.uint8)).shape!=(39,):raise ValueError('Visual dimensions')
    checked=0;aligned_count=0;files=[]
    for i in range(100):
        folder=source/f'{i:03d}';trace=json.loads((folder/'trace.json').read_bytes());alignment=json.loads((aligned/f'{i:03d}.json').read_bytes())
        if sha(folder/'features.npz')!=trace['features_sha256']:raise ValueError('Feature mutation')
        with np.load(folder/'features.npz',allow_pickle=False) as f:
            for key,dim in [('text',128),('audio',16),('vision',39)]:
                if f[key].ndim!=2 or f[key].shape[1]!=dim or not np.isfinite(f[key]).all():raise ValueError('Invalid feature arrays')
            for key in ['audio_pts','video_pts']:
                if np.any(np.diff(f[key])<=0):raise ValueError('Timestamp ordering')
            if alignment['status']=='COMPUTED_TEMPORAL_CHECKS_PASS':
                if len(alignment['words'])!=len(f['text']):raise ValueError('Word coverage')
                for word in alignment['words']:
                    if not alignment['audio_start']<=word['start']<word['end']<=alignment['audio_end']+.02:raise ValueError('Word outside waveform')
                    if not 0<=word['video_feature_index']<len(f['vision']):raise ValueError('Frame reference')
                    if not word['audio_feature_indices']:raise ValueError('No corresponding acoustic frame')
                aligned_count+=1
            elif alignment['words']:raise ValueError('Failed alignment invented words')
        files.append(dict(row=i,feature_sha256=sha(folder/'features.npz'),alignment_sha256=sha(aligned/f'{i:03d}.json')));checked+=1
    save(aligned/'VERIFIED_MANIFEST_PRIVATE.json',dict(files=files))
    result=dict(status='PASS',samples_checked=checked,computed_word_alignments_checked=aligned_count,human_timing_accuracy='UNKNOWN',synthetic_checks=['MFCC_shape_centroid_frequency_response','deterministic_text_hash','visual_dimension'],features_unchanged=True,private_manifest_sha256=sha(aligned/'VERIFIED_MANIFEST_PRIVATE.json'))
    save(ROOT/'reports/s03_readiness/Q1_CHECKS.json',result);print(json.dumps(result))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--aligned',required=True);a=p.parse_args();run(Path(a.source),Path(a.aligned))
